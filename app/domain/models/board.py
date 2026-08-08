import uuid
from typing import List
from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.domain.models.enums import IssueStatus


class Board(BaseModel):
    """Kanban board belonging to a project. A project may have multiple boards."""

    __tablename__ = "boards"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="boards")
    columns: Mapped[List["BoardColumn"]] = relationship(
        "BoardColumn",
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="BoardColumn.position",
    )


class BoardColumn(BaseModel):
    """A single Kanban column that maps to one IssueStatus value."""

    __tablename__ = "board_columns"
    __table_args__ = (
        UniqueConstraint("board_id", "mapped_status", name="uq_board_columns_board_status"),
        Index("ix_board_columns_board_position", "board_id", "position"),
    )

    board_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapped_status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status_enum", create_type=False),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    board: Mapped["Board"] = relationship("Board", back_populates="columns")
