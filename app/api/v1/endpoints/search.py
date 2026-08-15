import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.search import (
    GlobalSearchResponse,
    SavedSearchCreateRequest,
    SavedSearchResponse,
)
from app.services.search_service import SearchService

router = APIRouter()


@router.get(
    "/{org_id}/search",
    response_model=GlobalSearchResponse,
    summary="Global Enterprise Search across Issues, Projects, Comments & Members",
)
async def global_search(
    org_id: uuid.UUID,
    q: str = Query("", description="Full text search query string"),
    entity_types: Optional[List[str]] = Query(None, description="Entity types to search (issue, project, comment, member)"),
    status: Optional[str] = Query(None, description="Filter by issue status"),
    priority: Optional[str] = Query(None, description="Filter by issue priority"),
    project_id: Optional[uuid.UUID] = Query(None, description="Filter by specific project UUID"),
    limit: int = Query(30, ge=1, le=100, description="Max results limit"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GlobalSearchResponse:
    service = SearchService(db)
    return await service.global_search(
        org_id=org_id,
        actor=current_user,
        query=q,
        entity_types=entity_types,
        status=status,
        priority=priority,
        project_id=project_id,
        limit=limit,
    )


@router.post(
    "/{org_id}/saved-searches",
    response_model=SavedSearchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Saved Search Preset",
)
async def create_saved_search(
    org_id: uuid.UUID,
    dto: SavedSearchCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchResponse:
    service = SearchService(db)
    saved = await service.create_saved_search(org_id, current_user, dto)
    return SavedSearchResponse.model_validate(saved)


@router.get(
    "/{org_id}/saved-searches",
    response_model=List[SavedSearchResponse],
    summary="List Saved Search Presets",
)
async def list_saved_searches(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[SavedSearchResponse]:
    service = SearchService(db)
    searches = await service.list_saved_searches(org_id, current_user)
    return [SavedSearchResponse.model_validate(s) for s in searches]


@router.delete(
    "/{org_id}/saved-searches/{saved_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Saved Search Preset",
)
async def delete_saved_search(
    org_id: uuid.UUID,
    saved_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = SearchService(db)
    await service.delete_saved_search(org_id, current_user, saved_id)
    return {"message": "Saved search deleted successfully."}
