import uuid
from typing import List, Optional
from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from app.db.types import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, Base

# Secondary junction table for Issue <-> Label M2M
issue_labels = Table(
    "issue_labels",
    Base.metadata,
    Column("issue_id", UUID(), ForeignKey("issues.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", UUID(), ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class Label(BaseModel):
    """Project-level Issue Label."""

    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_labels_project_name"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")  # Hex color string

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", secondary=issue_labels, back_populates="labels"
    )
