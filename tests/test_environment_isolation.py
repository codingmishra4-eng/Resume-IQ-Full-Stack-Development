"""Subprocess regressions never inspect or modify the developer's private .env."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from scripts.test_environment import disposable_url, isolated_environment

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = {
    'CLOUD_ENABLED':'true', 'CLOUD_AI_ENABLED':'true', 'API_PUBLIC_MODE':'true',
    'API_LEGACY_UPLOAD_ENABLED':'false', 'CLOUD_DATABASE_URL':'postgresql+psycopg://synthetic:synthetic@127.0.0.1/live_forbidden',
    'CLOUD_MIGRATION_DATABASE_URL':'postgresql+psycopg://synthetic:synthetic@127.0.0.1/admin_forbidden',
    'PHASE5_MIGRATION_AUDIT_DATABASE_URL':'postgresql+psycopg://synthetic@127.0.0.1/audit_forbidden',
    'SUPABASE_URL':'https://synthetic.supabase.co',
    'SUPABASE_JWT_ISSUER':'https://synthetic.supabase.co/auth/v1',
    'SUPABASE_JWKS_URL':'https://synthetic.supabase.co/auth/v1/.well-known/jwks.json',
    'SUPABASE_JWT_AUDIENCE':'authenticated','SUPABASE_JWT_ALGORITHM':'ES256',
    'SUPABASE_STORAGE_BUCKET':'resumes','SUPABASE_SECRET_KEY':'sb_secret_synthetic_never_real',
    'OPENAI_API_KEY':'sk-synthetic-never-real', 'PGPASSWORD':'synthetic-not-real',
}


@pytest.mark.parametrize('scenario',['no-file','dotenv','inherited'])
def test_isolation_precedes_application_collection(tmp_path, scenario):
    for directory in ('backend','database','resume_builder','scripts'):
        shutil.copytree(ROOT/directory,tmp_path/directory,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT/'config.py',tmp_path/'config.py')
    (tmp_path/'tests').mkdir()
    shutil.copy2(ROOT/'tests/conftest.py',tmp_path/'tests/conftest.py')
    (tmp_path/'pytest.ini').write_text('[pytest]\npythonpath = .\n')
    original=''.join(f'{key}={value}\n' for key,value in SYNTHETIC.items())
    if scenario=='dotenv':(tmp_path/'.env').write_text(original)
    (tmp_path/'tests/test_probe.py').write_text('''
import os
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.api_v1.settings import APISettings
from backend.cloud.settings import CloudSettings
import config

def test_clean_collection_and_public_guard():
    assert os.environ['PYTHON_DOTENV_DISABLED']=='1'
    assert CloudSettings.from_env() is None
    assert config.AIConfig().api_key is None
    assert 'CLOUD_MIGRATION_DATABASE_URL' not in os.environ
    assert 'PHASE5_MIGRATION_AUDIT_DATABASE_URL' not in os.environ
    assert 'PGPASSWORD' not in os.environ
    with TestClient(create_app(APISettings(public_mode=True,legacy_upload_enabled=False))) as client:
        assert client.get('/api/me').status_code==401
''')
    environment=isolated_environment(os.environ)
    environment.pop('TEST_POSTGRES_URL',None)
    environment.pop('RESUMEIQ_TEST_POSTGRES_DISPOSABLE',None)
    # Prove bootstrap works even when process settings or a file provide a
    # complete, structurally valid cloud configuration before pytest starts.
    if scenario=='inherited':environment.update(SYNTHETIC)
    result=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=tmp_path,env=environment,capture_output=True,timeout=60)
    assert result.returncode==0, 'Isolated synthetic pytest subprocess failed; output suppressed.'
    if scenario=='dotenv':assert (tmp_path/'.env').read_text()==original


def test_live_network_and_database_checkouts_are_blocked():
    import httpx
    import urllib.request
    with pytest.raises(RuntimeError,match='Network access blocked'):
        httpx.get('https://synthetic.invalid')
    with pytest.raises(RuntimeError,match='Network access blocked'):
        urllib.request.urlopen('https://synthetic.invalid')
    engine=create_engine('postgresql+psycopg://synthetic@127.0.0.1/not_the_disposable_database')
    try:
        with pytest.raises(RuntimeError,match='Network database access blocked'):
            engine.connect()
    finally:engine.dispose()


def test_disposable_database_requires_local_explicit_acknowledgement():
    url='postgresql+psycopg://synthetic@127.0.0.1/resumeiq_test'
    assert disposable_url({}) is None
    with pytest.raises(ValueError):disposable_url({'TEST_POSTGRES_URL':url})
    assert disposable_url({'TEST_POSTGRES_URL':url,'RESUMEIQ_TEST_POSTGRES_DISPOSABLE':'true'}) is not None
    with pytest.raises(ValueError):
        disposable_url({'TEST_POSTGRES_URL':'postgresql+psycopg://synthetic@project.supabase.co/live','RESUMEIQ_TEST_POSTGRES_DISPOSABLE':'true'})


def test_environment_copy_preserves_explicit_disposable_opt_in():
    original=SYNTHETIC | {'TEST_POSTGRES_URL':'postgresql+psycopg://synthetic@127.0.0.1/test','RESUMEIQ_TEST_POSTGRES_DISPOSABLE':'true'}
    clean=isolated_environment(original)
    assert original['CLOUD_ENABLED']=='true'
    assert clean['CLOUD_ENABLED']=='false' and clean['TEST_POSTGRES_URL']==original['TEST_POSTGRES_URL']
    assert all(key not in clean for key in ('CLOUD_MIGRATION_DATABASE_URL','SUPABASE_SECRET_KEY','OPENAI_API_KEY','PGPASSWORD'))
