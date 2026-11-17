import pytest
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.api_v1.settings import APISettings
from backend.api_v1.middleware import LegacyUploadGuard


def test_public_mode_requires_disabled_legacy_upload(monkeypatch):
    monkeypatch.setenv('API_PUBLIC_MODE', 'true')
    monkeypatch.setenv('API_LEGACY_UPLOAD_ENABLED', 'true')
    with pytest.raises(ValueError, match='API_LEGACY_UPLOAD_ENABLED=false'):
        APISettings.from_env()
    monkeypatch.setenv('API_LEGACY_UPLOAD_ENABLED', 'false')
    assert APISettings.from_env().public_mode


@pytest.mark.parametrize('name', ['API_PUBLIC_MODE', 'API_LEGACY_UPLOAD_ENABLED'])
def test_public_flags_are_strict(monkeypatch, name):
    monkeypatch.setenv(name, 'invalid')
    with pytest.raises(ValueError, match='must be true or false'):
        APISettings.from_env()


@pytest.mark.parametrize('path', ['/api/resume/upload', '/api/resume/upload/'])
def test_public_legacy_upload_blocked_without_changing_protected_auth(path):
    settings = APISettings(public_mode=True, legacy_upload_enabled=False)
    with TestClient(create_app(settings)) as client:
        assert client.post(path, content=b'not even multipart').status_code == 404
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/me').status_code == 401
        assert client.get('/api/v1/resumes').status_code == 401


@pytest.mark.anyio
async def test_disabled_route_does_not_read_body():
    called = False
    async def app(scope, receive, send):
        nonlocal called
        called = True
    async def receive():
        raise AssertionError('Body must not be read')
    messages = []
    async def send(message):
        messages.append(message)
    await LegacyUploadGuard(app, enabled=False)({'type': 'http', 'path': '/api/resume/upload'}, receive, send)
    assert not called and messages[0]['status'] == 404


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_cloud_api_always_requests_restricted_runtime(monkeypatch):
    from types import SimpleNamespace
    import backend.api as api
    settings = SimpleNamespace(database_url='postgresql+psycopg://synthetic@localhost/test')
    monkeypatch.setattr(api.CloudSettings, 'from_env', lambda: settings)
    monkeypatch.setattr(api, 'TokenVerifier', lambda cfg: object())
    monkeypatch.setattr(api, 'PrivateStorage', lambda cfg: object())
    calls = []
    def database(url, require_runtime=False):
        calls.append(require_runtime)
        return object()
    monkeypatch.setattr(api, 'CloudDatabase', database)
    api.create_app(APISettings())
    assert calls == [True]


def test_disabled_legacy_route_stays_blocked_under_proxy_root():
    settings = APISettings(public_mode=True, legacy_upload_enabled=False)
    with TestClient(create_app(settings), root_path='/proxy') as client:
        assert client.post('/proxy/api/resume/upload', content=b'not multipart').status_code == 404
