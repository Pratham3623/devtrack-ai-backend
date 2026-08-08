import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundException, ForbiddenException, ValidationException
from app.domain.models.enums import IssuePriority, IssueStatus, OrgRole, UserRole
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.issue import IssueCreate, IssueUpdate
from app.services.issue_service import IssueService


async def setup_service_fixtures(db_session: AsyncSession):
    """Setup test fixture data for org, users, and project."""
    owner = User(
        email="owner@devtrack.ai", full_name="Org Owner", role=UserRole.MEMBER, is_active=True
    )
    member = User(
        email="member@devtrack.ai", full_name="Org Member", role=UserRole.MEMBER, is_active=True
    )
    outsider = User(
        email="outsider@other.ai", full_name="Outside User", role=UserRole.MEMBER, is_active=True
    )
    db_session.add_all([owner, member, outsider])
    await db_session.flush()

    # Org 1
    org1 = Organization(name="Primary Corp", slug="primary", owner_id=owner.id)
    db_session.add(org1)
    await db_session.flush()

    m1 = OrgMember(organization_id=org1.id, user_id=owner.id, role=OrgRole.OWNER)
    m2 = OrgMember(organization_id=org1.id, user_id=member.id, role=OrgRole.DEVELOPER)
    db_session.add_all([m1, m2])

    # Org 2 (For cross-org isolation testing)
    org2 = Organization(name="Secondary Corp", slug="secondary", owner_id=outsider.id)
    db_session.add(org2)
    await db_session.flush()
    m3 = OrgMember(organization_id=org2.id, user_id=outsider.id, role=OrgRole.OWNER)
    db_session.add(m3)

    # Project in Org 1
    proj1 = Project(
        organization_id=org1.id,
        name="Core Engine",
        key="CORE",
        owner_id=owner.id,
    )
    # Project in Org 2
    proj2 = Project(
        organization_id=org2.id,
        name="Secret Engine",
        key="SEC",
        owner_id=outsider.id,
    )
    db_session.add_all([proj1, proj2])
    await db_session.commit()

    await db_session.refresh(owner)
    await db_session.refresh(member)
    await db_session.refresh(outsider)
    await db_session.refresh(org1)
    await db_session.refresh(org2)
    await db_session.refresh(proj1)
    await db_session.refresh(proj2)

    return owner, member, outsider, org1, org2, proj1, proj2


# 1. Test Create Issue via Service
@pytest.mark.asyncio
async def test_create_issue_service_success(db_session: AsyncSession):
    owner, member, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    dto = IssueCreate(
        title="Setup Redis Cache Pool",
        description="Redis connection pool configuration.",
        status=IssueStatus.TODO,
        priority=IssuePriority.HIGH,
        assignee_id=member.id,
    )

    issue = await service.create_issue(org1.id, proj1.id, owner, dto)
    assert issue.id is not None
    assert issue.issue_number == 1
    assert issue.identifier == "CORE-1"
    assert issue.title == "Setup Redis Cache Pool"
    assert issue.assignee_id == member.id
    assert issue.reporter_id == owner.id


# 2. Test Retrieve Issue (by ID & by Number)
@pytest.mark.asyncio
async def test_retrieve_issue_by_id_and_number(db_session: AsyncSession):
    owner, _, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    created = await service.create_issue(
        org1.id, proj1.id, owner, IssueCreate(title="Retrieval Test Issue")
    )

    by_id = await service.get_issue(org1.id, proj1.id, created.id, owner)
    assert by_id.id == created.id
    assert by_id.title == "Retrieval Test Issue"

    by_num = await service.get_issue_by_number(org1.id, proj1.id, 1, owner)
    assert by_num.id == created.id
    assert by_num.identifier == "CORE-1"


# 3. Test List Issues with Filtering
@pytest.mark.asyncio
async def test_list_issues_with_filters(db_session: AsyncSession):
    owner, member, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    await service.create_issue(
        org1.id, proj1.id, owner, IssueCreate(title="Task A", status=IssueStatus.TODO, priority=IssuePriority.LOW)
    )
    await service.create_issue(
        org1.id, proj1.id, owner, IssueCreate(title="Task B", status=IssueStatus.IN_PROGRESS, priority=IssuePriority.URGENT, assignee_id=member.id)
    )
    await service.create_issue(
        org1.id, proj1.id, owner, IssueCreate(title="Task C", status=IssueStatus.DONE, priority=IssuePriority.HIGH)
    )

    all_issues = await service.list_issues(org1.id, proj1.id, owner)
    assert len(all_issues) == 3

    in_prog = await service.list_issues(org1.id, proj1.id, owner, status=IssueStatus.IN_PROGRESS)
    assert len(in_prog) == 1
    assert in_prog[0].title == "Task B"

    assigned_to_member = await service.list_issues(org1.id, proj1.id, owner, assignee_id=member.id)
    assert len(assigned_to_member) == 1
    assert assigned_to_member[0].title == "Task B"


# 4. Test Update Issue
@pytest.mark.asyncio
async def test_update_issue_fields(db_session: AsyncSession):
    owner, member, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    issue = await service.create_issue(
        org1.id, proj1.id, owner, IssueCreate(title="Initial Title")
    )

    updated = await service.update_issue(
        org1.id,
        proj1.id,
        issue.id,
        owner,
        IssueUpdate(title="Updated Title Summary", description="New body text", priority=IssuePriority.URGENT, assignee_id=member.id),
    )

    assert updated.title == "Updated Title Summary"
    assert updated.description == "New body text"
    assert updated.priority == IssuePriority.URGENT
    assert updated.assignee_id == member.id


# 5. Test Archive and Restore Issue
@pytest.mark.asyncio
async def test_archive_and_restore_issue(db_session: AsyncSession):
    owner, _, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    issue = await service.create_issue(org1.id, proj1.id, owner, IssueCreate(title="To Archive"))

    archived = await service.archive_issue(org1.id, proj1.id, issue.id, owner)
    assert archived.is_archived is True
    assert archived.archived_at is not None

    # Excluded from standard list
    active_list = await service.list_issues(org1.id, proj1.id, owner, include_archived=False)
    assert len(active_list) == 0

    # Restored
    restored = await service.restore_issue(org1.id, proj1.id, issue.id, owner)
    assert restored.is_archived is False
    assert restored.archived_at is None


# 6. Test Status and Priority Transitions
@pytest.mark.asyncio
async def test_status_and_priority_transitions(db_session: AsyncSession):
    owner, _, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    issue = await service.create_issue(org1.id, proj1.id, owner, IssueCreate(title="Workflow Issue"))

    s_updated = await service.change_status(org1.id, proj1.id, issue.id, owner, IssueStatus.IN_REVIEW)
    assert s_updated.status == IssueStatus.IN_REVIEW

    p_updated = await service.change_priority(org1.id, proj1.id, issue.id, owner, IssuePriority.URGENT)
    assert p_updated.priority == IssuePriority.URGENT


# 7. Test Assignment and Unassignment
@pytest.mark.asyncio
async def test_assignment_and_unassignment(db_session: AsyncSession):
    owner, member, _, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    issue = await service.create_issue(org1.id, proj1.id, owner, IssueCreate(title="Assign Task"))

    assigned = await service.assign_issue(org1.id, proj1.id, issue.id, owner, member.id)
    assert assigned.assignee_id == member.id

    unassigned = await service.unassign_issue(org1.id, proj1.id, issue.id, owner)
    assert unassigned.assignee_id is None


# 8. Test Invalid Assignee (Not in Organization)
@pytest.mark.asyncio
async def test_invalid_assignee_rejection(db_session: AsyncSession):
    owner, _, outsider, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    # Creating issue assigned to non-org user fails
    with pytest.raises(ValidationException):
        await service.create_issue(
            org1.id, proj1.id, owner, IssueCreate(title="Bad Assignee", assignee_id=outsider.id)
        )

    # Assigning existing issue to non-org user fails
    issue = await service.create_issue(org1.id, proj1.id, owner, IssueCreate(title="Valid Issue"))
    with pytest.raises(ValidationException):
        await service.assign_issue(org1.id, proj1.id, issue.id, owner, outsider.id)


# 9. Test Unauthorized Operations (Non-member Actor)
@pytest.mark.asyncio
async def test_unauthorized_actor_blocked(db_session: AsyncSession):
    owner, _, outsider, org1, _, proj1, _ = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    # Outsider cannot create issue in org1
    with pytest.raises(ForbiddenException):
        await service.create_issue(org1.id, proj1.id, outsider, IssueCreate(title="Hacker Issue"))

    # Outsider cannot list issues in org1
    with pytest.raises(ForbiddenException):
        await service.list_issues(org1.id, proj1.id, outsider)


# 10. Test Cross-Organization Isolation
@pytest.mark.asyncio
async def test_cross_org_isolation(db_session: AsyncSession):
    owner, _, outsider, org1, org2, proj1, proj2 = await setup_service_fixtures(db_session)
    service = IssueService(db_session)

    issue1 = await service.create_issue(org1.id, proj1.id, owner, IssueCreate(title="Org1 Task"))
    issue2 = await service.create_issue(org2.id, proj2.id, outsider, IssueCreate(title="Org2 Task"))

    # Attempting to fetch issue1 via org2 fails
    with pytest.raises(EntityNotFoundException):
        await service.get_issue(org2.id, proj1.id, issue1.id, outsider)
