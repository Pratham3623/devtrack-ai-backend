"""kanban_board

Revision ID: 0004_kanban_board
Revises: 0003_issue_domain
Create Date: 2026-08-08 16:11:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0004_kanban_board'
down_revision: Union[str, None] = '0003_issue_domain'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- boards table ---
    op.create_table(
        'boards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_boards_project_id_projects'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_boards')),
    )
    op.create_index(op.f('ix_boards_id'), 'boards', ['id'], unique=False)
    op.create_index(op.f('ix_boards_project_id'), 'boards', ['project_id'], unique=False)
    op.create_index(op.f('ix_boards_is_default'), 'boards', ['is_default'], unique=False)

    # --- board_columns table ---
    op.create_table(
        'board_columns',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('board_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column(
            'mapped_status',
            sa.Enum(
                'BACKLOG', 'TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE', 'CANCELLED',
                name='issue_status_enum',
                create_type=False,   # enum already exists from 0003_issue_domain
            ),
            nullable=False,
        ),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_hidden', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['board_id'], ['boards.id'],
            name=op.f('fk_board_columns_board_id_boards'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_board_columns')),
        sa.UniqueConstraint('board_id', 'mapped_status', name='uq_board_columns_board_status'),
    )
    op.create_index(op.f('ix_board_columns_id'), 'board_columns', ['id'], unique=False)
    op.create_index(op.f('ix_board_columns_board_id'), 'board_columns', ['board_id'], unique=False)
    op.create_index(
        'ix_board_columns_board_position', 'board_columns', ['board_id', 'position'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_board_columns_board_position', table_name='board_columns')
    op.drop_index(op.f('ix_board_columns_board_id'), table_name='board_columns')
    op.drop_index(op.f('ix_board_columns_id'), table_name='board_columns')
    op.drop_table('board_columns')

    op.drop_index(op.f('ix_boards_is_default'), table_name='boards')
    op.drop_index(op.f('ix_boards_project_id'), table_name='boards')
    op.drop_index(op.f('ix_boards_id'), table_name='boards')
    op.drop_table('boards')
