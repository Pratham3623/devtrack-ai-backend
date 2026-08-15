"""
Phase 9 — Analytics & Dashboard API Integration Tests
======================================================
Verifies API endpoints and service calculations for executive dashboard metrics,
sprint velocity trends, burndown charts, team productivity, activity graphs,
issue statistics, and dynamic project health score calculations.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.issue import Issue
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project, ProjectMember
from app.domain.models.user import User


async def setup_analytics_fixtures(db_session: AsyncSession):
    user = User(email="analytics_owner@devtrack.ai", full_name="Analytics Owner", role=UserRole.MEMBER, is_active=True)
    dev = User(email="analytics_dev@devtrack.ai", full_name="Analytics Dev", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="analytics_outsider@other.ai", full_name="Analytics Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, dev, outsider])
    await db_session.flush()

    org = Organization(name="Analytics Corp", slug="analytics-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()

    db_session.add_all([
        OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org.id, user_id=dev.id, role=OrgRole.DEVELOPER),
    ])

    proj = Project(organization_id=org.id, name="Analytics Project", key="ANP", owner_id=user.id)
    db_session.add(proj)
    await db_session.flush()

    db_session.add_all([
        ProjectMember(project_id=proj.id, user_id=user.id),
        ProjectMember(project_id=proj.id, user_id=dev.id),
    ])

    from app.domain.models.enums import IssuePriority, IssueStatus
    i1 = Issue(project_id=proj.id, issue_number=1, title="Task 1", status=IssueStatus.DONE, priority=IssuePriority.HIGH, reporter_id=user.id, assignee_id=dev.id)
    i2 = Issue(project_id=proj.id, issue_number=2, title="Task 2", status=IssueStatus.IN_PROGRESS, priority=IssuePriority.URGENT, reporter_id=user.id, assignee_id=dev.id)
    i3 = Issue(project_id=proj.id, issue_number=3, title="Task 3", status=IssueStatus.TODO, priority=IssuePriority.MEDIUM, reporter_id=user.id, assignee_id=user.id)
    db_session.add_all([i1, i2, i3])


    await db_session.commit()

    return {
        "user": user,
        "dev": dev,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "headers_owner": {"Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role.value)}"},
        "headers_outsider": {"Authorization": f"Bearer {create_access_token(subject=str(outsider.id), role=outsider.role.value)}"},
    }


@pytest.mark.asyncio
async def test_get_project_dashboard_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_analytics_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/dashboard"

    resp = await async_client.get(url, headers=fix["headers_owner"])
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == str(fix["proj"].id)
    assert data["project_name"] == "Analytics Project"
    assert data["total_members"] == 2
    assert data["open_issues_count"] == 2
    assert data["completed_issues_count"] == 1
    assert 0 <= data["health_score"] <= 100
    assert round(data["completion_percentage"], 1) == 33.3


@pytest.mark.asyncio
async def test_get_project_analytics_api(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_analytics_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/analytics"

    resp = await async_client.get(url, headers=fix["headers_owner"])
    assert resp.status_code == 200
    data = resp.json()

    assert data["project_id"] == str(fix["proj"].id)

    # 1. Velocity Trend
    assert isinstance(data["velocity_trend"], list)
    assert len(data["velocity_trend"]) >= 3
    assert "committed" in data["velocity_trend"][0]
    assert "completed" in data["velocity_trend"][0]

    # 2. Issue Status & Priority Distributions
    assert data["issue_status_distribution"]["DONE"] == 1
    assert data["issue_status_distribution"]["IN_PROGRESS"] == 1
    assert data["issue_status_distribution"]["TODO"] == 1

    # 3. Burndown Chart
    assert isinstance(data["burndown_chart"], list)
    assert len(data["burndown_chart"]) == 8  # Days 0 to 7
    assert data["burndown_chart"][0]["day"] == "Day 0"
    assert "ideal_remaining" in data["burndown_chart"][0]
    assert "actual_remaining" in data["burndown_chart"][0]

    # 4. Productivity & Workload
    assert isinstance(data["productivity_metrics"], list)
    assert len(data["productivity_metrics"]) == 2
    dev_prod = next(p for p in data["productivity_metrics"] if p["user_name"] == "Analytics Dev")
    assert dev_prod["issues_assigned"] == 2
    assert dev_prod["issues_completed"] == 1


    # 5. Activity Graph
    assert isinstance(data["activity_graph"], list)
    assert len(data["activity_graph"]) == 7

    # 6. Issue Statistics & Health Breakdown
    assert "issue_statistics" in data
    assert data["issue_statistics"]["total_issues"] == 3
    assert data["issue_statistics"]["resolved_issues"] == 1

    assert "project_health_breakdown" in data
    assert "overall_score" in data["project_health_breakdown"]
    assert "health_status" in data["project_health_breakdown"]


@pytest.mark.asyncio
async def test_analytics_unauthorized_access(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_analytics_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/analytics"

    resp = await async_client.get(url, headers=fix["headers_outsider"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analytics_nonexistent_project(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_analytics_fixtures(db_session)
    import uuid
    random_id = uuid.uuid4()
    url = f"/api/v1/organizations/{fix['org'].id}/projects/{random_id}/analytics"

    resp = await async_client.get(url, headers=fix["headers_owner"])
    assert resp.status_code == 404
