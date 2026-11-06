"""chunks

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 19:42:12.324370

"""
from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chunk',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('version_id', sa.Uuid(), nullable=False),
    sa.Column('journal_id', sa.Uuid(), nullable=False),
    sa.Column('article_id', sa.Uuid(), nullable=True),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('locator', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
    sa.Column('embedding_model', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('english', content)", persisted=True), nullable=True),
    sa.ForeignKeyConstraint(['article_id'], ['article.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['version_id'], ['documentversion.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'chunk_index')
    )
    op.create_index(op.f('ix_chunk_article_id'), 'chunk', ['article_id'], unique=False)
    op.create_index('ix_chunk_embedding', 'chunk', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_chunk_journal_id'), 'chunk', ['journal_id'], unique=False)
    op.create_index('ix_chunk_tsv', 'chunk', ['tsv'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_chunk_version_id'), 'chunk', ['version_id'], unique=False)
    op.add_column('documentversion', sa.Column('status_detail', sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True))


def downgrade():
    op.drop_column('documentversion', 'status_detail')
    op.drop_index(op.f('ix_chunk_version_id'), table_name='chunk')
    op.drop_index('ix_chunk_tsv', table_name='chunk', postgresql_using='gin')
    op.drop_index(op.f('ix_chunk_journal_id'), table_name='chunk')
    op.drop_index('ix_chunk_embedding', table_name='chunk', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_chunk_article_id'), table_name='chunk')
    op.drop_table('chunk')
