"""Test-only configuration isolation. Never imported by production entry points."""
import os

PREFIXES = ('CLOUD_', 'SUPABASE_', 'OPENAI_', 'API_', 'PHASE2_', 'PHASE5_', 'NEXT_PUBLIC_', 'PG')
NAMES = {'DATABASE_URL', 'MAX_UPLOAD_MB', 'GENERATED_DIR', 'APP_PORT', 'PORT',
         'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PGSERVICE',
         'PGSERVICEFILE', 'PGPASSFILE', 'PGOPTIONS'}


def isolated_environment(source):
    """Copy, never log or modify the caller's private files/settings."""
    result = {key: value for key, value in source.items()
              if key not in NAMES and not key.startswith(PREFIXES)}
    result.update(PYTHON_DOTENV_DISABLED='1', CLOUD_ENABLED='false', CLOUD_AI_ENABLED='false',
                  API_PUBLIC_MODE='false', API_LEGACY_UPLOAD_ENABLED='true')
    return result


def disposable_url(environment):
    """Explicit local-only destructive-test opt-in; never load a URL from dotenv."""
    value = environment.get('TEST_POSTGRES_URL')
    if not value:
        return None
    from sqlalchemy.engine import make_url
    try:
        url = make_url(value)
        valid = (url.drivername == 'postgresql+psycopg' and url.host in {'localhost','127.0.0.1','::1'}
                 and bool(url.database) and not url.query
                 and environment.get('RESUMEIQ_TEST_POSTGRES_DISPOSABLE') == 'true')
    except Exception:
        valid = False
    if not valid:
        raise ValueError('Disposable tests require an explicit local PostgreSQL URL and RESUMEIQ_TEST_POSTGRES_DISPOSABLE=true; no connection attempted.')
    return url


def install():
    """Run before application imports; inherited settings cannot affect collection."""
    clean = isolated_environment(os.environ)
    allowed = disposable_url(clean)
    for key in tuple(os.environ):
        if key not in clean:
            del os.environ[key]
    os.environ.update(clean)

    # libpq connects in native code, bypassing Python socket guards. Stop any
    # SQLAlchemy network DB checkout except the explicitly acknowledged test URL.
    from sqlalchemy.engine import Engine
    original = Engine.raw_connection
    def raw_connection(engine):
        if engine.url.get_backend_name() != 'sqlite' and engine.url != allowed:
            raise RuntimeError('Network database access blocked by test isolation.')
        return original(engine)
    Engine.raw_connection = raw_connection
