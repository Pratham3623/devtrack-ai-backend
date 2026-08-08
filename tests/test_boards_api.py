import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import IssueStatus, OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

async def setup_board_fixtures(db_session: AsyncSession):
    """Create two orgs/users/projects for board API tests."""
    owner = User(email="board_owner@devtrack.ai", full_name="Board Owner", role=UserRole.MEMBER, is_active=True)
    member = User(email="board_member@devtrack.ai", full_name="Board Member", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="board_outsider@other.ai", full_name="Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([owner, member, outsider])
    await db_session.flush()

    org = Organization(name="Board Corp", slug="board-corp", owner_id=owner.id)
    db_session.add(org)
    await db_session.flush()

    db_session.add_all([
        OrgMember(organization_id=org.id, user_id=owner.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org.id, user_id=member.id, role=OrgRole.DEVELOPER),
    ])

    other_org = Organization(name="Other Corp", slug="other-corp", owner_id=outsider.id)
    db_session.add(other_org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=other_org.id, user_id=outsider.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="Board Project", key="BRD", owner_id=owner.id)
    other_proj = Project(organization_id=other_org.id, name="Other Project", key="OTH", owner_id=outsider.id)
    db_session.add_all([proj, other_proj])
    await db_session.commit()

    return {
        "owner": owner,
        "member": member,
        "outsider": outsider,
        "org": org,
        "other_org": other_org,
        "proj": proj,
        "other_proj": other_proj,
        "token_owner": create_access_token(subject=str(owner.id), role=owner.role.value),
        "token_member": create_access_token(subject=str(member.id), role=member.role.value),
        "token_outsider": create_access_token(subject=str(outsider.id), role=outsider.role.value),
    }


def board_url(fix, path=""):
    return f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/boards{path}"


# ---------------------------------------------------------------------------
# 1. Board creation and retrieval
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_board_and_get(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_board_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token_owner']}"}

    # Create board
    resp = await async_client.post(board_url(fix), json={"name": "Sprint 1", "is_default": True}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Sprint 1"
    assert data["is_default"] is True
    board_id = data["id"]

    # Get board details (with columns)
    get_resp = await async_client.get(board_url(fix, f"/{board_id}"), headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == board_id

    # List boards
    list_resp = await async_client.get(board_url(fix), headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Update board name
    patch_resp = await async_client.patch(
        board_url(fix, f"/{board_id}"), json={"name": "Sprint 1 Renamed"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Sprint 1 Renamed"

    # Unauthenticated request is rejected
    unauth = await async_client.get(board_url(fix, f"/{board_id}"))
    assert unauth.status_code == 401


# ---------------------------------------------------------------------------
# 2. Column creation, renaming, and reorder
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_column_create_rename_and_reorder(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_board_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token_owner']}"}

    # Create board
    board = (await async_client.post(board_url(fix), json={"name": "Main Board"}, headers=headers)).json()
    board_id = board["id"]
    col_url = board_url(fix, f"/{board_id}/columns")

    # Create three columns
    c1 = (await async_client.post(col_url, json={"name": "Backlog", "mapped_status": "BACKLOG"}, headers=headers)).json()
    c2 = (await async_client.post(col_url, json={"name": "In Progress", "mapped_status": "IN_PROGRESS"}, headers=headers)).json()
    c3 = (await async_client.post(col_url, json={"name": "Done", "mapped_status": "DONE"}, headers=headers)).json()

    assert c1["position"] == 1000
    assert c2["position"] == 2000
    assert c3["position"] == 3000

    # Rename a column
    rename_resp = await async_client.patch(
        board_url(fix, f"/{board_id}/columns/{c2['id']}"),
        json={"name": "In Flight"},
        headers=headers,
    )
    assert rename_resp.status_code == 200
    assert rename_resp.json()["name"] == "In Flight"

    # Reorder: put Done first, then Backlog, then In Flight
    reorder_resp = await async_client.put(
        board_url(fix, f"/{board_id}/columns/reorder"),
        json={"ordered_column_ids": [c3["id"], c1["id"], c2["id"]]},
        headers=headers,
    )
    assert reorder_resp.status_code == 200
    ordered = reorder_resp.json()["columns"]
    assert ordered[0]["id"] == c3["id"]
    assert ordered[0]["position"] == 1000
    assert ordered[1]["id"] == c1["id"]
    assert ordered[1]["position"] == 2000
    assert ordered[2]["id"] == c2["id"]
    assert ordered[2]["position"] == 3000

    # Duplicate mapped_status rejected
    dup_resp = await async_client.post(
        col_url, json={"name": "Another Backlog", "mapped_status": "BACKLOG"}, headers=headers
    )
    assert dup_resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. Move issue between columns (status sync)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_move_issue_between_columns(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_board_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token_owner']}"}

    # Create board + columns
    board = (await async_client.post(board_url(fix), json={"name": "Flow Board"}, headers=headers)).json()
    board_id = board["id"]
    col_url = board_url(fix, f"/{board_id}/columns")

    todo_col = (await async_client.post(col_url, json={"name": "Todo", "mapped_status": "TODO"}, headers=headers)).json()
    done_col = (await async_client.post(col_url, json={"name": "Done", "mapped_status": "DONE"}, headers=headers)).json()

    # Create an issue (starts as TODO by default)
    issue_resp = await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Movable Issue", "status": "TODO"},
        headers=headers,
    )
    issue_id = issue_resp.json()["id"]

    # Move to Done column
    move_resp = await async_client.post(
        board_url(fix, f"/{board_id}/issues/{issue_id}/move"),
        json={"column_id": done_col["id"]},
        headers=headers,
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["status"] == "DONE"

    # Verify issue status changed via issue API
    issue_check = await async_client.get(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues/{issue_id}",
        headers=headers,
    )
    assert issue_check.json()["status"] == "DONE"

    # Move back to Todo column
    move_back = await async_client.post(
        board_url(fix, f"/{board_id}/issues/{issue_id}/move"),
        json={"column_id": todo_col["id"]},
        headers=headers,
    )
    assert move_back.status_code == 200
    assert move_back.json()["status"] == "TODO"


# ---------------------------------------------------------------------------
# 4. Delete column — blocked when active issues exist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_column_blocked_with_active_issues(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_board_fixtures(db_session)
    headers = {"Authorization": f"Bearer {fix['token_owner']}"}

    board = (await async_client.post(board_url(fix), json={"name": "Delete Test Board"}, headers=headers)).json()
    board_id = board["id"]
    col_url = board_url(fix, f"/{board_id}/columns")

    col = (await async_client.post(col_url, json={"name": "In Progress", "mapped_status": "IN_PROGRESS"}, headers=headers)).json()
    empty_col = (await async_client.post(col_url, json={"name": "In Review", "mapped_status": "IN_REVIEW"}, headers=headers)).json()

    # Create issue in IN_PROGRESS
    await async_client.post(
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['proj'].id}/issues",
        json={"title": "Blocking Issue", "status": "IN_PROGRESS"},
        headers=headers,
    )

    # Deletion of column with active issues should be blocked (422)
    del_resp = await async_client.delete(
        board_url(fix, f"/{board_id}/columns/{col['id']}"), headers=headers
    )
    assert del_resp.status_code == 422

    # Deletion of column with no issues should succeed (204)
    del_ok = await async_client.delete(
        board_url(fix, f"/{board_id}/columns/{empty_col['id']}"), headers=headers
    )
    assert del_ok.status_code == 204


# ---------------------------------------------------------------------------
# 5. Cross-project / cross-org security
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_unauthorized_and_cross_project(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_board_fixtures(db_session)
    owner_headers = {"Authorization": f"Bearer {fix['token_owner']}"}
    outsider_headers = {"Authorization": f"Bearer {fix['token_outsider']}"}

    # Create a board in owner's project
    board = (await async_client.post(board_url(fix), json={"name": "Private Board"}, headers=owner_headers)).json()
    board_id = board["id"]

    # Outsider cannot access owner's board (403)
    forbidden = await async_client.get(board_url(fix, f"/{board_id}"), headers=outsider_headers)
    assert forbidden.status_code == 403

    # Outsider cannot create column in owner's board (403)
    col_forbidden = await async_client.post(
        board_url(fix, f"/{board_id}/columns"),
        json={"name": "Hack", "mapped_status": "TODO"},
        headers=outsider_headers,
    )
    assert col_forbidden.status_code == 403

    # Cross-project board access: board belongs to proj but accessed via other_proj (404)
    cross_proj_url = (
        f"/api/v1/organizations/{fix['org'].id}/projects/{fix['other_proj'].id}/boards/{board_id}"
    )
    cross_resp = await async_client.get(cross_proj_url, headers=owner_headers)
    assert cross_resp.status_code in [403, 404]

    # Reorder with foreign column IDs rejected (422)
    col = (await async_client.post(
        board_url(fix, f"/{board_id}/columns"),
        json={"name": "Backlog", "mapped_status": "BACKLOG"},
        headers=owner_headers,
    )).json()

    bad_reorder = await async_client.put(
        board_url(fix, f"/{board_id}/columns/reorder"),
        json={"ordered_column_ids": [str(uuid.uuid4())]},  # foreign ID
        headers=owner_headers,
    )
    assert bad_reorder.status_code == 422
