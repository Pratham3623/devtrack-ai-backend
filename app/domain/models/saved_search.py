import uuid
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.db.types import UUID


class SavedSearch(BaseModel):
    """Stores user-defined saved search criteria and filter presets."""

    __tablename__ = "saved_searches"
    __table_args__ = (
        Index("ix_saved_searches_org_user", "organization_id", "user_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query_params: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    organization = relationship("Organization", lazy="raise")
    user = relationship("User", lazy="raise")
