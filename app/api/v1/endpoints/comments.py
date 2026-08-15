import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.comment import (
    ActivityItemResponse,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
)
from app.services.comment_service import CommentService

router = APIRouter()


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Comment to Issue",
)
async def create_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    service = CommentService(db)
    comment = await service.create_comment(org_id, project_id, issue_id, current_user, dto)
    return CommentResponse.model_validate(comment)


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/comments",
    response_model=List[CommentResponse],
    summary="List Issue Comments",
)
async def list_comments(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[CommentResponse]:
    service = CommentService(db)
    comments = await service.list_comments(org_id, project_id, issue_id, current_user)
    return [CommentResponse.model_validate(c) for c in comments]


@router.patch(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/comments/{comment_id}",
    response_model=CommentResponse,
    summary="Update Comment",
)
async def update_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    comment_id: uuid.UUID,
    dto: CommentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    service = CommentService(db)
    comment = await service.update_comment(
        org_id, project_id, issue_id, comment_id, current_user, dto
    )
    return CommentResponse.model_validate(comment)


@router.delete(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Comment",
)
async def delete_comment(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = CommentService(db)
    await service.delete_comment(org_id, project_id, issue_id, comment_id, current_user)


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/activity",
    response_model=List[ActivityItemResponse],
    summary="Get Issue Activity Stream & Timeline",
)
async def get_issue_activity(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[ActivityItemResponse]:
    service = CommentService(db)
    return await service.get_activity_timeline(org_id, project_id, issue_id, current_user)
