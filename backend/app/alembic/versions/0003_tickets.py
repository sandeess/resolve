"""tickets

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05 20:27:42.983357

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SEQUENCE ticket_number_seq")
    op.create_table('ticket',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), sa.Sequence('ticket_number_seq'), nullable=False),
    sa.Column('journal_id', sa.Uuid(), nullable=False),
    sa.Column('article_id', sa.Uuid(), nullable=True),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=10000), nullable=False),
    sa.Column('status', sa.Enum('open', 'resolved', 'closed', name='ticketstatus', native_enum=False, length=32), nullable=False),
    sa.Column('priority', sa.Enum('low', 'normal', 'high', name='ticketpriority', native_enum=False, length=32), nullable=False),
    sa.Column('source', sa.Enum('web', 'ask_escalation', name='ticketsource', native_enum=False, length=32), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('assignee_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['article.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['assignee_id'], ['app_user.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
    sa.ForeignKeyConstraint(['journal_id'], ['journal.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    op.create_index(op.f('ix_ticket_article_id'), 'ticket', ['article_id'], unique=False)
    op.create_index(op.f('ix_ticket_journal_id'), 'ticket', ['journal_id'], unique=False)
    op.create_index('ix_ticket_journal_status', 'ticket', ['journal_id', 'status'], unique=False)
    op.create_table('ticketmessage',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('body', sqlmodel.sql.sqltypes.AutoString(length=10000), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['app_user.id'], ),
    sa.ForeignKeyConstraint(['ticket_id'], ['ticket.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ticketmessage_ticket_id'), 'ticketmessage', ['ticket_id'], unique=False)
    op.create_table('ticketresolution',
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('answer', sqlmodel.sql.sqltypes.AutoString(length=10000), nullable=False),
    sa.Column('resolved_by', sa.Uuid(), nullable=False),
    sa.Column('approved_by', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['app_user.id'], ),
    sa.ForeignKeyConstraint(['resolved_by'], ['app_user.id'], ),
    sa.ForeignKeyConstraint(['ticket_id'], ['ticket.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('ticket_id')
    )
    op.add_column('chunk', sa.Column('ticket_id', sa.Uuid(), nullable=True))
    op.alter_column('chunk', 'version_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.create_index(op.f('ix_chunk_ticket_id'), 'chunk', ['ticket_id'], unique=False)
    op.create_unique_constraint('chunk_ticket_id_chunk_index_key', 'chunk', ['ticket_id', 'chunk_index'])
    op.create_foreign_key('chunk_ticket_id_fkey', 'chunk', 'ticket', ['ticket_id'], ['id'], ondelete='CASCADE')
    op.create_check_constraint(
        'ck_chunk_one_source', 'chunk', '(version_id IS NULL) <> (ticket_id IS NULL)'
    )


def downgrade():
    op.drop_constraint('ck_chunk_one_source', 'chunk', type_='check')
    op.drop_constraint('chunk_ticket_id_fkey', 'chunk', type_='foreignkey')
    op.drop_constraint('chunk_ticket_id_chunk_index_key', 'chunk', type_='unique')
    op.drop_index(op.f('ix_chunk_ticket_id'), table_name='chunk')
    op.alter_column('chunk', 'version_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.drop_column('chunk', 'ticket_id')
    op.drop_table('ticketresolution')
    op.drop_index(op.f('ix_ticketmessage_ticket_id'), table_name='ticketmessage')
    op.drop_table('ticketmessage')
    op.drop_index('ix_ticket_journal_status', table_name='ticket')
    op.drop_index(op.f('ix_ticket_journal_id'), table_name='ticket')
    op.drop_index(op.f('ix_ticket_article_id'), table_name='ticket')
    op.drop_table('ticket')
    op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")
