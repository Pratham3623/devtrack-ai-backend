"""labels_domain

Revision ID: 0006_labels_domain
Revises: 0005_comments_and_activity
Create Date: 2026-08-15 16:26:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0006_labels_domain'
down_revision: Union[str, None] = '0005_comments_and_activity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- labels table ---
    op.create_table(
        'labels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'],
            name=op.f('fk_labels_project_id_projects'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_labels')),
        sa.UniqueConstraint('project_id', 'name', name='uq_labels_project_name'),
    )
    op.create_index(op.f('ix_labels_id'), 'labels', ['id'], unique=False)
    op.create_index(op.f('ix_labels_project_id'), 'labels', ['project_id'], unique=False)

    # --- issue_labels table ---
    op.create_table(
        'issue_labels',
        sa.Column('issue_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['issue_id'], ['issues.id'],
            name=op.f('fk_issue_labels_issue_id_issues'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['label_id'], ['labels.id'],
            name=op.f('fk_issue_labels_label_id_labels'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('issue_id', 'label_id', name=op.f('pk_issue_labels')),
    )


def downgrade() -> None:
    op.drop_table('issue_labels')
    op.drop_index(op.f('ix_labels_project_id'), table_name='labels')
    op.drop_index(op.f('ix_labels_id'), table_name='labels')
    op.drop_table('labels')
