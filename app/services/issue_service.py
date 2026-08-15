import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import logger
from app.domain.models.enums import IssuePriority, IssueStatus, OrgRole
from app.domain.models.issue import Issue
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.issue import IssueCreate, IssuePaginatedResponse, IssueResponse, IssueUpdate
from app.repositories.issue_repository import IssueRepository
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


class IssueService:
    """Service handling business logic, validation, authorization, and workflow state transitions for Issues."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = IssueRepository(db)
        self.project_repo = ProjectRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def _check_org_access(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: Optional[List[OrgRole]] = None,
    ):
        """Verify actor has access to organization."""
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise ForbiddenException("User is not a member of this organization.")
        if allowed_roles and membership.role not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenException(f"Organization role in [{roles_str}] required.")
        return membership

    async def _validate_user_in_org(self, org_id: uuid.UUID, user_id: uuid.UUID):
        """Verify target user is a member of the organization (e.g. for assignment/reporter)."""
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise ValidationException(f"User '{user_id}' is not a member of this organization.")
        return membership

    async def _get_project_in_org(self, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """Fetch project and verify it belongs to specified organization."""
        project = await self.project_repo.get_by_id(project_id)
        if not project or project.organization_id != org_id:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def create_issue(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
        dto: IssueCreate,
    ) -> Issue:
        """Create a new issue within a project with concurrent-safe sequential issue numbering."""
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        if dto.assignee_id:
            await self._validate_user_in_org(org_id, dto.assignee_id)

        issue = await self.repo.create_issue(
            project_id=project_id,
            reporter_id=actor.id,
            title=dto.title,
            description=dto.description,
            status=dto.status,
            priority=dto.priority,
            assignee_id=dto.assignee_id,
        )
        logger.info(
            f"Issue '{issue.title}' (Number #{issue.issue_number}) created in Project {project_id} by User {actor.id}"
        )
        return issue

    async def get_issue(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, actor: User
    ) -> Issue:
        """Fetch issue by UUID."""
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        issue = await self.repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)
        return issue

    async def get_issue_by_number(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_number: int, actor: User
    ) -> Issue:
        """Fetch issue by sequential issue number (e.g. DEV-1)."""
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        issue = await self.repo.get_by_project_and_number(project_id, issue_number)
        if not issue:
            raise EntityNotFoundException("Issue", f"#{issue_number}")
        return issue

    async def list_issues(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
        include_archived: bool = False,
        status: Optional[IssueStatus] = None,
        priority: Optional[IssuePriority] = None,
        assignee_id: Optional[uuid.UUID] = None,
    ) -> List[Issue]:
        """List issues for a project with optional filtering."""
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        stmt = select(Issue).where(Issue.project_id == project_id).options(selectinload(Issue.project))
        if not include_archived:
            stmt = stmt.where(Issue.is_archived == False)
        if status:
            stmt = stmt.where(Issue.status == status)
        if priority:
            stmt = stmt.where(Issue.priority == priority)
        if assignee_id:
            stmt = stmt.where(Issue.assignee_id == assignee_id)

        stmt = stmt.order_by(Issue.issue_number.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_issues_paginated(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
        q: Optional[str] = None,
        status: Optional[IssueStatus] = None,
        priority: Optional[IssuePriority] = None,
        assignee_id: Optional[uuid.UUID] = None,
        reporter_id: Optional[uuid.UUID] = None,
        label_id: Optional[uuid.UUID] = None,
        include_archived: bool = False,
        sort_by: str = "issue_number",
        sort_order: str = "asc",
        page: int = 1,
        size: int = 20,
    ) -> IssuePaginatedResponse:
        """Fetch paginated, searchable, filtered, sorted project issues."""
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        offset = (page - 1) * size
        issues, total = await self.repo.get_project_issues_paginated(
            project_id=project_id,
            query_str=q,
            status=status.value if status else None,
            priority=priority.value if priority else None,
            assignee_id=assignee_id,
            reporter_id=reporter_id,
            label_id=label_id,
            include_archived=include_archived,
            sort_by=sort_by,
            sort_order=sort_order,
            offset=offset,
            limit=size,
        )

        pages = math.ceil(total / size) if size > 0 else 0
        items = [IssueResponse.model_validate(i) for i in issues]

        return IssuePaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def update_issue(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        dto: IssueUpdate,
    ) -> Issue:
        """Update issue details (title, description, status, priority, assignee)."""
        await self._check_org_access(org_id, actor.id)
        issue = await self.get_issue(org_id, project_id, issue_id, actor)

        if dto.assignee_id is not None:
            await self._validate_user_in_org(org_id, dto.assignee_id)
            issue.assignee_id = dto.assignee_id

        if dto.title is not None:
            issue.title = dto.title
        if dto.description is not None:
            issue.description = dto.description
        if dto.status is not None:
            issue.status = dto.status
        if dto.priority is not None:
            issue.priority = dto.priority

        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def archive_issue(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, actor: User
    ) -> Issue:
        """Archive (soft-delete) an issue."""
        await self._check_org_access(org_id, actor.id)
        issue = await self.get_issue(org_id, project_id, issue_id, actor)

        issue.is_archived = True
        issue.archived_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(issue)
        logger.info(f"Issue {issue_id} archived by User {actor.id}")
        return issue

    async def restore_issue(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, actor: User
    ) -> Issue:
        """Restore an archived issue."""
        await self._check_org_access(org_id, actor.id)
        issue = await self.get_issue(org_id, project_id, issue_id, actor)

        issue.is_archived = False
        issue.archived_at = None

        await self.db.commit()
        await self.db.refresh(issue)
        logger.info(f"Issue {issue_id} restored by User {actor.id}")
        return issue

    async def change_status(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        new_status: IssueStatus,
    ) -> Issue:
        """Transition issue workflow status."""
        await self._check_org_access(org_id, actor.id)
        issue = await self.get_issue(org_id, project_id, issue_id, actor)

        issue.status = new_status
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def change_priority(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        new_priority: IssuePriority,
    ) -> Issue:
        """Update issue priority."""
        await self._check_org_access(org_id, actor.id)
        issue = await self.get_issue(org_id, project_id, issue_id, actor)

        issue.priority = new_priority
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def assign_issue(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        assignee_id: Optional[uuid.UUID],
    ) -> Issue:
        """Assign issue to a valid organization member or unassign if None."""
        await self._check_org_access(org_id, actor.id)
        if assignee_id is not None:
            await self._validate_user_in_org(org_id, assignee_id)

        issue = await self.get_issue(org_id, project_id, issue_id, actor)
        issue.assignee_id = assignee_id
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def unassign_issue(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID, actor: User
    ) -> Issue:
        """Remove assignee from issue."""
        return await self.assign_issue(org_id, project_id, issue_id, actor, assignee_id=None)

    async def change_reporter(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        new_reporter_id: uuid.UUID,
    ) -> Issue:
        """Update issue reporter."""
        await self._check_org_access(org_id, actor.id)
        await self._validate_user_in_org(org_id, new_reporter_id)

        issue = await self.get_issue(org_id, project_id, issue_id, actor)
        issue.reporter_id = new_reporter_id
        await self.db.commit()
        await self.db.refresh(issue)
        return issue
