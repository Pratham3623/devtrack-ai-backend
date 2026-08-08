import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.issue import Issue
from app.domain.models.project import Project
from app.repositories.base_repository import BaseRepository


class IssueRepository(BaseRepository[Issue]):
    """Repository handling data access and concurrency-safe issue numbering for Issues."""

    def __init__(self, db: AsyncSession):
        super().__init__(Issue, db)

    async def get_next_issue_number(self, project_id: uuid.UUID) -> int:
        """
        Calculates next sequential issue_number for project.
        Uses pessimistic row-level locking on parent Project to prevent race conditions.
        """
        # 1. Lock parent project row for duration of transaction
        lock_stmt = select(Project.id).where(Project.id == project_id).with_for_update()
        await self.db.execute(lock_stmt)

        # 2. Get current maximum issue_number
        max_stmt = select(func.coalesce(func.max(Issue.issue_number), 0)).where(
            Issue.project_id == project_id
        )
        res = await self.db.execute(max_stmt)
        current_max = res.scalar() or 0
        return current_max + 1

    async def create_issue(
        self,
        project_id: uuid.UUID,
        reporter_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[uuid.UUID] = None,
    ) -> Issue:
        """Creates a new issue with automatically assigned sequential issue_number."""
        next_num = await self.get_next_issue_number(project_id)
        
        issue_kwargs = {
            "project_id": project_id,
            "issue_number": next_num,
            "title": title,
            "description": description,
            "reporter_id": reporter_id,
            "assignee_id": assignee_id,
        }
        if status:
            issue_kwargs["status"] = status
        if priority:
            issue_kwargs["priority"] = priority

        issue = Issue(**issue_kwargs)
        self.db.add(issue)
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def get_by_project_and_number(
        self, project_id: uuid.UUID, issue_number: int
    ) -> Optional[Issue]:
        """Fetch issue by project UUID and sequential issue number."""
        stmt = (
            select(Issue)
            .where(Issue.project_id == project_id, Issue.issue_number == issue_number)
            .options(selectinload(Issue.project))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_with_project(self, issue_id: uuid.UUID) -> Optional[Issue]:
        """Fetch issue with loaded project relationship for identifier resolution."""
        stmt = select(Issue).where(Issue.id == issue_id).options(selectinload(Issue.project))
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_project(
        self, project_id: uuid.UUID, include_archived: bool = False
    ) -> List[Issue]:
        """List issues belonging to a project."""
        stmt = select(Issue).where(Issue.project_id == project_id)
        if not include_archived:
            stmt = stmt.where(Issue.is_archived == False)
        stmt = stmt.order_by(Issue.issue_number.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_project_issues_paginated(
        self,
        project_id: uuid.UUID,
        query_str: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[uuid.UUID] = None,
        reporter_id: Optional[uuid.UUID] = None,
        include_archived: bool = False,
        sort_by: str = "issue_number",
        sort_order: str = "asc",
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Issue], int]:
        """Fetch paginated, filtered, searchable, and sorted project issues."""
        stmt = select(Issue).where(Issue.project_id == project_id).options(selectinload(Issue.project))

        if not include_archived:
            stmt = stmt.where(Issue.is_archived == False)

        if status:
            stmt = stmt.where(Issue.status == status)

        if priority:
            stmt = stmt.where(Issue.priority == priority)

        if assignee_id:
            stmt = stmt.where(Issue.assignee_id == assignee_id)

        if reporter_id:
            stmt = stmt.where(Issue.reporter_id == reporter_id)

        if query_str:
            pattern = f"%{query_str}%"
            stmt = stmt.where((Issue.title.ilike(pattern)) | (Issue.description.ilike(pattern)))

        # Count total matching
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Sorting
        sort_column = getattr(Issue, sort_by, Issue.issue_number)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        stmt = stmt.offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all()), total
