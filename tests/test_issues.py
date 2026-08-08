import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.enums import IssuePriority, IssueStatus, OrgRole, ProjectRole, UserRole
from app.domain.models.issue import Issue
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project, ProjectMember
from app.domain.models.user import User
from app.domain.schemas.issue import IssueCreate, IssueUpdate
from app.repositories.issue_repository import IssueRepository



# Helper fixture to setup user, org, and project
async def create_test_fixtures(db_session: AsyncSession):
    # User / Reporter
    user = User(
        email="reporter@devtrack.ai",
        full_name="Reporter User",
        role=UserRole.MEMBER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    # Assignee User
    assignee = User(
        email="assignee@devtrack.ai",
        full_name="Assignee User",
        role=UserRole.MEMBER,
        is_active=True,
        is_verified=True,
    )
    db_session.add(assignee)
    await db_session.flush()

    # Org
    org = Organization(name="DevCorp", slug="devcorp", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()

    # Project
    project = Project(
        organization_id=org.id,
        name="DevEngine",
        key="DEV",
        description="DevTrack Engine Project",
        owner_id=user.id,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(assignee)
    await db_session.refresh(project)

    return user, assignee, project


# 1. Test Issue Creation & Repository
@pytest.mark.asyncio
async def test_issue_creation_and_repository(db_session: AsyncSession):
    user, assignee, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    issue = await repo.create_issue(
        project_id=project.id,
        reporter_id=user.id,
        title="Setup PostgreSQL Connection Pool",
        description="Configure asyncpg pool with 20 connections.",
        status=IssueStatus.TODO,
        priority=IssuePriority.HIGH,
        assignee_id=assignee.id,
    )

    assert issue.id is not None
    assert issue.project_id == project.id
    assert issue.issue_number == 1
    assert issue.title == "Setup PostgreSQL Connection Pool"
    assert issue.status == IssueStatus.TODO
    assert issue.priority == IssuePriority.HIGH

    assert issue.reporter_id == user.id
    assert issue.assignee_id == assignee.id
    assert issue.is_archived is False


# 2. Test Issue-Project Relationship
@pytest.mark.asyncio
async def test_issue_project_relationship(db_session: AsyncSession):
    user, _, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    issue = await repo.create_issue(
        project_id=project.id,
        reporter_id=user.id,
        title="Relationship Test Issue",
    )

    fetched_issue = await repo.get_with_project(issue.id)
    assert fetched_issue is not None
    assert fetched_issue.project.id == project.id
    assert fetched_issue.project.key == "DEV"
    assert fetched_issue.project.name == "DevEngine"


# 3. Test Sequential Issue Number Generation
@pytest.mark.asyncio
async def test_issue_number_sequential_generation(db_session: AsyncSession):
    user, _, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    issue1 = await repo.create_issue(project_id=project.id, reporter_id=user.id, title="Issue One")
    issue2 = await repo.create_issue(project_id=project.id, reporter_id=user.id, title="Issue Two")
    issue3 = await repo.create_issue(project_id=project.id, reporter_id=user.id, title="Issue Three")

    assert issue1.issue_number == 1
    assert issue2.issue_number == 2
    assert issue3.issue_number == 3


# 4. Test Identifier Foundation (DEV-1, DEV-2)
@pytest.mark.asyncio
async def test_identifier_generation(db_session: AsyncSession):
    user, _, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    issue = await repo.create_issue(project_id=project.id, reporter_id=user.id, title="Identifier Test")
    fetched = await repo.get_by_project_and_number(project.id, 1)

    assert fetched is not None
    assert fetched.identifier == "DEV-1"


# 5. Test Issue Number Uniqueness Constraint
@pytest.mark.asyncio
async def test_issue_number_uniqueness_constraint(db_session: AsyncSession):
    user, _, project = await create_test_fixtures(db_session)

    # Manually insert duplicate (project_id, issue_number=1) to bypass repo logic
    i1 = Issue(project_id=project.id, issue_number=1, title="Manual 1", reporter_id=user.id)
    i2 = Issue(project_id=project.id, issue_number=1, title="Manual 2", reporter_id=user.id)

    db_session.add(i1)
    await db_session.commit()

    db_session.add(i2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# 6. Test Invalid Issue Data Validation (Schema layer)
def test_invalid_issue_data_validation():
    # Empty title
    with pytest.raises(ValidationError):
        IssueCreate(title="", status=IssueStatus.TODO)

    # Whitespace-only title
    with pytest.raises(ValidationError):
        IssueCreate(title="    ", status=IssueStatus.TODO)

    # Valid schema creation
    dto = IssueCreate(title="Valid Issue Title", priority=IssuePriority.URGENT)
    assert dto.title == "Valid Issue Title"
    assert dto.priority == IssuePriority.URGENT
    assert dto.status == IssueStatus.TODO


# 7. Test Status and Priority Enums
@pytest.mark.asyncio
async def test_status_and_priority_enums(db_session: AsyncSession):
    user, _, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    for st in [IssueStatus.BACKLOG, IssueStatus.IN_PROGRESS, IssueStatus.IN_REVIEW, IssueStatus.DONE, IssueStatus.CANCELLED]:
        iss = await repo.create_issue(project_id=project.id, reporter_id=user.id, title=f"Status {st}", status=st)
        assert iss.status == st

    for pr in [IssuePriority.NO_PRIORITY, IssuePriority.LOW, IssuePriority.URGENT]:
        iss = await repo.create_issue(project_id=project.id, reporter_id=user.id, title=f"Priority {pr}", priority=pr)
        assert iss.priority == pr


# 8. Test Foreign-Key Integrity and Nullable Assignee
@pytest.mark.asyncio
async def test_foreign_key_integrity_and_nullable_assignee(db_session: AsyncSession):
    user, assignee, project = await create_test_fixtures(db_session)
    repo = IssueRepository(db_session)

    # Nullable assignee is valid
    unassigned = await repo.create_issue(
        project_id=project.id, reporter_id=user.id, title="Unassigned Task", assignee_id=None
    )
    assert unassigned.assignee_id is None

    # Assigned task is valid
    assigned = await repo.create_issue(
        project_id=project.id, reporter_id=user.id, title="Assigned Task", assignee_id=assignee.id
    )
    assert assigned.assignee_id == assignee.id

    # Non-nullable reporter_id constraint check
    missing_reporter = Issue(
        project_id=project.id,
        issue_number=999,
        title="No Reporter",
        reporter_id=None,
    )
    db_session.add(missing_reporter)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

