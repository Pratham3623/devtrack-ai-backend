"""
DevTrack AI — Development Demo Data Seeder

Populates local development database with a realistic enterprise workspace:
- 1 Organization: "DevTrack Technologies"
- 3 Users: Admin, Project Manager, Developer (DemoPass123!)
- 2 Projects: "DevTrack AI Engine" (DE) & "Mobile Platform" (MP)
- 1 Kanban Board with 5 workflow columns
- 7 Project Labels
- 25 Realistic Issues covering Auth, AI, WebSockets, Redis, Postgres, Docker, CI/CD, UI, and Performance
- Subtasks & Realistic Dependency Chain
- Comments & Activity History
- Saved Searches & Filter Presets

Usage:
  python -m app.scripts.seed_demo
"""

import asyncio
import sys
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.domain.models.audit_log import AuditLog
from app.domain.models.board import Board, BoardColumn
from app.domain.models.comment import Comment
from app.domain.models.dependency import DependencyType, IssueDependency
from app.domain.models.enums import (
    AuditAction,
    IssuePriority,
    IssueStatus,
    OAuthProvider,
    OrgRole,
    ProjectRole,
    ProjectTemplateType,
    UserRole,
)
from app.domain.models.issue import Issue
from app.domain.models.label import Label
from app.domain.models.organization import Organization, OrgMember
from app.domain.models.project import Project, ProjectMember
from app.domain.models.saved_search import SavedSearch
from app.domain.models.user import User


async def seed():
    if settings.APP_ENV == "production":
        print("ERROR: Demo data seeder must never be run in production environment!")
        sys.exit(1)

    print("\n============================================================")
    print("  DevTrack AI — Seeding Realistic Demo Data")
    print("============================================================\n")

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check idempotency — if organization exists, skip duplicate seed
        stmt = select(Organization).where(Organization.name == "DevTrack Technologies")
        result = await session.execute(stmt)
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print("Notice: Organization 'DevTrack Technologies' already exists.")
            print("Ensuring demo user password hashes are updated to 'DemoPass123!'...")
            demo_password_hash = hash_password("DemoPass123!")
            from sqlalchemy import update
            await session.execute(
                update(User)
                .where(User.email.in_(["demo@devtrack.ai", "pm@devtrack.ai", "dev@devtrack.ai"]))
                .values(hashed_password=demo_password_hash)
            )
            await session.commit()
            print("Skipping duplicate seed operation (Idempotent execution).\n")
            await print_summary(existing_org.id)
            return

        # ── 1. Users ────────────────────────────────────────────────
        demo_password_hash = hash_password("DemoPass123!")

        admin_user = User(
            email="demo@devtrack.ai",
            hashed_password=demo_password_hash,
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            oauth_provider=OAuthProvider.LOCAL,
        )

        pm_user = User(
            email="pm@devtrack.ai",
            hashed_password=demo_password_hash,
            full_name="Sarah PM",
            role=UserRole.MEMBER,
            is_active=True,
            is_verified=True,
            oauth_provider=OAuthProvider.LOCAL,
        )

        dev_user = User(
            email="dev@devtrack.ai",
            hashed_password=demo_password_hash,
            full_name="Alex Developer",
            role=UserRole.MEMBER,
            is_active=True,
            is_verified=True,
            oauth_provider=OAuthProvider.LOCAL,
        )

        session.add_all([admin_user, pm_user, dev_user])
        await session.flush()

        # ── 2. Organization ──────────────────────────────────────────
        org = Organization(
            name="DevTrack Technologies",
            slug="devtrack-tech",
            owner_id=admin_user.id,
        )
        session.add(org)
        await session.flush()

        # Organization Memberships
        session.add_all([
            OrgMember(organization_id=org.id, user_id=admin_user.id, role=OrgRole.OWNER),
            OrgMember(organization_id=org.id, user_id=pm_user.id, role=OrgRole.ADMIN),
            OrgMember(organization_id=org.id, user_id=dev_user.id, role=OrgRole.MEMBER),
        ])

        # ── 3. Projects ──────────────────────────────────────────────
        p1 = Project(
            organization_id=org.id,
            owner_id=admin_user.id,
            name="DevTrack AI Engine",
            key="DE",
            description="AI-Powered Enterprise Project Management & Issue Tracking Engine",
            template_type=ProjectTemplateType.KANBAN,
        )

        p2 = Project(
            organization_id=org.id,
            owner_id=pm_user.id,
            name="Mobile Platform",
            key="MP",
            description="React Native iOS & Android companion application",
            template_type=ProjectTemplateType.SCRUM,
        )

        session.add_all([p1, p2])
        await session.flush()

        # Project Memberships
        session.add_all([
            ProjectMember(project_id=p1.id, user_id=admin_user.id, role=ProjectRole.LEAD),
            ProjectMember(project_id=p1.id, user_id=pm_user.id, role=ProjectRole.MAINTAINER),
            ProjectMember(project_id=p1.id, user_id=dev_user.id, role=ProjectRole.CONTRIBUTOR),
            ProjectMember(project_id=p2.id, user_id=pm_user.id, role=ProjectRole.LEAD),
            ProjectMember(project_id=p2.id, user_id=dev_user.id, role=ProjectRole.CONTRIBUTOR),
        ])

        # ── 4. Board & Columns for DE ────────────────────────────────
        board = Board(
            project_id=p1.id,
            name="Engine Core Board",
            is_default=True,
        )
        session.add(board)
        await session.flush()

        col_backlog = BoardColumn(board_id=board.id, name="Backlog", mapped_status=IssueStatus.BACKLOG, position=0)
        col_todo = BoardColumn(board_id=board.id, name="To Do", mapped_status=IssueStatus.TODO, position=1)
        col_in_progress = BoardColumn(board_id=board.id, name="In Progress", mapped_status=IssueStatus.IN_PROGRESS, position=2)
        col_in_review = BoardColumn(board_id=board.id, name="In Review", mapped_status=IssueStatus.IN_REVIEW, position=3)
        col_done = BoardColumn(board_id=board.id, name="Done", mapped_status=IssueStatus.DONE, position=4)

        session.add_all([col_backlog, col_todo, col_in_progress, col_in_review, col_done])
        await session.flush()

        # ── 5. Labels ────────────────────────────────────────────────
        lbl_bug = Label(project_id=p1.id, name="bug", color="#ef4444")
        lbl_feature = Label(project_id=p1.id, name="feature", color="#6366f1")
        lbl_backend = Label(project_id=p1.id, name="backend", color="#3b82f6")
        lbl_frontend = Label(project_id=p1.id, name="frontend", color="#10b981")
        lbl_ai = Label(project_id=p1.id, name="AI", color="#a855f7")
        lbl_security = Label(project_id=p1.id, name="security", color="#f59e0b")
        lbl_urgent = Label(project_id=p1.id, name="urgent", color="#dc2626")

        session.add_all([lbl_bug, lbl_feature, lbl_backend, lbl_frontend, lbl_ai, lbl_security, lbl_urgent])
        await session.flush()

        # ── 6. Issues (25 Realistic Issues) ──────────────────────────
        issue_specs = [
            # 1
            {
                "num": 1,
                "title": "Implement GitHub OAuth authentication with secure account linking, email verification and session management",
                "desc": "Build GitHub OAuth 2.0 flow with token exchange, state validation, and secure account linking for single sign-on.",
                "status": IssueStatus.TODO,
                "priority": IssuePriority.HIGH,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_backend, lbl_security],
            },
            # 2
            {
                "num": 2,
                "title": "Optimize PostgreSQL connection pooling & asyncpg statement caching under load",
                "desc": "Tune SQLAlchemy async engine pool size (20) and max overflow (10) to prevent connection starvation during peak API traffic.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.HIGH,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend],
            },
            # 3
            {
                "num": 3,
                "title": "Configure Redis pub/sub cluster for real-time WebSocket presence and typing indicators",
                "desc": "Implement multi-node Redis message broker broadcasting user join/leave events and typing indicators across instances.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend, lbl_feature],
            },
            # 4
            {
                "num": 4,
                "title": "Fix Kanban column drag-and-drop ghost preview position in Safari browser",
                "desc": "DOM drag-and-drop ghost image offsets incorrectly on WebKit render engine when dragging cards across columns.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.LOW,
                "reporter": dev_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_bug, lbl_frontend],
            },
            # 5
            {
                "num": 5,
                "title": "Build AI-assisted sprint planning backlog capacity analyzer algorithm",
                "desc": "Develop AI prompt engineering pipeline to inspect backlog story points, team velocity history, and generate optimal sprint allocations.",
                "status": IssueStatus.IN_PROGRESS,
                "priority": IssuePriority.URGENT,
                "reporter": pm_user.id,
                "assignee": admin_user.id,
                "labels": [lbl_ai, lbl_feature, lbl_backend],
            },
            # 6
            {
                "num": 6,
                "title": "Add full-text global search Command Palette with saved search presets (Ctrl+K)",
                "desc": "Build modal command palette UI executing PostgreSQL tsvector full-text queries across issues, projects, and comments.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.HIGH,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_frontend],
            },
            # 7
            {
                "num": 7,
                "title": "Implement multi-stage Docker build with non-root appuser and health probes",
                "desc": "Create production Dockerfile with builder prefix, unprivileged appuser (UID 1001), and curl healthcheck probes.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.HIGH,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend, lbl_security],
            },
            # 8
            {
                "num": 8,
                "title": "Set up GitHub Actions CI/CD pipeline for automated linting, pytest, and container publishing",
                "desc": "Build github workflows for ruff lint, pytest coverage fail-under check, and GHCR container image pushing.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend],
            },
            # 9
            {
                "num": 9,
                "title": "Add S3 and local dual-backend file storage manager with presigned URL signing",
                "desc": "Implement StorageBackend factory supporting local disk and AWS S3 with HMAC signed URL expiration.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.HIGH,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_backend, lbl_security],
            },
            # 10
            {
                "num": 10,
                "title": "Refactor structlog JSON logging with request-ID propagation middleware",
                "desc": "Replace basic print statements with structured JSON logging binding request_id, client_ip, and method.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend],
            },
            # 11
            {
                "num": 11,
                "title": "Fix mobile viewport horizontal scroll overflow on issue detail drawer",
                "desc": "Drawer container exceeds 100vw width on screens below 480px, causing unwanted horizontal scrollbar.",
                "status": IssueStatus.TODO,
                "priority": IssuePriority.LOW,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_bug, lbl_frontend],
            },
            # 12
            {
                "num": 12,
                "title": "Implement issue dependency graph cycle detection and depth validation",
                "desc": "Build recursive graph traversal preventing circular BLOCKS relationships when linking issues.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.HIGH,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_backend],
            },
            # 13
            {
                "num": 13,
                "title": "Build subtask hierarchy progress bar and completion percentage tracking",
                "desc": "Render dynamic subtask checklist and calculate percentage completion badge on issue modal.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_frontend],
            },
            # 14
            {
                "num": 14,
                "title": "Add Prometheus FastAPI instrumentation and custom metric endpoints",
                "desc": "Instrument HTTP request rates, response latency histograms, and expose /metrics scrape route.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend],
            },
            # 15
            {
                "num": 15,
                "title": "Configure Grafana pre-provisioned executive dashboard with p95 latency panels",
                "desc": "Create devtrack.json dashboard definition visualizing RPS, error rates, and API uptime.",
                "status": IssueStatus.IN_REVIEW,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_backend],
            },
            # 16
            {
                "num": 16,
                "title": "Implement real-time WebSocket event broadcasting for issue field mutations",
                "desc": "Broadcast ISSUE_MOVED and COMMENT_CREATED events over WebSocket connection to update open client boards.",
                "status": IssueStatus.IN_PROGRESS,
                "priority": IssuePriority.HIGH,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_backend],
            },
            # 17
            {
                "num": 17,
                "title": "Audit multi-tenant organization isolation and IDOR vulnerability resistance",
                "desc": "Verify strict tenant checking across all API routes to guarantee cross-org parameter tampering is impossible.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.URGENT,
                "reporter": admin_user.id,
                "assignee": admin_user.id,
                "labels": [lbl_security, lbl_urgent],
            },
            # 18
            {
                "num": 18,
                "title": "Design executive analytics dashboard with burn-down and team velocity charts",
                "desc": "Render SVG release burndown arc, sprint velocity bars, and member productivity tables in analytics view.",
                "status": IssueStatus.IN_REVIEW,
                "priority": IssuePriority.HIGH,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_frontend],
            },
            # 19
            {
                "num": 19,
                "title": "Add label filter dropdown to Kanban board filter bar",
                "desc": "Filter issues dynamically on the Kanban board based on selected project label chips.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.LOW,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_frontend],
            },
            # 20
            {
                "num": 20,
                "title": "Implement SSE streaming endpoint for AI bug fix diagnostic summaries",
                "desc": "Stream Server-Sent Events from OpenAI API to render real-time diagnostic token response in issue drawer.",
                "status": IssueStatus.IN_PROGRESS,
                "priority": IssuePriority.HIGH,
                "reporter": admin_user.id,
                "assignee": admin_user.id,
                "labels": [lbl_ai, lbl_feature, lbl_backend],
            },
            # 21
            {
                "num": 21,
                "title": "Fix session token expiration toast notification flicker",
                "desc": "Toast notification duplicates when multiple concurrent requests receive 401 response simultaneously.",
                "status": IssueStatus.BACKLOG,
                "priority": IssuePriority.LOW,
                "reporter": dev_user.id,
                "assignee": None,
                "labels": [lbl_bug, lbl_frontend],
            },
            # 22
            {
                "num": 22,
                "title": "Add dark mode glassmorphism theme tokens to CSS design system",
                "desc": "Introduce CSS custom properties for translucent glassmorphic cards and backdrop filters.",
                "status": IssueStatus.BACKLOG,
                "priority": IssuePriority.LOW,
                "reporter": pm_user.id,
                "assignee": None,
                "labels": [lbl_frontend],
            },
            # 23
            {
                "num": 23,
                "title": "Build automated weekly security vulnerability audit workflow with Trivy",
                "desc": "Schedule GitHub Actions cron job every Monday scanning npm and python dependencies for CVE vulnerabilities.",
                "status": IssueStatus.TODO,
                "priority": IssuePriority.MEDIUM,
                "reporter": admin_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_security],
            },
            # 24
            {
                "num": 24,
                "title": "Optimize virtualized rendering for 500+ issues on Kanban board",
                "desc": "Implement DOM recycling for board cards when rendering large project backlogs.",
                "status": IssueStatus.BACKLOG,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": None,
                "labels": [lbl_frontend],
            },
            # 25
            {
                "num": 25,
                "title": "Implement file versioning modal with revision history timeline",
                "desc": "Modal UI showing version history, changelogs, size badges, and download triggers for attachments.",
                "status": IssueStatus.DONE,
                "priority": IssuePriority.MEDIUM,
                "reporter": pm_user.id,
                "assignee": dev_user.id,
                "labels": [lbl_feature, lbl_frontend],
            },
        ]

        created_issues = {}
        for spec in issue_specs:
            issue = Issue(
                project_id=p1.id,
                issue_number=spec["num"],
                title=spec["title"],
                description=spec["desc"],
                status=spec["status"],
                priority=spec["priority"],
                reporter_id=spec["reporter"],
                assignee_id=spec["assignee"],
            )
            for lbl in spec["labels"]:
                issue.labels.append(lbl)

            session.add(issue)
            created_issues[spec["num"]] = issue

        await session.flush()

        # ── 7. Subtasks (Children of DE-1 & DE-5) ───────────────────
        subtask1 = Issue(
            project_id=p1.id,
            issue_number=26,
            title="Add GitHub OAuth app credentials to environment schema",
            description="Update config.py and Settings model to validate GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.",
            status=IssueStatus.DONE,
            priority=IssuePriority.MEDIUM,
            reporter_id=pm_user.id,
            assignee_id=dev_user.id,
            parent_id=created_issues[1].id,
        )

        subtask2 = Issue(
            project_id=p1.id,
            issue_number=27,
            title="Build OAuth callback handler endpoint and user profile lookup",
            description="Handle code exchange with GitHub token endpoint and fetch user email from GitHub API.",
            status=IssueStatus.IN_PROGRESS,
            priority=IssuePriority.HIGH,
            reporter_id=pm_user.id,
            assignee_id=dev_user.id,
            parent_id=created_issues[1].id,
        )

        subtask3 = Issue(
            project_id=p1.id,
            issue_number=28,
            title="Build velocity estimation model prompt for sprint analyzer",
            description="Draft system prompt feeding story point history into GPT-4o-mini API.",
            status=IssueStatus.DONE,
            priority=IssuePriority.HIGH,
            reporter_id=pm_user.id,
            assignee_id=admin_user.id,
            parent_id=created_issues[5].id,
        )

        session.add_all([subtask1, subtask2, subtask3])
        await session.flush()

        # ── 8. Issue Dependencies (Realistic Chain) ─────────────────
        dep1 = IssueDependency(
            issue_id=created_issues[5].id,        # DE-5 (AI Sprint Planner)
            target_issue_id=created_issues[18].id, # BLOCKS DE-18 (Analytics Dashboard)
            dependency_type=DependencyType.BLOCKS,
        )
        dep2 = IssueDependency(
            issue_id=created_issues[1].id,        # DE-1 (GitHub OAuth)
            target_issue_id=created_issues[17].id, # BLOCKS DE-17 (Multi-tenant Security Audit)
            dependency_type=DependencyType.BLOCKS,
        )
        dep3 = IssueDependency(
            issue_id=created_issues[3].id,        # DE-3 (Redis PubSub)
            target_issue_id=created_issues[16].id, # BLOCKS DE-16 (WebSocket Event Broadcasting)
            dependency_type=DependencyType.BLOCKS,
        )

        session.add_all([dep1, dep2, dep3])

        # ── 9. Comments ──────────────────────────────────────────────
        comments = [
            Comment(
                issue_id=created_issues[1].id,
                author_id=pm_user.id,
                content="Please ensure the state parameter uses HMAC signature to prevent CSRF during OAuth callback.",
            ),
            Comment(
                issue_id=created_issues[1].id,
                author_id=dev_user.id,
                content="Implemented state validation in security helper. Working on user account linking next.",
            ),
            Comment(
                issue_id=created_issues[5].id,
                author_id=admin_user.id,
                content="Prompt template tested against GPT-4o-mini. Returns clean JSON sprint allocation strategy.",
            ),
            Comment(
                issue_id=created_issues[17].id,
                author_id=admin_user.id,
                content="Security audit passed with 100% clean isolation across all write endpoints.",
            ),
        ]
        session.add_all(comments)

        # ── 10. Audit Logs ───────────────────────────────────────────
        logs = [
            AuditLog(
                organization_id=org.id,
                actor_id=admin_user.id,
                action=AuditAction.PROJECT_CREATED,
                metadata_json={"project_id": str(p1.id), "name": p1.name, "key": p1.key},
            ),
            AuditLog(
                organization_id=org.id,
                actor_id=pm_user.id,
                action=AuditAction.ISSUE_CREATED,
                metadata_json={"project_id": str(p1.id), "issue_id": str(created_issues[1].id), "title": created_issues[1].title, "issue_number": 1},
            ),
            AuditLog(
                organization_id=org.id,
                actor_id=dev_user.id,
                action=AuditAction.ISSUE_STATUS_CHANGED,
                metadata_json={"project_id": str(p1.id), "issue_id": str(created_issues[2].id), "from_status": "IN_PROGRESS", "to_status": "DONE"},
            ),
        ]
        session.add_all(logs)

        # ── 11. Saved Searches ───────────────────────────────────────
        s1 = SavedSearch(
            organization_id=org.id,
            user_id=admin_user.id,
            name="Urgent Security Items",
            query_params={"q": "security", "priority": "URGENT"},
            is_shared=True,
        )
        s2 = SavedSearch(
            organization_id=org.id,
            user_id=pm_user.id,
            name="AI Feature Engine Backlog",
            query_params={"q": "AI", "status": "IN_PROGRESS"},
            is_shared=True,
        )
        s3 = SavedSearch(
            organization_id=org.id,
            user_id=dev_user.id,
            name="High Priority Backend Tasks",
            query_params={"q": "backend", "priority": "HIGH"},
            is_shared=False,
        )
        session.add_all([s1, s2, s3])

        await session.commit()
        print_summary(org.id)


def print_summary(org_id):
    print("\nDemo Data Seeded Successfully!")
    print("============================================================")
    print("  Organization  : DevTrack Technologies")
    print(f"  Org ID        : {org_id}")
    print("  Projects      : 2 (DevTrack AI Engine [DE], Mobile Platform [MP])")
    print("  Users         : 3 (Admin, PM, Developer)")
    print("  Issues        : 28 total (25 main issues + 3 subtasks)")
    print("  Kanban Board  : 5 Columns (Backlog, To Do, In Progress, In Review, Done)")
    print("  Labels        : 7 (bug, feature, backend, frontend, AI, security, urgent)")
    print("  Dependencies  : 3 dependency links (BLOCKS relationships)")
    print("  Comments      : 4 thread entries")
    print("  Saved Searches: 3 search presets")
    print("============================================================\n")
    print("DEMO LOGIN CREDENTIALS:")
    print("------------------------------------------------------------")
    print("  1. Admin / Owner     : demo@devtrack.ai  / DemoPass123!")
    print("  2. Project Manager   : pm@devtrack.ai    / DemoPass123!")
    print("  3. Developer         : dev@devtrack.ai   / DemoPass123!")
    print("============================================================\n")


if __name__ == "__main__":
    asyncio.run(seed())
