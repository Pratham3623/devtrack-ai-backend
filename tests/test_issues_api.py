import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import IssuePriority, IssueStatus, OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_api_fixtures(db_session: AsyncSession):
    """Create test users, orgs, projects, and Bearer tokens for API tests."""
    user1 = User(
        email="owner_api@devtrack.ai", full_name="API Owner", role=UserRole.MEMBER, is_active=True
    )
    user2 = User(
        email="member_api@devtrack.ai", full_name="API Member", role=UserRole.MEMBER, is_active=True
    )
    outsider = User(
        email="outsider_api@other.ai", full_name="Outsider User", role=UserRole.MEMBER, is_active=True
    )
    db_session.add_all([user1, user2, outsider])
    await db_session.flush()

    org1 = Organization(name="API Primary Corp", slug="api-primary", owner_id=user1.id)
    db_session.add(org1)
    await db_session.flush()

    m1 = OrgMember(organization_id=org1.id, user_id=user1.id, role=OrgRole.OWNER)
    m2 = OrgMember(organization_id=org1.id, user_id=user2.id, role=OrgRole.DEVELOPER)
    db_session.add_all([m1, m2])

    org2 = Organization(name="API Secondary Corp", slug="api-secondary", owner_id=outsider.id)
    db_session.add(org2)
    await db_session.flush()
    m3 = OrgMember(organization_id=org2.id, user_id=outsider.id, role=OrgRole.OWNER)
    db_session.add(m3)

    proj1 = Project(organization_id=org1.id, name="API Project", key="APIP", owner_id=user1.id)
    proj2 = Project(organization_id=org2.id, name="Other Project", key="OTH", owner_id=outsider.id)
    db_session.add_all([proj1, proj2])
    await db_session.commit()

    token1 = create_access_token(subject=str(user1.id), role=user1.role.value)
    token2 = create_access_token(subject=str(user2.id), role=user2.role.value)
    token_outsider = create_access_token(subject=str(outsider.id), role=outsider.role.value)

    return {
        "user1": user1,
        "user2": user2,
        "outsider": outsider,
        "token1": token1,
        "token2": token2,
        "token_outsider": token_outsider,
        "org1": org1,
        "org2": org2,
        "proj1": proj1,
        "proj2": proj2,
    }


# 1. Test Create Issue API (201 Created & 422 Validation Error)
@pytest.mark.asyncio
async def test_create_issue_api_success_and_validation(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_api_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token1']}"}

    # Success case
    payload = {
        "title": "Implement JWT Middleware",
        "description": "Add SecurityHeadersMiddleware to FastAPI app.",
        "status": "TODO",
        "priority": "HIGH",
        "assignee_id": str(fix["user2"].id),
    }
    resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Implement JWT Middleware"
    assert data["issue_number"] == 1
    assert data["identifier"] == "APIP-1"
    assert data["assignee_id"] == str(fix["user2"].id)

    # Validation failure case (empty title)
    bad_payload = {"title": "   ", "status": "TODO"}
    bad_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json=bad_payload,
        headers=headers,
    )
    assert bad_resp.status_code == 422


# 2. Test Get Issue Details (by UUID and by Number)
@pytest.mark.asyncio
async def test_get_issue_by_id_and_number_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_api_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token1']}"}

    # Create issue
    create_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Get Issue API Test"},
        headers=headers,
    )
    issue_id = create_resp.json()["id"]

    # Get by UUID
    resp_id = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}",
        headers=headers,
    )
    assert resp_id.status_code == 200
    assert resp_id.json()["id"] == issue_id

    # Get by Number
    resp_num = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/number/1",
        headers=headers,
    )
    assert resp_num.status_code == 200
    assert resp_num.json()["identifier"] == "APIP-1"


# 3. Test List Issues with Pagination, Search, Filter & Sorting
@pytest.mark.asyncio
async def test_list_issues_api_pagination_search_sort(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_api_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token1']}"}

    # Create 3 issues
    await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Frontend Auth Screen", "status": "TODO", "priority": "LOW"},
        headers=headers,
    )
    await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Backend Migration", "status": "IN_PROGRESS", "priority": "URGENT"},
        headers=headers,
    )
    await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Backend Redis Caching", "status": "DONE", "priority": "HIGH"},
        headers=headers,
    )

    # Paginated List
    list_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues?page=1&size=2",
        headers=headers,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["pages"] == 2

    # Search filter
    search_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues?q=Backend",
        headers=headers,
    )
    assert search_resp.status_code == 200
    assert len(search_resp.json()["items"]) == 2

    # Priority & Status Filter
    filter_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues?status=DONE&priority=HIGH",
        headers=headers,
    )
    assert filter_resp.status_code == 200
    assert len(filter_resp.json()["items"]) == 1
    assert filter_resp.json()["items"][0]["title"] == "Backend Redis Caching"


# 4. Test Update, Archive, Restore, Status, Priority & Assignment Endpoints
@pytest.mark.asyncio
async def test_update_archive_restore_status_priority_assign_api(
    async_client: AsyncClient, db_session: AsyncSession
):
    fix = await setup_api_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token1']}"}

    create_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Lifecycle Task"},
        headers=headers,
    )
    issue_id = create_resp.json()["id"]

    # PATCH Update
    update_resp = await async_client.patch(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}",
        json={"title": "Lifecycle Task Updated", "priority": "HIGH"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Lifecycle Task Updated"

    # PATCH Status
    status_resp = await async_client.patch(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/status",
        json={"status": "IN_REVIEW"},
        headers=headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "IN_REVIEW"

    # PATCH Priority
    priority_resp = await async_client.patch(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/priority",
        json={"priority": "URGENT"},
        headers=headers,
    )
    assert priority_resp.status_code == 200
    assert priority_resp.json()["priority"] == "URGENT"

    # POST Assign
    assign_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/assign",
        json={"assignee_id": str(fix["user2"].id)},
        headers=headers,
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["assignee_id"] == str(fix["user2"].id)

    # POST Unassign
    unassign_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/unassign",
        headers=headers,
    )
    assert unassign_resp.status_code == 200
    assert unassign_resp.json()["assignee_id"] is None

    # POST Archive
    archive_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/archive",
        headers=headers,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    # POST Restore
    restore_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}/restore",
        headers=headers,
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["is_archived"] is False


# 5. Test Security: Auth, RBAC & Cross-Organization Isolation
@pytest.mark.asyncio
async def test_api_security_auth_rbac_and_cross_org(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_api_fixtures(db_session)
    valid_headers = {"Authorization": f"Bearer {fix['token1']}"}
    outsider_headers = {"Authorization": f"Bearer {fix['token_outsider']}"}

    # Create issue in Org1/Proj1
    create_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues",
        json={"title": "Secured Issue"},
        headers=valid_headers,
    )
    issue_id = create_resp.json()["id"]

    # Unauthenticated (401 Unauthorized)
    no_auth_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}"
    )
    assert no_auth_resp.status_code == 401

    # Unauthorized outsider accessing Org1 issue (403 Forbidden)
    forbidden_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org1'].id}/projects/{fix['proj1'].id}/issues/{issue_id}",
        headers=outsider_headers,
    )
    assert forbidden_resp.status_code == 403

    # Cross-Organization route mismatch (404 Not Found)
    cross_org_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org2'].id}/projects/{fix['proj1'].id}/issues/{issue_id}",
        headers=outsider_headers,
    )
    assert cross_org_resp.status_code in [404, 403]
