"""
File Service — Phase 11 Files & Storage.
Orchestrates upload, download, versioning, permissions, and signed URL generation.
"""
from __future__ import annotations

import mimetypes
import re
import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.storage import get_storage, make_storage_key
from app.domain.models.enums import OrgRole
from app.domain.models.file import FileAttachment, FileVersion
from app.domain.models.user import User
from app.domain.schemas.file import (
    FileAttachmentResponse,
    FileListResponse,
    FileUploadResponse,
    FileVersionResponse,
)
from app.repositories.file_repository import FileRepository
from app.repositories.org_repository import OrganizationRepository

IMAGE_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
    "image/bmp", "image/tiff",
}


def _sanitize_filename(name: str) -> str:
    """Strip path components and unsafe characters."""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:255] or "file"


async def _check_org_member(org_repo: OrganizationRepository, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    member = await org_repo.get_membership(org_id, user_id)
    if not member:
        raise ForbiddenException("You are not a member of this organization.")


class FileService:
    """Orchestrates file upload, download, versioning, and signed URL generation."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = FileRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.storage = get_storage()

    # ── Upload ─────────────────────────────────────────────────────────────────

    async def upload_file(
        self,
        org_id: uuid.UUID,
        actor: User,
        file_bytes: bytes,
        original_filename: str,
        content_type: str,
        *,
        project_id: Optional[uuid.UUID] = None,
        issue_id: Optional[uuid.UUID] = None,
    ) -> FileUploadResponse:
        await _check_org_member(self.org_repo, org_id, actor.id)

        # Validate size
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValidationException(f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB.")

        # Validate MIME type
        if content_type not in settings.ALLOWED_MIME_TYPES:
            # Attempt to sniff from filename
            guessed, _ = mimetypes.guess_type(original_filename)
            if guessed and guessed in settings.ALLOWED_MIME_TYPES:
                content_type = guessed
            else:
                raise ValidationException(f"File type '{content_type}' is not allowed.")

        filename = _sanitize_filename(original_filename)
        storage_key = make_storage_key(str(org_id), filename)
        is_image = content_type in IMAGE_MIME_TYPES

        # Upload to storage backend
        await self.storage.upload(storage_key, file_bytes, content_type)

        # Persist master record
        record = await self.repo.create_file_record({
            "organization_id": str(org_id),
            "project_id": str(project_id) if project_id else None,
            "issue_id": str(issue_id) if issue_id else None,
            "uploader_id": str(actor.id),
            "original_filename": original_filename,
            "filename": filename,
            "content_type": content_type,
            "size_bytes": len(file_bytes),
            "storage_key": storage_key,
            "storage_backend": self.storage.backend_name,
            "is_image": is_image,
            "current_version": 1,
        })

        # Create initial FileVersion row (v1)
        await self.repo.create_version({
            "file_id": str(record.id),
            "version_number": 1,
            "storage_key": storage_key,
            "size_bytes": len(file_bytes),
            "uploader_id": str(actor.id),
            "changelog": "Initial upload",
        })

        await self.db.commit()

        download_url = await self.storage.get_signed_url(storage_key, settings.S3_SIGNED_URL_EXPIRY)
        thumbnail_url = download_url if is_image else None

        return FileUploadResponse(
            id=record.id,
            filename=record.filename,
            original_filename=record.original_filename,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            is_image=record.is_image,
            current_version=record.current_version,
            storage_backend=record.storage_backend,
            download_url=download_url,
            thumbnail_url=thumbnail_url,
            created_at=record.created_at,
        )

    # ── Versioning ─────────────────────────────────────────────────────────────

    async def upload_new_version(
        self,
        org_id: uuid.UUID,
        file_id: uuid.UUID,
        actor: User,
        file_bytes: bytes,
        content_type: str,
        changelog: Optional[str] = None,
    ) -> FileVersionResponse:
        await _check_org_member(self.org_repo, org_id, actor.id)

        record = await self.repo.get_file_by_id(file_id, org_id)
        if not record:
            raise EntityNotFoundException("FileAttachment", file_id)

        # Validate size
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValidationException(f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB.")

        new_version = record.current_version + 1
        versioned_key = make_storage_key(str(org_id), record.filename, prefix=f"files/v{new_version}")
        await self.storage.upload(versioned_key, file_bytes, content_type)

        version_record = await self.repo.create_version({
            "file_id": str(record.id),
            "version_number": new_version,
            "storage_key": versioned_key,
            "size_bytes": len(file_bytes),
            "uploader_id": str(actor.id),
            "changelog": changelog or f"Version {new_version}",
        })

        # Update master record
        await self.repo.update_file_record(record.id, {
            "storage_key": versioned_key,
            "size_bytes": len(file_bytes),
            "current_version": new_version,
        })
        await self.db.commit()

        download_url = await self.storage.get_signed_url(versioned_key, settings.S3_SIGNED_URL_EXPIRY)
        return FileVersionResponse(
            id=version_record.id,
            file_id=version_record.file_id,
            version_number=version_record.version_number,
            size_bytes=version_record.size_bytes,
            uploader_id=version_record.uploader_id,
            changelog=version_record.changelog,
            created_at=version_record.created_at,
            download_url=download_url,
        )

    async def list_versions(
        self, org_id: uuid.UUID, file_id: uuid.UUID, actor: User
    ) -> List[FileVersionResponse]:
        await _check_org_member(self.org_repo, org_id, actor.id)
        record = await self.repo.get_file_by_id(file_id, org_id)
        if not record:
            raise EntityNotFoundException("FileAttachment", file_id)

        versions = await self.repo.list_versions(file_id)
        results = []
        for v in versions:
            url = await self.storage.get_signed_url(v.storage_key, settings.S3_SIGNED_URL_EXPIRY)
            results.append(FileVersionResponse(
                id=v.id,
                file_id=v.file_id,
                version_number=v.version_number,
                size_bytes=v.size_bytes,
                uploader_id=v.uploader_id,
                changelog=v.changelog,
                created_at=v.created_at,
                download_url=url,
            ))
        return results

    async def get_version_download_url(
        self, org_id: uuid.UUID, file_id: uuid.UUID, version_number: int, actor: User
    ) -> str:
        await _check_org_member(self.org_repo, org_id, actor.id)
        version = await self.repo.get_version_by_number(file_id, version_number)
        if not version:
            raise EntityNotFoundException("FileVersion", f"{file_id}/v{version_number}")
        return await self.storage.get_signed_url(version.storage_key, settings.S3_SIGNED_URL_EXPIRY)

    # ── List & Download ────────────────────────────────────────────────────────

    async def list_files(
        self,
        org_id: uuid.UUID,
        actor: User,
        *,
        project_id: Optional[uuid.UUID] = None,
        issue_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FileListResponse:
        await _check_org_member(self.org_repo, org_id, actor.id)
        records, total = await self.repo.list_files(
            org_id, project_id=project_id, issue_id=issue_id, page=page, page_size=page_size
        )

        items = []
        for r in records:
            url = await self.storage.get_signed_url(r.storage_key, settings.S3_SIGNED_URL_EXPIRY)
            thumb = url if r.is_image else None
            items.append(FileAttachmentResponse(
                **{c.key: getattr(r, c.key) for c in r.__table__.columns},
                download_url=url,
                thumbnail_url=thumb,
                versions=[],
            ))

        return FileListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_file(self, org_id: uuid.UUID, file_id: uuid.UUID, actor: User) -> FileAttachmentResponse:
        await _check_org_member(self.org_repo, org_id, actor.id)
        record = await self.repo.get_file_by_id(file_id, org_id)
        if not record:
            raise EntityNotFoundException("FileAttachment", file_id)

        url = await self.storage.get_signed_url(record.storage_key, settings.S3_SIGNED_URL_EXPIRY)
        thumb = url if record.is_image else None

        version_responses = []
        for v in record.versions:
            vurl = await self.storage.get_signed_url(v.storage_key, settings.S3_SIGNED_URL_EXPIRY)
            version_responses.append(FileVersionResponse(
                id=v.id, file_id=v.file_id, version_number=v.version_number,
                size_bytes=v.size_bytes, uploader_id=v.uploader_id,
                changelog=v.changelog, created_at=v.created_at, download_url=vurl,
            ))

        return FileAttachmentResponse(
            **{c.key: getattr(record, c.key) for c in record.__table__.columns},
            download_url=url,
            thumbnail_url=thumb,
            versions=version_responses,
        )

    async def get_download_url(self, org_id: uuid.UUID, file_id: uuid.UUID, actor: User) -> str:
        await _check_org_member(self.org_repo, org_id, actor.id)
        record = await self.repo.get_file_by_id(file_id, org_id)
        if not record:
            raise EntityNotFoundException("FileAttachment", file_id)
        return await self.storage.get_signed_url(record.storage_key, settings.S3_SIGNED_URL_EXPIRY)

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_file(self, org_id: uuid.UUID, file_id: uuid.UUID, actor: User) -> None:
        await _check_org_member(self.org_repo, org_id, actor.id)
        record = await self.repo.get_file_by_id(file_id, org_id)
        if not record:
            raise EntityNotFoundException("FileAttachment", file_id)

        # Only uploader or admin/owner can delete
        if str(record.uploader_id) != str(actor.id):
            member = await self.org_repo.get_membership(org_id, actor.id)
            if not member or member.role not in [OrgRole.OWNER, OrgRole.ADMIN]:
                raise ForbiddenException("Only the uploader or an admin can delete this file.")

        archived = await self.repo.archive_file(file_id, org_id)
        if archived:
            await self.db.commit()

    # ── Local signed-URL token serving ─────────────────────────────────────────

    async def serve_local_file(self, token: str) -> tuple[bytes, str]:
        """Validate HMAC token and return (bytes, content_type)."""
        from app.core.storage import LocalStorageBackend
        backend = self.storage
        if not isinstance(backend, LocalStorageBackend):
            raise ForbiddenException("Direct serving only supported on local backend.")

        storage_key = LocalStorageBackend.verify_token(token)
        if not storage_key:
            raise ForbiddenException("Invalid or expired download token.")

        data = await backend.download(storage_key)
        # Infer content type from key
        ct, _ = mimetypes.guess_type(storage_key)
        return data, ct or "application/octet-stream"
