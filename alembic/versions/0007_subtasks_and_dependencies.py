"""subtasks_and_dependencies

Revision ID: 0007_subtasks_and_dependencies
Revises: 0006_labels_domain
Create Date: 2026-08-15 16:29:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0007_subtasks_and_dependencies'
down_revision: Union[str, None] = '0006_labels_domain'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add parent_id column to issues table ---
    op.add_column(
        'issues',
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        op.f('fk_issues_parent_id_issues'),
        'issues', 'issues',
        ['parent_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index(op.f('ix_issues_parent_id'), 'issues', ['parent_id'], unique=False)

    # --- issue_dependencies table ---
    op.create_table(
        'issue_dependencies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_issue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'dependency_type',
            sa.Enum('BLOCKS', 'BLOCKED_BY', 'RELATES_TO', name='dependency_type_enum'),
            nullable=False
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['issue_id'], ['issues.id'],
            name=op.f('fk_issue_dependencies_issue_id_issues'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['target_issue_id'], ['issues.id'],
            name=op.f('fk_issue_dependencies_target_issue_id_issues'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_issue_dependencies')),
        sa.UniqueConstraint('issue_id', 'target_issue_id', 'dependency_type', name='uq_issue_dependency_type'),
    )
    op.create_index(op.f('ix_issue_dependencies_id'), 'issue_dependencies', ['id'], unique=False)
    op.create_index(op.f('ix_issue_dependencies_issue_id'), 'issue_dependencies', ['issue_id'], unique=False)
    op.create_index(op.f('ix_issue_dependencies_target_issue_id'), 'issue_dependencies', ['target_issue_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_issue_dependencies_target_issue_id'), table_name='issue_dependencies')
    op.drop_index(op.f('ix_issue_dependencies_issue_id'), table_name='issue_dependencies')
    op.drop_index(op.f('ix_issue_dependencies_id'), table_name='issue_dependencies')
    op.drop_table('issue_dependencies')

    op.drop_constraint(op.f('fk_issues_parent_id_issues'), 'issues', type_='foreignkey')
    op.drop_index(op.f('ix_issues_parent_id'), table_name='issues')
    op.drop_column('issues', 'parent_id')
