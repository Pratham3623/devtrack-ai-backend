import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.organization import (
    AcceptInvitationRequest,
    AddTeamMemberRequest,
    AuditLogResponse,
    InvitationResponse,
    InviteMemberRequest,
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
    OrgMemberResponse,
    OrgMemberRoleUpdateRequest,
    RejectInvitationRequest,
    TeamCreateRequest,
    TeamMemberResponse,
    TeamMemberRoleUpdateRequest,
    TeamResponse,
    TeamUpdateRequest,
    TransferOwnershipRequest,
)
from app.services.org_service import OrgService

router = APIRouter()


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Organization",
)
async def create_organization(
    dto: OrganizationCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrgService(db)
    org = await service.create_organization(current_user, dto)
    return OrganizationResponse.model_validate(org)


@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List User Organizations",
)
async def list_user_organizations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[OrganizationResponse]:
    service = OrgService(db)
    orgs = await service.get_user_organizations(current_user)
    return [OrganizationResponse.model_validate(o) for o in orgs]


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get Organization Details",
)
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrgService(db)
    org = await service.get_organization(org_id, current_user)
    return OrganizationResponse.model_validate(org)


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update Organization Settings",
)
async def update_organization(
    org_id: uuid.UUID,
    dto: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrgService(db)
    org = await service.update_organization(org_id, current_user, dto)
    return OrganizationResponse.model_validate(org)


@router.delete(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Delete/Archive Organization",
)
async def delete_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrgService(db)
    org = await service.delete_organization(org_id, current_user)
    return OrganizationResponse.model_validate(org)


@router.post(
    "/{org_id}/invitations",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Invite Member to Organization",
)
async def invite_member(
    org_id: uuid.UUID,
    dto: InviteMemberRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = OrgService(db)
    invitation, raw_token = await service.invite_member(org_id, current_user, dto)
    return {
        "message": f"Invitation sent to '{dto.email}'.",
        "invitation_id": str(invitation.id),
        "raw_token": raw_token,
    }


@router.get(
    "/{org_id}/invitations",
    response_model=List[InvitationResponse],
    summary="List Organization Invitations",
)
async def list_invitations(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[InvitationResponse]:
    service = OrgService(db)
    invitations = await service.list_invitations(org_id, current_user)
    return [InvitationResponse.model_validate(i) for i in invitations]


@router.post(
    "/invitations/accept",
    response_model=OrgMemberResponse,
    summary="Accept Organization Invitation",
)
async def accept_invitation(
    dto: AcceptInvitationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMemberResponse:
    service = OrgService(db)
    member = await service.accept_invitation(current_user, dto.token)
    return OrgMemberResponse.model_validate(member)


@router.post(
    "/invitations/reject",
    response_model=InvitationResponse,
    summary="Reject Organization Invitation",
)
async def reject_invitation(
    dto: RejectInvitationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    service = OrgService(db)
    invitation = await service.reject_invitation(current_user, dto.token)
    return InvitationResponse.model_validate(invitation)


@router.delete(
    "/{org_id}/invitations/{invitation_id}",
    response_model=InvitationResponse,
    summary="Cancel Organization Invitation",
)
async def cancel_invitation(
    org_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    service = OrgService(db)
    invitation = await service.cancel_invitation(org_id, invitation_id, current_user)
    return InvitationResponse.model_validate(invitation)


@router.get(
    "/{org_id}/members",
    response_model=List[OrgMemberResponse],
    summary="List Organization Members",
)
async def list_members(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[OrgMemberResponse]:
    service = OrgService(db)
    members = await service.get_members(org_id, current_user)
    return [OrgMemberResponse.model_validate(m) for m in members]


@router.patch(
    "/{org_id}/members/{user_id}/role",
    response_model=OrgMemberResponse,
    summary="Update Member Role",
)
async def update_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    dto: OrgMemberRoleUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrgMemberResponse:
    service = OrgService(db)
    member = await service.update_member_role(org_id, user_id, current_user, dto.role)
    return OrgMemberResponse.model_validate(member)


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Member from Organization",
)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = OrgService(db)
    await service.remove_member(org_id, user_id, current_user)
    return {"message": "Member removed successfully."}


@router.post(
    "/{org_id}/transfer-ownership",
    response_model=OrganizationResponse,
    summary="Transfer Organization Ownership",
)
async def transfer_ownership(
    org_id: uuid.UUID,
    dto: TransferOwnershipRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    service = OrgService(db)
    org = await service.transfer_ownership(org_id, current_user, dto.new_owner_id)
    return OrganizationResponse.model_validate(org)


@router.post(
    "/{org_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Squad Team",
)
async def create_team(
    org_id: uuid.UUID,
    dto: TeamCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    service = OrgService(db)
    team = await service.create_team(org_id, current_user, dto)
    return TeamResponse.model_validate(team)


@router.get(
    "/{org_id}/teams",
    response_model=List[TeamResponse],
    summary="List Organization Teams",
)
async def list_teams(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[TeamResponse]:
    service = OrgService(db)
    teams = await service.get_teams(org_id, current_user)
    return [TeamResponse.model_validate(t) for t in teams]


@router.get(
    "/{org_id}/teams/{team_id}",
    response_model=TeamResponse,
    summary="Get Team Details",
)
async def get_team(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    service = OrgService(db)
    team = await service.get_team(org_id, team_id, current_user)
    return TeamResponse.model_validate(team)


@router.patch(
    "/{org_id}/teams/{team_id}",
    response_model=TeamResponse,
    summary="Update Team",
)
async def update_team(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    dto: TeamUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    service = OrgService(db)
    team = await service.update_team(org_id, team_id, current_user, dto)
    return TeamResponse.model_validate(team)


@router.delete(
    "/{org_id}/teams/{team_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Team",
)
async def delete_team(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = OrgService(db)
    await service.delete_team(org_id, team_id, current_user)
    return {"message": "Team deleted successfully."}


@router.post(
    "/{org_id}/teams/{team_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Add Member to Team",
)
async def add_team_member(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    dto: AddTeamMemberRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = OrgService(db)
    await service.add_team_member(team_id, current_user, dto)
    return {"message": "Team member added successfully."}


@router.get(
    "/{org_id}/teams/{team_id}/members",
    response_model=List[TeamMemberResponse],
    summary="List Team Members",
)
async def list_team_members(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[TeamMemberResponse]:
    service = OrgService(db)
    members = await service.list_team_members(org_id, team_id, current_user)
    return [TeamMemberResponse.model_validate(m) for m in members]


@router.patch(
    "/{org_id}/teams/{team_id}/members/{user_id}",
    response_model=TeamMemberResponse,
    summary="Update Team Member Role",
)
async def update_team_member_role(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    dto: TeamMemberRoleUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    service = OrgService(db)
    member = await service.update_team_member_role(org_id, team_id, user_id, current_user, dto.role)
    return TeamMemberResponse.model_validate(member)


@router.delete(
    "/{org_id}/teams/{team_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove Team Member",
)
async def remove_team_member(
    org_id: uuid.UUID,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = OrgService(db)
    await service.remove_team_member(org_id, team_id, user_id, current_user)
    return {"message": "Team member removed successfully."}


@router.get(
    "/{org_id}/audit-logs",
    response_model=List[AuditLogResponse],
    summary="Get Organization Audit Logs",
)
async def get_audit_logs(
    org_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[AuditLogResponse]:
    service = OrgService(db)
    logs = await service.get_audit_logs(org_id, current_user, limit)
    return [AuditLogResponse.model_validate(l) for l in logs]
