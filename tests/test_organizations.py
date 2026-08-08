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
