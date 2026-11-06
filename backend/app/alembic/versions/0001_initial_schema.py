"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-05 18:15:02.169183

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('app_user',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sub', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_app_user_email'), 'app_user', ['email'], unique=False)
    op.create_index(op.f('ix_app_user_sub'), 'app_user', ['sub'], unique=True)
    op.create_table('journal',
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_journal_code'), 'journal', ['code'], unique=True)
    op.create_table('article',
    sa.Column('manuscript_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('journal_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('journal_id', 'manuscript_id')
    )
    op.create_index(op.f('ix_article_journal_id'), 'article', ['journal_id'], unique=False)
    op.create_table('journalmember',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('journal_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('lead', 'assistant', 'viewer', name='role', native_enum=False, length=32), nullable=False),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('journal_id', 'user_id')
    )
    op.create_index(op.f('ix_journalmember_journal_id'), 'journalmember', ['journal_id'], unique=False)
    op.create_index(op.f('ix_journalmember_user_id'), 'journalmember', ['user_id'], unique=False)
    op.create_table('document',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('journal_id', sa.Uuid(), nullable=False),
    sa.Column('article_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.Enum('stylesheet', 'guideline', 'manuscript', 'email_attachment', 'other', name='documentkind', native_enum=False, length=32), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['article.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_article_id'), 'document', ['article_id'], unique=False)
    op.create_index(op.f('ix_document_journal_id'), 'document', ['journal_id'], unique=False)
    op.create_index('uq_document_identity', 'document', ['journal_id', sa.literal_column("coalesce(article_id, '00000000-0000-0000-0000-000000000000')"), 'kind', 'name'], unique=True)
    op.create_table('documentversion',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('storage_key', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
    sa.Column('status', sa.Enum('pending', 'indexed', 'failed', name='versionstatus', native_enum=False, length=32), nullable=False),
    sa.Column('uploaded_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['document.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['app_user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'version_no')
    )
    op.create_index(op.f('ix_documentversion_document_id'), 'documentversion', ['document_id'], unique=False)
    op.create_index(op.f('ix_documentversion_sha256'), 'documentversion', ['sha256'], unique=False)
    op.create_index('uq_document_current_version', 'documentversion', ['document_id'], unique=True, postgresql_where=sa.text('is_current'))


def downgrade():
    op.drop_index('uq_document_current_version', table_name='documentversion', postgresql_where=sa.text('is_current'))
    op.drop_index(op.f('ix_documentversion_sha256'), table_name='documentversion')
    op.drop_index(op.f('ix_documentversion_document_id'), table_name='documentversion')
    op.drop_table('documentversion')
    op.drop_index('uq_document_identity', table_name='document')
    op.drop_index(op.f('ix_document_journal_id'), table_name='document')
    op.drop_index(op.f('ix_document_article_id'), table_name='document')
    op.drop_table('document')
    op.drop_index(op.f('ix_journalmember_user_id'), table_name='journalmember')
    op.drop_index(op.f('ix_journalmember_journal_id'), table_name='journalmember')
    op.drop_table('journalmember')
    op.drop_index(op.f('ix_article_journal_id'), table_name='article')
    op.drop_table('article')
    op.drop_index(op.f('ix_journal_code'), table_name='journal')
    op.drop_table('journal')
    op.drop_index(op.f('ix_app_user_sub'), table_name='app_user')
    op.drop_index(op.f('ix_app_user_email'), table_name='app_user')
    op.drop_table('app_user')
