import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.domain.models.enums import IssuePriority, IssueStatus


class Issue(BaseModel):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("project_id", "issue_number", name="uq_project_issue_number"),
        CheckConstraint("issue_number > 0", name="ck_issue_number_positive"),
        Index("ix_issues_project_issue", "project_id", "issue_number"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status_enum", create_type=True),
        default=IssueStatus.TODO,
        nullable=False,
        index=True,
    )
    priority: Mapped[IssuePriority] = mapped_column(
        Enum(IssuePriority, name="issue_priority_enum", create_type=True),
        default=IssuePriority.MEDIUM,
        nullable=False,
        index=True,
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=True, index=True
    )

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="issues")
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id])
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id])
    labels: Mapped[List["Label"]] = relationship(
        "Label", secondary="issue_labels", back_populates="issues"
    )
    parent: Mapped[Optional["Issue"]] = relationship(
        "Issue", remote_side="Issue.id", back_populates="subtasks"
    )
    subtasks: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="parent", cascade="all, delete-orphan"
    )

    @property
    def identifier(self) -> str:
        """Formatted human-readable issue key e.g. 'DEV-1' if project is loaded."""
        if hasattr(self, "project") and self.project and hasattr(self.project, "key"):
            return f"{self.project.key}-{self.issue_number}"
        return f"ISSUE-{self.issue_number}"
