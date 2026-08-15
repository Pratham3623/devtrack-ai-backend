"""
Pydantic schemas for Phase 11 — Files & Storage.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FileVersionResponse(BaseModel):
    id: UUID
    file_id: UUID
    version_number: int
    size_bytes: int
    uploader_id: Optional[UUID] = None
    changelog: Optional[str] = None
    created_at: datetime
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class FileAttachmentResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: Optional[UUID] = None
    issue_id: Optional[UUID] = None
    uploader_id: Optional[UUID] = None
    original_filename: str
    filename: str
    content_type: str
    size_bytes: int
    storage_backend: str
    is_image: bool
    is_archived: bool
    current_version: int
    created_at: datetime
    updated_at: datetime

    # Resolved at request time
    download_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    versions: List[FileVersionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    items: List[FileAttachmentResponse]
    total: int
    page: int
    page_size: int


class FileUploadResponse(BaseModel):
    """Lightweight response returned immediately after upload."""
    id: UUID
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    is_image: bool
    current_version: int
    storage_backend: str
    download_url: str
    thumbnail_url: Optional[str] = None
    created_at: datetime


class FileVersionCreateRequest(BaseModel):
    changelog: Optional[str] = Field(None, max_length=1024, description="What changed in this version")
