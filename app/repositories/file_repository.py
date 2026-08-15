"""
File Repository — Phase 11 Files & Storage.
Handles all DB operations for FileAttachment and FileVersion.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.file import FileAttachment, FileVersion


class FileRepository:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── FileAttachment CRUD ────────────────────────────────────────────────────

    async def create_file_record(self, data: dict) -> FileAttachment:
        record = FileAttachment(**data)
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_file_by_id(self, file_id: UUID, org_id: UUID) -> Optional[FileAttachment]:
        stmt = (
            select(FileAttachment)
            .options(selectinload(FileAttachment.versions))
            .where(
                FileAttachment.id == str(file_id),
                FileAttachment.organization_id == str(org_id),
                FileAttachment.is_archived == False,  # noqa: E712
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_file_by_id_any_org(self, file_id: UUID) -> Optional[FileAttachment]:
        """Used internally for signed-URL token serving."""
        stmt = select(FileAttachment).where(FileAttachment.id == str(file_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_files(
        self,
        org_id: UUID,
        *,
        project_id: Optional[UUID] = None,
        issue_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[FileAttachment], int]:
        conditions = [
            FileAttachment.organization_id == str(org_id),
            FileAttachment.is_archived == False,  # noqa: E712
        ]
        if project_id:
            conditions.append(FileAttachment.project_id == str(project_id))
        if issue_id:
            conditions.append(FileAttachment.issue_id == str(issue_id))

        # Count
        count_stmt = select(func.count()).select_from(FileAttachment).where(and_(*conditions))
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Fetch
        stmt = (
            select(FileAttachment)
            .where(and_(*conditions))
            .order_by(FileAttachment.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def update_file_record(self, file_id: UUID, data: dict) -> Optional[FileAttachment]:
        record = await self.db.get(FileAttachment, str(file_id))
        if not record:
            return None
        for k, v in data.items():
            setattr(record, k, v)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def archive_file(self, file_id: UUID, org_id: UUID) -> bool:
        record = await self.get_file_by_id(file_id, org_id)
        if not record:
            return False
        record.is_archived = True
        await self.db.flush()
        return True

    # ── FileVersion CRUD ───────────────────────────────────────────────────────

    async def create_version(self, data: dict) -> FileVersion:
        version = FileVersion(**data)
        self.db.add(version)
        await self.db.flush()
        await self.db.refresh(version)
        return version

    async def list_versions(self, file_id: UUID) -> List[FileVersion]:
        stmt = (
            select(FileVersion)
            .where(FileVersion.file_id == str(file_id))
            .order_by(FileVersion.version_number.asc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_version_by_number(self, file_id: UUID, version_number: int) -> Optional[FileVersion]:
        stmt = select(FileVersion).where(
            FileVersion.file_id == str(file_id),
            FileVersion.version_number == version_number,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
