import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.enums import AuditAction, OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember


# Helper fixture creating logged-in user
async def get_authenticated_user_tokens(async_client: AsyncClient, email: str, name: str):
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": name},
    )
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    data = login_resp.json()
    return data["access_token"], data["user"]


@pytest.mark.asyncio
async def test_create_organization_and_owner_membership(async_client: AsyncClient):
    token, user = await get_authenticated_user_tokens(async_client, "owner@devtrack.ai", "Owner User")

    response = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Acme Corp", "slug": "acme-corp"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert data["owner_id"] == user["id"]


@pytest.mark.asyncio
async def test_list_user_organizations(async_client: AsyncClient):
    token, _ = await get_authenticated_user_tokens(async_client, "multi@devtrack.ai", "Multi User")

    # Create 2 Organizations
    await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Org 1"},
    )
    await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Org 2"},
    )

    list_resp = await async_client.get(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    orgs = list_resp.json()
    assert len(orgs) == 2


@pytest.mark.asyncio
async def test_invite_member_and_accept_flow(async_client: AsyncClient):
    # Owner
    owner_token, _ = await get_authenticated_user_tokens(async_client, "inviter@devtrack.ai", "Inviter User")

    # Create Org
    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Invite Org"},
    )
    org_id = org_resp.json()["id"]

    # Target Member Registers
    member_token, member_user = await get_authenticated_user_tokens(async_client, "invitee@devtrack.ai", "Invitee User")

    # Owner Invites Member
    invite_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "invitee@devtrack.ai", "role": "MEMBER"},
    )
    assert invite_resp.status_code == 201
    raw_token = invite_resp.json()["raw_token"]

    # Member Accepts Invite
    accept_resp = await async_client.post(
        "/api/v1/organizations/invitations/accept",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": raw_token},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["role"] == "MEMBER"
    assert accept_resp.json()["user_id"] == member_user["id"]


@pytest.mark.asyncio
async def test_update_member_role_and_rbac_checks(async_client: AsyncClient):
    owner_token, _ = await get_authenticated_user_tokens(async_client, "admin_owner@devtrack.ai", "Admin Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Role Org"},
    )
    org_id = org_resp.json()["id"]

    member_token, member_user = await get_authenticated_user_tokens(async_client, "role_member@devtrack.ai", "Role Member")

    # Invite and Accept
    inv_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "role_member@devtrack.ai", "role": "MEMBER"},
    )
    await async_client.post(
        "/api/v1/organizations/invitations/accept",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": inv_resp.json()["raw_token"]},
    )

    # Promote Member to ADMIN
    promote_resp = await async_client.patch(
        f"/api/v1/organizations/{org_id}/members/{member_user['id']}/role",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"role": "ADMIN"},
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_transfer_ownership_flow(async_client: AsyncClient):
    owner_token, owner_user = await get_authenticated_user_tokens(async_client, "old_owner@devtrack.ai", "Old Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Transfer Org"},
    )
    org_id = org_resp.json()["id"]

    new_owner_token, new_owner_user = await get_authenticated_user_tokens(async_client, "new_owner@devtrack.ai", "New Owner")

    # Invite & Accept New Owner
    inv_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "new_owner@devtrack.ai", "role": "ADMIN"},
    )
    await async_client.post(
        "/api/v1/organizations/invitations/accept",
        headers={"Authorization": f"Bearer {new_owner_token}"},
        json={"token": inv_resp.json()["raw_token"]},
    )

    # Transfer Ownership
    transfer_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/transfer-ownership",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"new_owner_id": new_owner_user["id"]},
    )
    assert transfer_resp.status_code == 200
    assert transfer_resp.json()["owner_id"] == new_owner_user["id"]


@pytest.mark.asyncio
async def test_create_team_and_add_member(async_client: AsyncClient):
    owner_token, owner_user = await get_authenticated_user_tokens(async_client, "team_owner@devtrack.ai", "Team Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Team Org"},
    )
    org_id = org_resp.json()["id"]

    # Create Team
    team_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/teams",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Core Platform Squad", "description": "Backend & Cloud Infra Squad"},
    )
    assert team_resp.status_code == 201
    team = team_resp.json()
    assert team["name"] == "Core Platform Squad"

    # Add Owner to Squad Team
    add_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/teams/{team['id']}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": owner_user["id"], "role": "LEAD"},
    )
    assert add_resp.status_code == 201


@pytest.mark.asyncio
async def test_audit_log_recording(async_client: AsyncClient):
    owner_token, _ = await get_authenticated_user_tokens(async_client, "audit_owner@devtrack.ai", "Audit Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Audit Org"},
    )
    org_id = org_resp.json()["id"]

    # Fetch Audit Logs
    logs_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/audit-logs",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "ORG_CREATED"


# ==========================================
# PHASE 4 NEW EXPANDED TESTS
# ==========================================

@pytest.mark.asyncio
async def test_organization_soft_delete_and_archive(async_client: AsyncClient):
    owner_token, _ = await get_authenticated_user_tokens(async_client, "softdel_owner@devtrack.ai", "SoftDel Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Archive Org"},
    )
    org_id = org_resp.json()["id"]

    # Delete / Archive Org
    del_resp = await async_client.delete(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["is_archived"] is True
    assert del_resp.json()["archived_at"] is not None

    # Fetch archived org fails with 404
    get_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_team_full_crud_lifecycle_and_members(async_client: AsyncClient):
    owner_token, owner_user = await get_authenticated_user_tokens(async_client, "team_crud_owner@devtrack.ai", "Team CRUD Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Team Lifecycle Org"},
    )
    org_id = org_resp.json()["id"]

    # 1. Create Team
    team_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/teams",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Frontend Guild", "description": "UI/UX Engineers"},
    )
    assert team_resp.status_code == 201
    team_id = team_resp.json()["id"]

    # 2. Get Team Details
    get_team_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/teams/{team_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert get_team_resp.status_code == 200
    assert get_team_resp.json()["name"] == "Frontend Guild"

    # 3. Update Team
    patch_resp = await async_client.patch(
        f"/api/v1/organizations/{org_id}/teams/{team_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "UI/UX Guild", "description": "Updated Description"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "UI/UX Guild"

    # 4. Add Member and List Team Members
    await async_client.post(
        f"/api/v1/organizations/{org_id}/teams/{team_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"user_id": owner_user["id"], "role": "LEAD"},
    )
    members_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/teams/{team_id}/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert members_resp.status_code == 200
    assert len(members_resp.json()) == 1
    assert members_resp.json()[0]["role"] == "LEAD"

    # 5. Delete Team
    del_team_resp = await async_client.delete(
        f"/api/v1/organizations/{org_id}/teams/{team_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert del_team_resp.status_code == 200


@pytest.mark.asyncio
async def test_invitation_rejection_and_cancellation(async_client: AsyncClient):
    owner_token, _ = await get_authenticated_user_tokens(async_client, "inv_manage_owner@devtrack.ai", "Inv Manage Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Inv Manage Org"},
    )
    org_id = org_resp.json()["id"]

    rejectee_token, _ = await get_authenticated_user_tokens(async_client, "rejectee@devtrack.ai", "Rejectee User")

    # Invite user 1 (for rejection)
    inv1_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "rejectee@devtrack.ai", "role": "MEMBER"},
    )
    raw_token1 = inv1_resp.json()["raw_token"]

    # Reject invitation
    reject_resp = await async_client.post(
        "/api/v1/organizations/invitations/reject",
        headers={"Authorization": f"Bearer {rejectee_token}"},
        json={"token": raw_token1},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    # Invite user 2 (for cancellation by owner)
    inv2_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "cancel_target@devtrack.ai", "role": "MEMBER"},
    )
    inv2_id = inv2_resp.json()["invitation_id"]

    # Cancel invitation
    cancel_resp = await async_client.delete(
        f"/api/v1/organizations/{org_id}/invitations/{inv2_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_granular_roles_and_permissions(async_client: AsyncClient):
    owner_token, _ = await get_authenticated_user_tokens(async_client, "pm_owner@devtrack.ai", "PM Owner")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Granular Roles Org"},
    )
    org_id = org_resp.json()["id"]

    pm_token, pm_user = await get_authenticated_user_tokens(async_client, "pm@devtrack.ai", "PM User")

    # Invite PM
    inv_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "pm@devtrack.ai", "role": "PROJECT_MANAGER"},
    )
    await async_client.post(
        "/api/v1/organizations/invitations/accept",
        headers={"Authorization": f"Bearer {pm_token}"},
        json={"token": inv_resp.json()["raw_token"]},
    )

    # PM creates team (allowed)
    pm_team_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/teams",
        headers={"Authorization": f"Bearer {pm_token}"},
        json={"name": "PM Managed Team"},
    )
    assert pm_team_resp.status_code == 201

    # PM attempts to transfer ownership (forbidden 403)
    pm_transfer = await async_client.post(
        f"/api/v1/organizations/{org_id}/transfer-ownership",
        headers={"Authorization": f"Bearer {pm_token}"},
        json={"new_owner_id": pm_user["id"]},
    )
    assert pm_transfer.status_code == 403


@pytest.mark.asyncio
async def test_cross_organization_isolation_and_unauthorized_access(async_client: AsyncClient):
    userA_token, _ = await get_authenticated_user_tokens(async_client, "usera@devtrack.ai", "User A")
    userB_token, _ = await get_authenticated_user_tokens(async_client, "userb@devtrack.ai", "User B")

    # User A creates Org A
    orgA_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {userA_token}"},
        json={"name": "Org A"},
    )
    orgA_id = orgA_resp.json()["id"]

    # User B attempts to view Org A (forbidden 403)
    unauth_resp = await async_client.get(
        f"/api/v1/organizations/{orgA_id}",
        headers={"Authorization": f"Bearer {userB_token}"},
    )
    assert unauth_resp.status_code == 403
