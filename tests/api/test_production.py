import logging
from types import SimpleNamespace
from uuid import uuid4
import pytest
from backend.api_v1.production import UserRateLimit
from backend.api_v1.errors import APIError
from scripts.start_api import options, main, EventOnlyFormatter


def test_verified_user_rate_limits_and_bounded_state():
    clock=[0]; limiter=UserRateLimit(requests=3,writes=1,clock=lambda:clock[0],capacity=2)
    a,b,c=uuid4(),uuid4(),uuid4()
    limiter.check(a,True)
    with pytest.raises(APIError) as error: limiter.check(a,True)
    assert error.value.status_code==429 and error.value.headers['Retry-After']=='60'
    limiter.check(a);limiter.check(a)
    with pytest.raises(APIError): limiter.check(a)
    limiter.check(b)
    with pytest.raises(APIError): limiter.check(c)
    clock[0]=60;limiter.check(a,True)
    assert len(limiter.entries)==1


def test_readiness_fails_closed_without_cloud(client):
    assert client.get('/api/health').status_code==200
    response=client.get('/api/ready')
    assert response.status_code==503 and response.json()['code']=='not_ready'


def test_production_startup_is_guarded(monkeypatch):
    for key in ('API_PUBLIC_MODE','API_LEGACY_UPLOAD_ENABLED','CLOUD_ENABLED'): monkeypatch.delenv(key,raising=False)
    with pytest.raises(RuntimeError,match='Production requires'):main()
    monkeypatch.setenv('API_PUBLIC_MODE','true');monkeypatch.setenv('API_LEGACY_UPLOAD_ENABLED','false');monkeypatch.setenv('CLOUD_ENABLED','true');monkeypatch.setenv('CLOUD_MIGRATION_DATABASE_URL','synthetic-admin-url')
    with pytest.raises(RuntimeError,match='Migration credentials'):main()
    monkeypatch.delenv('CLOUD_MIGRATION_DATABASE_URL')
    monkeypatch.setenv('PHASE5_MIGRATION_AUDIT_DATABASE_URL','synthetic-audit-url')
    with pytest.raises(RuntimeError,match='Migration credentials'):main()
    assert options()['workers']==1 and options()['access_log'] is False


def test_production_log_formatter_excludes_tracebacks():
    try: raise ValueError('synthetic-sensitive-message')
    except ValueError:
        import sys
        record=logging.LogRecord('uvicorn.error',40,'synthetic',1,'synthetic-private-url',(),sys.exc_info())
    assert EventOnlyFormatter().format(record)=='ERROR uvicorn.error server event'


def test_public_cors_requires_https(monkeypatch):
    from backend.api_v1.settings import APISettings
    for origin in ('http://example.com','https://[invalid'):
        with pytest.raises(ValueError):APISettings(public_mode=True,legacy_upload_enabled=False,allowed_origins=(origin,))


def test_production_requires_explicit_database_tls(monkeypatch):
    for name,value in {'API_PUBLIC_MODE':'true','API_LEGACY_UPLOAD_ENABLED':'false','CLOUD_ENABLED':'true','CLOUD_DATABASE_URL':'postgresql+psycopg://synthetic@localhost/test'}.items():monkeypatch.setenv(name,value)
    monkeypatch.delenv('CLOUD_MIGRATION_DATABASE_URL',raising=False)
    with pytest.raises(RuntimeError,match='explicit TLS'):main()


def test_verified_user_limit_returns_429_not_401():
    from fastapi.testclient import TestClient
    from backend.api import create_app
    from backend.api_v1.settings import APISettings
    from backend.cloud.auth import Identity
    app=create_app(APISettings(public_mode=True,legacy_upload_enabled=False))
    app.state.token_verifier=SimpleNamespace(verify=lambda token:Identity(uuid4()))
    # Stable verified ID: token contents never become a limiter key.
    identity=Identity(uuid4());app.state.token_verifier.verify=lambda token:identity
    app.state.user_rate_limit=UserRateLimit(requests=1,writes=1)
    with TestClient(app) as client:
        assert client.get('/api/me',headers={'Authorization':'Bearer synthetic-token'}).status_code==200
        response=client.get('/api/me',headers={'Authorization':'Bearer another-synthetic-token'})
        assert response.status_code==429 and response.headers['retry-after']=='60'
