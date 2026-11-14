import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.api_v1.middleware import UploadBodyLimitMiddleware
from backend.api_v1.settings import APISettings


@pytest.mark.parametrize("origin", ["*", "https://*.example.com", "https://web.example.com/path", "null", "https://user:pass@example.com", "https://example.com/", "https://example.com:99999", "https://example.com?x=1"])
def test_invalid_cors_config_fails_closed(monkeypatch, origin):
    monkeypatch.setenv("API_ALLOWED_ORIGINS", origin)
    with pytest.raises(ValueError, match="exact HTTP"):
        APISettings.from_env()


def test_cors_environment(monkeypatch):
    monkeypatch.setenv("API_ALLOWED_ORIGINS", "http://localhost:3000, https://web.example.com,http://localhost:3000")
    settings = APISettings.from_env()
    assert settings.allowed_origins == ("http://localhost:3000", "https://web.example.com")
    with TestClient(create_app(settings)) as client:
        headers = {"Origin": "https://web.example.com", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"}
        response = client.options("/api/resume/upload", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://web.example.com"
        assert "access-control-allow-credentials" not in response.headers
        headers["Origin"] = "https://other.example.com"
        response = client.options("/api/resume/upload", headers=headers)
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-origin" not in client.get("/api/health", headers={"Origin": "https://other.example.com"}).headers
        error = client.post("/api/resume/upload", files={"file": ("r.exe", b"x")}, headers={"Origin": "https://web.example.com"})
        assert error.status_code == 400
        assert error.headers["access-control-allow-origin"] == "https://web.example.com"


def test_unconfigured_cors_denies_cross_origin(monkeypatch):
    monkeypatch.delenv("API_ALLOWED_ORIGINS", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/api/health", headers={"Origin": "https://web.example.com"})
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "not-a-number"])
def test_invalid_size_config(monkeypatch, value):
    monkeypatch.setenv("MAX_UPLOAD_MB", value)
    with pytest.raises(ValueError):
        APISettings.from_env()


def test_body_limit_counts_chunks_without_trusting_content_length():
    async def run():
        called = False
        async def inner(scope, receive, send):
            nonlocal called
            called = True
        messages = iter([
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5678", "more_body": False},
        ])
        async def receive():
            return next(messages)
        sent = []
        async def send(message):
            sent.append(message)
        await UploadBodyLimitMiddleware(inner, max_bytes=7)(
            {"type": "http", "method": "POST", "path": "/api/resume/upload", "headers": [(b"content-length", b"1")]},
            receive, send,
        )
        assert not called
        assert sent[0]["status"] == 400
        assert b"file_too_large" in sent[1]["body"]
    asyncio.run(run())


def test_body_at_limit_replayed_and_disconnect_handled():
    async def run():
        received = []
        async def inner(scope, receive, send):
            received.append(await receive())
        async def send(message):
            pass
        async def receive():
            return {"type": "http.request", "body": b"1234", "more_body": False}
        middleware = UploadBodyLimitMiddleware(inner, max_bytes=4)
        scope = {"type": "http", "method": "POST"}
        await middleware(scope, receive, send)
        assert received == [{"type": "http.request", "body": b"1234", "more_body": False}]
        received.clear()
        async def disconnected():
            return {"type": "http.disconnect"}
        await middleware(scope, disconnected, send)
        assert received == []
    asyncio.run(run())


def test_cors_on_unexpected_server_error(monkeypatch):
    from backend.resume_parser import ResumeParser
    def fail(*args):
        raise TypeError("private exception")
    monkeypatch.setattr(ResumeParser, "parse", fail)
    settings = APISettings(allowed_origins=("https://web.example.com",))
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/resume/upload", files={"file": ("resume.pdf", b"%PDF-1.7 fake")},
            headers={"Origin": "https://web.example.com"},
        )
        assert response.status_code == 500
        assert response.headers["access-control-allow-origin"] == "https://web.example.com"
        assert "private exception" not in response.text
