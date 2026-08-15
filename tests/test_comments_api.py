import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


async def setup_comment_fixtures(db_session: AsyncSession):
    author = User(email="commenter@devtrack.ai", full_name="Comment Author", role=UserRole.MEMBER, is_active=True)
    member = User(email="other_member@devtrack.ai", full_name="Other Member", role=UserRole.MEMBER, is_active=True)
    admin = User(email="org_admin@devtrack.ai", full_name="Org Admin", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="outsider@other.ai", full_name="Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([author, member, admin, outsider])
    await db_session.flush()

    org = Organization(name="Comment Corp", slug="comment-corp", owner_id=admin.id)
    db_session.add(org)
    await db_session.flush()

    db_session.add_all([
        OrgMember(organization_id=org.id, user_id=admin.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org.id, user_id=author.id, role=OrgRole.DEVELOPER),
        OrgMember(organization_id=org.id, user_id=member.id, role=OrgRole.DEVELOPER),
    ])

    proj = Project(organization_id=org.id, name="Comment Project", key="CMT", owner_id=admin.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "author": author,
        "member": member,
        "admin": admin,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "token_author": create_access_token(subject=str(author.id), role=author.role.value),
        "token_member": create_access_token(subject=str(member.id), role=member.role.value),
        "token_admin": create_access_token(subject=str(admin.id), role=admin.role.value),
        "token_outsider": create_access_token(subject=str(outsider.id), role=outsider.role.value),
    }


@pytest.mark.asyncio
async def test_comment_crud_and_authorization(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_comment_fixtures(db_session)
    author_h = {"Authorization": f"Bearer {fix['token_author']}"}
    member_h = {"Authorization": f"Bearer {fix['token_member']}"}
    admin_h = {"Authorization": f"Bearer {fix['token_admin']}"}
    outsider_h = {"Authorization": f"Bearer {fix['token_outsider']}"}

    # 1. Create issue
    issue_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Issue for commenting"},
        headers=author_h,
    )
    issue_id = issue_resp.json()["id"]

    # 2. Add comment
    c_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments",
        json={"content": "First comment on task!"},
        headers=author_h,
    )
    assert c_resp.status_code == 201
    c_data = c_resp.json()
    comment_id = c_data["id"]
    assert c_data["content"] == "First comment on task!"
    assert c_data["author"]["email"] == fix["author"].email

    # 3. List comments
    list_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments",
        headers=author_h,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 4. Other non-author member cannot edit author's comment (403)
    edit_forbidden = await async_client.patch(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments/{comment_id}",
        json={"content": "Hacked content"},
        headers=member_h,
    )
    assert edit_forbidden.status_code == 403

    # 5. Author can edit comment
    edit_ok = await async_client.patch(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments/{comment_id}",
        json={"content": "Updated comment content"},
        headers=author_h,
    )
    assert edit_ok.status_code == 200
    assert edit_ok.json()["content"] == "Updated comment content"

    # 6. Activity stream contains comment events
    act_resp = await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/activity",
        headers=author_h,
    )
    assert act_resp.status_code == 200
    activities = act_resp.json()
    assert len(activities) >= 1

    # 7. Org admin can delete author's comment
    del_ok = await async_client.delete(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments/{comment_id}",
        headers=admin_h,
    )
    assert del_ok.status_code == 204

    # 8. Outsider cannot post comment (403)
    out_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}/comments",
        json={"content": "Outsider comment"},
        headers=outsider_h,
    )
    assert out_resp.status_code == 403
