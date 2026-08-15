import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.logging import logger
from app.domain.models.enums import OrgRole
from app.domain.models.issue import Issue
from app.domain.models.label import Label
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.label import LabelCreate, LabelUpdate
from app.repositories.issue_repository import IssueRepository
from app.repositories.label_repository import LabelRepository
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


class LabelService:
    """Service handling project labels and issue-label associations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LabelRepository(db)
        self.issue_repo = IssueRepository(db)
        self.project_repo = ProjectRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def _check_org_access(self, org_id: uuid.UUID, user_id: uuid.UUID):
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise ForbiddenException("User is not a member of this organization.")
        return membership

    async def _get_project_in_org(self, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project or project.organization_id != org_id:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def create_label(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
        dto: LabelCreate,
    ) -> Label:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        existing = await self.repo.get_by_name(project_id, dto.name)
        if existing:
            raise ValidationException(f"Label '{dto.name}' already exists in this project.")

        label = await self.repo.create_label(
            project_id=project_id,
            name=dto.name,
            color=dto.color,
        )
        await self.db.commit()
        await self.db.refresh(label)
        logger.info(f"Label '{label.name}' created in Project {project_id} by User {actor.id}")
        return label

    async def list_labels(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
    ) -> List[Label]:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        return await self.repo.list_by_project(project_id)

    async def update_label(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        label_id: uuid.UUID,
        actor: User,
        dto: LabelUpdate,
    ) -> Label:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        label = await self.repo.get_by_id(label_id)
        if not label or label.project_id != project_id:
            raise EntityNotFoundException("Label", label_id)

        if dto.name is not None and dto.name != label.name:
            existing = await self.repo.get_by_name(project_id, dto.name)
            if existing:
                raise ValidationException(f"Label '{dto.name}' already exists in this project.")

        label = await self.repo.update_label(label, name=dto.name, color=dto.color)
        await self.db.commit()
        await self.db.refresh(label)
        return label

    async def delete_label(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        label_id: uuid.UUID,
        actor: User,
    ) -> None:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        label = await self.repo.get_by_id(label_id)
        if not label or label.project_id != project_id:
            raise EntityNotFoundException("Label", label_id)

        await self.repo.delete_label(label)
        await self.db.commit()

    async def assign_label(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        label_id: uuid.UUID,
        actor: User,
    ) -> List[Label]:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        issue = await self.issue_repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)

        label = await self.repo.get_by_id(label_id)
        if not label or label.project_id != project_id:
            raise EntityNotFoundException("Label", label_id)

        await self.repo.assign_label_to_issue(issue.id, label.id)
        await self.db.commit()
        return await self.repo.get_issue_labels(issue.id)

    async def remove_label(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        label_id: uuid.UUID,
        actor: User,
    ) -> List[Label]:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        issue = await self.issue_repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)

        await self.repo.remove_label_from_issue(issue.id, label_id)
        await self.db.commit()
        return await self.repo.get_issue_labels(issue.id)

    async def get_issue_labels(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
    ) -> List[Label]:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        return await self.repo.get_issue_labels(issue_id)
