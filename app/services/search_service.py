import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ForbiddenException
from app.domain.models.enums import OrgRole
from app.domain.models.saved_search import SavedSearch
from app.domain.models.user import User
from app.domain.schemas.search import (
    GlobalSearchResponse,
    GlobalSearchResultItem,
    SavedSearchCreateRequest,
)
from app.repositories.org_repository import OrganizationRepository
from app.repositories.search_repository import SearchRepository


class SearchService:
    """Service orchestrating Enterprise Search & Saved Searches."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SearchRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def _check_org_access(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.org_repo.get_membership(org_id, user_id)
        if not member:
            raise ForbiddenException("You are not a member of this organization.")


    async def global_search(
        self,
        org_id: uuid.UUID,
        actor: User,
        query: str,
        entity_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
        limit: int = 30,
    ) -> GlobalSearchResponse:
        """Executes enterprise global search across issues, projects, comments, and members."""
        await self._check_org_access(org_id, actor.id)

        clean_query = (query or "").strip()
        raw_items, exec_time = await self.repo.global_search(
            org_id=org_id,
            query=clean_query,
            entity_types=entity_types,
            status=status,
            priority=priority,
            project_id=project_id,
            limit=limit,
        )

        items = [GlobalSearchResultItem(**item) for item in raw_items]
        return GlobalSearchResponse(
            query=clean_query,
            total_results=len(items),
            items=items,
            execution_time_ms=exec_time,
        )

    async def create_saved_search(
        self, org_id: uuid.UUID, actor: User, dto: SavedSearchCreateRequest
    ) -> SavedSearch:
        """Creates a saved search preset."""
        await self._check_org_access(org_id, actor.id)
        return await self.repo.create_saved_search(
            org_id=org_id,
            user_id=actor.id,
            name=dto.name,
            query_params=dto.query_params,
            is_shared=dto.is_shared,
        )

    async def list_saved_searches(self, org_id: uuid.UUID, actor: User) -> List[SavedSearch]:
        """Lists user and shared saved searches."""
        await self._check_org_access(org_id, actor.id)
        return await self.repo.list_saved_searches(org_id, actor.id)

    async def delete_saved_search(self, org_id: uuid.UUID, actor: User, saved_id: uuid.UUID) -> None:
        """Deletes a saved search preset."""
        await self._check_org_access(org_id, actor.id)
        saved = await self.repo.get_saved_search(org_id, saved_id)
        if not saved:
            raise EntityNotFoundException("SavedSearch", saved_id)
        if saved.user_id != actor.id:
            # Only owner can delete saved search
            member = await self.org_repo.get_membership(org_id, actor.id)
            if not member or member.role not in [OrgRole.OWNER, OrgRole.ADMIN]:
                raise ForbiddenException("You cannot delete this saved search preset.")


        await self.db.delete(saved)
        await self.db.commit()
