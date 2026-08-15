import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_dependency_fixtures(db_session: AsyncSession):
    user = User(email="dep_user@devtrack.ai", full_name="Dep User", role=UserRole.MEMBER, is_active=True)
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Dep Corp", slug="dep-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="Dep Project", key="DEP", owner_id=user.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "user": user,
        "org": org,
        "proj": proj,
        "token": create_access_token(subject=str(user.id), role=user.role.value),
    }


@pytest.mark.asyncio
async def test_subtasks_hierarchy_and_progress(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_dependency_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token']}"}

    # 1. Create parent issue
    parent = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Parent Issue Task"},
        headers=headers,
    )).json()

    # 2. Create subtask 1 under parent
    s1 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{parent['id']}/subtasks",
        json={"title": "Subtask 1", "status": "TODO"},
        headers=headers,
    )).json()
    assert s1["title"] == "Subtask 1"

    # 3. Create subtask 2 under parent (Done)
    s2 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{parent['id']}/subtasks",
        json={"title": "Subtask 2", "status": "DONE"},
        headers=headers,
    )).json()

    # 4. Check subtask progress (1/2 = 50%)
    prog = (await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{parent['id']}/subtasks/progress",
        headers=headers,
    )).json()
    assert prog["total_subtasks"] == 2
    assert prog["completed_subtasks"] == 1
    assert prog["completion_percentage"] == 50.0

    # 5. Prevent subtask nesting deeper than 1 level (422)
    nested_attempt = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{s1['id']}/subtasks",
        json={"title": "Level 2 Subtask"},
        headers=headers,
    )
    assert nested_attempt.status_code == 422


@pytest.mark.asyncio
async def test_dependencies_and_circular_prevention(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_dependency_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token']}"}

    # Create 3 issues: A, B, C
    iA = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Task A"},
        headers=headers,
    )).json()

    iB = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Task B"},
        headers=headers,
    )).json()

    iC = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Task C"},
        headers=headers,
    )).json()

    # 1. A BLOCKS B
    dep1 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{iA['id']}/dependencies",
        json={"target_issue_id": iB["id"], "dependency_type": "BLOCKS"},
        headers=headers,
    )).json()
    assert dep1["dependency_type"] == "BLOCKS"

    # 2. B BLOCKS C
    dep2 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{iB['id']}/dependencies",
        json={"target_issue_id": iC["id"], "dependency_type": "BLOCKS"},
        headers=headers,
    )).json()
    assert dep2["dependency_type"] == "BLOCKS"

    # 3. Attempt C BLOCKS A -> Circular dependency! Should be blocked with 422
    cycle_attempt = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{iC['id']}/dependencies",
        json={"target_issue_id": iA["id"], "dependency_type": "BLOCKS"},
        headers=headers,
    )
    assert cycle_attempt.status_code == 422

    # 4. Attempt Self-dependency (A BLOCKS A) -> Should be blocked with 422
    self_attempt = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{iA['id']}/dependencies",
        json={"target_issue_id": iA["id"], "dependency_type": "BLOCKS"},
        headers=headers,
    )
    assert self_attempt.status_code == 422
