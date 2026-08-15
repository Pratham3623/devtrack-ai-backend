"""
Phase 8 — AI REST & Streaming API Integration Tests
===================================================
Verifies API endpoints for AI issue generation, sprint planning, documentation,
bug analysis, project executive summary, SSE streaming, and cross-tenant authorization.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_ai_api_fixtures(db_session: AsyncSession):
    user = User(email="ai_api_owner@devtrack.ai", full_name="AI Owner", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="ai_api_outsider@other.ai", full_name="AI Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, outsider])
    await db_session.flush()

    org = Organization(name="AI API Corp", slug="ai-api-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="AI API Project", key="AIP", owner_id=user.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "user": user,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "headers_owner": {"Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role.value)}"},
        "headers_outsider": {"Authorization": f"Bearer {create_access_token(subject=str(outsider.id), role=outsider.role.value)}"},
    }


@pytest.mark.asyncio
async def test_ai_generate_issues_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/generate-issues"

    # Success
    resp = await async_client.post(url, json={"prompt": "Build OAuth SSO", "count": 2}, headers=fix["headers_owner"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["generated_issues"]) == 2

    # Outsider blocked
    unauth = await async_client.post(url, json={"prompt": "Build OAuth SSO", "count": 2}, headers=fix["headers_outsider"])
    assert unauth.status_code == 403


@pytest.mark.asyncio
async def test_ai_sprint_plan_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/sprint-plan"

    resp = await async_client.post(
        url,
        json={"sprint_name": "Sprint 1", "sprint_goal": "MVP Launch", "capacity_issues": 4},
        headers=fix["headers_owner"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sprint_name"] == "Sprint 1"
    assert data["capacity_used"] >= 1


@pytest.mark.asyncio
async def test_ai_generate_docs_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/generate-docs"

    resp = await async_client.post(
        url,
        json={"doc_type": "README"},
        headers=fix["headers_owner"],
    )
    assert resp.status_code == 200
    assert "README" in resp.json()["doc_type"]


@pytest.mark.asyncio
async def test_ai_bug_analysis_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/bug-analysis"

    resp = await async_client.post(
        url,
        json={
            "bug_title": "404 on login",
            "bug_description": "Login route returns 404",
            "stack_trace": "NotFoundHttpException",
        },
        headers=fix["headers_owner"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bug_title"] == "404 on login"
    assert data["code_fix_snippet"] is not None


@pytest.mark.asyncio
async def test_ai_project_summary_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/summary"

    resp = await async_client.post(
        url,
        json={"period_days": 14},
        headers=fix["headers_owner"],
    )
    assert resp.status_code == 200
    assert resp.json()["project_name"] == "AI API Project"


@pytest.mark.asyncio
async def test_ai_stream_response_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_ai_api_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/ai/stream?prompt=Test"

    resp = await async_client.get(url, headers=fix["headers_owner"])
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "data:" in resp.text
