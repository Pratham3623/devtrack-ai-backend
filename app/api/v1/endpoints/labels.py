import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.label import (
    IssueLabelAssignRequest,
    LabelCreate,
    LabelResponse,
    LabelUpdate,
)
from app.services.label_service import LabelService

router = APIRouter()


@router.post(
    "/{org_id}/projects/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Project Label",
)
async def create_label(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: LabelCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    service = LabelService(db)
    label = await service.create_label(org_id, project_id, current_user, dto)
    return LabelResponse.model_validate(label)


@router.get(
    "/{org_id}/projects/{project_id}/labels",
    response_model=List[LabelResponse],
    summary="List Project Labels",
)
async def list_labels(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[LabelResponse]:
    service = LabelService(db)
    labels = await service.list_labels(org_id, project_id, current_user)
    return [LabelResponse.model_validate(l) for l in labels]


@router.patch(
    "/{org_id}/projects/{project_id}/labels/{label_id}",
    response_model=LabelResponse,
    summary="Update Label",
)
async def update_label(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    label_id: uuid.UUID,
    dto: LabelUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LabelResponse:
    service = LabelService(db)
    label = await service.update_label(org_id, project_id, label_id, current_user, dto)
    return LabelResponse.model_validate(label)


@router.delete(
    "/{org_id}/projects/{project_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Label",
)
async def delete_label(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    label_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = LabelService(db)
    await service.delete_label(org_id, project_id, label_id, current_user)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/labels",
    response_model=List[LabelResponse],
    summary="Assign Label to Issue",
)
async def assign_label_to_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssueLabelAssignRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[LabelResponse]:
    service = LabelService(db)
    labels = await service.assign_label(org_id, project_id, issue_id, dto.label_id, current_user)
    return [LabelResponse.model_validate(l) for l in labels]


@router.delete(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/labels/{label_id}",
    response_model=List[LabelResponse],
    summary="Remove Label from Issue",
)
async def remove_label_from_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    label_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[LabelResponse]:
    service = LabelService(db)
    labels = await service.remove_label(org_id, project_id, issue_id, label_id, current_user)
    return [LabelResponse.model_validate(l) for l in labels]


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/labels",
    response_model=List[LabelResponse],
    summary="List Issue Labels",
)
async def list_issue_labels(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[LabelResponse]:
    service = LabelService(db)
    labels = await service.get_issue_labels(org_id, project_id, issue_id, current_user)
    return [LabelResponse.model_validate(l) for l in labels]
