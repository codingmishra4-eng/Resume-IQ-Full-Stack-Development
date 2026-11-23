"""Cloud ownership tables and defense-in-depth RLS; independent of local tables."""
from alembic import op
import sqlalchemy as sa
revision = '0001_cloud'
down_revision = None
branch_labels = None
depends_on = None
TABLES = ('cloud_resumes', 'cloud_analyses', 'cloud_saved_resumes', 'cloud_history')


def upgrade():
    for table in TABLES:
        fields = [sa.Column('id', sa.Uuid(), primary_key=True),
                  sa.Column('user_id', sa.Uuid(), nullable=False),
                  sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                  sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]
        if table == 'cloud_resumes':
            fields += [sa.Column('object_path', sa.String(160), nullable=False, unique=True),
                       sa.Column('state', sa.String(16), nullable=False),
                       sa.Column('metadata_json', sa.JSON(), nullable=False),
                       sa.CheckConstraint("state IN ('pending','ready','deleting')", name='resume_state')]
        elif table == 'cloud_history':
            fields += [sa.Column('event', sa.String(32), nullable=False),
                       sa.Column('resource_id', sa.Uuid(), nullable=False)]
        else:
            fields += [sa.Column('summary_json' if table == 'cloud_analyses' else 'data_json', sa.JSON(), nullable=False)]
        op.create_table(table, *fields, schema='public')
        op.create_index('ix_' + table + '_user_id', table, ['user_id'], schema='public')
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        # TO PUBLIC is safe here: the role-name condition denies every role but
        # the dedicated backend. The role need not exist at migration time.
        owner = "current_user = 'resumeiq_runtime' AND user_id = NULLIF(current_setting('resumeiq.user_id', true), '')::uuid"
        op.execute(f"CREATE POLICY owner_access ON public.{table} USING ({owner}) WITH CHECK ({owner})")
    # Supabase may grant new public tables to Data API roles through default
    # privileges. Revoke *after creation*, including Alembic's version table.
    # Never change default privileges/schema ACLs for unrelated applications.
    for table in (*TABLES, 'alembic_version'):
        op.execute(f'REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC')
        op.execute(f"""
            DO $acl$
            DECLARE role_name text;
            BEGIN
                FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I', '{table}', role_name);
                        -- REVOKE cannot remove inherited privileges or superuser
                        -- access. Abort atomically rather than claim isolation.
                        IF has_table_privilege(role_name, 'public.{table}',
                            'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                           OR pg_has_role(role_name,
                               (SELECT pg_get_userbyid(relowner) FROM pg_class
                                WHERE oid = 'public.{table}'::regclass), 'MEMBER') THEN
                            RAISE EXCEPTION 'Data API role retains cloud table privileges; review role memberships';
                        END IF;
                    END IF;
                END LOOP;
            END $acl$;
        """)


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table, schema='public')
