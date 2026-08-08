import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def get_authenticated_user(async_client: AsyncClient, email: str, name: str):
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
async def test_list_project_templates(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/projects/templates")
    assert resp.status_code == 200
    templates = resp.json()
    assert len(templates) >= 4
    template_types = [t["template_type"] for t in templates]
    assert "KANBAN" in template_types
    assert "SCRUM" in template_types


@pytest.mark.asyncio
async def test_create_and_get_project(async_client: AsyncClient):
    token, user = await get_authenticated_user(async_client, "proj_owner@devtrack.ai", "Proj Owner")

    # Create Org
    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Project Org"},
    )
    org_id = org_resp.json()["id"]

    # Create Project
    proj_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "DevTrack Engine",
            "description": "AI SaaS Core Backend Engine",
            "template_type": "SCRUM",
        },
    )
    assert proj_resp.status_code == 201
    proj = proj_resp.json()
    assert proj["name"] == "DevTrack Engine"
    assert proj["template_type"] == "SCRUM"
    assert proj["owner_id"] == user["id"]
    project_id = proj["id"]

    # Get Details
    get_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "DevTrack Engine"


@pytest.mark.asyncio
async def test_search_filter_pagination_projects(async_client: AsyncClient):
    token, _ = await get_authenticated_user(async_client, "search_user@devtrack.ai", "Search User")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Search Org"},
    )
    org_id = org_resp.json()["id"]

    # Create 3 Projects
    await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Alpha Kanban Project", "template_type": "KANBAN"},
    )
    await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Beta Scrum Project", "template_type": "SCRUM"},
    )
    await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Gamma Bug Tracker", "template_type": "BUG_TRACKING"},
    )

    # 1. Search Query
    search_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects?q=Alpha",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 1
    assert search_resp.json()["items"][0]["name"] == "Alpha Kanban Project"

    # 2. Template Filter
    filter_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects?template_type=SCRUM",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert filter_resp.status_code == 200
    assert filter_resp.json()["total"] == 1
    assert filter_resp.json()["items"][0]["name"] == "Beta Scrum Project"

    # 3. Pagination
    page_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects?page=1&size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page_resp.status_code == 200
    assert len(page_resp.json()["items"]) == 2
    assert page_resp.json()["total"] == 3
    assert page_resp.json()["pages"] == 2


@pytest.mark.asyncio
async def test_archive_and_restore_project(async_client: AsyncClient):
    token, _ = await get_authenticated_user(async_client, "archiver@devtrack.ai", "Archiver User")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Archiving Org"},
    )
    org_id = org_resp.json()["id"]

    proj_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Temporary Project"},
    )
    project_id = proj_resp.json()["id"]

    # Archive
    arch_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert arch_resp.status_code == 200
    assert arch_resp.json()["is_archived"] is True
    assert arch_resp.json()["archived_at"] is not None

    # Restore
    rest_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/restore",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rest_resp.status_code == 200
    assert rest_resp.json()["is_archived"] is False


@pytest.mark.asyncio
async def test_project_dashboard_and_analytics(async_client: AsyncClient):
    token, _ = await get_authenticated_user(async_client, "metrics_user@devtrack.ai", "Metrics User")

    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Metrics Org"},
    )
    org_id = org_resp.json()["id"]

    proj_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Analytics Board"},
    )
    project_id = proj_resp.json()["id"]

    # Get Dashboard
    dash_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dash_resp.status_code == 200
    dash = dash_resp.json()
    assert dash["project_name"] == "Analytics Board"
    assert dash["health_score"] >= 80
    assert "workflow_columns" in dash

    # Get Analytics
    analytics_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert "velocity_trend" in analytics
    assert "issue_status_distribution" in analytics


@pytest.mark.asyncio
async def test_project_member_management(async_client: AsyncClient):
    token_lead, lead_user = await get_authenticated_user(async_client, "lead@devtrack.ai", "Lead User")
    token_member, member_user = await get_authenticated_user(async_client, "contrib@devtrack.ai", "Contrib User")

    # Create Org & Invite Contrib User to Org
    org_resp = await async_client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token_lead}"},
        json={"name": "Member Org"},
    )
    org_id = org_resp.json()["id"]

    inv_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers={"Authorization": f"Bearer {token_lead}"},
        json={"email": "contrib@devtrack.ai", "role": "MEMBER"},
    )
    await async_client.post(
        "/api/v1/organizations/invitations/accept",
        headers={"Authorization": f"Bearer {token_member}"},
        json={"token": inv_resp.json()["raw_token"]},
    )

    # Create Project
    proj_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects",
        headers={"Authorization": f"Bearer {token_lead}"},
        json={"name": "Team Project"},
    )
    project_id = proj_resp.json()["id"]

    # Add Member to Project
    add_mem_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/members",
        headers={"Authorization": f"Bearer {token_lead}"},
        json={"user_id": member_user["id"], "role": "CONTRIBUTOR"},
    )
    assert add_mem_resp.status_code == 201
    assert add_mem_resp.json()["role"] == "CONTRIBUTOR"

    # List Project Members
    list_mem_resp = await async_client.get(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/members",
        headers={"Authorization": f"Bearer {token_lead}"},
    )
    assert list_mem_resp.status_code == 200
    assert len(list_mem_resp.json()) == 2  # Lead + Contrib

    # Update Member Role
    patch_role_resp = await async_client.patch(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/members/{member_user['id']}",
        headers={"Authorization": f"Bearer {token_lead}"},
        json={"role": "MAINTAINER"},
    )
    assert patch_role_resp.status_code == 200
    assert patch_role_resp.json()["role"] == "MAINTAINER"

    # Remove Member
    del_mem_resp = await async_client.delete(
        f"/api/v1/organizations/{org_id}/projects/{project_id}/members/{member_user['id']}",
        headers={"Authorization": f"Bearer {token_lead}"},
    )
    assert del_mem_resp.status_code == 200
