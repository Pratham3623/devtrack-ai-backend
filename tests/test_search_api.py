"""
Phase 10 — Global Search & Saved Search API Integration Tests
===============================================================
Verifies multi-entity enterprise search (Issues, Projects, Comments, Members),
full-text pattern matching, filters, sorting, and Saved Search CRUD preset management.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import IssuePriority, IssueStatus, OrgRole, UserRole
from app.domain.models.issue import Issue
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_search_fixtures(db_session: AsyncSession):
    user = User(email="search_owner@devtrack.ai", full_name="Search Owner", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="search_outsider@other.ai", full_name="Search Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, outsider])
    await db_session.flush()

    org = Organization(name="Search Corp", slug="search-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="Alpha Engine", key="ALP", description="Core engine module", owner_id=user.id)
    db_session.add(proj)
    await db_session.flush()

    i1 = Issue(project_id=proj.id, issue_number=101, title="Refactor OAuth Authentication", description="Fix token refresh deadlock", status=IssueStatus.IN_PROGRESS, priority=IssuePriority.URGENT, reporter_id=user.id)
    i2 = Issue(project_id=proj.id, issue_number=102, title="Update Dashboard CSS", description="Make charts dark mode compatible", status=IssueStatus.DONE, priority=IssuePriority.LOW, reporter_id=user.id)
    db_session.add_all([i1, i2])

    await db_session.commit()

    return {
        "user": user,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "i1": i1,
        "i2": i2,
        "headers_owner": {"Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role.value)}"},
        "headers_outsider": {"Authorization": f"Bearer {create_access_token(subject=str(outsider.id), role=outsider.role.value)}"},
    }


@pytest.mark.asyncio
async def test_global_search_api_multi_entity(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_search_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/search"

    # Search for "OAuth" -> should match Issue #101
    resp = await async_client.get(url, params={"q": "OAuth"}, headers=fix["headers_owner"])
    assert resp.status_code == 200
    data = resp.json()

    assert data["query"] == "OAuth"
    assert data["total_results"] >= 1
    assert data["execution_time_ms"] >= 0
    items = data["items"]
    assert any("Refactor OAuth" in item["title"] for item in items)


@pytest.mark.asyncio
async def test_global_search_api_filtered(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_search_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/search"

    # Search with Priority filter
    resp = await async_client.get(url, params={"priority": "URGENT"}, headers=fix["headers_owner"])
    assert resp.status_code == 200
    data = resp.json()

    items = data["items"]
    assert len(items) >= 1
    assert all(item["metadata"].get("priority") == "URGENT" for item in items if item["entity_type"] == "issue")


@pytest.mark.asyncio
async def test_saved_search_crud_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_search_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/saved-searches"

    # 1. Create Saved Search
    dto = {
        "name": "Urgent OAuth Issues",
        "query_params": {"q": "OAuth", "priority": "URGENT"},
        "is_shared": True,
    }
    create_resp = await async_client.post(url, json=dto, headers=fix["headers_owner"])
    assert create_resp.status_code == 201
    saved_data = create_resp.json()
    saved_id = saved_data["id"]
    assert saved_data["name"] == "Urgent OAuth Issues"
    assert saved_data["is_shared"] is True

    # 2. List Saved Searches
    list_resp = await async_client.get(url, headers=fix["headers_owner"])
    assert list_resp.status_code == 200
    searches = list_resp.json()
    assert any(s["id"] == saved_id for s in searches)

    # 3. Delete Saved Search
    del_resp = await async_client.delete(f"{url}/{saved_id}", headers=fix["headers_owner"])
    assert del_resp.status_code == 200

    # 4. Verify Deleted
    list_after = await async_client.get(url, headers=fix["headers_owner"])
    assert not any(s["id"] == saved_id for s in list_after.json())


@pytest.mark.asyncio
async def test_search_tenant_isolation(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_search_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/search"

    # Outsider blocked
    resp = await async_client.get(url, params={"q": "OAuth"}, headers=fix["headers_outsider"])
    assert resp.status_code == 403
