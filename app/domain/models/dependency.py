import uuid
from enum import Enum
from sqlalchemy import Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class DependencyType(str, Enum):
    BLOCKS = "BLOCKS"
    BLOCKED_BY = "BLOCKED_BY"
    RELATES_TO = "RELATES_TO"


class IssueDependency(BaseModel):
    """Dependency link between two issues in the same project."""

    __tablename__ = "issue_dependencies"
    __table_args__ = (
        UniqueConstraint("issue_id", "target_issue_id", "dependency_type", name="uq_issue_dependency_type"),
    )

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependency_type: Mapped[DependencyType] = mapped_column(
        SQLEnum(DependencyType, name="dependency_type_enum", create_type=True),
        nullable=False,
    )

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", foreign_keys=[issue_id])
    target_issue: Mapped["Issue"] = relationship("Issue", foreign_keys=[target_issue_id])
