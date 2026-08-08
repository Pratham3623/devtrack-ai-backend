"""issue_domain

Revision ID: 0003_issue_domain
Revises: 0002_project_management
Create Date: 2026-08-08 15:52:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003_issue_domain'
down_revision: Union[str, None] = '0002_project_management'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issue_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('BACKLOG', 'TODO', 'IN_PROGRESS', 'IN_REVIEW', 'DONE', 'CANCELLED', name='issue_status_enum'),
            nullable=False,
        ),
        sa.Column(
            'priority',
            sa.Enum('NO_PRIORITY', 'LOW', 'MEDIUM', 'HIGH', 'URGENT', name='issue_priority_enum'),
            nullable=False,
        ),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assignee_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('issue_number > 0', name='ck_issue_number_positive'),
        sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], name=op.f('fk_issues_assignee_id_users'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_issues_project_id_projects'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], name=op.f('fk_issues_reporter_id_users'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_issues')),
        sa.UniqueConstraint('project_id', 'issue_number', name='uq_project_issue_number')
    )
    op.create_index(op.f('ix_issues_assignee_id'), 'issues', ['assignee_id'], unique=False)
    op.create_index(op.f('ix_issues_id'), 'issues', ['id'], unique=False)
    op.create_index(op.f('ix_issues_is_archived'), 'issues', ['is_archived'], unique=False)
    op.create_index(op.f('ix_issues_priority'), 'issues', ['priority'], unique=False)
    op.create_index(op.f('ix_issues_project_id'), 'issues', ['project_id'], unique=False)
    op.create_index('ix_issues_project_issue', 'issues', ['project_id', 'issue_number'], unique=False)
    op.create_index(op.f('ix_issues_reporter_id'), 'issues', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_issues_status'), 'issues', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_issues_status'), table_name='issues')
    op.drop_index(op.f('ix_issues_reporter_id'), table_name='issues')
    op.drop_index('ix_issues_project_issue', table_name='issues')
    op.drop_index(op.f('ix_issues_project_id'), table_name='issues')
    op.drop_index(op.f('ix_issues_priority'), table_name='issues')
    op.drop_index(op.f('ix_issues_is_archived'), table_name='issues')
    op.drop_index(op.f('ix_issues_id'), table_name='issues')
    op.drop_index(op.f('ix_issues_assignee_id'), table_name='issues')
    op.drop_table('issues')
