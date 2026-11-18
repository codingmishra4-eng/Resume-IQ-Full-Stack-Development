"""No credentials or network: staging CLI is exercised with generated settings."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import text
from scripts import staging_preflight as audit
from scripts import verify_phase5 as live
from scripts.verify_phase2 import VerificationError

REF='a'*20
OTHER='b'*20


def values():
    return {'SUPABASE_URL':f'https://{REF}.supabase.co',
            'CLOUD_DATABASE_URL':f'postgresql+psycopg://resumeiq_runtime:synthetic-password@db.{REF}.supabase.co/postgres?sslmode=require',
            'PHASE5_MIGRATION_AUDIT_DATABASE_URL':f'postgresql+psycopg://postgres:synthetic-password@db.{REF}.supabase.co/postgres?sslmode=require'}


def write_settings(tmp_path, data=None):
    path=tmp_path/'staging.env'
    path.write_text(''.join(f'{key}={value}\n' for key,value in (data or values()).items()))
    return path


def test_password_free_readonly_ignores_inherited_settings(tmp_path,monkeypatch,capsys):
    path=write_settings(tmp_path);original=path.read_bytes();calls=[]
    monkeypatch.setenv('SUPABASE_URL',f'https://{OTHER}.supabase.co')
    monkeypatch.setenv('CLOUD_MIGRATION_DATABASE_URL','not-a-staging-connection')
    monkeypatch.setattr(live.Phase5Verifier,'__init__',lambda *a,**k:pytest.fail('Live verifier constructed'))
    monkeypatch.setattr('scripts.verify_phase2.getpass',lambda *a:pytest.fail('Password requested'))
    monkeypatch.setattr(audit.StagingReadOnly,'run',lambda self:calls.append(self.target))
    assert live.main(['--read-only','--env-file',str(path),'--expected-project-ref',REF])==0
    assert calls[0].runtime_url.host==f'db.{REF}.supabase.co'
    assert path.read_bytes()==original
    output=capsys.readouterr().out
    assert 'PASS:' in output and 'PENDING:' in output
    assert 'synthetic-password' not in output and REF not in output


def test_requested_windows_private_path_only_when_opted_in(tmp_path,monkeypatch):
    private=tmp_path/'ResumeIQ-Private';private.mkdir();path=write_settings(private)
    monkeypatch.setenv('USERPROFILE',str(tmp_path))
    observed=[]
    monkeypatch.setattr(audit.StagingReadOnly,'run',lambda self:observed.append(self.target))
    assert live.main([])==2
    assert not observed
    assert live.main(['--read-only','--expected-project-ref',REF])==0
    assert len(observed)==1 and path.exists()


@pytest.mark.parametrize('change',[
    {'SUPABASE_URL':f'https://{OTHER}.supabase.co'},
    {'STAGING_PROJECT_REF':OTHER},
    {'SUPABASE_JWKS_URL':f'https://{OTHER}.supabase.co/auth/v1/.well-known/jwks.json'},
    {'CLOUD_DATABASE_URL':f'postgresql+psycopg://resumeiq_runtime:synthetic@db.{OTHER}.supabase.co/postgres?sslmode=require'},
    {'CLOUD_DATABASE_URL':f'postgresql+psycopg://postgres:synthetic@db.{REF}.supabase.co/postgres?sslmode=require'},
    {'PHASE5_MIGRATION_AUDIT_DATABASE_URL':f'postgresql+psycopg://postgres:synthetic@db.{OTHER}.supabase.co/postgres?sslmode=require'},
    {'CLOUD_DATABASE_URL':f'postgresql+psycopg://resumeiq_runtime:synthetic@db.{REF}.supabase.co/postgres'},
    {'CLOUD_DATABASE_URL':f'postgresql+psycopg://resumeiq_runtime:synthetic@db.{REF}.supabase.co/postgres?sslmode=require&host=forbidden.invalid'},
    {'CLOUD_MIGRATION_DATABASE_URL':f'postgresql+psycopg://postgres:synthetic@db.{OTHER}.supabase.co/postgres?sslmode=require'},
    {'CLOUD_DATABASE_URL':'${CLOUD_DATABASE_URL}'},
],ids=['origin','project-pin','jwks','runtime-project','runtime-admin','audit-project','tls','routing-override','unused-admin-mismatch','interpolation'])
def test_mismatch_fails_before_any_connection(tmp_path,monkeypatch,change,capsys):
    path=write_settings(tmp_path,values()|change)
    monkeypatch.setattr(audit,'engine_for',lambda *a:pytest.fail('Connection attempted'))
    assert live.main(['--read-only','--env-file',str(path),'--expected-project-ref',REF])==1
    assert 'synthetic' not in capsys.readouterr().out


def test_independent_project_pin_required_before_file_read(monkeypatch):
    monkeypatch.setattr(audit,'dotenv_values',lambda *a,**k:pytest.fail('File read before identity pin'))
    with pytest.raises(VerificationError):audit.load_target(Path('never-read'),None)


def test_session_pooler_bound_to_project_and_role(tmp_path):
    data=values()
    host='aws-0-eu-west-1.pooler.supabase.com'
    data['CLOUD_DATABASE_URL']=f'postgresql+psycopg://resumeiq_runtime.{REF}:synthetic@{host}:5432/postgres?sslmode=require'
    data['PHASE5_MIGRATION_AUDIT_DATABASE_URL']=f'postgresql+psycopg://postgres.{REF}:synthetic@{host}:5432/postgres?sslmode=require'
    assert audit.load_target(write_settings(tmp_path,data),REF).runtime_url.host==host
    data['CLOUD_DATABASE_URL']=data['CLOUD_DATABASE_URL'].replace('runtime.'+REF,'runtime.'+OTHER)
    with pytest.raises(VerificationError):audit.load_target(write_settings(tmp_path,data),REF)


@pytest.mark.parametrize('sql',['INSERT INTO x VALUES (1)','UPDATE x SET n=1','DELETE FROM x','CREATE TABLE x (n int)',
    'SELECT 1; DELETE FROM x',"SELECT set_config('default_transaction_read_only','off',false)"],
    ids=['insert','update','delete','ddl','multi-statement','readonly-disable'])
def test_readonly_surface_rejects_writes(sql):
    underlying=SimpleNamespace(execute=lambda *a:pytest.fail('Unsafe SQL reached driver'))
    with pytest.raises(VerificationError):audit.ReadOnlyConnection(underlying).execute(text(sql))


class Result:
    def __init__(self,one=None,rows=None):self.value=one;self.rows=rows or []
    def mappings(self):return self
    def scalars(self):return self
    def one(self):return self.value
    def one_or_none(self):return self.value
    def first(self):return self.value
    def scalar(self):return self.value
    def all(self):return self.rows


class Connection:
    def __init__(self,events,fail=False):self.events=events;self.fail=fail
    def begin(self):self.events.append('begin');return SimpleNamespace(rollback=lambda:self.events.append('rollback'))
    def exec_driver_sql(self,sql):self.events.append(sql)
    def execute(self,query,parameters):
        sql=str(query);self.events.append(sql)
        assert 'SET TRANSACTION READ ONLY' in self.events
        if self.fail:raise RuntimeError('synthetic-secret-driver-error')
        if 'AS name' in sql:return Result({'name':'resumeiq_runtime','privileged':False})
        if 'relrowsecurity' in sql:return Result((True,True))
        if 'SELECT rolname' in sql:return Result(rows=[{'access':False,'member':False}]*3)
        if 'pg_policy' in sql:
            expression="current_user = 'resumeiq_runtime' AND user_id = NULLIF(current_setting('resumeiq.user_id', true), '')::uuid"
            return Result(rows=[{'polname':'owner_access','polcmd':'*','polroles':[0],'polpermissive':True,'using_expr':expression,'check_expr':expression}])
        if 'version_num' in sql:return Result(rows=['0002_feature_links'])
        if 'pg_constraint' in sql:return Result(1)
        if parameters.get('operation'):return Result(True)
        return Result(False if 'SELECT id ' not in sql else None)


class Engine:
    def __init__(self,fail=False):self.events=[];self.connection=Connection(self.events,fail);self.disposed=False
    @contextmanager
    def connect(self):yield self.connection
    def dispose(self):self.disposed=True


def test_full_catalog_reuse_readonly_rollback_and_no_passwords(tmp_path,monkeypatch,capsys):
    engines=[]
    def factory(url):
        engine=Engine();engines.append(engine);return engine
    monkeypatch.setattr(audit,'engine_for',factory)
    path=write_settings(tmp_path)
    assert live.main(['--read-only','--env-file',str(path),'--expected-project-ref',REF])==0
    assert len(engines)==2 and all(engine.disposed for engine in engines)
    assert all('rollback' in engine.events for engine in engines)
    assert all('SET TRANSACTION READ ONLY' in engine.events for engine in engines)
    output=capsys.readouterr().out
    assert '0002_feature_links' in output and 'synthetic-password' not in output


def test_driver_error_redacted_and_transaction_rolled_back(tmp_path,monkeypatch,capsys):
    engine=Engine(fail=True)
    monkeypatch.setattr(audit,'engine_for',lambda url:engine)
    assert live.main(['--read-only','--env-file',str(write_settings(tmp_path)),'--expected-project-ref',REF])==1
    assert engine.disposed and engine.events[-1]=='rollback'
    output=capsys.readouterr().out
    assert 'FAIL:' in output and 'synthetic-secret' not in output


def test_write_mode_requires_independent_api_pin(tmp_path,monkeypatch):
    monkeypatch.setattr(live,'create_engine',lambda *a,**k:pytest.fail('Live operation entered'))
    path=write_settings(tmp_path,values()|{'PHASE2_API_URL':'https://staging-api.example.invalid'})
    assert live.main(['--allow-live-writes','--env-file',str(path),'--expected-project-ref',REF])==1
    assert live.main(['--allow-live-writes','--env-file',str(path),'--expected-project-ref',REF,
                      '--expected-api-origin','https://different.example.invalid'])==1


def test_modes_mutually_exclusive_before_file_read(monkeypatch):
    monkeypatch.setattr(audit,'load_target',lambda *a:pytest.fail('File accessed'))
    assert live.main(['--read-only','--allow-live-writes'])==1


def test_readonly_ignores_even_unusable_test_passwords(tmp_path,monkeypatch):
    path=write_settings(tmp_path,values()|{'PHASE2_TEST_USER_A_PASSWORD':'${UNUSED}',
        'PHASE2_TEST_USER_B_PASSWORD':'','PHASE2_TEST_USER_A_EMAIL':'not-an-email'})
    monkeypatch.setattr(audit.StagingReadOnly,'run',lambda self:None)
    assert live.main(['--read-only','--env-file',str(path),'--expected-project-ref',REF])==0


def test_actual_write_mode_reuses_phase5_verifier_and_file_settings(tmp_path,monkeypatch):
    data=values()|{'PHASE2_API_URL':'https://staging-api.example.invalid','SUPABASE_PUBLISHABLE_KEY':'sb_publishable_synthetic',
        'SUPABASE_SECRET_KEY':'sb_secret_synthetic','SUPABASE_STORAGE_BUCKET':'resumes',
        'PHASE2_TEST_USER_A_EMAIL':'a@example.invalid','PHASE2_TEST_USER_B_EMAIL':'b@example.invalid',
        'PHASE2_TEST_USER_A_PASSWORD':'synthetic-a','PHASE2_TEST_USER_B_PASSWORD':'synthetic-b'}
    path=write_settings(tmp_path,data);calls=[];engine=Engine()
    monkeypatch.setattr(live,'create_engine',lambda *a,**k:engine)
    class FakeVerifier:
        def __init__(self,settings,client,db,journal,**kwargs):
            assert settings.passwords==('synthetic-a','synthetic-b')
            assert settings.api==data['PHASE2_API_URL']
            assert kwargs['migration_audit_url']==data['PHASE5_MIGRATION_AUDIT_DATABASE_URL']
        def run(self):calls.append('live');return 0
    monkeypatch.setattr(live,'Phase5Verifier',FakeVerifier)
    assert live.main(['--allow-live-writes','--env-file',str(path),'--expected-project-ref',REF,
                      '--expected-api-origin',data['PHASE2_API_URL']])==0
    assert calls==['live'] and engine.disposed


def test_configured_https_cors_does_not_shadow_origin_validator(tmp_path,monkeypatch,capsys):
    data=values()|{'CLOUD_ENABLED':'true','API_PUBLIC_MODE':'true',
        'API_LEGACY_UPLOAD_ENABLED':'false',
        'API_ALLOWED_ORIGINS':'https://staging.example.invalid,https://preview.example.invalid'}
    path=write_settings(tmp_path,data)
    monkeypatch.setattr(audit.StagingReadOnly,'run',lambda self:None)
    assert live.main(['--read-only','--env-file',str(path),'--expected-project-ref',REF])==0
    assert 'PASS: Render public-mode flags and exact HTTPS CORS configuration' in capsys.readouterr().out
    data['API_ALLOWED_ORIGINS']='http://unsafe.example.invalid'
    assert live.main(['--read-only','--env-file',str(write_settings(tmp_path,data)),'--expected-project-ref',REF])==1
