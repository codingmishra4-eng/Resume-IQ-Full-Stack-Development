"""Opt-in synthetic integration checks. No migrations or account provisioning.

--allow-live-writes authorizes login and test-resource writes for two dedicated,
exclusively used test accounts. No file/network/DB secrets are printed. Journals
contain only resource UUIDs, relative object paths and hashes and must be retained on incomplete cleanup.
"""
import argparse
from dataclasses import dataclass
from getpass import getpass, GetPassWarning
import warnings
import hashlib
import io
import json
import logging
import os
import re
from pathlib import Path
import sys
import tempfile
from urllib.parse import quote, urlsplit
from uuid import UUID, uuid4
import httpx
from sqlalchemy import create_engine, text

TABLES = ('cloud_resumes', 'cloud_analyses', 'cloud_saved_resumes', 'cloud_history')
DENIED = {400, 401, 403, 404}


class VerificationError(Exception):
    """Static messages only; never interpolate input or response bodies."""


def require(condition, label):
    if not condition:
        raise VerificationError(label)


def origin(value, local=False):
    url = urlsplit(value)
    require(url.scheme == 'https' or (local and url.scheme == 'http' and url.hostname in {'localhost', '127.0.0.1', '::1'}), 'Invalid verification origin.')
    require(bool(url.hostname) and not (url.username or url.password or url.query or url.fragment or url.path), 'Use exact origins without credentials or paths.')
    return value


METADATA_FIELDS = {'file_name', 'file_type', 'pages', 'word_count', 'section_order',
                   'bullet_count', 'tables_detected', 'images_detected', 'headings_look_caps'}


def public_resume(item):
    require(set(item) == {'id', 'created_at', 'metadata'}, 'Unexpected resume response fields.')
    metadata = item['metadata']
    require(isinstance(metadata, dict) and set(metadata) == METADATA_FIELDS, 'Unexpected metadata response fields.')
    require(metadata['file_name'] in {'resume.pdf', 'resume.docx'} and metadata['file_type'] in {'pdf', 'docx'},
            'Unsafe display filename/type.')


@dataclass(repr=False)
class Settings:
    api: str
    supabase: str
    publishable: str
    secret: str
    database: str
    bucket: str
    emails: tuple[str, str]
    passwords: tuple[str, str]

    @classmethod
    def from_env(cls):
        names = ('PHASE2_API_URL', 'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SECRET_KEY',
                 'CLOUD_DATABASE_URL', 'SUPABASE_STORAGE_BUCKET', 'PHASE2_TEST_USER_A_EMAIL', 'PHASE2_TEST_USER_B_EMAIL')
        require(all(os.getenv(name) for name in names), 'Required settings/test accounts are missing.')
        api, supabase, publishable, secret, database, bucket, a, b = (os.environ[name] for name in names)
        origin(api, local=True)
        origin(supabase)
        require(re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]+', publishable) and re.fullmatch(r'sb_secret_[A-Za-z0-9_-]+', secret), 'Modern API keys required.')
        require(database.startswith('postgresql+psycopg://'), 'Restricted PostgreSQL runtime URL required.')
        require(bucket and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in bucket), 'Invalid private bucket.')
        require(a.casefold() != b.casefold(), 'Use two distinct dedicated test accounts.')
        passwords = []
        for letter in ('A', 'B'):
            value = os.getenv(f'PHASE2_TEST_USER_{letter}_PASSWORD')
            if not value:
                require(sys.stdin.isatty(), 'Use a secure interactive terminal or environment-injected test passwords.')
                with warnings.catch_warnings():
                    warnings.simplefilter('error', GetPassWarning)  # Never fall back to echoed input.
                    value = getpass(f'Dedicated test user {letter} password: ')
            require(bool(value), 'Test password is required.')
            passwords.append(value)
        return cls(api, supabase, publishable, secret, database, bucket, (a, b), tuple(passwords))


def documents():
    """Synthetic-only documents generated in memory."""
    from docx import Document
    import pymupdf
    words = 'Python SQL testing teamwork delivery synthetic verification ' * 25
    words += '\nSynthetic run ' + uuid4().hex
    doc = Document()
    doc.add_heading('Synthetic Integration Candidate', 0)
    doc.add_heading('Skills', 1)
    doc.add_paragraph(words)
    buffer = io.BytesIO()
    doc.save(buffer)
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_textbox(pymupdf.Rect(40, 40, 550, 780), 'Skills\n' + words)
        return {'.docx': buffer.getvalue(), '.pdf': pdf.tobytes()}


class Verifier:
    def __init__(self, settings, client, engine, journal):
        self.cfg, self.http, self.engine, self.journal = settings, client, engine, journal
        self.users, self.baseline, self.created = [], {}, {}
        self.uncertain, self.ambiguous_upload, self.paths = {}, False, {}
        self.payloads = documents()
        self.hashes = {hashlib.sha256(data).hexdigest() for data in self.payloads.values()}
        self.passed = self.failed = 0
        self.active = 'preflight'

    def check(self, label, action):
        self.active = label
        action()
        self.passed += 1
        print('PASS:', label)  # Fixed label only, never input/response data.

    def request(self, method, url, **kwargs):
        try:
            return self.http.request(method, url, **kwargs)
        except Exception:
            raise VerificationError('Request failed; sensitive details suppressed.') from None

    def api(self, method, path, user=None, **kwargs):
        headers = {'Authorization': 'Bearer ' + user['token']} if user else {}
        return self.request(method, self.cfg.api + path, headers=headers, **kwargs)

    def storage(self, method, path, user=None, privileged=False, **kwargs):
        headers = {'apikey': self.cfg.secret if privileged else self.cfg.publishable}
        if user:
            headers['Authorization'] = 'Bearer ' + user['token']
        return self.request(method, self.cfg.supabase + '/storage/v1/' + path, headers=headers, **kwargs)

    def rows(self, user, table):
        require(table in {'cloud_resumes', 'cloud_history'}, 'Invalid verification table.')
        with self.engine.begin() as connection:
            connection.execute(text("SELECT set_config('resumeiq.user_id', :owner, true)"), {'owner': user['id']})
            columns = 'id, object_path, state' if table == 'cloud_resumes' else 'id, resource_id'
            return list(connection.execute(text(f'SELECT {columns} FROM public.{table} WHERE user_id=:owner'),
                                           {'owner': UUID(user['id'])}).mappings())

    def audit_database(self):
        with self.engine.begin() as connection:
            role = connection.execute(text('SELECT current_user AS name, rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication AS privileged FROM pg_roles WHERE rolname=current_user')).mappings().one()
            require(role['name'] == 'resumeiq_runtime' and not role['privileged'], 'Runtime role is not restricted.')
            require(not connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))")), 'Runtime has parent role memberships.')
            require(not connection.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')")), 'Runtime has schema CREATE privileges.')
            for table in TABLES:
                row = connection.execute(text('SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:table)'), {'table': 'public.' + table}).one_or_none()
                require(row == (True, True), 'Cloud table missing RLS/FORCE RLS.')
            for table in (*TABLES, 'alembic_version'):
                public = connection.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE c.oid=to_regclass(:table) AND a.grantee=0)'), {'table': 'public.' + table})
                require(not public, 'PUBLIC retains application-table privileges.')
                roles = connection.execute(text("SELECT rolname, has_table_privilege(oid,:table,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS access, pg_has_role(oid,'resumeiq_runtime','MEMBER') AS member FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role')"), {'table': 'public.' + table}).mappings().all()
                require(len(roles) == 3 and not any(row['access'] or row['member'] for row in roles), 'Data API roles retain application-table access.')
            connection.execute(text("SELECT set_config('resumeiq.user_id', '', true)"))
            require(not connection.execute(text('SELECT id FROM public.cloud_resumes LIMIT 1')).first(), 'Unscoped runtime sees records.')

    def login(self):
        for email, password in zip(self.cfg.emails, self.cfg.passwords):
            response = self.request('POST', self.cfg.supabase + '/auth/v1/token?grant_type=password',
                                    headers={'apikey': self.cfg.publishable}, json={'email': email, 'password': password})
            require(response.status_code == 200, 'Test-user login failed.')
            data = response.json()
            user = {'id': str(UUID(data['user']['id'])), 'token': data['access_token']}
            self.users.append(user)  # Track even when second login fails.
            require(not data['user'].get('is_anonymous', False), 'Nonanonymous test users required.')
        require(self.users[0]['id'] != self.users[1]['id'], 'Distinct test identities required.')
        for user in self.users:
            self.baseline[user['id']] = {str(row['id']) for row in self.rows(user, 'cloud_resumes')}
            self.created[user['id']] = set()
        self.save_journal()

    def save_journal(self):
        data = {'version': 1, 'created': {owner: sorted(ids) for owner, ids in self.created.items()}, 'hashes': sorted(self.hashes), 'baseline': {owner: sorted(ids) for owner, ids in self.baseline.items()},
                'uncertain': {owner: sorted(ids) for owner, ids in self.uncertain.items()}, 'ambiguous_upload': self.ambiguous_upload, 'paths': self.paths}
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='.phase2-', dir=self.journal.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                json.dump(data, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.journal)  # Never truncate the last good recovery record.
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def snapshot_list(self, path, user):
        items = []
        for offset in range(0, 10000, 100):
            response = self.api('GET', f'{path}?offset={offset}', user)
            require(response.status_code == 200 and isinstance(response.json(), list), 'Owned list failed.')
            batch = response.json()
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise VerificationError('Dedicated test account has too many records.')

    def authenticate(self):
        for user in self.users:
            response = self.api('GET', '/api/me', user)
            require(response.status_code == 200 and response.json() == {'id': user['id']}, 'FastAPI JWT identity mismatch.')
        for path in ('/api/me', '/api/v1/resumes', '/api/v1/history'):
            require(self.api('GET', path).status_code == 401, 'Missing JWT accepted.')
            require(self.api('GET', path, {'token': 'not-a-valid-jwt'}).status_code == 401, 'Invalid JWT accepted.')
        for caller in (None, {'token': 'not-a-valid-jwt'}):
            require(self.api('POST', '/api/v1/resumes', caller,
                             files={'file': ('synthetic.docx', self.payloads['.docx'])}).status_code == 401,
                    'Unauthenticated cloud upload accepted.')

    def table_api_restrictions(self):
        # Real Data API denial, not just a catalog assertion. Read at most one
        # UUID and never serialize response bodies if a permission is wrong.
        callers = (None, *self.users)
        for table in (*TABLES, 'alembic_version'):
            url = self.cfg.supabase + '/rest/v1/' + table + '?select=id&limit=1'
            # Alembic uses version_num, not id. Asking for the real column avoids
            # mistaking a malformed query for an authorization denial.
            if table == 'alembic_version':
                url = self.cfg.supabase + '/rest/v1/alembic_version?select=version_num&limit=1'
            for caller in callers:
                headers = {'apikey': self.cfg.publishable}
                if caller:
                    headers['Authorization'] = 'Bearer ' + caller['token']
                require(self.request('GET', url, headers=headers).status_code in {401, 403, 404},
                        'Data API exposes a private application table.')
            require(self.request('GET', url, headers={'apikey': self.cfg.secret}).status_code in {401, 403, 404},
                    'Privileged Data API exposes an application table.')

    def validate_files(self):
        for suffix, data in [('exe', b'not a document'), ('pdf', b''), ('pdf', b'%PDF-corrupt'), ('docx', b'PKcorrupt'), ('pdf', b'x' * (10 * 1024 * 1024 + 1))]:
            response = self.api('POST', '/api/v1/resumes', self.users[0], files={'file': ('synthetic.' + suffix, data)})
            require(response.status_code == 400, 'Invalid document accepted.')
        response = self.api('POST', '/api/resume/upload', files={'file': ('synthetic.docx', self.payloads['.docx'])})
        require(response.status_code in {403, 404}, 'Legacy unauthenticated upload is publicly reachable.')

    def bucket_private(self):
        response = self.storage('GET', 'bucket/' + quote(self.cfg.bucket, safe=''), privileged=True)
        require(response.status_code == 200 and response.json().get('public') is False, 'Bucket not verified private.')

    def lifecycle(self):
        self.active = 'synthetic upload/private Storage lifecycle'
        for user, suffix in zip(self.users, ('.docx', '.pdf')):
            other = next(item for item in self.users if item is not user)
            data = self.payloads[suffix]
            self.ambiguous_upload = True
            self.save_journal()
            response = self.api('POST', '/api/v1/resumes', user, files={'file': ('synthetic' + suffix, data)})
            self.ambiguous_upload = False
            require(response.status_code == 201, 'Synthetic resume upload failed.')
            body = response.json()
            id = str(UUID(body['id']))
            require(id not in self.baseline[user['id']], 'Upload returned a pre-existing resource.')
            self.created[user['id']].add(id)
            self.save_journal()
            public_resume(body)
            rows = {str(row['id']): row for row in self.rows(user, 'cloud_resumes')}
            require(id in rows and rows[id]['state'] == 'ready', 'Metadata not persisted in supplied runtime database.')
            path = rows[id]['object_path']
            self.paths[id] = path
            self.save_journal()
            require(path.startswith(user['id'] + '/') and '..' not in path, 'Unsafe object ownership path.')
            object_path = quote(self.cfg.bucket, safe='') + '/' + quote(path, safe='/')
            require(id in {item['id'] for item in self.snapshot_list('/api/v1/resumes', user)}, 'Owned listing missing resume.')
            require(id not in {item['id'] for item in self.snapshot_list('/api/v1/resumes', other)}, 'Cross-user listing leak.')
            for item in self.snapshot_list('/api/v1/resumes', user):
                public_resume(item)
            own = self.api('GET', f'/api/v1/resumes/{id}', user)
            require(own.status_code == 200, 'Owned metadata lookup failed.')
            public_resume(own.json())
            for method, tail in [('GET', ''), ('POST', '/download'), ('DELETE', '')]:
                require(self.api(method, f'/api/v1/resumes/{id}{tail}', other).status_code == 404, 'Cross-user resource operation accepted.')
            signed = self.api('POST', f'/api/v1/resumes/{id}/download', user)
            require(signed.status_code == 200 and 0 < signed.json()['expires_in'] <= 60, 'Owner signed download failed.')
            url = signed.json()['url']
            parsed, expected = urlsplit(url), urlsplit(self.cfg.supabase)
            require((parsed.scheme, parsed.netloc) == (expected.scheme, expected.netloc)
                    and parsed.path.startswith('/storage/v1/object/sign/') and not parsed.username and not parsed.password,
                    'Unexpected signed download origin.')
            download = self.request('GET', url)
            require(download.status_code == 200 and download.content == data, 'Stored synthetic document mismatch.')
            for caller in (None, user, other):
                raw = self.storage('GET', 'object/authenticated/' + object_path, caller)
                require(raw.status_code in DENIED, 'Direct client Storage access accepted.')
                sign = self.storage('POST', 'object/sign/' + object_path, caller, json={'expiresIn': 60})
                require(sign.status_code in DENIED, 'Direct client Storage signing accepted.')
                listing = self.storage('POST', 'object/list/' + quote(self.cfg.bucket, safe=''), caller,
                                       json={'prefix': user['id'], 'search': path.rsplit('/', 1)[1], 'limit': 100})
                require(listing.status_code in DENIED or (listing.status_code == 200 and isinstance(listing.json(), list)
                        and not any(item.get('name') == path.rsplit('/', 1)[1] for item in listing.json())),
                        'Direct client Storage listing exposes the document.')
            public = self.request('GET', self.cfg.supabase + '/storage/v1/object/public/' + object_path)
            require(public.status_code in DENIED, 'Public object download accepted.')
            self.passed += 1
            print('PASS: synthetic upload, persistence, isolation and private download lifecycle')

    def history(self):
        for user in self.users:
            items = self.snapshot_list('/api/v1/history', user)
            own = self.created[user['id']]
            others = set().union(*(ids for owner, ids in self.created.items() if owner != user['id']))
            require(own <= {item['resource_id'] for item in items}, 'Upload history missing.')
            require(not others & {item['resource_id'] for item in items}, 'Cross-user history leak.')
            require(all(set(item) == {'id', 'created_at', 'event', 'resource_id'} for item in items), 'Unexpected history response fields.')

    def cleanup(self):
        """Delete confirmed IDs/hash-matched synthetic objects only; retain journal on outage."""
        ok = not self.ambiguous_upload
        for user in self.users:
            owner = user['id']
            if owner not in self.baseline:
                continue
            try:
                for row in self.rows(user, 'cloud_resumes'):
                    id = str(row['id'])
                    if id in self.baseline[owner] or id in self.created[owner]:
                        continue
                    path = row['object_path']
                    require(path.startswith(owner + '/') and '..' not in path, 'Unsafe cleanup candidate.')
                    response = self.storage('GET', 'object/authenticated/' + quote(self.cfg.bucket, safe='') + '/' + quote(path, safe='/'), privileged=True)
                    if response.status_code == 200 and hashlib.sha256(response.content).hexdigest() in self.hashes:
                        self.created[owner].add(id)
                        self.paths[id] = path
                    else:
                        self.uncertain.setdefault(owner, set()).add(id)
                        ok = False  # Unverifiable resources remain untouched.
                    self.save_journal()
                for id in list(self.created[owner]):
                    rows = {str(row['id']): row for row in self.rows(user, 'cloud_resumes')}
                    path = rows[id]['object_path'] if id in rows else self.paths.get(id)
                    if path:
                        require(path.startswith(owner + '/') and '..' not in path, 'Unsafe cleanup path.')
                        self.paths[id] = path
                        self.save_journal()
                    response = self.api('DELETE', f'/api/v1/resumes/{id}', user)
                    require(response.status_code in {204, 404}, 'Cleanup deletion failed.')
                    require(id not in {str(row['id']) for row in self.rows(user, 'cloud_resumes')}, 'Metadata remained after deletion.')
                    if not path:
                        ok = False  # Metadata disappeared before its object path could be verified.
                    if path:
                        prefix, name = path.rsplit('/', 1)
                        response = self.storage('POST', 'object/list/' + quote(self.cfg.bucket, safe=''), privileged=True,
                                                json={'prefix': prefix, 'search': name, 'limit': 100})
                        require(response.status_code == 200 and isinstance(response.json(), list)
                                and not any(item.get('name') == name for item in response.json()), 'Stored file remained after deletion.')
                with self.engine.begin() as connection:
                    connection.execute(text("SELECT set_config('resumeiq.user_id', :owner, true)"), {'owner': owner})
                    for id in self.created[owner]:
                        connection.execute(text('DELETE FROM public.cloud_history WHERE user_id=:owner AND resource_id=:id'),
                                           {'owner': UUID(owner), 'id': UUID(id)})
            except Exception:
                ok = False
        for user in self.users:
            try:
                response = self.request('POST', self.cfg.supabase + '/auth/v1/logout?scope=local',
                                        headers={'apikey': self.cfg.publishable, 'Authorization': 'Bearer ' + user['token']})
                require(response.status_code in {200, 204}, 'Test session logout failed.')
            except Exception:
                ok = False
        if ok:
            if self.journal.exists():
                self.journal.unlink()
            self.passed += 1
            print('PASS: test resource cleanup and test-session logout')
        else:
            self.failed += 1
            self.save_journal()
            print('FAIL: cleanup incomplete; retain the local recovery journal for operator review')
        return ok

    def recover(self, source):
        """Explicit replay after an operator confirms all old uploads have settled."""
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            data = json.loads(source.read_text(encoding='utf-8'))
            require(data.get('version') == 1, 'Unsupported recovery journal.')
            self.audit_database()
            self.bucket_private()
            self.login()  # Fresh local Auth sessions; no tokens are stored in journals.
            owners = {user['id'] for user in self.users}
            require(set(data['created']) <= owners and set(data['baseline']) <= owners, 'Journal belongs to different accounts.')
            baseline = {owner: {str(UUID(id)) for id in ids} for owner, ids in data['baseline'].items()}
            created = {owner: {str(UUID(id)) for id in ids} for owner, ids in data['created'].items()}
            hashes = set(data['hashes'])
            require(hashes and all(len(value) == 64 and all(c in '0123456789abcdef' for c in value) for value in hashes), 'Invalid recovery hashes.')
            paths = data.get('paths', {})
            for id, path in paths.items():
                owner = next((owner for owner, ids in created.items() if id in ids), None)
                parts = path.split('/')
                require(owner is not None and len(parts) == 2 and parts[0] == owner, 'Invalid recovery object path.')
                name, suffix = parts[1].rsplit('.', 1)
                require(str(UUID(name)) == name and suffix in {'pdf', 'docx'}, 'Invalid recovery object name.')
            for owner, ids in created.items():
                require(owner in baseline and not ids & baseline[owner], 'Journal includes pre-existing IDs.')
                user = next(user for user in self.users if user['id'] == owner)
                for row in self.rows(user, 'cloud_resumes'):
                    id = str(row['id'])
                    if id not in ids:
                        continue
                    path = row['object_path']
                    require(path.startswith(owner + '/') and '..' not in path, 'Unsafe recovery candidate.')
                    response = self.storage('GET', 'object/authenticated/' + quote(self.cfg.bucket, safe='') + '/' + quote(path, safe='/'), privileged=True)
                    require(response.status_code == 200 and hashlib.sha256(response.content).hexdigest() in hashes,
                            'Cannot prove candidate is this run synthetic document; operator review required.')
            self.baseline, self.created, self.hashes, self.paths = baseline, created, hashes, paths
            temporary_journal = self.journal
            self.journal = source
            self.ambiguous_upload = False  # Explicit recovery requires old requests to be settled.
            self.save_journal()
            if temporary_journal != source and temporary_journal.exists():
                temporary_journal.unlink()
        except (Exception, KeyboardInterrupt):
            self.failed += 1
            print('FAIL: recovery validation; sensitive details suppressed')
        finally:
            try:
                ok = self.cleanup()
            finally:
                logging.disable(previous)
        return 0 if ok and self.failed == 0 else 1

    def run(self):
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            self.check('restricted runtime, RLS and table ACLs', self.audit_database)
            self.check('private Storage bucket', self.bucket_private)
            self.check('two dedicated test-user logins', self.login)
            self.check('FastAPI JWT identity and rejection', self.authenticate)
            self.check('direct Data API denial', self.table_api_restrictions)
            self.check('document validation and legacy upload blocking', self.validate_files)
            self.lifecycle()
            self.check('owned history and isolation', self.history)
        except (Exception, KeyboardInterrupt):
            self.failed += 1
            print('FAIL:', self.active, '(sensitive details suppressed)')
        finally:
            try:
                self.cleanup()
            finally:
                logging.disable(previous)
        print(f'Verification checks: {self.passed} passed, {self.failed} failed; live tests attempted.')
        return 0 if self.failed == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, help='Explicit local ignored environment file; none is loaded by default.')
    parser.add_argument('--cleanup-journal', type=Path, help='Replay a retained journal after all old requests have settled.')
    parser.add_argument('--allow-live-writes', action='store_true', help='Authorize writes for two dedicated, exclusively used test accounts.')
    args = parser.parse_args(argv)
    if not args.allow_live_writes:
        print('PENDING: live checks require dedicated settings and --allow-live-writes. No network or DB access performed.')
        return 2
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)  # HTTP diagnostics may contain signed URLs.
    try:
        if args.env_file:
            from dotenv import load_dotenv
            require(args.env_file.is_file(), 'Environment file missing.')
            load_dotenv(args.env_file, override=False)
        settings = Settings.from_env()
        engine = create_engine(settings.database, pool_pre_ping=True, hide_parameters=True)
        journal = Path('work') / ('phase2-verification-' + uuid4().hex + '.json')
        try:
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                verifier = Verifier(settings, client, engine, journal)
                return verifier.recover(args.cleanup_journal) if args.cleanup_journal else verifier.run()
        finally:
            engine.dispose()
    except (Exception, KeyboardInterrupt):
        print('FAIL: configuration or verification unavailable; sensitive details suppressed.')
        return 1
    finally:
        logging.disable(previous)


if __name__ == '__main__':
    raise SystemExit(main())
