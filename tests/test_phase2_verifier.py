"""Operator verifier regressions: all provider requests below are mocked."""
from contextlib import contextmanager
import hashlib
import io
import json
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from docx import Document
from scripts import verify_phase2 as live


class TestWorld:
    __test__ = False
    def __init__(self):
        self.ids = [str(uuid4()), str(uuid4())]
        self.tokens = ['synthetic-token-A', 'synthetic-token-B']
        self.rows, self.objects, self.events = {}, {}, []
        self.logout = 0
        self.fail_download = self.fail_delete = self.ambiguous = False
        self.delete_calls = []
        self.cfg = live.Settings('http://127.0.0.1:8000', 'https://project.example.invalid',
                                'sb_publishable_unit_test_only', 'sb_secret_unit_test_only',
                                'postgresql+psycopg://synthetic@localhost/test', 'resumes',
                                ('a@example.invalid', 'b@example.invalid'), ('password-unit-A', 'password-unit-B'))

    def summary(self, id):
        suffix = self.rows[id]['object_path'].rsplit('.', 1)[1]
        return {'id': id, 'created_at': 'synthetic', 'metadata': {
            'file_name': 'resume.' + suffix, 'file_type': suffix, 'pages': 1, 'word_count': 150,
            'section_order': ['skills'], 'bullet_count': 0, 'tables_detected': 0,
            'images_detected': 0, 'headings_look_caps': False}}

    def owner(self, request):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        return self.ids[self.tokens.index(token)] if token in self.tokens else None

    def provider(self, request):
        path, method = request.url.path, request.method
        owner = self.owner(request)
        response = lambda status, **kwargs: httpx.Response(status, **kwargs)
        if path == '/auth/v1/token':
            email = json.loads(request.content)['email']
            index = self.cfg.emails.index(email)
            assert request.headers['apikey'] == self.cfg.publishable
            return response(200, json={'access_token': self.tokens[index], 'user': {'id': self.ids[index]}})
        if path == '/auth/v1/logout':
            self.logout += 1
            return response(204)
        if path == '/api/resume/upload':
            return response(404)
        if path.startswith('/api/'):
            if not owner:
                return response(401)
            if path == '/api/me':
                return response(200, json={'id': owner})
            if path == '/api/v1/history':
                return response(200, json=[{k: v for k, v in event.items() if k != '_owner'} for event in self.events if event['_owner'] == owner])
            if path == '/api/v1/resumes':
                if method == 'GET':
                    return response(200, json=[self.summary(id) for id, row in self.rows.items() if row['owner'] == owner])
                data = request.content
                if len(data) > 10 * 1024 * 1024 or b'filename="synthetic.exe"' in data or b'PKcorrupt' in data or b'%PDF-corrupt' in data or b'filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n\r\n' in data:
                    return response(400)
                # Extract the actual multipart document for byte-for-byte Storage checks.
                document = data.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
                if not document:
                    return response(400)
                id = str(uuid4())
                object_path = owner + '/' + id + ('.docx' if b'filename="synthetic.docx"' in data else '.pdf')
                self.rows[id] = {'id': id, 'owner': owner, 'object_path': object_path, 'state': 'ready'}
                self.objects[object_path] = document
                self.events.append({'id': str(uuid4()), 'created_at': 'synthetic', 'event': 'resume_uploaded', 'resource_id': id, '_owner': owner})
                if self.ambiguous:
                    raise httpx.ReadTimeout('sensitive transport detail')
                return response(201, json=self.summary(id))
            id = path.split('/')[4]
            row = self.rows.get(id)
            if not row or row['owner'] != owner:
                return response(404)
            if path.endswith('/download'):
                if self.fail_download:
                    return response(500, json={'secret': self.cfg.secret, 'token': self.tokens[0]})
                return response(200, json={'expires_in': 60, 'url': self.cfg.supabase + '/storage/v1/object/sign/resumes/' + row['object_path'] + '?token=synthetic-signed-link'})
            if method == 'DELETE':
                if self.fail_delete:
                    return response(503)
                self.delete_calls.append(id)
                self.objects.pop(row['object_path'], None)
                del self.rows[id]
                return response(204)
            return response(200, json=self.summary(id))
        if '/object/sign/' in path and method == 'GET':
            assert 'apikey' not in request.headers and 'authorization' not in request.headers
            return response(200, content=self.objects[path.split('/object/sign/resumes/', 1)[1]])
        if '/object/public/' in path:
            return response(404)
        privileged = request.headers.get('apikey') == self.cfg.secret
        if privileged:
            assert 'authorization' not in request.headers
        if '/bucket/' in path:
            return response(200, json={'public': False})
        if '/object/list/' in path:
            if not privileged:
                return response(403)
            params = json.loads(request.content)
            return response(200, json=[{'name': key.rsplit('/', 1)[1]} for key in self.objects if key.startswith(params['prefix'] + '/') and key.endswith(params['search'])])
        if '/object/authenticated/' in path and privileged:
            key = path.split('/object/authenticated/resumes/', 1)[1]
            return response(200, content=self.objects[key]) if key in self.objects else response(404)
        return response(403)

    @contextmanager
    def begin(self):
        def execute(statement, params):
            if str(statement).startswith('DELETE FROM public.cloud_history'):
                self.events[:] = [event for event in self.events if not (event['_owner'] == str(params['owner']) and event['resource_id'] == str(params['id']))]
        yield SimpleNamespace(execute=execute)

    def verifier(self, path):
        client = httpx.Client(transport=httpx.MockTransport(self.provider))
        verifier = live.Verifier(self.cfg, client, self, path)
        verifier.audit_database = lambda: None  # Actual SQL audited by disposable PG tests.
        verifier.rows = lambda user, table: [dict(row) for row in self.rows.values() if row['owner'] == user['id']]
        return verifier


def test_default_never_reads_env_or_connects(monkeypatch, capsys):
    monkeypatch.setattr(live, 'create_engine', lambda *args, **kwargs: pytest.fail('Unexpected connection'))
    assert live.main(['--env-file', 'nonexistent']) == 2
    assert 'PENDING' in capsys.readouterr().out


def test_generated_docx_is_synthetic():
    payloads = live.documents()
    assert set(payloads) == {'.docx', '.pdf'}
    assert 'Synthetic Integration Candidate' in '\n'.join(p.text for p in Document(io.BytesIO(payloads['.docx'])).paragraphs)
    assert payloads['.pdf'].startswith(b'%PDF')


@pytest.mark.parametrize('failure', ['none', 'download', 'delete', 'ambiguous'], ids=['success', 'provider-error', 'cleanup-error', 'lost-upload-response'])
def test_mocked_lifecycle_cleanup_and_no_secret_output(tmp_path, capsys, caplog, failure):
    world = TestWorld()
    world.fail_download = failure == 'download'
    world.fail_delete = failure == 'delete'
    world.ambiguous = failure == 'ambiguous'
    journal = tmp_path / 'journal.json'
    verifier = world.verifier(journal)
    assert verifier.run() == (0 if failure == 'none' else 1)
    output = capsys.readouterr().out + caplog.text
    for sensitive in (*world.tokens, *world.cfg.passwords, world.cfg.secret, world.cfg.database, 'synthetic-signed-link'):
        assert sensitive not in output
        if journal.exists():
            assert sensitive not in journal.read_text()
    assert world.logout == 2
    if failure in {'none', 'download', 'ambiguous'}:
        assert not world.rows and not world.objects and not world.events
    assert journal.exists() == (failure in {'delete', 'ambiguous'})
    verifier.http.close()


def test_preexisting_resources_never_deleted(tmp_path):
    world = TestWorld()
    id = str(uuid4())
    world.rows[id] = {'id': id, 'owner': world.ids[0], 'object_path': world.ids[0] + '/' + id + '.pdf', 'state': 'ready'}
    world.objects[world.rows[id]['object_path']] = b'pre-existing data'
    verifier = world.verifier(tmp_path / 'journal.json')
    assert verifier.run() == 0
    assert id in world.rows and id not in world.delete_calls
    verifier.http.close()


def test_unknown_nonmatching_resources_are_not_deleted(tmp_path):
    world = TestWorld()
    verifier = world.verifier(tmp_path / 'journal.json')
    verifier.login()
    id = str(uuid4())
    world.rows[id] = {'id': id, 'owner': world.ids[0], 'object_path': world.ids[0] + '/' + id + '.pdf', 'state': 'ready'}
    world.objects[world.rows[id]['object_path']] = b'unrelated concurrent data'
    assert not verifier.cleanup()
    assert id in world.rows and id not in world.delete_calls
    assert id in verifier.journal.read_text()
    verifier.http.close()


def test_main_suppresses_configuration_values(monkeypatch, capsys):
    secret = 'do-not-echo-sensitive-configuration'
    monkeypatch.setattr(live.Settings, 'from_env', lambda: (_ for _ in ()).throw(ValueError(secret)))
    assert live.main(['--allow-live-writes']) == 1
    assert secret not in capsys.readouterr().out


def test_recovery_after_failed_delete_uses_fresh_sessions(tmp_path):
    world = TestWorld()
    world.fail_delete = True
    journal = tmp_path / 'retained.json'
    first = world.verifier(journal)
    assert first.run() == 1 and journal.exists() and world.rows
    first.http.close()
    world.fail_delete = False
    second = world.verifier(tmp_path / 'temporary.json')
    assert second.recover(journal) == 0
    assert not world.rows and not world.objects and not world.events
    assert not journal.exists() and world.logout == 4
    assert not (tmp_path / 'temporary.json').exists()
    second.http.close()


def test_recovery_refuses_wrong_accounts_without_deleting(tmp_path):
    world = TestWorld()
    world.fail_delete = True
    journal = tmp_path / 'retained.json'
    first = world.verifier(journal)
    assert first.run() == 1
    first.http.close()
    original_ids = set(world.rows)
    world.ids = [str(uuid4()), str(uuid4())]
    second = world.verifier(tmp_path / 'temporary.json')
    assert second.recover(journal) == 1
    assert set(world.rows) == original_ids and journal.exists()
    second.http.close()


def configure_test_environment(monkeypatch):
    values = dict(PHASE2_API_URL='http://127.0.0.1:8000', SUPABASE_URL='https://project.example.invalid',
                  SUPABASE_PUBLISHABLE_KEY='sb_publishable_unit_test_only', SUPABASE_SECRET_KEY='sb_secret_unit_test_only',
                  CLOUD_DATABASE_URL='postgresql+psycopg://synthetic@localhost/test', SUPABASE_STORAGE_BUCKET='resumes',
                  PHASE2_TEST_USER_A_EMAIL='a@example.invalid', PHASE2_TEST_USER_B_EMAIL='b@example.invalid')
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    for letter in ('A', 'B'):
        monkeypatch.delenv(f'PHASE2_TEST_USER_{letter}_PASSWORD', raising=False)


def test_password_input_never_falls_back_to_echo(monkeypatch):
    import warnings
    configure_test_environment(monkeypatch)
    monkeypatch.setattr(live.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    def unsafe_prompt(*args):
        warnings.warn('Echo could not be disabled', live.GetPassWarning)
        pytest.fail('Insecure echoed fallback must not be reached')
    monkeypatch.setattr(live, 'getpass', unsafe_prompt)
    with pytest.raises(live.GetPassWarning):
        live.Settings.from_env()


def test_missing_password_in_noninteractive_context_fails(monkeypatch):
    configure_test_environment(monkeypatch)
    monkeypatch.setattr(live.sys, 'stdin', SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(live, 'getpass', lambda *args: pytest.fail('No insecure prompt'))
    with pytest.raises(live.VerificationError, match='secure interactive'):
        live.Settings.from_env()


@pytest.mark.parametrize('url', ['http://remote.example', 'https://user:password@example.invalid', 'https://example.invalid/path', 'https://example.invalid?token=unit'],
                         ids=['insecure-remote', 'embedded-credential', 'path', 'query'])
def test_verifier_rejects_unsafe_origins(url):
    with pytest.raises(live.VerificationError):
        live.origin(url, local=True)


@pytest.mark.parametrize('exposure', ['data-api', 'bucket-public', 'signed-redirect'],
                         ids=['data-api-empty-success-is-unsafe', 'public-bucket', 'unexpected-signed-origin'])
def test_verifier_fails_on_security_exposure(tmp_path, exposure):
    world = TestWorld()
    verifier = world.verifier(tmp_path / 'journal.json')
    verifier.http.close()
    def provider(request):
        if exposure == 'data-api' and request.url.path.startswith('/rest/v1/'):
            return httpx.Response(200, json=[])
        if exposure == 'bucket-public' and '/bucket/' in request.url.path:
            return httpx.Response(200, json={'public': True})
        if exposure == 'signed-redirect' and request.url.path.endswith('/download') and world.owner(request) == world.ids[0]:
            return httpx.Response(200, json={'expires_in': 60, 'url': 'https://untrusted.example/download'})
        return world.provider(request)
    verifier.http = httpx.Client(transport=httpx.MockTransport(provider))
    assert verifier.run() == 1
    assert not world.rows and not world.objects
    verifier.http.close()
