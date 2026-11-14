"""Opt-in REAL PostgreSQL migration/RLS checks. Dedicated disposable database only."""
import os
import subprocess
import sys
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text, inspect
from backend.cloud.database import CloudDatabase
from backend.cloud.models import SavedResume

URL = os.getenv('TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not URL, reason='TEST_POSTGRES_URL not set; requires disposable PostgreSQL')


def test_postgres_migrations_crud_rls():
    env = os.environ | {'CLOUD_DATABASE_URL': URL}
    def migrate(*args):
        subprocess.run([sys.executable, '-m', 'alembic', *args], env=env, check=True, capture_output=True)
    migrate('upgrade', 'head')
    db = CloudDatabase(URL)
    owner, other = uuid4(), uuid4()
    row = db.create(SavedResume, owner, data_json={'template': 'synthetic'})
    assert db.list(SavedResume, other) == []
    with pytest.raises(Exception):
        db.update(SavedResume, other, row.id, data_json={})
    db.update(SavedResume, owner, row.id, data_json={'updated': True})
    with db.engine.begin() as conn:
        conn.execute(text('CREATE ROLE phase2_rls_test NOLOGIN'))
        conn.execute(text('GRANT USAGE ON SCHEMA public TO phase2_rls_test'))
        conn.execute(text('GRANT SELECT, INSERT, UPDATE, DELETE ON cloud_saved_resumes TO phase2_rls_test'))
        conn.execute(text('SET LOCAL ROLE phase2_rls_test'))
        assert conn.execute(text('SELECT id FROM cloud_saved_resumes')).all() == []
        conn.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {'user_id': str(owner)})
        assert conn.execute(text('SELECT id FROM cloud_saved_resumes')).scalar() == row.id
        conn.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {'user_id': str(other)})
        assert conn.execute(text('SELECT id FROM cloud_saved_resumes')).all() == []
        with pytest.raises(Exception):
            conn.execute(text('INSERT INTO cloud_saved_resumes (id,user_id,created_at,updated_at,data_json) VALUES (:id,:owner,now(),now(),\'{}\')'), {'id': uuid4(), 'owner': owner})
        # Failed SQL aborts this transaction and rolls back temporary role creation.
    # A second transaction cannot mutate a row while ownership is being checked.
    from sqlalchemy.exc import OperationalError
    with db.sessions.begin() as first:
        db.owned(first, SavedResume, owner, row.id)
        with db.sessions.begin() as second:
            second.execute(text("SET LOCAL lock_timeout = '50ms'"))
            with pytest.raises(OperationalError):
                db.owned(second, SavedResume, owner, row.id)
    db.delete(SavedResume, owner, row.id)
    migrate('downgrade', 'base')
    assert 'cloud_saved_resumes' not in inspect(db.engine).get_table_names()
    migrate('upgrade', 'head')
    db.engine.dispose()
