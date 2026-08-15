"""
ORM models for Phase 11 — Files & Storage.
FileAttachment: master file record.
FileVersion: versioning history per file.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import BaseModel
from app.db.types import UUID


class FileAttachment(BaseModel):
    """Master file record — one row per logical file."""
    __tablename__ = "file_attachments"

    # Scoping
    organization_id = Column(UUID, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_id = Column(UUID, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, index=True)
    uploader_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # File metadata
    original_filename = Column(String(512), nullable=False)
    filename = Column(String(512), nullable=False)  # sanitized
    content_type = Column(String(256), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_key = Column(String(1024), nullable=False)  # path on disk / S3 key
    storage_backend = Column(String(16), nullable=False, default="local")  # "local" | "s3"

    # Flags
    is_image = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False)
    current_version = Column(Integer, nullable=False, default=1)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan", lazy="select")


class FileVersion(BaseModel):
    """Version history for a FileAttachment."""
    __tablename__ = "file_versions"

    file_id = Column(UUID, ForeignKey("file_attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    storage_key = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploader_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changelog = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    file = relationship("FileAttachment", back_populates="versions")
