"""Staging-only target validation and read-only audits; no implicit dotenv lookup.

This module never imports application config, creates accounts or mutates files.
Only the CLI's explicit read-only/live opt-in can load an operator-selected file.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
import re
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from dotenv import dotenv_values
from scripts.verify_phase2 import Verifier, TABLES, require, origin


@dataclass(repr=False, frozen=True)
class StagingTarget:
    values: dict = field(repr=False)
    runtime_url: object = field(repr=False)
    audit_url: object = field(repr=False)


def load_target(path, expected_ref):
    # The pin is supplied independently from Supabase URL/credentials, copied by
    # the operator from the STAGING dashboard. Never infer it from the target URL.
    require(bool(re.fullmatch(r'[a-z0-9]{20}', expected_ref or '')), 'A valid independent staging project reference is required.')
    values = dict(dotenv_values(Path(path), interpolate=False, encoding='utf-8-sig'))
    require(bool(values), 'The explicit staging configuration file is missing or empty.')
    literal_keys = ('STAGING_PROJECT_REF','SUPABASE_URL','SUPABASE_JWT_ISSUER','SUPABASE_JWKS_URL',
                    'SUPABASE_JWT_ALGORITHM','SUPABASE_JWT_AUDIENCE','NEXT_PUBLIC_SUPABASE_URL',
                    'CLOUD_DATABASE_URL','PHASE5_MIGRATION_AUDIT_DATABASE_URL','CLOUD_MIGRATION_DATABASE_URL')
    require(all(not values.get(key) or '${' not in values[key] for key in literal_keys),
            'Staging target settings must be explicit literals without environment interpolation.')
    require(values.get('STAGING_PROJECT_REF', expected_ref) == expected_ref, 'Staging project identity mismatch.')
    supabase_origin = 'https://' + expected_ref + '.supabase.co'
    require(values.get('SUPABASE_URL') == supabase_origin, 'Staging Supabase origin mismatch.')
    for name, expected in (('SUPABASE_JWT_ISSUER', supabase_origin+'/auth/v1'),
                           ('SUPABASE_JWKS_URL', supabase_origin+'/auth/v1/.well-known/jwks.json'),
                           ('NEXT_PUBLIC_SUPABASE_URL', supabase_origin)):
        require(not values.get(name) or values[name] == expected, 'Staging authentication project mismatch.')
    require(not values.get('SUPABASE_JWT_ALGORITHM') or values['SUPABASE_JWT_ALGORITHM']=='ES256', 'ES256 staging authentication configuration required.')
    require(not values.get('SUPABASE_JWT_AUDIENCE') or values['SUPABASE_JWT_AUDIENCE']=='authenticated', 'Invalid staging JWT audience.')
    for flag in ('CLOUD_ENABLED','CLOUD_AI_ENABLED','API_PUBLIC_MODE','API_LEGACY_UPLOAD_ENABLED'):
        require(not values.get(flag) or values[flag] in {'true','false'}, 'Invalid staging environment flag.')
    if values.get('API_PUBLIC_MODE') == 'true':
        require(values.get('API_LEGACY_UPLOAD_ENABLED') == 'false', 'Public API configuration must disable legacy uploads.')
    for item in filter(None,(part.strip() for part in values.get('API_ALLOWED_ORIGINS','').split(','))):
        require('*' not in item and not any(character.isspace() for character in item), 'CORS requires exact HTTPS origins.')
        origin(item)
    runtime = database_target(values.get('CLOUD_DATABASE_URL'), expected_ref, runtime=True)
    audit_value = values.get('PHASE5_MIGRATION_AUDIT_DATABASE_URL') or values.get('CLOUD_MIGRATION_DATABASE_URL')
    audit = database_target(audit_value, expected_ref, runtime=False)
    require(runtime.database == audit.database, 'Staging runtime/audit database mismatch.')
    # Validate *every* configured DB endpoint, even an unused migration fallback.
    if values.get('CLOUD_MIGRATION_DATABASE_URL'):
        migration = database_target(values['CLOUD_MIGRATION_DATABASE_URL'], expected_ref, runtime=False)
        require(migration.database == runtime.database, 'Staging migration database mismatch.')
    return StagingTarget(values, runtime, audit)


def database_target(value, ref, runtime):
    require(bool(value), 'Required staging database connection is missing.')
    try:
        url = make_url(value)
        direct = url.host == 'db.' + ref + '.supabase.co'
        pooler = bool(re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)*\.pooler\.supabase\.com', url.host or ''))
        role = url.username or ''
        if pooler:
            require(role.endswith('.'+ref), 'Staging pooler project mismatch.')
            role = role[:-(len(ref)+1)]
        require(direct or pooler, 'Database endpoint is not bound to the expected staging project.')
        require(url.drivername == 'postgresql+psycopg' and url.database == 'postgres'
                and url.port in (None,5432,6543) and bool(url.password), 'Invalid staging database connection.')
        require(role == 'resumeiq_runtime' if runtime else bool(re.fullmatch(r'[a-z_][a-z0-9_]*',role)), 'Invalid staging database role configuration.')
        require(set(url.query) <= {'sslmode','sslrootcert','channel_binding'}, 'Database routing/startup overrides are not allowed.')
        require(url.query.get('sslmode') in {'require','verify-ca','verify-full'}, 'Explicit database TLS is required.')
        require(url.query.get('channel_binding','prefer') in {'disable','prefer','require'}, 'Invalid database TLS configuration.')
        return url
    except Exception:
        # SQLAlchemy parse errors can embed passwords/URLs; never propagate them.
        from scripts.verify_phase2 import VerificationError
        raise VerificationError('Staging database identity, role or TLS validation failed.') from None


class ReadOnlyConnection:
    """Narrow SELECT-only surface in addition to server-enforced READ ONLY."""
    def __init__(self, connection):
        self._connection = connection

    def execute(self, query, parameters=None):
        sql = ' '.join(str(query).split())
        require(sql.upper().startswith('SELECT ') and ';' not in sql, 'Non-read-only audit statement blocked.')
        if 'set_config' in sql.lower():
            require(sql == "SELECT set_config('resumeiq.user_id', '', true)", 'Audit session mutation blocked.')
        return self._connection.execute(query, parameters or {})

    def scalar(self, query, parameters=None):
        return self.execute(query, parameters).scalar()


class ReadOnlyEngine:
    def __init__(self, engine):
        self._engine = engine

    @contextmanager
    def begin(self):
        with self._engine.connect() as connection:
            # Set before any audit SELECT. Roll back even a successful audit.
            transaction = connection.begin()
            try:
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                connection.exec_driver_sql("SET LOCAL statement_timeout = '5000ms'")
                connection.exec_driver_sql("SET LOCAL lock_timeout = '2000ms'")
                yield ReadOnlyConnection(connection)
            finally:
                transaction.rollback()

    connect = begin


def engine_for(url):
    return create_engine(url, hide_parameters=True, pool_pre_ping=False,
                         connect_args={'connect_timeout':5}, pool_size=1, max_overflow=0)


def policy_expression(value):
    return re.sub(r'::(?:text|name|uuid)\b|[\s()]', '', value.casefold())


class StagingReadOnly:
    """Reuse existing catalog audit, with no login/HTTP/cleanup/write capability."""
    def __init__(self, target):
        self.target = target

    def run(self):
        engines = []
        try:
            runtime = engine_for(self.target.runtime_url); engines.append(runtime)
            self.engine = ReadOnlyEngine(runtime)
            # Existing Phase 2 role, parent memberships, schema CREATE, ACL,
            # enabled/forced RLS and unscoped-row-denial assertions are retained.
            Verifier.audit_database(self)
            print('PASS: restricted runtime, table ACLs and enabled/forced RLS')
            with self.engine.begin() as connection:
                for table in TABLES:
                    for operation in ('SELECT','INSERT','UPDATE','DELETE'):
                        require(connection.scalar(text('SELECT has_table_privilege(current_user,:table,:operation)'),
                            {'table':'public.'+table,'operation':operation}), 'Runtime lacks a required application privilege.')
                    require(not connection.scalar(text("SELECT has_table_privilege(current_user,:table,'TRUNCATE,REFERENCES,TRIGGER')"),
                        {'table':'public.'+table}), 'Runtime has excessive application privileges.')
                    policies = connection.execute(text("""SELECT polname,polcmd,polroles,polpermissive,
                        pg_get_expr(polqual,polrelid) AS using_expr,pg_get_expr(polwithcheck,polrelid) AS check_expr
                        FROM pg_policy WHERE polrelid=to_regclass(:table)"""), {'table':'public.'+table}).mappings().all()
                    expected = policy_expression("current_user = 'resumeiq_runtime' AND user_id = NULLIF(current_setting('resumeiq.user_id', true), '')::uuid")
                    require(len(policies)==1, 'Unexpected application RLS policy set.')
                    policy = policies[0]
                    require(policy['polname']=='owner_access' and policy['polcmd']=='*'
                        and list(policy['polroles'])==[0] and policy['polpermissive']
                        and policy_expression(policy['using_expr'] or '')==expected
                        and policy_expression(policy['check_expr'] or '')==expected, 'Unexpected ownership policy definition.')
                require(connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conrelid='public.cloud_analyses'::regclass AND conname='fk_cloud_analysis_resume_owner'")) == 1,
                        'Phase 4 ownership constraint is missing.')
            print('PASS: runtime CRUD limits and exact ownership policies')
            audit = engine_for(self.target.audit_url); engines.append(audit)
            with ReadOnlyEngine(audit).begin() as connection:
                revisions = connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars().all()
                require(revisions==['0002_feature_links'], 'Expected migration 0002_feature_links.')
            print('PASS: migration revision 0002_feature_links (separate read-only audit connection)')
        finally:
            for engine in engines: engine.dispose()


def report_environment(target):
    values = target.values
    auth = all(values.get(key) for key in ('SUPABASE_JWT_ISSUER','SUPABASE_JWKS_URL','SUPABASE_JWT_ALGORITHM','SUPABASE_JWT_AUDIENCE'))
    print(('PASS' if auth else 'PENDING') + ': ES256 JWT issuer, JWKS and audience configuration')
    public = (values.get('CLOUD_ENABLED')=='true' and values.get('API_PUBLIC_MODE')=='true'
              and values.get('API_LEGACY_UPLOAD_ENABLED')=='false' and bool(values.get('API_ALLOWED_ORIGINS')))
    print(('PASS' if public else 'PENDING') + ': Render public-mode flags and exact HTTPS CORS configuration')
    print('PENDING: Render/Vercel deployment, Auth redirects and emails, hosted health, browser QA, edge protection and launch approval')
