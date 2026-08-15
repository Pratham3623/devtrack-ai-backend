import uuid
from typing import Optional
from sqlalchemy import ForeignKey, Text
from app.db.types import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Comment(BaseModel):
    """User comment on an Issue."""

    __tablename__ = "comments"

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue")
    author: Mapped["User"] = relationship("User")
