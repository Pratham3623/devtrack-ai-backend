import uuid
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.dependency import DependencyType, IssueDependency
from app.domain.models.issue import Issue
from app.repositories.base_repository import BaseRepository


class DependencyRepository(BaseRepository[IssueDependency]):
    """Data access layer for Subtasks and Issue Dependencies."""

    def __init__(self, db: AsyncSession):
        super().__init__(IssueDependency, db)

    async def list_subtasks(self, parent_issue_id: uuid.UUID) -> List[Issue]:
        stmt = (
            select(Issue)
            .where(Issue.parent_id == parent_issue_id)
            .options(selectinload(Issue.project))
            .order_by(Issue.issue_number.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_subtask_progress(self, parent_issue_id: uuid.UUID) -> tuple[int, int]:
        subtasks = await self.list_subtasks(parent_issue_id)
        total = len(subtasks)
        completed = sum(1 for s in subtasks if s.status.value in ["DONE", "CANCELLED"])
        return total, completed

    async def create_dependency(
        self, issue_id: uuid.UUID, target_issue_id: uuid.UUID, dep_type: DependencyType
    ) -> IssueDependency:
        dep = IssueDependency(
            issue_id=issue_id,
            target_issue_id=target_issue_id,
            dependency_type=dep_type,
        )
        self.db.add(dep)
        await self.db.flush()
        return await self.get_dependency_with_target(dep.id)

    async def get_dependency_with_target(self, dep_id: uuid.UUID) -> Optional[IssueDependency]:
        stmt = (
            select(IssueDependency)
            .where(IssueDependency.id == dep_id)
            .options(selectinload(IssueDependency.target_issue).selectinload(Issue.project))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_dependencies(self, issue_id: uuid.UUID) -> List[IssueDependency]:
        stmt = (
            select(IssueDependency)
            .where(IssueDependency.issue_id == issue_id)
            .options(selectinload(IssueDependency.target_issue).selectinload(Issue.project))
            .order_by(IssueDependency.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def delete_dependency(self, dep: IssueDependency) -> None:
        await self.db.delete(dep)
        await self.db.flush()

    async def get_all_blocks_edges(self, project_id: uuid.UUID) -> List[tuple[uuid.UUID, uuid.UUID]]:
        """Returns all (source_issue_id, blocked_issue_id) directed edges for cycle detection."""
        stmt = (
            select(IssueDependency.issue_id, IssueDependency.target_issue_id)
            .join(Issue, IssueDependency.issue_id == Issue.id)
            .where(
                Issue.project_id == project_id,
                IssueDependency.dependency_type == DependencyType.BLOCKS,
            )
        )
        res = await self.db.execute(stmt)
        return [(r[0], r[1]) for r in res.all()]
