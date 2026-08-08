import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import logger
from app.domain.models.enums import AuditAction, OrgRole, ProjectRole, ProjectTemplateType
from app.domain.models.project import Project, ProjectMember
from app.domain.models.user import User
from app.domain.schemas.project import (
    ProjectAnalyticsResponse,
    ProjectCreateRequest,
    ProjectDashboardResponse,
    ProjectMemberAddRequest,
    ProjectPaginatedResponse,
    ProjectResponse,
    ProjectTemplateResponse,
    ProjectUpdateRequest,
)
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


TEMPLATES_CATALOG: Dict[ProjectTemplateType, Dict[str, Any]] = {
    ProjectTemplateType.KANBAN: {
        "name": "Agile Kanban Board",
        "description": "Continuous delivery template with Backlog, In Progress, Code Review, and Done columns.",
        "default_columns": ["Backlog", "In Progress", "In Review", "Done"],
        "default_settings": {"wip_limits": {"In Progress": 5}, "enable_sprints": False},
    },
    ProjectTemplateType.SCRUM: {
        "name": "Scrum Sprint Tracker",
        "description": "Iterative sprint planning template with Story Points, Sprints, Product Backlog, and Burndown metrics.",
        "default_columns": ["Sprint Backlog", "In Progress", "Testing", "Completed"],
        "default_settings": {"enable_sprints": True, "sprint_duration_weeks": 2},
    },
    ProjectTemplateType.BUG_TRACKING: {
        "name": "Software Defect & Issue Tracker",
        "description": "High-priority defect triage workflow with Triage, Investigating, Fix In Progress, and Resolved columns.",
        "default_columns": ["Reported", "Triaged", "In Fix", "Verified", "Closed"],
        "default_settings": {"require_reproduction_steps": True},
    },
    ProjectTemplateType.ROADMAP: {
        "name": "Product Strategy & Feature Roadmap",
        "description": "Strategic milestone tracking template with Now, Next, Later, and Completed horizons.",
        "default_columns": ["Discovery", "Now", "Next", "Later", "Shipped"],
        "default_settings": {"enable_milestones": True},
    },
    ProjectTemplateType.CUSTOM: {
        "name": "Custom Project Board",
        "description": "Blank flexible canvas tailored for unique engineering workflows.",
        "default_columns": ["To Do", "In Progress", "Done"],
        "default_settings": {},
    },
}


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProjectRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def _check_org_access(self, org_id: uuid.UUID, user_id: uuid.UUID, allowed_roles: List[OrgRole]):
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership or membership.role not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenException(f"Organization role in [{roles_str}] required.")
        return membership

    async def _get_project_by_id(self, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """Fetch project directly by ID (ignores archive state). Raises if not found in org."""
        from sqlalchemy import select
        stmt = select(Project).where(Project.id == project_id, Project.organization_id == org_id)
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise EntityNotFoundException("Project", project_id)
        return project

    def _generate_project_key(self, name: str) -> str:
        words = name.strip().split()
        if len(words) >= 2:
            key = "".join([w[0].upper() for w in words[:4]])
        else:
            key = name[:3].upper()
        # Clean non-alphanumeric
        key = "".join([c for c in key if c.isalnum()])
        if len(key) < 2:
            key = (key + "PRJ")[:3]
        return key

    async def get_templates(self) -> List[ProjectTemplateResponse]:
        """List available project templates."""
        return [
            ProjectTemplateResponse(
                template_type=ttype,
                name=meta["name"],
                description=meta["description"],
                default_columns=meta["default_columns"],
                default_settings=meta["default_settings"],
            )
            for ttype, meta in TEMPLATES_CATALOG.items()
        ]

    async def create_project(
        self, org_id: uuid.UUID, actor: User, dto: ProjectCreateRequest
    ) -> Project:
        """Create a new project within organization."""
        await self._check_org_access(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        key = (dto.key or self._generate_project_key(dto.name)).upper()
        existing_key = await self.repo.get_by_key(org_id, key)
        if existing_key:
            key = f"{key}{uuid.uuid4().hex[:3].upper()}"

        template_meta = TEMPLATES_CATALOG.get(dto.template_type, TEMPLATES_CATALOG[ProjectTemplateType.CUSTOM])
        settings = dto.settings_json or template_meta["default_settings"]
        settings["columns"] = template_meta["default_columns"]

        project = Project(
            organization_id=org_id,
            name=dto.name,
            key=key,
            description=dto.description,
            logo_url=dto.logo_url,
            owner_id=actor.id,
            template_type=dto.template_type,
            is_archived=False,
            settings_json=settings,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)

        # Add Creator as LEAD
        member = ProjectMember(
            project_id=project.id,
            user_id=actor.id,
            role=ProjectRole.LEAD,
        )
        self.db.add(member)
        await self.db.commit()

        logger.info(f"Project '{project.name}' (Key: {project.key}) created in Org {org_id}")
        return project

    async def get_projects(
        self,
        org_id: uuid.UUID,
        actor: User,
        query: Optional[str] = None,
        template_type: Optional[ProjectTemplateType] = None,
        include_archived: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> ProjectPaginatedResponse:
        """Fetch paginated, searchable, filtered projects."""
        await self._check_org_access(
            org_id,
            actor.id,
            [
                OrgRole.OWNER,
                OrgRole.ADMIN,
                OrgRole.PROJECT_MANAGER,
                OrgRole.DEVELOPER,
                OrgRole.VIEWER,
                OrgRole.MEMBER,
                OrgRole.GUEST,
            ],
        )

        offset = (page - 1) * size
        projects, total = await self.repo.get_org_projects_paginated(
            org_id=org_id,
            query_str=query,
            template_type=template_type,
            include_archived=include_archived,
            offset=offset,
            limit=size,
        )

        pages = math.ceil(total / size) if size > 0 else 0
        items = [ProjectResponse.model_validate(p) for p in projects]

        return ProjectPaginatedResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_project(self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User) -> Project:
        """Get project details."""
        await self._check_org_access(
            org_id,
            actor.id,
            [
                OrgRole.OWNER,
                OrgRole.ADMIN,
                OrgRole.PROJECT_MANAGER,
                OrgRole.DEVELOPER,
                OrgRole.VIEWER,
                OrgRole.MEMBER,
                OrgRole.GUEST,
            ],
        )
        project = await self.repo.get_by_id(project_id)
        if not project or project.organization_id != org_id:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def update_project(
        self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User, dto: ProjectUpdateRequest
    ) -> Project:
        """Update project details."""
        await self._check_org_access(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        project = await self.get_project(org_id, project_id, actor)

        if dto.name is not None:
            project.name = dto.name
        if dto.key is not None:
            project.key = dto.key.upper()
        if dto.description is not None:
            project.description = dto.description
        if dto.logo_url is not None:
            project.logo_url = dto.logo_url
        if dto.settings_json is not None:
            project.settings_json = dto.settings_json
        if dto.is_archived is not None:
            project.is_archived = dto.is_archived
            if dto.is_archived:
                project.archived_at = datetime.now(timezone.utc)
            else:
                project.archived_at = None

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def archive_project(self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User) -> Project:
        """Archive a project."""
        await self._check_org_access(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        project = await self._get_project_by_id(org_id, project_id)
        project.is_archived = True
        project.archived_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def restore_project(self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User) -> Project:
        """Restore an archived project."""
        await self._check_org_access(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        project = await self._get_project_by_id(org_id, project_id)
        project.is_archived = False
        project.archived_at = None
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete_project(self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User) -> None:
        """Hard delete a project."""
        await self._check_org_access(org_id, actor.id, [OrgRole.OWNER])
        project = await self.get_project(org_id, project_id, actor)
        await self.db.delete(project)
        await self.db.commit()

    async def get_project_dashboard(
        self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User
    ) -> ProjectDashboardResponse:
        """Get project dashboard metrics."""
        project = await self.get_project(org_id, project_id, actor)
        members = await self.repo.get_project_members(project_id)
        settings = project.settings_json or {}
        columns = settings.get("columns", ["To Do", "In Progress", "Done"])

        # Operational metrics placeholders (ready for Task entity integration)
        return ProjectDashboardResponse(
            project_id=project.id,
            project_name=project.name,
            project_key=project.key,
            total_members=len(members),
            open_issues_count=12,
            completed_issues_count=28,
            health_score=94,
            completion_percentage=70.0,
            workflow_columns=columns,
        )

    async def get_project_analytics(
        self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User
    ) -> ProjectAnalyticsResponse:
        """Get project analytics & velocity charts data."""
        project = await self.get_project(org_id, project_id, actor)
        members = await self.repo.get_project_members(project_id)

        velocity_trend = [
            {"sprint": "Sprint 1", "completed": 20, "committed": 24},
            {"sprint": "Sprint 2", "completed": 25, "committed": 25},
            {"sprint": "Sprint 3", "completed": 28, "committed": 30},
        ]

        status_dist = {
            "Backlog": 5,
            "In Progress": 8,
            "Code Review": 4,
            "Done": 28,
        }

        workload = [
            {"user_name": m.user.full_name, "assigned_issues": 4} for m in members[:5]
        ]

        return ProjectAnalyticsResponse(
            project_id=project.id,
            velocity_trend=velocity_trend,
            issue_status_distribution=status_dist,
            member_workload=workload,
            created_vs_resolved={"created": 45, "resolved": 37},
        )

    async def add_project_member(
        self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User, dto: ProjectMemberAddRequest
    ) -> ProjectMember:
        """Add member to project."""
        await self.get_project(org_id, project_id, actor)
        await self._check_org_access(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        existing = await self.repo.get_member(project_id, dto.user_id)
        if existing:
            raise ValidationException("User is already a project member.")

        member = ProjectMember(
            project_id=project_id,
            user_id=dto.user_id,
            role=dto.role,
        )
        self.db.add(member)
        await self.db.commit()

        from sqlalchemy import select
        res = await self.db.execute(
            select(ProjectMember).options(selectinload(ProjectMember.user)).where(ProjectMember.id == member.id)
        )
        return res.scalar_one()

    async def list_project_members(
        self, org_id: uuid.UUID, project_id: uuid.UUID, actor: User
    ) -> List[ProjectMember]:
        """List members of a project."""
        await self.get_project(org_id, project_id, actor)
        return await self.repo.get_project_members(project_id)

    async def update_member_role(
        self, org_id: uuid.UUID, project_id: uuid.UUID, target_user_id: uuid.UUID, actor: User, new_role: ProjectRole
    ) -> ProjectMember:
        """Update member role in project."""
        await self.get_project(org_id, project_id, actor)
        await self._check_org_access(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        member = await self.repo.get_member(project_id, target_user_id)
        if not member:
            raise EntityNotFoundException("ProjectMember", target_user_id)

        member.role = new_role
        await self.db.commit()

        # Re-fetch with eager-loaded user to avoid MissingGreenlet during serialization
        from sqlalchemy import select
        stmt = (
            select(ProjectMember)
            .options(selectinload(ProjectMember.user))
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == target_user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def remove_member(
        self, org_id: uuid.UUID, project_id: uuid.UUID, target_user_id: uuid.UUID, actor: User
    ) -> None:
        """Remove member from project."""
        await self.get_project(org_id, project_id, actor)
        await self._check_org_access(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        member = await self.repo.get_member(project_id, target_user_id)
        if member:
            await self.db.delete(member)
            await self.db.commit()

