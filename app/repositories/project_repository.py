import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.enums import ProjectTemplateType
from app.domain.models.project import Project, ProjectMember
from app.repositories.base_repository import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: AsyncSession):
        super().__init__(Project, db)

    async def get_by_key(self, org_id: uuid.UUID, key: str) -> Optional[Project]:
        stmt = select(Project).where(
            Project.organization_id == org_id,
            Project.key == key.upper(),
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_org_projects_paginated(
        self,
        org_id: uuid.UUID,
        query_str: Optional[str] = None,
        template_type: Optional[ProjectTemplateType] = None,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Project], int]:
        stmt = select(Project).where(Project.organization_id == org_id)

        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))

        if template_type:
            stmt = stmt.where(Project.template_type == template_type)

        if query_str:
            q = f"%{query_str}%"
            stmt = stmt.where((Project.name.ilike(q)) | (Project.key.ilike(q)) | (Project.description.ilike(q)))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Execute paginated results
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        results = await self.db.execute(stmt)
        return list(results.scalars().all()), total

    async def get_project_members(self, project_id: uuid.UUID) -> List[ProjectMember]:
        stmt = (
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(ProjectMember.project_id == project_id)
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_member(self, project_id: uuid.UUID, user_id: uuid.UUID) -> Optional[ProjectMember]:
        stmt = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()
