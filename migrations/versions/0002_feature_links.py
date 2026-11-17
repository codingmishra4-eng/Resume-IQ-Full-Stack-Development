"""Link owned feature results to resumes without replacing Phase 2 data/RLS."""
from alembic import op
import sqlalchemy as sa
revision = '0002_feature_links'
down_revision = '0001_cloud'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_cloud_resume_owner', 'cloud_resumes', ['id', 'user_id'], schema='public')
    op.add_column('cloud_analyses', sa.Column('resume_id', sa.Uuid(), nullable=True), schema='public')
    op.add_column('cloud_analyses', sa.Column('kind', sa.String(16), nullable=False, server_default='analysis'), schema='public')
    op.create_check_constraint('cloud_analysis_kind', 'cloud_analyses', "kind IN ('analysis','match')", schema='public')
    op.create_index('ix_cloud_analyses_resume_id', 'cloud_analyses', ['resume_id'], schema='public')
    op.create_foreign_key('fk_cloud_analysis_resume_owner', 'cloud_analyses', 'cloud_resumes', ['resume_id','user_id'], ['id','user_id'], source_schema='public', referent_schema='public', ondelete='CASCADE')
    # ALTER preserves existing RLS, grants and restricted runtime. No new table/role.


def downgrade():
    op.drop_constraint('fk_cloud_analysis_resume_owner', 'cloud_analyses', schema='public', type_='foreignkey')
    op.drop_index('ix_cloud_analyses_resume_id', 'cloud_analyses', schema='public')
    op.drop_constraint('cloud_analysis_kind', 'cloud_analyses', schema='public', type_='check')
    op.drop_column('cloud_analyses', 'kind', schema='public')
    op.drop_column('cloud_analyses', 'resume_id', schema='public')
    op.drop_constraint('uq_cloud_resume_owner', 'cloud_resumes', schema='public', type_='unique')
