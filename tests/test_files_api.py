"""
Phase 11 — Files & Storage API Integration Tests
=================================================
Verifies file upload (org, project, issue scope), image detection, signed download URLs,
file versioning, version history, soft-delete archiving, local HMAC token serving, and RBAC tenant isolation.
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


async def setup_file_fixtures(db_session: AsyncSession):
    user = User(email="file_owner@devtrack.ai", full_name="File Owner", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="file_outsider@other.ai", full_name="File Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, outsider])
    await db_session.flush()

    org = Organization(name="File Storage Corp", slug="file-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="Storage Core", key="STG", description="Files module project", owner_id=user.id)
    db_session.add(proj)
    await db_session.flush()

    issue = Issue(project_id=proj.id, issue_number=201, title="Upload Bug", status=IssueStatus.TODO, priority=IssuePriority.HIGH, reporter_id=user.id)
    db_session.add(issue)
    await db_session.commit()

    return {
        "user": user,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "issue": issue,
        "headers_owner": {"Authorization": f"Bearer {create_access_token(subject=str(user.id), role=user.role.value)}"},
        "headers_outsider": {"Authorization": f"Bearer {create_access_token(subject=str(outsider.id), role=outsider.role.value)}"},
    }


@pytest.mark.asyncio
async def test_file_upload_and_metadata(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    url = f"/api/v1/organizations/{fix['org'].id}/files/upload"

    # Upload text file
    files = {"file": ("architecture_doc.txt", b"DevTrack Storage Engine Design Spec", "text/plain")}
    resp = await async_client.post(url, files=files, headers=fix["headers_owner"])
    assert resp.status_code == 201
    data = resp.json()

    assert data["original_filename"] == "architecture_doc.txt"
    assert data["content_type"] == "text/plain"
    assert data["size_bytes"] == len(b"DevTrack Storage Engine Design Spec")
    assert data["is_image"] is False
    assert data["current_version"] == 1
    assert "download_url" in data

    # Upload PNG image file
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    files_img = {"file": ("diagram.png", png_bytes, "image/png")}
    resp_img = await async_client.post(url, files=files_img, headers=fix["headers_owner"])
    assert resp_img.status_code == 201
    data_img = resp_img.json()
    assert data_img["is_image"] is True
    assert data_img["thumbnail_url"] is not None


@pytest.mark.asyncio
async def test_file_list_and_filter(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    org_id = fix["org"].id
    proj_id = fix["proj"].id
    issue_id = fix["issue"].id

    # 1. Org-level upload
    files1 = {"file": ("org_policy.pdf", b"%PDF-1.4 Mock Policy PDF Content", "application/pdf")}
    await async_client.post(f"/api/v1/organizations/{org_id}/files/upload", files=files1, headers=fix["headers_owner"])

    # 2. Project-level upload
    files2 = {"file": ("proj_spec.md", b"# Project Specification", "text/markdown")}
    await async_client.post(f"/api/v1/organizations/{org_id}/projects/{proj_id}/files/upload", files=files2, headers=fix["headers_owner"])

    # 3. Issue-level upload
    files3 = {"file": ("bug_log.txt", b"Error traceback line 42", "text/plain")}
    await async_client.post(f"/api/v1/organizations/{org_id}/projects/{proj_id}/issues/{issue_id}/files/upload", files=files3, headers=fix["headers_owner"])

    # List Org Files
    list_org = await async_client.get(f"/api/v1/organizations/{org_id}/files", headers=fix["headers_owner"])
    assert list_org.status_code == 200
    assert list_org.json()["total"] >= 3

    # List Project Files
    list_proj = await async_client.get(f"/api/v1/organizations/{org_id}/projects/{proj_id}/files", headers=fix["headers_owner"])
    assert list_proj.status_code == 200
    assert list_proj.json()["total"] >= 2

    # List Issue Files
    list_issue = await async_client.get(f"/api/v1/organizations/{org_id}/projects/{proj_id}/issues/{issue_id}/files", headers=fix["headers_owner"])
    assert list_issue.status_code == 200
    assert list_issue.json()["total"] == 1
    assert list_issue.json()["items"][0]["original_filename"] == "bug_log.txt"


@pytest.mark.asyncio
async def test_file_versioning(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    org_id = fix["org"].id

    # 1. Upload initial version (v1)
    files = {"file": ("release_notes.txt", b"v1.0.0 initial release notes", "text/plain")}
    up_resp = await async_client.post(f"/api/v1/organizations/{org_id}/files/upload", files=files, headers=fix["headers_owner"])
    file_id = up_resp.json()["id"]

    # 2. Upload new version (v2) with changelog
    v2_files = {"file": ("release_notes.txt", b"v1.1.0 updated release notes with hotfixes", "text/plain")}
    v2_resp = await async_client.post(
        f"/api/v1/organizations/{org_id}/files/{file_id}/versions",
        files=v2_files,
        data={"changelog": "Added hotfix details"},
        headers=fix["headers_owner"],
    )
    assert v2_resp.status_code == 201
    v2_data = v2_resp.json()
    assert v2_data["version_number"] == 2
    assert v2_data["changelog"] == "Added hotfix details"

    # 3. List all versions
    ver_resp = await async_client.get(f"/api/v1/organizations/{org_id}/files/{file_id}/versions", headers=fix["headers_owner"])
    assert ver_resp.status_code == 200
    versions = ver_resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 1
    assert versions[1]["version_number"] == 2

    # 4. Verify master record reflects current_version = 2
    file_get = await async_client.get(f"/api/v1/organizations/{org_id}/files/{file_id}", headers=fix["headers_owner"])
    assert file_get.json()["current_version"] == 2


@pytest.mark.asyncio
async def test_file_permissions_rbac(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    org_id = fix["org"].id

    # Outsider upload blocked (403)
    files = {"file": ("hack.txt", b"malicious content", "text/plain")}
    resp = await async_client.post(f"/api/v1/organizations/{org_id}/files/upload", files=files, headers=fix["headers_outsider"])
    assert resp.status_code == 403

    # Outsider list files blocked (403)
    list_resp = await async_client.get(f"/api/v1/organizations/{org_id}/files", headers=fix["headers_outsider"])
    assert list_resp.status_code == 403


@pytest.mark.asyncio
async def test_file_delete_archive(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    org_id = fix["org"].id

    # Upload
    files = {"file": ("temp_config.json", b'{"key": "value"}', "application/json")}
    up = await async_client.post(f"/api/v1/organizations/{org_id}/files/upload", files=files, headers=fix["headers_owner"])
    file_id = up.json()["id"]

    # Delete (archive)
    del_resp = await async_client.delete(f"/api/v1/organizations/{org_id}/files/{file_id}", headers=fix["headers_owner"])
    assert del_resp.status_code == 200

    # Get single file returns 404 (not active)
    get_resp = await async_client.get(f"/api/v1/organizations/{org_id}/files/{file_id}", headers=fix["headers_owner"])
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_local_token_serving(async_client: AsyncClient, db_session: AsyncSession):
    fix = await setup_file_fixtures(db_session)
    org_id = fix["org"].id

    files = {"file": ("served_doc.txt", b"Content served via HMAC token", "text/plain")}
    up = await async_client.post(f"/api/v1/organizations/{org_id}/files/upload", files=files, headers=fix["headers_owner"])
    data = up.json()

    download_url = data["download_url"]
    assert "/api/v1/files/serve/" in download_url

    # Fetch token directly
    token_resp = await async_client.get(download_url, headers=fix["headers_owner"])
    assert token_resp.status_code == 200
    assert token_resp.content == b"Content served via HMAC token"
