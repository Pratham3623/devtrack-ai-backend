import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.audit_log import AuditLog
from app.domain.models.invitation import Invitation
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.team import Team, TeamMember
from app.repositories.base_repository import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, db: AsyncSession):
        super().__init__(Organization, db)

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        stmt = select(Organization).where(Organization.slug == slug)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_user_organizations(self, user_id: uuid.UUID, include_archived: bool = False) -> List[Organization]:
        stmt = (
            select(Organization)
            .join(OrgMember, OrgMember.organization_id == Organization.id)
            .where(OrgMember.user_id == user_id)
        )
        if not include_archived:
            stmt = stmt.where(Organization.is_archived.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_membership(self, org_id: uuid.UUID, user_id: uuid.UUID) -> Optional[OrgMember]:
        stmt = select(OrgMember).where(
            OrgMember.organization_id == org_id,
            OrgMember.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_members(self, org_id: uuid.UUID) -> List[OrgMember]:
        stmt = (
            select(OrgMember)
            .options(selectinload(OrgMember.user))
            .where(OrgMember.organization_id == org_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_team_by_id(self, team_id: uuid.UUID) -> Optional[Team]:
        stmt = select(Team).where(Team.id == team_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_teams_by_org(self, org_id: uuid.UUID, include_archived: bool = False) -> List[Team]:
        stmt = select(Team).where(Team.organization_id == org_id)
        if not include_archived:
            stmt = stmt.where(Team.is_archived.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_team_members(self, team_id: uuid.UUID) -> List[TeamMember]:
        stmt = (
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(TeamMember.team_id == team_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_invitation_by_token(self, token_hash: str) -> Optional[Invitation]:
        stmt = select(Invitation).where(Invitation.token_hash == token_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_invitation_by_id(self, invitation_id: uuid.UUID) -> Optional[Invitation]:
        stmt = select(Invitation).where(Invitation.id == invitation_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_invitations_by_org(self, org_id: uuid.UUID) -> List[Invitation]:
        stmt = select(Invitation).where(
            Invitation.organization_id == org_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
