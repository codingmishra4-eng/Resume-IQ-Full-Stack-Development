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
        op.create_table(table, *fields)
        op.create_index('ix_' + table + '_user_id', table, ['user_id'])
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY owner_access ON {table} USING (user_id = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid) WITH CHECK (user_id = NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid)")


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
