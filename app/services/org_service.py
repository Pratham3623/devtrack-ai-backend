import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.core.logging import logger
from app.core.security import generate_opaque_token, hash_token
from app.domain.models.audit_log import AuditLog
from app.domain.models.enums import AuditAction, InvitationStatus, OrgRole, TeamRole
from app.domain.models.invitation import Invitation
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.team import Team, TeamMember
from app.domain.models.user import User
from app.domain.schemas.organization import (
    AddTeamMemberRequest,
    InviteMemberRequest,
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    TeamCreateRequest,
    TeamUpdateRequest,
)
from app.repositories.org_repository import OrganizationRepository


class OrgService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = OrganizationRepository(db)

    async def _check_user_org_permission(
        self, org_id: uuid.UUID, user_id: uuid.UUID, allowed_roles: List[OrgRole]
    ) -> OrgMember:
        """Helper enforcing Organization RBAC role check."""
        membership = await self.repo.get_membership(org_id, user_id)
        if not membership or membership.role not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenException(f"You require one of [{roles_str}] roles in this organization.")
        return membership

    async def _log_audit_action(
        self, org_id: uuid.UUID, actor_id: uuid.UUID, action: AuditAction, metadata: Optional[dict] = None
    ) -> AuditLog:
        """Record an immutable audit log entry."""
        audit = AuditLog(
            organization_id=org_id,
            actor_id=actor_id,
            action=action,
            metadata_json=metadata or {},
        )
        self.db.add(audit)
        await self.db.commit()
        return audit

    async def create_organization(self, creator: User, dto: OrganizationCreateRequest) -> Organization:
        """Create a new organization and assign creator as OWNER."""
        slug = dto.slug or dto.name.lower().replace(" ", "-").replace("/", "-")
        existing = await self.repo.get_by_slug(slug)
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(
            name=dto.name,
            slug=slug,
            logo_url=dto.logo_url,
            owner_id=creator.id,
            plan_tier="FREE",
            is_archived=False,
        )
        self.db.add(org)
        await self.db.commit()
        await self.db.refresh(org)

        # Create Owner OrgMember
        member = OrgMember(
            organization_id=org.id,
            user_id=creator.id,
            role=OrgRole.OWNER,
        )
        self.db.add(member)
        await self.db.commit()

        await self._log_audit_action(org.id, creator.id, AuditAction.ORG_CREATED, {"org_name": org.name})
        logger.info(f"Organization created: '{org.name}' (ID: {org.id}) by User {creator.email}")
        return org

    async def get_user_organizations(self, user: User, include_archived: bool = False) -> List[Organization]:
        """List all organizations where the user is a member."""
        return await self.repo.get_user_organizations(user.id, include_archived=include_archived)

    async def get_organization(self, org_id: uuid.UUID, user: User) -> Organization:
        """Fetch organization details after validating membership."""
        await self._check_user_org_permission(
            org_id,
            user.id,
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
        org = await self.repo.get_by_id(org_id)
        if not org or org.is_archived:
            raise EntityNotFoundException("Organization", org_id)
        return org

    async def update_organization(
        self, org_id: uuid.UUID, actor: User, dto: OrganizationUpdateRequest
    ) -> Organization:
        """Update organization details (Owner / Admin only)."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        org = await self.get_organization(org_id, actor)

        if dto.name:
            org.name = dto.name
        if dto.logo_url is not None:
            org.logo_url = dto.logo_url
        if dto.is_archived is not None:
            org.is_archived = dto.is_archived
            if dto.is_archived:
                org.archived_at = datetime.now(timezone.utc)
            else:
                org.archived_at = None

        await self.db.commit()
        await self.db.refresh(org)

        await self._log_audit_action(
            org.id,
            actor.id,
            AuditAction.ORG_UPDATED,
            {"updated_fields": list(dto.model_dump(exclude_unset=True).keys())},
        )
        return org

    async def delete_organization(self, org_id: uuid.UUID, actor: User) -> Organization:
        """Soft delete (archive) organization (Owner only)."""
        org = await self.get_organization(org_id, actor)
        if org.owner_id != actor.id:
            raise ForbiddenException("Only the Organization Owner can delete/archive the organization.")

        org.is_archived = True
        org.archived_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(org)

        await self._log_audit_action(org.id, actor.id, AuditAction.ORG_UPDATED, {"action": "archived"})
        logger.info(f"Organization '{org.name}' (ID: {org.id}) archived by Owner")
        return org

    async def invite_member(
        self, org_id: uuid.UUID, actor: User, dto: InviteMemberRequest
    ) -> Tuple[Invitation, str]:
        """Invite user to organization via email."""
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        # Check if invite target is already a member
        from app.domain.models.user import User as UserModel
        from sqlalchemy import select

        stmt_user = select(UserModel).where(UserModel.email == dto.email.lower())
        res_user = await self.db.execute(stmt_user)
        existing_user = res_user.scalar_one_or_none()

        if existing_user:
            membership = await self.repo.get_membership(org_id, existing_user.id)
            if membership:
                raise ValidationException(f"User with email '{dto.email}' is already a member of this organization.")

        raw_token = generate_opaque_token()
        hashed_token = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        invitation = Invitation(
            organization_id=org_id,
            email=dto.email.lower(),
            role=dto.role,
            token_hash=hashed_token,
            invited_by_id=actor.id,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        await self._log_audit_action(
            org_id, actor.id, AuditAction.MEMBER_INVITED, {"email": dto.email, "role": dto.role.value}
        )
        logger.info(f"User '{dto.email}' invited to Org {org_id} with role {dto.role.value}")
        return invitation, raw_token

    async def accept_invitation(self, user: User, raw_token: str) -> OrgMember:
        """Accept an invitation using raw token."""
        hashed = hash_token(raw_token)
        invitation = await self.repo.get_invitation_by_token(hashed)

        if not invitation or invitation.status != InvitationStatus.PENDING:
            raise ValidationException("Invalid or expired invitation token.")

        now = datetime.now(timezone.utc)
        exp_time = (
            invitation.expires_at.replace(tzinfo=timezone.utc)
            if invitation.expires_at.tzinfo is None
            else invitation.expires_at
        )

        if exp_time < now:
            invitation.status = InvitationStatus.EXPIRED
            await self.db.commit()
            raise ValidationException("Invitation token has expired.")

        member = OrgMember(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
        )
        invitation.status = InvitationStatus.ACCEPTED
        self.db.add(member)
        await self.db.commit()

        from sqlalchemy import select

        res_mem = await self.db.execute(
            select(OrgMember).options(selectinload(OrgMember.user)).where(OrgMember.id == member.id)
        )
        loaded_member = res_mem.scalar_one()

        await self._log_audit_action(
            invitation.organization_id, user.id, AuditAction.MEMBER_JOINED, {"role": loaded_member.role.value}
        )
        return loaded_member

    async def reject_invitation(self, user: User, raw_token: str) -> Invitation:
        """Reject an invitation using raw token."""
        hashed = hash_token(raw_token)
        invitation = await self.repo.get_invitation_by_token(hashed)

        if not invitation or invitation.status != InvitationStatus.PENDING:
            raise ValidationException("Invalid or expired invitation token.")

        invitation.status = InvitationStatus.REJECTED
        await self.db.commit()
        await self.db.refresh(invitation)
        return invitation

    async def cancel_invitation(
        self, org_id: uuid.UUID, invitation_id: uuid.UUID, actor: User
    ) -> Invitation:
        """Cancel/revoke a pending invitation (Owner / Admin only)."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        invitation = await self.repo.get_invitation_by_id(invitation_id)

        if not invitation or invitation.organization_id != org_id:
            raise EntityNotFoundException("Invitation", invitation_id)

        invitation.status = InvitationStatus.REVOKED
        await self.db.commit()
        await self.db.refresh(invitation)
        return invitation

    async def list_invitations(self, org_id: uuid.UUID, actor: User) -> List[Invitation]:
        """List invitations for an organization (Owner / Admin / PM)."""
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        return await self.repo.get_pending_invitations_by_org(org_id)

    async def get_members(self, org_id: uuid.UUID, actor: User) -> List[OrgMember]:
        """Fetch all organization members with loaded user relations."""
        await self._check_user_org_permission(
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
        return await self.repo.get_members(org_id)

    async def update_member_role(
        self, org_id: uuid.UUID, target_user_id: uuid.UUID, actor: User, new_role: OrgRole
    ) -> OrgMember:
        """Update role of an org member."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        org = await self.get_organization(org_id, actor)

        if target_user_id == org.owner_id and new_role != OrgRole.OWNER:
            raise ValidationException("Cannot change role of Organization Owner. Use ownership transfer instead.")

        from sqlalchemy import select

        stmt = select(OrgMember).options(selectinload(OrgMember.user)).where(
            OrgMember.organization_id == org_id, OrgMember.user_id == target_user_id
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise EntityNotFoundException("OrgMember", target_user_id)

        old_role = member.role.value
        member.role = new_role
        await self.db.commit()
        await self.db.refresh(member)

        await self._log_audit_action(
            org_id,
            actor.id,
            AuditAction.ROLE_UPDATED,
            {"target_user_id": str(target_user_id), "old_role": old_role, "new_role": new_role.value},
        )
        return member

    async def remove_member(self, org_id: uuid.UUID, target_user_id: uuid.UUID, actor: User) -> None:
        """Remove a member from the organization."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        org = await self.get_organization(org_id, actor)

        if target_user_id == org.owner_id:
            raise ValidationException("Cannot remove the Organization Owner.")

        member = await self.repo.get_membership(org_id, target_user_id)
        if member:
            await self.db.delete(member)
            await self.db.commit()
            await self._log_audit_action(
                org_id, actor.id, AuditAction.MEMBER_REMOVED, {"target_user_id": str(target_user_id)}
            )

    async def transfer_ownership(
        self, org_id: uuid.UUID, current_owner: User, new_owner_id: uuid.UUID
    ) -> Organization:
        """Transfer organization ownership to another active member."""
        org = await self.get_organization(org_id, current_owner)

        if org.owner_id != current_owner.id:
            raise ForbiddenException("Only the current Organization Owner can transfer ownership.")

        if current_owner.id == new_owner_id:
            raise ValidationException("Target user is already the owner.")

        new_owner_member = await self.repo.get_membership(org_id, new_owner_id)
        if not new_owner_member:
            raise ValidationException("Target user must be a member of the organization.")

        old_owner_member = await self.repo.get_membership(org_id, current_owner.id)
        if not old_owner_member:
            raise ValidationException("Current owner membership record missing.")

        org.owner_id = new_owner_id
        new_owner_member.role = OrgRole.OWNER
        old_owner_member.role = OrgRole.ADMIN

        await self.db.commit()
        await self.db.refresh(org)

        await self._log_audit_action(
            org_id,
            current_owner.id,
            AuditAction.OWNERSHIP_TRANSFERRED,
            {"previous_owner_id": str(current_owner.id), "new_owner_id": str(new_owner_id)},
        )
        logger.info(f"Ownership of Org {org.name} transferred to User {new_owner_id}")
        return org

    async def create_team(self, org_id: uuid.UUID, actor: User, dto: TeamCreateRequest) -> Team:
        """Create a squad team within the organization."""
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        team = Team(
            organization_id=org_id,
            name=dto.name,
            description=dto.description,
            is_archived=False,
        )
        self.db.add(team)
        await self.db.commit()
        await self.db.refresh(team)

        await self._log_audit_action(
            org_id, actor.id, AuditAction.TEAM_CREATED, {"team_name": team.name, "team_id": str(team.id)}
        )
        return team

    async def get_team(self, org_id: uuid.UUID, team_id: uuid.UUID, actor: User) -> Team:
        """Get team details after checking org membership."""
        await self._check_user_org_permission(
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
        team = await self.repo.get_team_by_id(team_id)
        if not team or team.organization_id != org_id or team.is_archived:
            raise EntityNotFoundException("Team", team_id)
        return team

    async def update_team(
        self, org_id: uuid.UUID, team_id: uuid.UUID, actor: User, dto: TeamUpdateRequest
    ) -> Team:
        """Update team details (Owner / Admin / PM)."""
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )
        team = await self.get_team(org_id, team_id, actor)

        if dto.name is not None:
            team.name = dto.name
        if dto.description is not None:
            team.description = dto.description
        if dto.is_archived is not None:
            team.is_archived = dto.is_archived

        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def delete_team(self, org_id: uuid.UUID, team_id: uuid.UUID, actor: User) -> None:
        """Delete/archive team (Owner / Admin)."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        team = await self.get_team(org_id, team_id, actor)
        await self.db.delete(team)
        await self.db.commit()

    async def get_teams(self, org_id: uuid.UUID, actor: User) -> List[Team]:
        """Fetch all teams in an organization."""
        await self._check_user_org_permission(
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
        return await self.repo.get_teams_by_org(org_id)

    async def add_team_member(
        self, team_id: uuid.UUID, actor: User, dto: AddTeamMemberRequest
    ) -> TeamMember:
        """Add user to squad team."""
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise EntityNotFoundException("Team", team_id)

        await self._check_user_org_permission(
            team.organization_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        # Verify user is in organization
        await self._check_user_org_permission(
            team.organization_id,
            dto.user_id,
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

        team_member = TeamMember(
            team_id=team_id,
            user_id=dto.user_id,
            role=dto.role,
        )
        self.db.add(team_member)
        await self.db.commit()
        await self.db.refresh(team_member)

        await self._log_audit_action(
            team.organization_id,
            actor.id,
            AuditAction.TEAM_MEMBER_ADDED,
            {"team_id": str(team_id), "user_id": str(dto.user_id)},
        )
        return team_member

    async def list_team_members(
        self, org_id: uuid.UUID, team_id: uuid.UUID, actor: User
    ) -> List[TeamMember]:
        """List team members."""
        await self.get_team(org_id, team_id, actor)
        return await self.repo.get_team_members(team_id)

    async def update_team_member_role(
        self, org_id: uuid.UUID, team_id: uuid.UUID, target_user_id: uuid.UUID, actor: User, new_role: TeamRole
    ) -> TeamMember:
        """Update team member role."""
        await self.get_team(org_id, team_id, actor)
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        from sqlalchemy import select

        stmt = select(TeamMember).options(selectinload(TeamMember.user)).where(
            TeamMember.team_id == team_id, TeamMember.user_id == target_user_id
        )
        res = await self.db.execute(stmt)
        member = res.scalar_one_or_none()

        if not member:
            raise EntityNotFoundException("TeamMember", target_user_id)

        member.role = new_role
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_team_member(
        self, org_id: uuid.UUID, team_id: uuid.UUID, target_user_id: uuid.UUID, actor: User
    ) -> None:
        """Remove user from team."""
        await self.get_team(org_id, team_id, actor)
        await self._check_user_org_permission(
            org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.PROJECT_MANAGER]
        )

        from sqlalchemy import select

        stmt = select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id)
        res = await self.db.execute(stmt)
        member = res.scalar_one_or_none()

        if member:
            await self.db.delete(member)
            await self.db.commit()

    async def get_audit_logs(self, org_id: uuid.UUID, actor: User, limit: int = 50) -> List[AuditLog]:
        """Fetch paginated audit logs for the organization."""
        await self._check_user_org_permission(org_id, actor.id, [OrgRole.OWNER, OrgRole.ADMIN])
        from sqlalchemy import select

        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.actor))
            .where(AuditLog.organization_id == org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
