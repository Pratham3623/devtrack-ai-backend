"""
AI Controller Endpoints
=======================
REST APIs for AI Issue Generator, AI Sprint Planner, AI Documentation Generator,
AI Bug Analysis, AI Project Summary, and SSE Streaming responses.
"""

import uuid
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.ai import (
    AIBugAnalysisRequest,
    AIBugAnalysisResponse,
    AIDocumentationRequest,
    AIDocumentationResponse,
    AIIssueGenerateRequest,
    AIIssueGenerateResponse,
    AIProjectSummaryRequest,
    AIProjectSummaryResponse,
    AISprintPlanRequest,
    AISprintPlanResponse,
)
from app.services.ai_service import AIService

router = APIRouter()


@router.post(
    "/{org_id}/projects/{project_id}/ai/generate-issues",
    response_model=AIIssueGenerateResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Issue Generator",
)
async def generate_issues(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: AIIssueGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIIssueGenerateResponse:
    service = AIService(db)
    return await service.generate_issues(org_id, project_id, current_user, dto)


@router.post(
    "/{org_id}/projects/{project_id}/ai/sprint-plan",
    response_model=AISprintPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Sprint Planner",
)
async def plan_sprint(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: AISprintPlanRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AISprintPlanResponse:
    service = AIService(db)
    return await service.plan_sprint(org_id, project_id, current_user, dto)


@router.post(
    "/{org_id}/projects/{project_id}/ai/generate-docs",
    response_model=AIDocumentationResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Documentation Generator",
)
async def generate_documentation(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: AIDocumentationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIDocumentationResponse:
    service = AIService(db)
    return await service.generate_documentation(org_id, project_id, current_user, dto)


@router.post(
    "/{org_id}/projects/{project_id}/ai/bug-analysis",
    response_model=AIBugAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Bug Analysis & Code Fix Generator",
)
async def analyze_bug(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: AIBugAnalysisRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIBugAnalysisResponse:
    service = AIService(db)
    return await service.analyze_bug(org_id, project_id, current_user, dto)


@router.post(
    "/{org_id}/projects/{project_id}/ai/summary",
    response_model=AIProjectSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="AI Project Executive Summary",
)
async def summarize_project(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: AIProjectSummaryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIProjectSummaryResponse:
    service = AIService(db)
    return await service.summarize_project(org_id, project_id, current_user, dto)


@router.get(
    "/{org_id}/projects/{project_id}/ai/stream",
    summary="AI Response Stream (Server-Sent Events)",
)
async def stream_ai(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    prompt: str = Query("Summarize project state"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    service = AIService(db)
    await service._check_org_access(org_id, current_user.id)
    await service._get_project(org_id, project_id)

    return StreamingResponse(
        service.stream_ai_response(prompt),
        media_type="text/event-stream",
    )
