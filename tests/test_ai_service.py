"""
Phase 8 — AI Service Domain Tests
=================================
Verifies AIService business logic for task generation, sprint planning,
documentation generation, bug analysis, project executive summaries,
and streaming responses.
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.domain.models.enums import OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.ai import (
    AIBugAnalysisRequest,
    AIDocumentationRequest,
    AIIssueGenerateRequest,
    AIProjectSummaryRequest,
    AISprintPlanRequest,
)
from app.services.ai_service import AIService


async def setup_ai_fixtures(db_session: AsyncSession):
    user = User(email="ai_user@devtrack.ai", full_name="AI User", role=UserRole.MEMBER, is_active=True)
    outsider = User(email="ai_outsider@other.ai", full_name="Outsider", role=UserRole.MEMBER, is_active=True)
    db_session.add_all([user, outsider])
    await db_session.flush()

    org = Organization(name="AI Corp", slug="ai-corp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()
    db_session.add(OrgMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER))

    proj = Project(organization_id=org.id, name="AI Project", key="AIP", owner_id=user.id)
    db_session.add(proj)
    await db_session.commit()

    return {
        "user": user,
        "outsider": outsider,
        "org": org,
        "proj": proj,
        "token": create_access_token(subject=str(user.id), role=user.role.value),
    }


@pytest.mark.asyncio
async def test_ai_issue_generator_service(db_session: AsyncSession):
    fix = await setup_ai_fixtures(db_session)
    service = AIService(db_session)

    req = AIIssueGenerateRequest(prompt="Implement Stripe Payment Gateway", count=3)
    resp = await service.generate_issues(fix["org"].id, fix["proj"].id, fix["user"], req)

    assert resp.prompt == "Implement Stripe Payment Gateway"
    assert len(resp.generated_issues) == 3
    assert "Implement Backend API" in resp.generated_issues[0].title
    assert len(resp.generated_issues[0].subtasks) >= 1


@pytest.mark.asyncio
async def test_ai_sprint_planner_service(db_session: AsyncSession):
    fix = await setup_ai_fixtures(db_session)
    service = AIService(db_session)

    req = AISprintPlanRequest(sprint_name="Sprint 1", sprint_goal="Authentication Engine", capacity_issues=5)
    resp = await service.plan_sprint(fix["org"].id, fix["proj"].id, fix["user"], req)

    assert resp.sprint_name == "Sprint 1"
    assert resp.sprint_goal == "Authentication Engine"
    assert len(resp.recommended_issues) >= 1


@pytest.mark.asyncio
async def test_ai_documentation_service(db_session: AsyncSession):
    fix = await setup_ai_fixtures(db_session)
    service = AIService(db_session)

    req = AIDocumentationRequest(doc_type="README")
    resp = await service.generate_documentation(fix["org"].id, fix["proj"].id, fix["user"], req)

    assert resp.doc_type == "README"
    assert "AI Project" in resp.title
    assert "# AI Project" in resp.content_markdown


@pytest.mark.asyncio
async def test_ai_bug_analysis_service(db_session: AsyncSession):
    fix = await setup_ai_fixtures(db_session)
    service = AIService(db_session)

    req = AIBugAnalysisRequest(
        bug_title="NullPointer in Auth Middleware",
        bug_description="Request crashes when authorization header is missing.",
        stack_trace="AttributeError: 'NoneType' object has no attribute 'split'",
    )
    resp = await service.analyze_bug(fix["org"].id, fix["proj"].id, fix["user"], req)

    assert resp.bug_title == "NullPointer in Auth Middleware"
    assert resp.severity == "HIGH"
    assert resp.code_fix_snippet is not None


@pytest.mark.asyncio
async def test_ai_project_summary_service(db_session: AsyncSession):
    fix = await setup_ai_fixtures(db_session)
    service = AIService(db_session)

    req = AIProjectSummaryRequest(period_days=14)
    resp = await service.summarize_project(fix["org"].id, fix["proj"].id, fix["user"], req)

    assert resp.project_name == "AI Project"
    assert len(resp.key_accomplishments) >= 1
