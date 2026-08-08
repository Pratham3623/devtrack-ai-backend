import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.enums import IssuePriority, IssueStatus
from app.domain.models.user import User
from app.domain.schemas.issue import (
    IssueAssignRequest,
    IssueCreateRequest,
    IssuePaginatedResponse,
    IssuePriorityUpdateRequest,
    IssueResponse,
    IssueStatusUpdateRequest,
    IssueUpdateRequest,
)
from app.services.issue_service import IssueService

router = APIRouter()


@router.post(
    "/{org_id}/projects/{project_id}/issues",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Issue",
)
async def create_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: IssueCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.create_issue(org_id, project_id, current_user, dto)
    return IssueResponse.model_validate(issue)


@router.get(
    "/{org_id}/projects/{project_id}/issues",
    response_model=IssuePaginatedResponse,
    summary="List Issues (Search, Filter, Sort, Pagination)",
)
async def list_issues(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    q: Optional[str] = Query(None, description="Search term for title or description"),
    status: Optional[IssueStatus] = Query(None, description="Filter by IssueStatus"),
    priority: Optional[IssuePriority] = Query(None, description="Filter by IssuePriority"),
    assignee_id: Optional[uuid.UUID] = Query(None, description="Filter by assignee UUID"),
    reporter_id: Optional[uuid.UUID] = Query(None, description="Filter by reporter UUID"),
    include_archived: bool = Query(False, description="Include archived issues"),
    sort_by: str = Query("issue_number", description="Sort field (issue_number, created_at, updated_at, status, priority)"),
    sort_order: str = Query("asc", description="Sort direction (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssuePaginatedResponse:
    service = IssueService(db)
    return await service.get_issues_paginated(
        org_id=org_id,
        project_id=project_id,
        actor=current_user,
        q=q,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        reporter_id=reporter_id,
        include_archived=include_archived,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        size=size,
    )


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}",
    response_model=IssueResponse,
    summary="Get Issue Details by UUID",
)
async def get_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.get_issue(org_id, project_id, issue_id, current_user)
    return IssueResponse.model_validate(issue)


@router.get(
    "/{org_id}/projects/{project_id}/issues/number/{issue_number}",
    response_model=IssueResponse,
    summary="Get Issue Details by Issue Number (e.g. DEV-1)",
)
async def get_issue_by_number(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_number: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.get_issue_by_number(org_id, project_id, issue_number, current_user)
    return IssueResponse.model_validate(issue)


@router.patch(
    "/{org_id}/projects/{project_id}/issues/{issue_id}",
    response_model=IssueResponse,
    summary="Update Issue Details",
)
async def update_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssueUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.update_issue(org_id, project_id, issue_id, current_user, dto)
    return IssueResponse.model_validate(issue)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/archive",
    response_model=IssueResponse,
    summary="Archive Issue",
)
async def archive_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.archive_issue(org_id, project_id, issue_id, current_user)
    return IssueResponse.model_validate(issue)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/restore",
    response_model=IssueResponse,
    summary="Restore Archived Issue",
)
async def restore_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.restore_issue(org_id, project_id, issue_id, current_user)
    return IssueResponse.model_validate(issue)


@router.patch(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/status",
    response_model=IssueResponse,
    summary="Change Issue Status",
)
async def change_status(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssueStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.change_status(org_id, project_id, issue_id, current_user, dto.status)
    return IssueResponse.model_validate(issue)


@router.patch(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/priority",
    response_model=IssueResponse,
    summary="Change Issue Priority",
)
async def change_priority(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssuePriorityUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.change_priority(org_id, project_id, issue_id, current_user, dto.priority)
    return IssueResponse.model_validate(issue)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/assign",
    response_model=IssueResponse,
    summary="Assign Issue to Member",
)
async def assign_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssueAssignRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.assign_issue(org_id, project_id, issue_id, current_user, dto.assignee_id)
    return IssueResponse.model_validate(issue)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/unassign",
    response_model=IssueResponse,
    summary="Unassign Issue",
)
async def unassign_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = IssueService(db)
    issue = await service.unassign_issue(org_id, project_id, issue_id, current_user)
    return IssueResponse.model_validate(issue)
