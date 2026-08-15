import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_label_fixtures(db_session: AsyncSession):
    user = User(email="labeler@devtrack.ai", full_name="Label User", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="label_outsider@other.ai", full_name="Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, outsider])
    await db_session.flush()

    org = Organization(name="Label Corp", slug="label-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="Label Project", key="LBL", owner_id=user.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "user": user,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "token_user": create_access_token(subject=str(user.id), role=user.role.value),
        "token_outsider": create_access_token(subject=str(outsider.id), role=outsider.role.value),
    }


@pytest.mark.asyncio
async def test_label_crud_assignment_and_filtering(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_label_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token_user']}"}

    # 1. Create Labels
    l1 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/labels",
        json={"name": "Frontend", "color": "#3b82f6"},
        headers=headers,
    )).json()

    l2 = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/labels",
        json={"name": "Backend", "color": "#10b981"},
        headers=headers,
    )).json()

    assert l1["name"] == "Frontend"
    assert l2["name"] == "Backend"

    # 2. List Labels
    labels_list = (await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/labels",
        headers=headers,
    )).json()
    assert len(labels_list) == 2

    # 3. Create Issue & Assign Label
    issue = (await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Label Assignment Test"},
        headers=headers,
    )).json()

    assign_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue['id']}/labels",
        json={"label_id": l1["id"]},
        headers=headers,
    )
    assert assign_resp.status_code == 200
    assert len(assign_resp.json()) == 1

    # 4. Filter issues by label_id
    filtered = (await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues?label_id={l1['id']}",
        headers=headers,
    )).json()
    assert filtered["total"] == 1

    # 5. Remove label from issue
    unassign_resp = await async_client.delete(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue['id']}/labels/{l1['id']}",
        headers=headers,
    )
    assert unassign_resp.status_code == 200
    assert len(unassign_resp.json()) == 0
