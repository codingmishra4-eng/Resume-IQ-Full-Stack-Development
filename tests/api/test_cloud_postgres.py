"""REAL migrations/ACL/RLS on an explicitly supplied disposable PostgreSQL only.

Creates NOLOGIN test roles, never real users/passwords. Do not point this suite at
Supabase or a database with valuable data. No .env connection fallback is used.
"""
import os
import subprocess
import sys
from uuid import uuid4
from pathlib import Path

import pytest
from sqlalchemy import text, inspect, event
from sqlalchemy.exc import DBAPIError, OperationalError
from backend.cloud.database import CloudDatabase
from backend.cloud.models import Resume, Analysis, SavedResume, History
from backend.api_v1.errors import APIError

URL = os.getenv('TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not URL, reason='TEST_POSTGRES_URL not set; requires disposable PostgreSQL')
TABLES = ('cloud_resumes', 'cloud_analyses', 'cloud_saved_resumes', 'cloud_history')
API_ROLES = ('anon', 'authenticated', 'service_role')


def migrate(*args, check=True):
    return subprocess.run([sys.executable, '-m', 'alembic', *args],
        env=os.environ | {'CLOUD_MIGRATION_DATABASE_URL': URL}, check=check, capture_output=True)


@pytest.fixture(scope='module')
def postgres():
    db = CloudDatabase(URL)
    # First verify plain PostgreSQL: no Supabase functions, schemas or roles.
    migrate('upgrade', 'head')
    migrate('downgrade', 'base')
    assert not set(TABLES) & set(inspect(db.engine).get_table_names())
    with db.engine.begin() as conn:
        for role in API_ROLES:
            conn.execute(text(f'CREATE ROLE {role} NOLOGIN' + (' BYPASSRLS' if role == 'service_role' else '')))
        conn.execute(text('CREATE ROLE resumeiq_runtime NOLOGIN NOINHERIT NOBYPASSRLS'))
        conn.execute(text('CREATE ROLE phase2_inherited NOLOGIN'))
        conn.execute(text('GRANT phase2_inherited TO service_role'))
        # Simulate Supabase's permissive new-table defaults, including inherited ACLs.
        conn.execute(text('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role, PUBLIC'))
        conn.execute(text('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO phase2_inherited'))
        conn.execute(text('CREATE TABLE public.phase2_unrelated (id integer)'))
    # Revoking direct grants cannot neutralize inherited access: fail atomically.
    result = migrate('upgrade', 'head', check=False)
    assert result.returncode != 0
    assert b'Data API role retains cloud table privileges' in result.stderr
    assert not set(TABLES) & set(inspect(db.engine).get_table_names())
    with db.engine.begin() as conn:
        conn.execute(text('REVOKE phase2_inherited FROM service_role'))
    migrate('upgrade', '0001_cloud')
    legacy_id, legacy_owner = uuid4(), uuid4()
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO public.cloud_analyses (id,user_id,summary_json,created_at,updated_at) VALUES (:id,:owner,CAST(:payload AS jsonb),now(),now())"), {'id':legacy_id,'owner':legacy_owner,'payload':'{"ats_score":42}'})
    migrate('upgrade', 'head')
    with db.engine.begin() as conn:
        row=conn.execute(text('SELECT resume_id,kind,summary_json FROM public.cloud_analyses WHERE id=:id'),{'id':legacy_id}).one()
        assert row.resume_id is None and row.kind=='analysis' and row.summary_json=={'ats_score':42}
        conn.execute(text('DELETE FROM public.cloud_analyses WHERE id=:id'),{'id':legacy_id})
    # Operator-reviewed provisioning grants, not automatic role/user creation.
    grants = Path('docs/sql/phase2_runtime.sql').read_text()
    with db.engine.connect() as conn:
        conn.exec_driver_sql(grants)
    yield db
    migrate('downgrade', 'base')
    assert not set(TABLES) & set(inspect(db.engine).get_table_names())
    assert 'phase2_unrelated' in inspect(db.engine).get_table_names()
    migrate('upgrade', 'head')
    db.engine.dispose()


def test_migration_permissions_and_force_rls(postgres):
    with postgres.engine.connect() as conn:
        for table in (*TABLES, 'alembic_version'):
            for role in API_ROLES:
                assert not conn.scalar(text("SELECT has_table_privilege(:role, :table, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"),
                                       {'role': role, 'table': 'public.' + table})
            assert not conn.scalar(text("""SELECT EXISTS (
                SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
                WHERE c.oid = to_regclass(:table) AND a.grantee = 0)"""), {'table': 'public.' + table})
        for table in TABLES:
            flags = conn.execute(text('SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass(:table)'),
                                 {'table': 'public.' + table}).one()
            assert flags == (True, True)
        # Unrelated defaults/objects have not been globally revoked.
        assert conn.scalar(text("SELECT has_table_privilege('anon', 'public.phase2_unrelated', 'SELECT')"))


@pytest.mark.parametrize('role', API_ROLES, ids=['anon', 'authenticated', 'service-role-bypass'])
def test_data_api_roles_denied_even_with_forged_identity(postgres, role):
    for table in (*TABLES, 'alembic_version'):
        with postgres.engine.connect() as conn, conn.begin():
            conn.execute(text(f'SET LOCAL ROLE {role}'))
            conn.execute(text("SELECT set_config('resumeiq.user_id', :id, true)"), {'id': str(uuid4())})
            with pytest.raises(DBAPIError) as exc:
                conn.execute(text(f'SELECT * FROM public.{table}'))
            assert exc.value.orig.sqlstate == '42501'


def runtime_database():
    db = CloudDatabase(URL, require_runtime=True)
    @event.listens_for(db.engine, 'connect')
    def assume_nologin_test_role(dbapi_connection, record):
        # Local test impersonation; no login user/password is created.
        with dbapi_connection.cursor() as cursor:
            cursor.execute('SET ROLE resumeiq_runtime')
        dbapi_connection.commit()
    return db


@pytest.mark.parametrize('model,values', [
    (Resume, {'object_path': 'synthetic/' + str(uuid4()) + '.pdf', 'state': 'ready', 'metadata_json': {}}),
    (Analysis, {'summary_json': {'ats_score': 80}}),
    (SavedResume, {'data_json': {'template': 'synthetic'}}),
    (History, {'event': 'test', 'resource_id': uuid4()})],
    ids=['resumes', 'analyses', 'saved-resumes', 'history'])
def test_runtime_rls_and_orm_owner_isolation(postgres, model, values):
    runtime = runtime_database()
    owner, other = uuid4(), uuid4()
    try:
        row = runtime.create(model, owner, **values)
        assert row.id in [item.id for item in runtime.list(model, owner)]
        assert runtime.list(model, other) == []
        # Direct SQL without an identity fails closed, including a pooled connection
        # previously used for owner. No application WHERE clause hides the result.
        with runtime.sessions() as session:
            assert session.scalars(text(f'SELECT id FROM public.{model.__tablename__}')).all() == []
        with runtime.for_user(other).sessions.begin() as session:
            assert session.scalars(text(f'SELECT id FROM public.{model.__tablename__}')).all() == []
            assert session.execute(text(f'DELETE FROM public.{model.__tablename__} WHERE id=:id'), {'id': row.id}).rowcount == 0
            assert session.execute(text(f'UPDATE public.{model.__tablename__} SET user_id=:other WHERE id=:id'),
                                   {'other': other, 'id': row.id}).rowcount == 0
        with pytest.raises(DBAPIError) as exc:
            with runtime.for_user(other).sessions.begin() as session:
                session.add(model(user_id=owner, **(values | {'object_path': 'synthetic/' + str(uuid4()) + '.pdf'} if model is Resume else values)))
        assert exc.value.orig.sqlstate == '42501'
        with pytest.raises(DBAPIError):
            with runtime.for_user(owner).sessions.begin() as session:
                session.execute(text(f'UPDATE public.{model.__tablename__} SET user_id=:other WHERE id=:id'),
                                {'other': other, 'id': row.id})
        with pytest.raises(APIError):
            with runtime.for_user(other).sessions() as session:
                runtime.owned(session, model, other, row.id)
        if model in (Analysis, SavedResume):
            key = 'summary_json' if model is Analysis else 'data_json'
            runtime.update(model, owner, row.id, **{key: {'updated': True}})
            with pytest.raises(APIError):
                runtime.update(model, other, row.id, **{key: {}})
        with runtime.for_user(owner).sessions.begin() as session:
            session.delete(runtime.owned(session, model, owner, row.id))
        assert runtime.list(model, owner) == []
    finally:
        runtime.engine.dispose()


def test_runtime_permissions_and_row_locks(postgres):
    runtime = runtime_database()
    owner = uuid4()
    try:
        with runtime.sessions() as session:
            assert not session.scalar(text("SELECT rolbypassrls OR rolcreaterole OR rolcreatedb OR rolsuper FROM pg_roles WHERE rolname=current_user"))
            assert not session.scalar(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')"))
            assert not session.scalar(text("SELECT has_table_privilege(current_user, 'public.alembic_version', 'SELECT')"))
            assert not session.scalar(text("SELECT has_table_privilege(current_user, 'public.cloud_resumes', 'TRUNCATE,REFERENCES,TRIGGER')"))
        with pytest.raises(DBAPIError):
            with runtime.sessions.begin() as session:
                session.execute(text('ALTER TABLE public.cloud_resumes ADD COLUMN forbidden integer'))
        row = runtime.create(SavedResume, owner, data_json={})
        with runtime.for_user(owner).sessions.begin() as first:
            runtime.owned(first, SavedResume, owner, row.id)
            with runtime.for_user(owner).sessions.begin() as second:
                second.execute(text("SET LOCAL lock_timeout = '50ms'"))
                with pytest.raises(OperationalError):
                    runtime.owned(second, SavedResume, owner, row.id)
        runtime.delete(SavedResume, owner, row.id)
        with pytest.raises(ValueError):
            runtime.for_user(owner).for_user(uuid4())
    finally:
        runtime.engine.dispose()


def test_nobypass_runtime_api_workflow(postgres, pdf_bytes):
    from fastapi.testclient import TestClient
    from backend.api import create_app
    from backend.api_v1.settings import APISettings
    from backend.cloud.auth import current_user, Identity
    from types import SimpleNamespace
    runtime = runtime_database()
    owner, other = Identity(uuid4()), Identity(uuid4())
    app = create_app(APISettings())
    app.state.cloud_db = runtime
    app.state.private_storage = SimpleNamespace(upload=lambda *args: None, delete=lambda *args: None,
                                               sign=lambda *args: 'https://example.invalid/temporary')
    app.dependency_overrides[current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            result = client.post('/api/v1/resumes', files={'file': ('synthetic.pdf', pdf_bytes)})
            assert result.status_code == 201, result.text
            id = result.json()['id']
            assert client.get(f'/api/v1/resumes/{id}').status_code == 200
            assert client.post(f'/api/v1/resumes/{id}/download').status_code == 200
            assert len(client.get('/api/v1/history').json()) == 1
            app.dependency_overrides[current_user] = lambda: other
            assert client.get('/api/v1/resumes').json() == []
            assert client.get('/api/v1/history').json() == []
            assert client.delete(f'/api/v1/resumes/{id}').status_code == 404
            app.dependency_overrides[current_user] = lambda: owner
            assert client.delete(f'/api/v1/resumes/{id}').status_code == 204
            assert len(client.get('/api/v1/history').json()) == 2
    finally:
        runtime.engine.dispose()


def test_concurrent_scopes_and_schema_shadowing(postgres):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import select
    runtime = runtime_database()
    users = [uuid4(), uuid4()]
    try:
        rows = [runtime.create(SavedResume, user, data_json={}) for user in users]
        def read_owner(index):
            for _ in range(10):
                assert [row.id for row in runtime.list(SavedResume, users[index])] == [rows[index].id]
        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(read_owner, (0, 1)))
        with runtime.for_user(users[0]).sessions.begin() as session:
            session.execute(text('CREATE TEMP TABLE cloud_saved_resumes (id uuid) ON COMMIT DROP'))
            assert session.scalar(select(SavedResume).where(SavedResume.id == rows[0].id)).id == rows[0].id
        for user, row in zip(users, rows):
            runtime.delete(SavedResume, user, row.id)
    finally:
        runtime.engine.dispose()


def test_runtime_grants_reject_bypass_role(postgres):
    grants = Path('docs/sql/phase2_runtime.sql').read_text()
    with postgres.engine.begin() as conn:
        conn.execute(text('ALTER ROLE resumeiq_runtime BYPASSRLS'))
    try:
        with postgres.engine.connect() as conn:
            with pytest.raises(DBAPIError) as exc:
                conn.exec_driver_sql(grants)
            assert 'Runtime must have no administrative attributes or BYPASSRLS' in str(exc.value)
    finally:
        with postgres.engine.begin() as conn:
            conn.execute(text('ALTER ROLE resumeiq_runtime NOBYPASSRLS'))


def test_api_runtime_guard_rejects_admin_and_verifier_audits_runtime(postgres, tmp_path):
    db = CloudDatabase(URL, require_runtime=True)
    try:
        with pytest.raises(RuntimeError, match='Restricted runtime'):
            with db.engine.connect():
                pass
    finally:
        db.engine.dispose()
    from scripts.verify_phase2 import Verifier
    runtime = runtime_database()
    try:
        verifier = Verifier(None, None, runtime.engine, tmp_path / 'unused.json')
        verifier.audit_database()
    finally:
        runtime.engine.dispose()


def test_feature_owner_foreign_key_and_cascade(postgres):
    """The database itself prevents a report linking to someone else's resume."""
    runtime = runtime_database()
    owner, other = uuid4(), uuid4()
    try:
        resume = runtime.create(Resume, owner, object_path=f'{owner}/{uuid4()}.pdf', state='ready', metadata_json={})
        with pytest.raises(DBAPIError) as exc:
            runtime.create(Analysis, other, resume_id=resume.id, kind='analysis', summary_json={})
        assert exc.value.orig.sqlstate == '23503'
        report = runtime.create(Analysis, owner, resume_id=resume.id, kind='analysis', summary_json={})
        match = runtime.create(Analysis, owner, resume_id=resume.id, kind='match', summary_json={})
        with runtime.for_user(other).sessions() as session:
            assert session.scalars(text('SELECT id FROM public.cloud_analyses WHERE id=:id'), {'id':report.id}).all() == []
        with runtime.for_user(owner).sessions.begin() as session:
            session.delete(runtime.owned(session, Resume, owner, resume.id))
        with runtime.for_user(owner).sessions() as session:
            assert session.scalars(text('SELECT id FROM public.cloud_analyses WHERE id IN (:a,:b)'), {'a':report.id,'b':match.id}).all() == []
    finally:
        runtime.engine.dispose()


def test_existing_summary_rows_remain_supported(postgres):
    """A fresh head and the additive upgrade both preserve old summary payloads."""
    runtime = runtime_database()
    owner = uuid4()
    try:
        row = runtime.create(Analysis, owner, summary_json={'ats_score':42})
        found = runtime.list(Analysis,owner)[0]
        assert found.resume_id is None and found.kind == 'analysis'
        assert found.summary_json == {'ats_score':42}
        runtime.delete(Analysis,owner,row.id)
    finally:
        runtime.engine.dispose()


def test_phase4_features_through_nobypass_runtime(postgres, pdf_bytes):
    from fastapi.testclient import TestClient
    from backend.api import create_app
    from backend.api_v1.settings import APISettings
    from backend.cloud.auth import current_user, Identity
    from tests.api.test_features import Storage, DATA, JD
    runtime = runtime_database()
    owner, other = Identity(uuid4()), Identity(uuid4())
    app = create_app(APISettings())
    app.state.cloud_db, app.state.private_storage = runtime, Storage()
    app.dependency_overrides[current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            uploaded=client.post('/api/v1/resumes',files={'file':('synthetic.pdf',pdf_bytes)})
            assert uploaded.status_code==201
            id=uploaded.json()['id']
            result=client.post(f'/api/v1/resumes/{id}/analyses',json={})
            assert result.status_code==201,result.text
            report_id=result.json()['id']
            result=client.post(f'/api/v1/resumes/{id}/matches',json={'job_description':JD})
            assert result.status_code==201,result.text
            match_id=result.json()['id']
            result=client.post('/api/v1/builder/drafts',json=DATA)
            assert result.status_code==201,result.text
            draft_id=result.json()['id']
            app.dependency_overrides[current_user]=lambda:other
            assert client.get('/api/v1/analyses').json()==[]
            assert client.get('/api/v1/builder/drafts').json()==[]
            assert client.get('/api/v1/history').json()==[]
            for path in [f'/analysis-reports/{report_id}',f'/job-matches/{match_id}',f'/builder/drafts/{draft_id}']:
                assert client.get('/api/v1'+path).status_code==404
            assert client.post(f'/api/v1/builder/drafts/{draft_id}/exports/pdf').status_code==404
            app.dependency_overrides[current_user]=lambda:owner
            assert client.post(f'/api/v1/builder/drafts/{draft_id}/exports/docx').status_code==200
            assert client.delete(f'/api/v1/resumes/{id}').status_code==204
            assert client.get(f'/api/v1/analysis-reports/{report_id}').status_code==404
            assert client.get(f'/api/v1/job-matches/{match_id}').status_code==404
            assert client.delete(f'/api/v1/builder/drafts/{draft_id}').status_code==204
    finally:
        runtime.engine.dispose()


def test_phase5_verifier_feature_cleanup_on_real_rls(postgres,pdf_bytes,tmp_path,monkeypatch):
    """Exercise opt-in verifier feature writes/cleanup on a disposable DB only."""
    import httpx
    from fastapi import Request
    from fastapi.testclient import TestClient
    from backend.api import create_app
    from backend.api_v1.settings import APISettings
    from backend.cloud.auth import current_user,Identity
    from scripts.verify_phase5 import Phase5Verifier
    from scripts.verify_phase2 import Verifier,Settings
    from tests.api.test_features import Storage
    runtime=runtime_database();a,b=Identity(uuid4()),Identity(uuid4())
    app=create_app(APISettings());storage=Storage();app.state.cloud_db=runtime;app.state.private_storage=storage
    def identity(request:Request):return a if request.headers.get('authorization')=='Bearer synthetic-A' else b
    app.dependency_overrides[current_user]=identity
    cfg=Settings('http://testserver','https://synthetic.example.invalid','sb_publishable_synthetic','sb_secret_synthetic','unused','resumes',('a','b'),('a','b'))
    with TestClient(app) as client:
        class Adapter:
            def request(self,method,url,**kwargs):
                if url.startswith(cfg.api):return client.request(method,url.removeprefix(cfg.api),**kwargs)
                return httpx.Response(200,json=[])
        verifier=Phase5Verifier(cfg,Adapter(),runtime.engine,tmp_path/'journal.json')
        verifier.users=[{'id':str(a.id),'token':'synthetic-A'},{'id':str(b.id),'token':'synthetic-B'}]
        monkeypatch.setenv('PHASE5_MIGRATION_AUDIT_DATABASE_URL',URL)
        verifier.audit_database()
        assert client.get('/api/ready').status_code==200
        for user in verifier.users:
            owner=user['id'];verifier.baseline[owner]=set();verifier.draft_baseline[owner]=set();verifier.drafts[owner]=set();verifier.feature_ids[owner]=set()
            result=verifier.api('POST','/api/v1/resumes',user,files={'file':('synthetic.pdf',pdf_bytes)})
            assert result.status_code==201
            id=result.json()['id'];verifier.created[owner]={id}
            verifier.paths[id]=verifier.rows(user,'cloud_resumes')[0]['object_path']
        monkeypatch.setattr(Verifier,'lifecycle',lambda self:None)
        verifier.lifecycle()
        assert verifier.cleanup()
        for user in verifier.users:
            assert verifier.draft_rows(user)==[]
            assert verifier.rows(user,'cloud_resumes')==[]
            assert verifier.rows(user,'cloud_history')==[]
        assert not verifier.journal.exists()
