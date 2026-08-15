"""
Phase 6I – Security Audit
=========================
Comprehensive regression tests for:
  1. Authentication enforcement  (401 on every protected endpoint)
  2. Multi-tenant isolation       (Org A data invisible to Org B members)
  3. RBAC / role-based access     (least-privilege for every role tier)
  4. Parameter tampering          (cross-project / cross-org ID substitution)
  5. IDOR prevention              (direct resource ID guessing across tenants)
  6. Token / JWT security         (forged, expired, malformed tokens)
  7. Comment authorship           (only author / org-admin may edit / delete)
  8. Dependency scope isolation   (cross-org dependencies blocked)
  9. Label scope isolation        (cross-org labels blocked)
 10. Board scope isolation        (cross-org board / column access blocked)
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User


# ---------------------------------------------------------------------------
# Shared test-fixture builder
# ---------------------------------------------------------------------------

async def build_two_tenant_world(db_session: AsyncSession):
    """
    Creates two completely independent organizations, each with their own
    owner and a regular developer member.  Returns a dict with all entities
    and pre-generated JWT tokens.

    Org A  →  owner_a (OWNER),  dev_a (DEVELOPER)
    Org B  →  owner_b (OWNER),  dev_b (DEVELOPER)
    """
    owner_a = User(email="owner_a@acme.ai",  full_name="Owner A",  role=UserRole.MEMBER, is_active=True)
    dev_a   = User(email="dev_a@acme.ai",    full_name="Dev A",    role=UserRole.MEMBER, is_active=True)
    owner_b = User(email="owner_b@rival.ai", full_name="Owner B",  role=UserRole.MEMBER, is_active=True)
    dev_b   = User(email="dev_b@rival.ai",   full_name="Dev B",    role=UserRole.MEMBER, is_active=True)
    db_session.add_all([owner_a, dev_a, owner_b, dev_b])
    await db_session.flush()

    org_a = Organization(name="Acme Corp",  slug="acme-corp",  owner_id=owner_a.id)
    org_b = Organization(name="Rival Corp", slug="rival-corp", owner_id=owner_b.id)
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    db_session.add_all([
        OrgMember(organization_id=org_a.id, user_id=owner_a.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org_a.id, user_id=dev_a.id,   role=OrgRole.DEVELOPER),
        OrgMember(organization_id=org_b.id, user_id=owner_b.id, role=OrgRole.OWNER),
        OrgMember(organization_id=org_b.id, user_id=dev_b.id,   role=OrgRole.DEVELOPER),
    ])

    proj_a = Project(organization_id=org_a.id, name="Project Alpha", key="ALPHA", owner_id=owner_a.id)
    proj_b = Project(organization_id=org_b.id, name="Project Beta",  key="BETA",  owner_id=owner_b.id)
    db_session.add_all([proj_a, proj_b])
    await db_session.commit()

    return {
        # Users
        "owner_a": owner_a, "dev_a": dev_a,
        "owner_b": owner_b, "dev_b": dev_b,
        # Orgs
        "org_a": org_a, "org_b": org_b,
        # Projects
        "proj_a": proj_a, "proj_b": proj_b,
        # Tokens
        "tok_owner_a": create_access_token(subject=str(owner_a.id), role=owner_a.role.value),
        "tok_dev_a":   create_access_token(subject=str(dev_a.id),   role=dev_a.role.value),
        "tok_owner_b": create_access_token(subject=str(owner_b.id), role=owner_b.role.value),
        "tok_dev_b":   create_access_token(subject=str(dev_b.id),   role=dev_b.role.value),
    }


# ===========================================================================
# 1. AUTHENTICATION ENFORCEMENT
#    Every write endpoint must return 401 when no token is supplied.
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_401_no_token_on_all_write_endpoints(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Confirm 401 is returned for unauthenticated requests on all resource classes."""
    fake_org  = uuid.uuid4()
    fake_proj = uuid.uuid4()
    fake_id   = uuid.uuid4()

    endpoints_without_auth = [
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}"),
        ("PATCH",  f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/archive"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/restore"),
        ("PATCH",  f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/status"),
        ("PATCH",  f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/priority"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/assign"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/unassign"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/comments"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/comments"),
        ("PATCH",  f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/comments/{fake_id}"),
        ("DELETE", f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/comments/{fake_id}"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/activity"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/labels"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/labels"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/subtasks"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/subtasks"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/dependencies"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/issues/{fake_id}/dependencies"),
        ("GET",    f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/boards"),
        ("POST",   f"/api/v1/organizations/{fake_org}/projects/{fake_proj}/boards"),
    ]

    for method, url in endpoints_without_auth:
        resp = await async_client.request(method, url)
        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated {method} {url}, got {resp.status_code}"
        )


# ===========================================================================
# 2. MULTI-TENANT ISOLATION — ORGANIZATIONS
#    Org B members must never reach Org A's org-level resources.
# ===========================================================================

@pytest.mark.asyncio
async def test_org_isolation_cross_tenant_access_blocked(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Org B members cannot GET, manage members, or audit Org A."""
    w = await build_two_tenant_world(db_session)
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # GET Org A details
    resp = await async_client.get(f"/api/v1/organizations/{w['org_a'].id}", headers=b_hdrs)
    assert resp.status_code == 403, "Org B owner must not read Org A details"

    # GET Org A members
    resp = await async_client.get(f"/api/v1/organizations/{w['org_a'].id}/members", headers=b_hdrs)
    assert resp.status_code == 403, "Org B owner must not list Org A members"

    # GET Org A audit logs
    resp = await async_client.get(f"/api/v1/organizations/{w['org_a'].id}/audit-logs", headers=b_hdrs)
    assert resp.status_code == 403, "Org B owner must not read Org A audit logs"


# ===========================================================================
# 3. MULTI-TENANT ISOLATION — PROJECTS
#    Org B members must never list or access Org A's projects.
# ===========================================================================

@pytest.mark.asyncio
async def test_project_isolation_cross_tenant(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Org B users cannot list, get, or modify Org A's projects."""
    w = await build_two_tenant_world(db_session)
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # List Org A projects
    resp = await async_client.get(f"/api/v1/organizations/{w['org_a'].id}/projects", headers=b_hdrs)
    assert resp.status_code == 403, "Org B owner must not list Org A projects"

    # GET specific project
    resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}", headers=b_hdrs
    )
    assert resp.status_code == 403, "Org B owner must not get Org A project details"


# ===========================================================================
# 4. MULTI-TENANT ISOLATION — ISSUES
#    Core IDOR test: can Org B read/modify an issue that belongs to Org A?
# ===========================================================================

@pytest.mark.asyncio
async def test_issue_isolation_cross_tenant_idor(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    IDOR test: Org B cannot GET, PATCH, archive, or change status
    of an issue belonging to Org A.
    """
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create an issue in Org A / Project A
    issue_resp = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        json={"title": "Org A Secret Issue"},
        headers=a_hdrs,
    )
    assert issue_resp.status_code == 201
    issue_id = issue_resp.json()["id"]

    # --- Org B attempts ---
    cases = [
        ("GET",   f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}", None),
        ("PATCH", f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}", {"title": "Tampered"}),
        ("POST",  f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/archive", None),
        ("PATCH", f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/status", {"status": "DONE"}),
        ("PATCH", f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/priority", {"priority": "URGENT"}),
        ("POST",  f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/assign", {"assignee_id": str(w["owner_b"].id)}),
    ]
    for method, url, body in cases:
        resp = await async_client.request(method, url, json=body, headers=b_hdrs)
        assert resp.status_code in (403, 404), (
            f"IDOR: {method} {url} returned {resp.status_code} for Org B user"
        )


# ===========================================================================
# 5. PARAMETER TAMPERING — CROSS-PROJECT ISSUE ACCESS
#    A valid Org A member uses Org B's project ID in the URL path.
# ===========================================================================

@pytest.mark.asyncio
async def test_cross_project_parameter_tampering(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    URL path tampering: authenticated Org A user substitutes Org B's project
    ID into the URL.  The issue must not be accessible.
    """
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}

    # Create an issue in Org A
    issue_resp = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        json={"title": "Tamper Target Issue"},
        headers=a_hdrs,
    )
    issue_id = issue_resp.json()["id"]

    # Try to access via Org B's project ID (should return 403 or 404)
    tampered = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_b'].id}/issues/{issue_id}",
        headers=a_hdrs,
    )
    assert tampered.status_code in (403, 404), (
        f"Cross-project tamper succeeded: got {tampered.status_code}"
    )

    # Try with fully substituted Org B path
    cross_org = await async_client.get(
        f"/api/v1/organizations/{w['org_b'].id}/projects/{w['proj_a'].id}/issues/{issue_id}",
        headers=a_hdrs,
    )
    assert cross_org.status_code in (403, 404), (
        f"Cross-org tamper succeeded: got {cross_org.status_code}"
    )


# ===========================================================================
# 6. TOKEN / JWT SECURITY
# ===========================================================================

@pytest.mark.asyncio
async def test_malformed_and_fake_tokens_rejected(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Various invalid tokens must all return 401."""
    w = await build_two_tenant_world(db_session)
    url = f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues"

    bad_tokens = [
        "not.a.jwt",
        "Bearer",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIifQ.invalid_sig",
        "null",
        "",
    ]
    for tok in bad_tokens:
        hdrs = {"Authorization": f"Bearer {tok}"} if tok else {"Authorization": "Bearer "}
        resp = await async_client.get(url, headers=hdrs)
        assert resp.status_code == 401, (
            f"Bad token '{tok[:30]}...' returned {resp.status_code} instead of 401"
        )


@pytest.mark.asyncio
async def test_token_for_nonexistent_user_rejected(
    async_client: AsyncClient, db_session: AsyncSession
):
    """A structurally valid JWT pointing to a non-existent user ID is rejected."""
    w = await build_two_tenant_world(db_session)
    ghost_token = create_access_token(subject=str(uuid.uuid4()), role="MEMBER")
    hdrs = {"Authorization": f"Bearer {ghost_token}"}

    resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        headers=hdrs,
    )
    assert resp.status_code == 401, (
        f"Token for non-existent user returned {resp.status_code} instead of 401"
    )


# ===========================================================================
# 7. RBAC — DEVELOPER CANNOT PERFORM OWNER-ONLY ACTIONS
# ===========================================================================

@pytest.mark.asyncio
async def test_rbac_developer_cannot_delete_org_or_transfer_ownership(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Developer role must be blocked from ownership-level actions."""
    w = await build_two_tenant_world(db_session)
    dev_hdrs = {"Authorization": f"Bearer {w['tok_dev_a']}"}

    # Developer cannot delete organization
    resp = await async_client.delete(
        f"/api/v1/organizations/{w['org_a'].id}", headers=dev_hdrs
    )
    assert resp.status_code == 403, (
        f"Developer was able to delete organization (got {resp.status_code})"
    )

    # Developer cannot transfer ownership
    resp = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/transfer-ownership",
        json={"new_owner_id": str(w["dev_a"].id)},
        headers=dev_hdrs,
    )
    assert resp.status_code == 403, (
        f"Developer was able to transfer ownership (got {resp.status_code})"
    )


@pytest.mark.asyncio
async def test_rbac_developer_cannot_remove_org_members(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Developer must not be able to remove other org members."""
    w = await build_two_tenant_world(db_session)
    dev_hdrs = {"Authorization": f"Bearer {w['tok_dev_a']}"}

    resp = await async_client.delete(
        f"/api/v1/organizations/{w['org_a'].id}/members/{w['owner_a'].id}",
        headers=dev_hdrs,
    )
    assert resp.status_code == 403, (
        f"Developer removed an org member (got {resp.status_code})"
    )


# ===========================================================================
# 8. COMMENT AUTHORSHIP — IDOR + RBAC COMBINATION
# ===========================================================================

@pytest.mark.asyncio
async def test_comment_authorship_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    - Org B member cannot post comments on Org A issues.
    - Org A developer (non-author) cannot edit another member's comment.
    - Org A developer (non-author) cannot delete another member's comment.
    - Org A owner CAN delete any comment (admin override).
    """
    w = await build_two_tenant_world(db_session)
    a_owner_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    a_dev_hdrs   = {"Authorization": f"Bearer {w['tok_dev_a']}"}
    b_owner_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create issue in Org A as owner
    issue = (await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        json={"title": "Comment Security Issue"},
        headers=a_owner_hdrs,
    )).json()
    issue_id = issue["id"]

    # Owner A posts a comment
    comment = (await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/comments",
        json={"content": "Owner A comment"},
        headers=a_owner_hdrs,
    )).json()
    comment_id = comment["id"]

    # Dev A (non-author) cannot edit owner's comment
    edit_resp = await async_client.patch(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/comments/{comment_id}",
        json={"content": "Hijacked!"},
        headers=a_dev_hdrs,
    )
    assert edit_resp.status_code == 403, (
        f"Non-author member edited comment (got {edit_resp.status_code})"
    )

    # Dev A (non-author) cannot delete owner's comment
    del_resp = await async_client.delete(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/comments/{comment_id}",
        headers=a_dev_hdrs,
    )
    assert del_resp.status_code == 403, (
        f"Non-author member deleted comment (got {del_resp.status_code})"
    )

    # Org B member cannot post a comment on Org A's issue
    out_comment = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/comments",
        json={"content": "Org B intrusion"},
        headers=b_owner_hdrs,
    )
    assert out_comment.status_code == 403, (
        f"Org B member posted comment on Org A issue (got {out_comment.status_code})"
    )

    # Org A owner (OWNER role) CAN delete any comment
    admin_del = await async_client.delete(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_id}/comments/{comment_id}",
        headers=a_owner_hdrs,
    )
    assert admin_del.status_code == 204, (
        f"Org A owner could not delete a comment (got {admin_del.status_code})"
    )


# ===========================================================================
# 9. LABEL SCOPE ISOLATION
# ===========================================================================

@pytest.mark.asyncio
async def test_label_cross_org_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Org B cannot list or manage Org A's project labels."""
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create a label in Org A
    lbl = (await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/labels",
        json={"name": "Confidential", "color": "#ff0000"},
        headers=a_hdrs,
    )).json()
    lbl_id = lbl["id"]

    # Org B cannot list Org A labels
    list_resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/labels",
        headers=b_hdrs,
    )
    assert list_resp.status_code == 403, (
        f"Org B listed Org A labels (got {list_resp.status_code})"
    )

    # Org B cannot create a label in Org A
    create_resp = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/labels",
        json={"name": "Injected Label", "color": "#000000"},
        headers=b_hdrs,
    )
    assert create_resp.status_code == 403, (
        f"Org B created a label in Org A (got {create_resp.status_code})"
    )

    # Org B cannot delete Org A label
    del_resp = await async_client.delete(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/labels/{lbl_id}",
        headers=b_hdrs,
    )
    assert del_resp.status_code == 403, (
        f"Org B deleted Org A label (got {del_resp.status_code})"
    )


# ===========================================================================
# 10. BOARD SCOPE ISOLATION
# ===========================================================================

@pytest.mark.asyncio
async def test_board_cross_org_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Org B cannot access or modify Org A's kanban boards or columns."""
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    board_base = f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/boards"

    # Create board in Org A
    board = (await async_client.post(
        board_base, json={"name": "A-Board"}, headers=a_hdrs
    )).json()
    board_id = board["id"]

    # Org B cannot GET Org A board
    get_resp = await async_client.get(f"{board_base}/{board_id}", headers=b_hdrs)
    assert get_resp.status_code == 403, (
        f"Org B read Org A board (got {get_resp.status_code})"
    )

    # Org B cannot create column in Org A board
    col_resp = await async_client.post(
        f"{board_base}/{board_id}/columns",
        json={"name": "Injected Col", "mapped_status": "TODO"},
        headers=b_hdrs,
    )
    assert col_resp.status_code == 403, (
        f"Org B created column in Org A board (got {col_resp.status_code})"
    )

    # Org B cannot patch Org A board
    patch_resp = await async_client.patch(
        f"{board_base}/{board_id}", json={"name": "Hijacked"}, headers=b_hdrs
    )
    assert patch_resp.status_code == 403, (
        f"Org B patched Org A board (got {patch_resp.status_code})"
    )


# ===========================================================================
# 11. DEPENDENCY SCOPE ISOLATION
#     Cross-org issues must not be linkable as dependencies.
# ===========================================================================

@pytest.mark.asyncio
async def test_dependency_cross_org_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    An issue in Org A cannot be linked as a dependency to an issue in Org B.
    Org B members cannot read or delete Org A's dependencies.
    """
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create issues in both orgs
    issue_a = (await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        json={"title": "Issue A"},
        headers=a_hdrs,
    )).json()

    issue_b = (await async_client.post(
        f"/api/v1/organizations/{w['org_b'].id}/projects/{w['proj_b'].id}/issues",
        json={"title": "Issue B"},
        headers=b_hdrs,
    )).json()

    # Org A user cannot create a dependency pointing to an Org B issue ID
    cross_dep = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_a['id']}/dependencies",
        json={"target_issue_id": issue_b["id"], "dependency_type": "BLOCKS"},
        headers=a_hdrs,
    )
    # Must be rejected — target issue is not in the same project scope
    assert cross_dep.status_code in (403, 404, 422), (
        f"Cross-org dependency was accepted (got {cross_dep.status_code})"
    )

    # Org B cannot list Org A's dependencies
    list_resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{issue_a['id']}/dependencies",
        headers=b_hdrs,
    )
    assert list_resp.status_code == 403, (
        f"Org B listed Org A dependencies (got {list_resp.status_code})"
    )


# ===========================================================================
# 12. SUBTASK SCOPE ISOLATION
# ===========================================================================

@pytest.mark.asyncio
async def test_subtask_cross_org_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Org B cannot list or create subtasks on Org A's issues."""
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create a parent issue in Org A
    parent = (await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        json={"title": "Parent A"},
        headers=a_hdrs,
    )).json()

    # Org B cannot list subtasks of Org A issue
    list_resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{parent['id']}/subtasks",
        headers=b_hdrs,
    )
    assert list_resp.status_code == 403, (
        f"Org B listed Org A subtasks (got {list_resp.status_code})"
    )

    # Org B cannot create a subtask under Org A issue
    create_resp = await async_client.post(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues/{parent['id']}/subtasks",
        json={"title": "Injected Subtask"},
        headers=b_hdrs,
    )
    assert create_resp.status_code == 403, (
        f"Org B created a subtask in Org A (got {create_resp.status_code})"
    )


# ===========================================================================
# 13. UUID ENUMERATION RESISTANCE
#     Requesting a resource with a randomly-generated UUID must return
#     404 (not found) or 403 (forbidden), never 500.
# ===========================================================================

@pytest.mark.asyncio
async def test_random_uuid_enumeration_resistance(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Random UUIDs must never cause 500 or leak data."""
    w = await build_two_tenant_world(db_session)
    hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}

    real_org  = w["org_a"].id
    real_proj = w["proj_a"].id

    for _ in range(5):
        fake_id = uuid.uuid4()
        # Random issue
        resp = await async_client.get(
            f"/api/v1/organizations/{real_org}/projects/{real_proj}/issues/{fake_id}",
            headers=hdrs,
        )
        assert resp.status_code in (404, 403), (
            f"Random issue UUID returned {resp.status_code} (expected 404/403)"
        )

        # Random board
        resp = await async_client.get(
            f"/api/v1/organizations/{real_org}/projects/{real_proj}/boards/{fake_id}",
            headers=hdrs,
        )
        assert resp.status_code in (404, 403), (
            f"Random board UUID returned {resp.status_code} (expected 404/403)"
        )


# ===========================================================================
# 14. ISSUE LIST ISOLATION
#     Paginated list of issues for Org A must contain zero Org B issues,
#     even when Org B has identically-titled issues.
# ===========================================================================

@pytest.mark.asyncio
async def test_issue_list_never_leaks_cross_tenant_data(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    Org A's issue list must be strictly scoped to Org A's project.
    Org B issues with the same title must not appear.
    """
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    # Create one issue in Org A and two in Org B (all same title)
    for _ in range(1):
        await async_client.post(
            f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
            json={"title": "Shared Title Issue"},
            headers=a_hdrs,
        )
    for _ in range(2):
        await async_client.post(
            f"/api/v1/organizations/{w['org_b'].id}/projects/{w['proj_b'].id}/issues",
            json={"title": "Shared Title Issue"},
            headers=b_hdrs,
        )

    # Org A list must show exactly 1 issue
    list_resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues",
        headers=a_hdrs,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1, (
        f"Org A issue list contains {data['total']} items (expected 1, possible tenant leak)"
    )


# ===========================================================================
# 15. SEARCH DOES NOT LEAK CROSS-TENANT DATA
# ===========================================================================

@pytest.mark.asyncio
async def test_search_is_tenant_scoped(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Full-text search must be scoped to the authenticated tenant's project."""
    w = await build_two_tenant_world(db_session)
    a_hdrs = {"Authorization": f"Bearer {w['tok_owner_a']}"}
    b_hdrs = {"Authorization": f"Bearer {w['tok_owner_b']}"}

    unique_title = "SUPERSECRET_PAYLOAD_XYZ"

    # Create a uniquely-named issue in Org B only
    await async_client.post(
        f"/api/v1/organizations/{w['org_b'].id}/projects/{w['proj_b'].id}/issues",
        json={"title": unique_title},
        headers=b_hdrs,
    )

    # Searching in Org A's project must return zero results
    search_resp = await async_client.get(
        f"/api/v1/organizations/{w['org_a'].id}/projects/{w['proj_a'].id}/issues?q={unique_title}",
        headers=a_hdrs,
    )
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] == 0, (
        f"Search leaked cross-tenant issue (got {search_resp.json()['total']} results)"
    )
