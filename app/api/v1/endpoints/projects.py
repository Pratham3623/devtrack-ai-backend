import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.enums import ProjectRole, ProjectTemplateType
from app.domain.models.user import User
from app.domain.schemas.project import (
    ProjectAnalyticsResponse,
    ProjectCreateRequest,
    ProjectDashboardResponse,
    ProjectMemberAddRequest,
    ProjectMemberResponse,
    ProjectMemberRoleUpdateRequest,
    ProjectPaginatedResponse,
    ProjectResponse,
    ProjectTemplateResponse,
    ProjectUpdateRequest,
)
from app.services.project_service import ProjectService

templates_router = APIRouter()  # mounted at /projects — no UUID conflict
org_router = APIRouter()         # mounted at /organizations — for org-scoped project endpoints


# ── Templates (public, no auth) ─────────────────────────────────────────────
@templates_router.get(
    "/templates",
    response_model=List[ProjectTemplateResponse],
    summary="List Pre-built Project Templates",
)
async def list_project_templates(
    db: AsyncSession = Depends(get_db),
) -> List[ProjectTemplateResponse]:
    service = ProjectService(db)
    return await service.get_templates()


# ── Projects CRUD ────────────────────────────────────────────────────────────
@org_router.post(
    "/{org_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project",
)
async def create_project(
    org_id: uuid.UUID,
    dto: ProjectCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(db)
    project = await service.create_project(org_id, current_user, dto)
    return ProjectResponse.model_validate(project)


@org_router.get(
    "/{org_id}/projects",
    response_model=ProjectPaginatedResponse,
    summary="List Projects (Search, Filter, Pagination)",
)
async def list_projects(
    org_id: uuid.UUID,
    q: Optional[str] = Query(None, description="Search term for name, key or description"),
    template_type: Optional[ProjectTemplateType] = Query(None, description="Filter by template type"),
    include_archived: bool = Query(False, description="Include archived projects"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPaginatedResponse:
    service = ProjectService(db)
    return await service.get_projects(
        org_id=org_id,
        actor=current_user,
        query=q,
        template_type=template_type,
        include_archived=include_archived,
        page=page,
        size=size,
    )


@org_router.get(
    "/{org_id}/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Get Project Details",
)
async def get_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(db)
    project = await service.get_project(org_id, project_id, current_user)
    return ProjectResponse.model_validate(project)


@org_router.patch(
    "/{org_id}/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Update Project Details",
)
async def update_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: ProjectUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(db)
    project = await service.update_project(org_id, project_id, current_user, dto)
    return ProjectResponse.model_validate(project)


@org_router.post(
    "/{org_id}/projects/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive Project",
)
async def archive_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(db)
    project = await service.archive_project(org_id, project_id, current_user)
    return ProjectResponse.model_validate(project)


@org_router.post(
    "/{org_id}/projects/{project_id}/restore",
    response_model=ProjectResponse,
    summary="Restore Archived Project",
)
async def restore_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    service = ProjectService(db)
    project = await service.restore_project(org_id, project_id, current_user)
    return ProjectResponse.model_validate(project)


@org_router.delete(
    "/{org_id}/projects/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Project",
)
async def delete_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = ProjectService(db)
    await service.delete_project(org_id, project_id, current_user)
    return {"message": "Project deleted successfully."}


# ── Dashboard & Analytics ────────────────────────────────────────────────────
@org_router.get(
    "/{org_id}/projects/{project_id}/dashboard",
    response_model=ProjectDashboardResponse,
    summary="Get Project Dashboard Metrics",
)
async def get_project_dashboard(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectDashboardResponse:
    service = ProjectService(db)
    return await service.get_project_dashboard(org_id, project_id, current_user)


@org_router.get(
    "/{org_id}/projects/{project_id}/analytics",
    response_model=ProjectAnalyticsResponse,
    summary="Get Project Analytics & Reports",
)
async def get_project_analytics(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectAnalyticsResponse:
    service = ProjectService(db)
    return await service.get_project_analytics(org_id, project_id, current_user)


# ── Member Management ────────────────────────────────────────────────────────
@org_router.get(
    "/{org_id}/projects/{project_id}/members",
    response_model=List[ProjectMemberResponse],
    summary="List Project Members",
)
async def list_project_members(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectMemberResponse]:
    service = ProjectService(db)
    members = await service.list_project_members(org_id, project_id, current_user)
    return [ProjectMemberResponse.model_validate(m) for m in members]


@org_router.post(
    "/{org_id}/projects/{project_id}/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Member to Project",
)
async def add_project_member(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: ProjectMemberAddRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberResponse:
    service = ProjectService(db)
    member = await service.add_project_member(org_id, project_id, current_user, dto)
    return ProjectMemberResponse.model_validate(member)


@org_router.patch(
    "/{org_id}/projects/{project_id}/members/{user_id}",
    response_model=ProjectMemberResponse,
    summary="Update Project Member Role",
)
async def update_project_member_role(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    dto: ProjectMemberRoleUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMemberResponse:
    service = ProjectService(db)
    member = await service.update_member_role(org_id, project_id, user_id, current_user, dto.role)
    return ProjectMemberResponse.model_validate(member)


@org_router.delete(
    "/{org_id}/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Project Member",
)
async def remove_project_member(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = ProjectService(db)
    await service.remove_member(org_id, project_id, user_id, current_user)
    return {"message": "Project member removed successfully."}
