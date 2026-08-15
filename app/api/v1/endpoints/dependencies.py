import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.dependency import (
    DependencyCreate,
    DependencyResponse,
    LinkedIssueResponse,
    SubtaskCreate,
    SubtaskProgressResponse,
)
from app.domain.schemas.issue import IssueResponse
from app.services.dependency_service import DependencyService

router = APIRouter()


# ---------------------------------------------------------------------------
# SUBTASKS
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/subtasks",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Subtask under Parent Issue",
)
async def create_subtask(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: SubtaskCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = DependencyService(db)
    subtask = await service.create_subtask(org_id, project_id, issue_id, current_user, dto)
    return IssueResponse.model_validate(subtask)


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/subtasks",
    response_model=List[IssueResponse],
    summary="List Subtasks for Issue",
)
async def list_subtasks(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[IssueResponse]:
    service = DependencyService(db)
    subtasks = await service.list_subtasks(org_id, project_id, issue_id, current_user)
    return [IssueResponse.model_validate(s) for s in subtasks]


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/subtasks/progress",
    response_model=SubtaskProgressResponse,
    summary="Get Subtask Completion Progress",
)
async def get_subtask_progress(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SubtaskProgressResponse:
    service = DependencyService(db)
    return await service.get_subtask_progress(org_id, project_id, issue_id, current_user)


# ---------------------------------------------------------------------------
# DEPENDENCIES
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Issue Dependency (BLOCKS, BLOCKED_BY, RELATES_TO)",
)
async def create_dependency(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: DependencyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DependencyResponse:
    service = DependencyService(db)
    dep = await service.create_dependency(org_id, project_id, issue_id, current_user, dto)
    return DependencyResponse.model_validate(dep)


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/dependencies",
    response_model=List[DependencyResponse],
    summary="List Issue Dependencies",
)
async def list_dependencies(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[DependencyResponse]:
    service = DependencyService(db)
    deps = await service.list_dependencies(org_id, project_id, issue_id, current_user)
    return [DependencyResponse.model_validate(d) for d in deps]


@router.delete(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Issue Dependency",
)
async def delete_dependency(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dependency_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = DependencyService(db)
    await service.delete_dependency(org_id, project_id, issue_id, dependency_id, current_user)
