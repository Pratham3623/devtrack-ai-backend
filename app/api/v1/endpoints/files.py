"""
Files & Storage REST Endpoints — Phase 11.

Routes:
  POST  /{org_id}/files/upload                                        — global org upload
  POST  /{org_id}/projects/{project_id}/files/upload                  — project-scoped upload
  POST  /{org_id}/projects/{project_id}/issues/{issue_id}/files/upload — issue-scoped upload
  GET   /{org_id}/files                                               — list org files
  GET   /{org_id}/projects/{project_id}/files                         — list project files
  GET   /{org_id}/projects/{project_id}/issues/{issue_id}/files       — list issue files
  GET   /{org_id}/files/{file_id}                                     — file metadata + signed URL
  GET   /{org_id}/files/{file_id}/download                            — redirect to signed URL
  POST  /{org_id}/files/{file_id}/versions                            — upload new version
  GET   /{org_id}/files/{file_id}/versions                            — list versions
  GET   /{org_id}/files/{file_id}/versions/{version_number}/download  — download specific version
  DELETE /{org_id}/files/{file_id}                                    — archive / delete

Local token-serving (no org scope):
  GET /api/v1/files/serve/{token}                                     — serve signed local file
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.file import (
    FileAttachmentResponse,
    FileListResponse,
    FileUploadResponse,
    FileVersionResponse,
)
from app.services.file_service import FileService

router = APIRouter()
serve_router = APIRouter()  # Mounted at /api/v1/files (no org prefix) for token serving


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _upload(
    org_id: uuid.UUID,
    actor: User,
    db: AsyncSession,
    file: UploadFile,
    project_id: Optional[uuid.UUID] = None,
    issue_id: Optional[uuid.UUID] = None,
) -> FileUploadResponse:
    service = FileService(db)
    file_bytes = await file.read()
    return await service.upload_file(
        org_id=org_id,
        actor=actor,
        file_bytes=file_bytes,
        original_filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        project_id=project_id,
        issue_id=issue_id,
    )


# ─── Upload endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file at organization scope",
)
async def upload_file_org(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileUploadResponse:
    return await _upload(org_id, current_user, db, file)


@router.post(
    "/{org_id}/projects/{project_id}/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file at project scope",
)
async def upload_file_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileUploadResponse:
    return await _upload(org_id, current_user, db, file, project_id=project_id)


@router.post(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/files/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file attachment to a specific issue",
)
async def upload_file_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileUploadResponse:
    return await _upload(org_id, current_user, db, file, project_id=project_id, issue_id=issue_id)


# ─── List endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/{org_id}/files",
    response_model=FileListResponse,
    summary="List all files in the organization",
)
async def list_files_org(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileListResponse:
    service = FileService(db)
    return await service.list_files(org_id, current_user, page=page, page_size=page_size)


@router.get(
    "/{org_id}/projects/{project_id}/files",
    response_model=FileListResponse,
    summary="List files in a project",
)
async def list_files_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileListResponse:
    service = FileService(db)
    return await service.list_files(org_id, current_user, project_id=project_id, page=page, page_size=page_size)


@router.get(
    "/{org_id}/projects/{project_id}/issues/{issue_id}/files",
    response_model=FileListResponse,
    summary="List file attachments on an issue",
)
async def list_files_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    issue_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileListResponse:
    service = FileService(db)
    return await service.list_files(
        org_id, current_user, project_id=project_id, issue_id=issue_id, page=page, page_size=page_size
    )


# ─── Single file operations ───────────────────────────────────────────────────

@router.get(
    "/{org_id}/files/{file_id}",
    response_model=FileAttachmentResponse,
    summary="Get file metadata and signed download URL",
)
async def get_file(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileAttachmentResponse:
    service = FileService(db)
    return await service.get_file(org_id, file_id, current_user)


@router.get(
    "/{org_id}/files/{file_id}/download",
    summary="Redirect to signed download URL for a file",
    status_code=307,
)
async def download_file(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    service = FileService(db)
    url = await service.get_download_url(org_id, file_id, current_user)
    return RedirectResponse(url=url, status_code=307)


@router.delete(
    "/{org_id}/files/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Archive (soft-delete) a file",
)
async def delete_file(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = FileService(db)
    await service.delete_file(org_id, file_id, current_user)
    return {"message": "File archived successfully."}


# ─── Versioning ───────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/files/{file_id}/versions",
    response_model=FileVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new version of an existing file",
)
async def upload_new_version(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    file: UploadFile = File(...),
    changelog: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FileVersionResponse:
    service = FileService(db)
    file_bytes = await file.read()
    return await service.upload_new_version(
        org_id=org_id,
        file_id=file_id,
        actor=current_user,
        file_bytes=file_bytes,
        content_type=file.content_type or "application/octet-stream",
        changelog=changelog,
    )


@router.get(
    "/{org_id}/files/{file_id}/versions",
    response_model=List[FileVersionResponse],
    summary="List all versions of a file",
)
async def list_versions(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[FileVersionResponse]:
    service = FileService(db)
    return await service.list_versions(org_id, file_id, current_user)


@router.get(
    "/{org_id}/files/{file_id}/versions/{version_number}/download",
    summary="Redirect to signed URL for a specific file version",
    status_code=307,
)
async def download_version(
    org_id: uuid.UUID,
    file_id: uuid.UUID,
    version_number: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    service = FileService(db)
    url = await service.get_version_download_url(org_id, file_id, version_number, current_user)
    return RedirectResponse(url=url, status_code=307)


# ─── Local file serving (HMAC token) ─────────────────────────────────────────

@serve_router.get(
    "/serve/{token}",
    summary="Serve a locally-stored file via HMAC-signed token",
)
async def serve_local_file(
    token: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    service = FileService(db)
    data, content_type = await service.serve_local_file(token)
    return Response(content=data, media_type=content_type)
