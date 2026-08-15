import uuid
from typing import List, Optional, Set, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.logging import logger
from app.domain.models.dependency import DependencyType, IssueDependency
from app.domain.models.issue import Issue
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.dependency import (
    DependencyCreate,
    SubtaskCreate,
    SubtaskProgressResponse,
)
from app.repositories.dependency_repository import DependencyRepository
from app.repositories.issue_repository import IssueRepository
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


class DependencyService:
    """Business logic for Subtasks and Issue Dependencies with Graph Cycle Detection."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DependencyRepository(db)
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

    async def _get_issue_in_project(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID
    ) -> Issue:
        await self._get_project_in_org(org_id, project_id)
        issue = await self.issue_repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)
        return issue

    # ---------------------------------------------------------------------------
    # SUBTASKS
    # ---------------------------------------------------------------------------

    async def create_subtask(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        parent_issue_id: uuid.UUID,
        actor: User,
        dto: SubtaskCreate,
    ) -> Issue:
        await self._check_org_access(org_id, actor.id)
        parent_issue = await self._get_issue_in_project(org_id, project_id, parent_issue_id)

        # 1-level hierarchy constraint: Parent cannot itself be a subtask
        if parent_issue.parent_id is not None:
            raise ValidationException("Subtasks cannot be nested more than 1 level deep.")

        # Generate issue number sequentially
        issue_number = await self.issue_repo.get_next_issue_number(project_id)

        subtask = Issue(
            project_id=project_id,
            issue_number=issue_number,
            title=dto.title,
            description=dto.description,
            status=dto.status,
            priority=dto.priority,
            reporter_id=actor.id,
            assignee_id=dto.assignee_id,
            parent_id=parent_issue.id,
        )
        self.db.add(subtask)
        await self.db.flush()
        await self.db.commit()
        return await self.issue_repo.get_with_project(subtask.id)

    async def list_subtasks(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        parent_issue_id: uuid.UUID,
        actor: User,
    ) -> List[Issue]:
        await self._check_org_access(org_id, actor.id)
        await self._get_issue_in_project(org_id, project_id, parent_issue_id)
        return await self.repo.list_subtasks(parent_issue_id)

    async def get_subtask_progress(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        parent_issue_id: uuid.UUID,
        actor: User,
    ) -> SubtaskProgressResponse:
        await self._check_org_access(org_id, actor.id)
        await self._get_issue_in_project(org_id, project_id, parent_issue_id)

        total, completed = await self.repo.get_subtask_progress(parent_issue_id)
        pct = (completed / total * 100.0) if total > 0 else 0.0
        return SubtaskProgressResponse(
            total_subtasks=total,
            completed_subtasks=completed,
            completion_percentage=round(pct, 1),
        )

    # ---------------------------------------------------------------------------
    # DEPENDENCIES & CYCLE DETECTION
    # ---------------------------------------------------------------------------

    async def create_dependency(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        dto: DependencyCreate,
    ) -> IssueDependency:
        await self._check_org_access(org_id, actor.id)
        source_issue = await self._get_issue_in_project(org_id, project_id, issue_id)
        target_issue = await self._get_issue_in_project(org_id, project_id, dto.target_issue_id)

        # Self-reference check
        if source_issue.id == target_issue.id:
            raise ValidationException("An issue cannot depend on itself.")

        dep_type = dto.dependency_type
        eff_source = source_issue.id
        eff_target = target_issue.id

        # Normalize BLOCKED_BY to BLOCKS (if A is BLOCKED_BY B, then B BLOCKS A)
        if dep_type == DependencyType.BLOCKED_BY:
            eff_source = target_issue.id
            eff_target = source_issue.id
            dep_type = DependencyType.BLOCKS

        # Cycle detection for BLOCKS dependencies
        if dep_type == DependencyType.BLOCKS:
            existing_edges = await self.repo.get_all_blocks_edges(project_id)
            # Add prospective new edge (eff_source -> eff_target)
            existing_edges.append((eff_source, eff_target))

            if self._has_cycle(existing_edges):
                raise ValidationException(
                    "Adding this dependency would create a circular blocking chain."
                )

        dep = await self.repo.create_dependency(
            issue_id=source_issue.id,
            target_issue_id=target_issue.id,
            dep_type=dto.dependency_type,
        )
        await self.db.commit()
        return dep

    def _has_cycle(self, edges: List[tuple[uuid.UUID, uuid.UUID]]) -> bool:
        """DFS graph cycle detection for directed BLOCKS edges."""
        adj: Dict[uuid.UUID, List[uuid.UUID]] = {}
        for src, dst in edges:
            if src not in adj:
                adj[src] = []
            adj[src].append(dst)

        visited: Set[uuid.UUID] = set()
        rec_stack: Set[uuid.UUID] = set()

        def dfs(node: uuid.UUID) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in list(adj.keys()):
            if node not in visited:
                if dfs(node):
                    return True
        return False

    async def list_dependencies(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
    ) -> List[IssueDependency]:
        await self._check_org_access(org_id, actor.id)
        await self._get_issue_in_project(org_id, project_id, issue_id)
        return await self.repo.list_dependencies(issue_id)

    async def delete_dependency(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        dependency_id: uuid.UUID,
        actor: User,
    ) -> None:
        await self._check_org_access(org_id, actor.id)
        await self._get_issue_in_project(org_id, project_id, issue_id)

        dep = await self.repo.get_by_id(dependency_id)
        if not dep or dep.issue_id != issue_id:
            raise EntityNotFoundException("IssueDependency", dependency_id)

        await self.repo.delete_dependency(dep)
        await self.db.commit()
