"""Local crypto/ORM/API tests; fake Storage, SQLite is NOT PostgreSQL verification."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import time
import io
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.api import create_app
from backend.api_v1.settings import APISettings
from backend.cloud.auth import TokenVerifier, current_user, Identity
from backend.cloud.settings import CloudSettings
from backend.cloud.database import CloudDatabase
from backend.cloud.models import Base, Resume, Analysis, SavedResume, History
from backend.cloud.storage import PrivateStorage


@pytest.fixture
def verifier():
    settings = SimpleNamespace(jwks_url='https://example.invalid/jwks', algorithm='ES256',
                               issuer='https://example.invalid/auth/v1', audience='authenticated')
    result = TokenVerifier(settings)
    key = ec.generate_private_key(ec.SECP256R1())
    result.keys = Mock()
    result.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    return result, key


def token(verifier, **overrides):
    instance, key = verifier
    claims = dict(sub=str(uuid4()), iss=instance.settings.issuer,
                  aud=instance.settings.audience, iat=int(time.time()),
                  exp=int(time.time()) + 300, role='authenticated')
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm='ES256', headers={'kid': 'test'})


@pytest.mark.parametrize('change', [{}, {'exp': 1}, {'iss': 'wrong'}, {'aud': 'wrong'},
                                   {'iat': int(time.time()) + 9999}, {'sub': 'bad'},
                                   {'role': 'service_role'}, {'nbf': int(time.time()) + 9999}])
def test_real_signature_claim_validation(verifier, change):
    instance, _ = verifier
    app = create_app(APISettings())
    app.state.token_verifier = instance
    with TestClient(app) as client:
        result = client.get('/api/me', headers={'Authorization': 'Bearer ' + token(verifier, **change)})
        assert result.status_code == (401 if change else 200)
        if change:
            assert result.json() == {'detail': 'Authentication required.', 'code': 'unauthorized'}
            assert result.headers['www-authenticate'] == 'Bearer'
        else:
            assert set(result.json()) == {'id'}


@pytest.mark.parametrize('header', ['', 'Bearer', 'Basic abc', 'Bearer junk', 'Bearer a b'])
def test_bad_headers(verifier, header):
    app = create_app(APISettings())
    app.state.token_verifier = verifier[0]
    with TestClient(app) as client:
        assert client.get('/api/v1/me', headers={'Authorization': header}).status_code == 401


def test_forged_and_hmac_tokens(verifier):
    app = create_app(APISettings())
    app.state.token_verifier = verifier[0]
    forged = (verifier[0], ec.generate_private_key(ec.SECP256R1()))
    with TestClient(app) as client:
        for value in [token(forged), jwt.encode({'sub': str(uuid4())}, 'attacker', algorithm='HS256')]:
            assert client.get('/api/me', headers={'Authorization': 'Bearer ' + value}).status_code == 401


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.fail_upload = False
        self.fail_delete = False

    def upload(self, path, data, content_type):
        self.objects[path] = data
        if self.fail_upload:
            raise RuntimeError('secret provider error')

    def delete(self, path):
        if self.fail_delete:
            raise RuntimeError('secret provider error')
        self.objects.pop(path, None)

    def sign(self, path):
        assert path in self.objects
        return 'https://example.invalid/temporary'


@pytest.fixture
def cloud():
    app = create_app(APISettings())
    user = Identity(uuid4())
    app.dependency_overrides[current_user] = lambda: user
    db = CloudDatabase.__new__(CloudDatabase)
    db.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(db.engine)  # unit fixture only; production uses Alembic
    db.sessions = sessionmaker(db.engine, expire_on_commit=False)
    app.state.cloud_db = db
    storage = FakeStorage()
    app.state.private_storage = storage
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, db, storage, user, app
    db.engine.dispose()


def test_private_upload_and_ownership(cloud, pdf_bytes):
    client, db, storage, user, app = cloud
    result = client.post('/api/v1/resumes', files={'file': ('../../private-name.pdf', pdf_bytes)})
    assert result.status_code == 201, result.text
    body = result.json()
    id = body['id']
    assert set(body) == {'id', 'created_at', 'metadata'}
    assert 'private' not in result.text and 'example.invalid' not in result.text
    assert next(iter(storage.objects)).startswith(str(user.id) + '/')
    assert len(client.get('/api/v1/resumes').json()) == 1
    assert client.get('/api/v1/resumes/' + id).status_code == 200
    assert client.post('/api/v1/resumes/' + id + '/download').json()['expires_in'] == 60
    app.dependency_overrides[current_user] = lambda: Identity(uuid4())
    assert client.get('/api/v1/resumes').json() == []
    for method, path in [('get', ''), ('delete', ''), ('post', '/download')]:
        assert getattr(client, method)('/api/v1/resumes/' + id + path).status_code == 404
    assert len(storage.objects) == 1
    app.dependency_overrides[current_user] = lambda: user
    assert client.delete('/api/v1/resumes/' + id).status_code == 204
    assert storage.objects == {}
    assert client.get('/api/v1/resumes/' + id).status_code == 404


# Keep payloads out of node IDs: pytest puts the current node ID in an
# environment variable, whose value is limited to 32,767 characters on Windows.
@pytest.mark.parametrize('filename,data,code', [('a.exe', b'x', 'unsupported_format'),
    ('a.pdf', b'', 'empty_file'), ('a.pdf', b'corrupt', 'invalid_file'),
    ('a.docx', b'PKfake', 'invalid_file'), ('a.pdf', b'x' * (10*1024*1024+1), 'file_too_large')],
    ids=['unsupported-extension', 'empty-pdf', 'corrupt-pdf', 'corrupt-docx', 'oversized-pdf'])
def test_private_invalid_files(cloud, filename, data, code):
    client, db, storage, user, _ = cloud
    response = client.post('/api/v1/resumes', files={'file': (filename, data)})
    assert response.status_code == 400
    assert response.json()['code'] == code
    assert storage.objects == {} and db.list(Resume, user.id) == []


def test_storage_failure_cleanup_and_durable_intent(cloud, pdf_bytes):
    client, db, storage, user, _ = cloud
    storage.fail_upload = True
    response = client.post('/api/v1/resumes', files={'file': ('a.pdf', pdf_bytes)})
    assert response.status_code == 503 and 'secret' not in response.text
    assert storage.objects == {}
    storage.fail_delete = True
    assert client.post('/api/v1/resumes', files={'file': ('a.pdf', pdf_bytes)}).status_code == 503
    assert client.get('/api/v1/resumes').json() == []
    with db.sessions() as session:
        from sqlalchemy import select
        pending = session.scalar(select(Resume))
        assert pending.state == 'pending'
        id = pending.id
    storage.fail_delete = False
    assert client.delete(f'/api/v1/resumes/{id}').status_code == 204
    assert storage.objects == {}


def test_delete_failure_is_retryable(cloud, pdf_bytes):
    client, db, storage, user, _ = cloud
    id = client.post('/api/v1/resumes', files={'file': ('a.pdf', pdf_bytes)}).json()['id']
    storage.fail_delete = True
    assert client.delete('/api/v1/resumes/' + id).status_code == 503
    assert client.get('/api/v1/resumes').json() == []
    storage.fail_delete = False
    assert client.delete('/api/v1/resumes/' + id).status_code == 204


def test_db_failure_before_upload(cloud, pdf_bytes, monkeypatch):
    client, db, storage, user, _ = cloud
    monkeypatch.setattr(db, 'create', Mock(side_effect=RuntimeError('password')))
    response = client.post('/api/v1/resumes', files={'file': ('a.pdf', pdf_bytes)})
    assert response.status_code == 500 and 'password' not in response.text
    assert not storage.objects


def test_cloud_crud_and_analysis_privacy(cloud):
    client, db, storage, user, _ = cloud
    a = db.create(Analysis, user.id, summary_json={'ats_score': 75, 'resume_text': 'PRIVATE'})
    b = uuid4()
    for model, values in [(Analysis, {'summary_json': {}}), (SavedResume, {'data_json': {}}),
                           (History, {'event': 'test', 'resource_id': uuid4()})]:
        row = db.create(model, user.id, **values)
        assert not db.list(model, b)
        with pytest.raises(Exception):
            db.delete(model, b, row.id)
        if model is not History:
            key = 'summary_json' if model is Analysis else 'data_json'
            db.update(model, user.id, row.id, **{key: {'x': 1}})
            with pytest.raises(Exception):
                db.update(model, b, row.id, **{key: {}})
        db.delete(model, user.id, row.id)
    assert 'PRIVATE' not in client.get('/api/v1/analyses').text
    assert client.get(f'/api/v1/analyses/{a.id}').json()['ats_score'] == 75


def test_configuration_closed(monkeypatch):
    from backend.cloud.settings import CloudSettings
    monkeypatch.setenv('CLOUD_ENABLED', 'true')
    with pytest.raises((KeyError, ValueError)):
        CloudSettings.from_env()
    values = dict(supabase_url='https://example.supabase.co', issuer='https://example.supabase.co/auth/v1',
                  audience='authenticated', jwks_url='https://example.supabase.co/auth/v1/.well-known/jwks.json',
                  algorithm='ES256', database_url='postgresql+psycopg://test@localhost/db',
                  bucket='resumes', service_key='fake-unit-test-key')
    CloudSettings(**values)
    for key, value in [('algorithm', 'HS256'), ('jwks_url', 'https://attacker.invalid'),
                       ('database_url', 'sqlite:///local.db'), ('bucket', '../public'), ('service_key', '')]:
        with pytest.raises(ValueError):
            CloudSettings(**(values | {key: value}))


def test_storage_refuses_public_bucket():
    storage = PrivateStorage(SimpleNamespace(bucket='resumes'))
    storage._request = Mock(return_value=SimpleNamespace(json=lambda: {'public': True}))
    with pytest.raises(RuntimeError):
        storage.check_private()


def test_migration_offline_sql():
    import subprocess, os
    result = subprocess.run([os.sys.executable, '-m', 'alembic', 'upgrade', 'head', '--sql'],
                            env=os.environ | {'CLOUD_DATABASE_URL': 'postgresql+psycopg://test@localhost/db'},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for table in ['cloud_resumes', 'cloud_analyses', 'cloud_saved_resumes', 'cloud_history']:
        assert f'CREATE TABLE {table}' in result.stdout
        assert f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY' in result.stdout
    assert 'WITH CHECK' in result.stdout


def test_finalize_failure_rolls_back_and_cleans(cloud, pdf_bytes, monkeypatch):
    client, db, storage, user, _ = cloud
    original = db.owned
    calls = 0
    def fail_once(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('sensitive database error')
        return original(*args)
    monkeypatch.setattr(db, 'owned', fail_once)
    response = client.post('/api/v1/resumes', files={'file': ('a.pdf', pdf_bytes)})
    assert response.status_code == 503
    assert not storage.objects
    assert not db.list(Resume, user.id)


def test_missing_claim_and_unknown_key(verifier):
    instance, key = verifier
    with pytest.raises(Exception):
        instance.verify(jwt.encode({'sub': str(uuid4())}, key, algorithm='ES256', headers={'kid': 'test'}))
    instance.keys.get_signing_key_from_jwt.side_effect = RuntimeError('JWKS unreachable')
    app = create_app(APISettings())
    app.state.token_verifier = instance
    with TestClient(app) as client:
        assert client.get('/api/me', headers={'Authorization': 'Bearer ' + token(verifier)}).status_code == 401


def test_private_docx_and_archive_rejection(cloud):
    from docx import Document
    from zipfile import ZipFile
    client, db, storage, user, _ = cloud
    document = Document()
    document.add_paragraph('Skills\n' + 'Python SQL development collaboration testing ' * 30)
    output = io.BytesIO()
    document.save(output)
    response = client.post('/api/v1/resumes', files={'file': ('a.docx', output.getvalue())})
    assert response.status_code == 201, response.text
    assert client.get('/api/v1/history').json()[0]['event'] == 'resume_uploaded'
    dangerous = io.BytesIO()
    with ZipFile(dangerous, 'w') as archive:
        for name in ['[Content_Types].xml', '_rels/.rels', 'word/document.xml']:
            archive.writestr(name, 'fake')
        for i in range(1001):
            archive.writestr(f'x{i}', 'x')
    response = client.post('/api/v1/resumes', files={'file': ('a.docx', dangerous.getvalue())})
    assert response.status_code == 400
    assert response.json()['code'] == 'unsafe_document'


def test_cors_authorization():
    with TestClient(create_app(APISettings(allowed_origins=('https://frontend.example',)))) as client:
        response = client.options('/api/v1/resumes', headers={
            'Origin': 'https://frontend.example', 'Access-Control-Request-Method': 'DELETE',
            'Access-Control-Request-Headers': 'Authorization'})
        assert response.status_code == 200
        assert 'authorization' in response.headers['access-control-allow-headers'].lower()


def test_protected_routes_without_identity(client):
    for method, path in [('get', '/api/me'), ('get', '/api/v1/resumes'),
                         ('get', '/api/v1/analyses'), ('get', '/api/v1/history'),
                         ('delete', f'/api/v1/resumes/{uuid4()}')]:
        assert getattr(client, method)(path).status_code == 401


def test_rsa_configuration():
    from cryptography.hazmat.primitives.asymmetric import rsa
    settings = SimpleNamespace(jwks_url='https://example.invalid/jwks', algorithm='RS256',
                               issuer='https://example.invalid/auth/v1', audience='authenticated')
    verifier = TokenVerifier(settings)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier.keys = Mock()
    verifier.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    id = uuid4()
    encoded = jwt.encode(dict(sub=str(id), iss=settings.issuer, aud=settings.audience,
                              exp=int(time.time()) + 60, iat=int(time.time()), role='authenticated'),
                         key, algorithm='RS256', headers={'kid': 'rsa'})
    assert verifier.verify(encoded).id == id


def test_reconcile_only_old_unfinished_records(cloud):
    from datetime import timedelta
    from backend.cloud.cleanup import reconcile
    client, db, storage, user, _ = cloud
    old = datetime.now(timezone.utc) - timedelta(days=2)
    for state, timestamp in [('pending', old), ('deleting', old), ('ready', old),
                              ('pending', datetime.now(timezone.utc))]:
        row = db.create(Resume, user.id, object_path=f'{user.id}/{uuid4()}.pdf', state=state,
                        metadata_json={}, updated_at=timestamp)
        storage.objects[row.object_path] = b'synthetic'
    assert reconcile(db, storage) == 2
    assert len(storage.objects) == 2


def test_storage_traversal_and_provider_contract():
    from unittest.mock import patch
    settings = SimpleNamespace(bucket='resumes', supabase_url='https://example.invalid', service_key='unit-only')
    storage = PrivateStorage(settings)
    with pytest.raises(ValueError):
        storage.path('../other/file.pdf')
    with patch('backend.cloud.storage.httpx.Client') as client:
        response = client.return_value.__enter__.return_value.request.return_value
        response.json.return_value = {'public': False}
        path = f'{uuid4()}/{uuid4()}.pdf'
        storage.upload(path, b'fake', 'application/pdf')
        args = client.return_value.__enter__.return_value.request.call_args
        assert args.kwargs['headers']['Content-Type'] == 'application/pdf'
        assert args.kwargs['headers']['x-upsert'] == 'false'
        assert args.kwargs['headers']['Authorization'] == 'Bearer unit-only'
