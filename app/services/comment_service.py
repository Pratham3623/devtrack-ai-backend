import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.logging import logger
from app.domain.models.audit_log import AuditLog
from app.domain.models.comment import Comment
from app.domain.models.enums import AuditAction, OrgRole
from app.domain.models.issue import Issue
from app.domain.models.project import Project
from app.domain.models.user import User
from app.domain.schemas.comment import (
    ActivityItemResponse,
    CommentCreate,
    CommentUpdate,
)
from app.repositories.comment_repository import CommentRepository
from app.repositories.issue_repository import IssueRepository
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


class CommentService:
    """Service handling comments and issue activity timeline."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommentRepository(db)
        self.issue_repo = IssueRepository(db)
        self.project_repo = ProjectRepository(db)
        self.org_repo = OrganizationRepository(db)

    async def _check_org_access(self, org_id: uuid.UUID, user_id: uuid.UUID):
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise ForbiddenException("User is not a member of this organization.")
        return membership

    async def _get_issue_in_project(
        self, org_id: uuid.UUID, project_id: uuid.UUID, issue_id: uuid.UUID
    ) -> Issue:
        project = await self.project_repo.get_by_id(project_id)
        if not project or project.organization_id != org_id:
            raise EntityNotFoundException("Project", project_id)

        issue = await self.issue_repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)
        return issue

    async def create_comment(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        dto: CommentCreate,
    ) -> Comment:
        await self._check_org_access(org_id, actor.id)
        issue = await self._get_issue_in_project(org_id, project_id, issue_id)

        comment = await self.repo.create_comment(
            issue_id=issue.id,
            author_id=actor.id,
            content=dto.content,
        )

        # Log audit entry for activity timeline
        audit = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action=AuditAction.COMMENT_CREATED,
            metadata_json={
                "issue_id": str(issue.id),
                "issue_number": issue.issue_number,
                "comment_id": str(comment.id),
                "content_preview": dto.content[:100],
            },
        )
        self.db.add(audit)
        await self.db.commit()
        logger.info(f"Comment {comment.id} added on Issue {issue.id} by User {actor.id}")

        # Broadcast live comment event over WebSockets
        try:
            from datetime import datetime, timezone
            from app.core.websockets.events import WSEvent, WSEventType
            from app.core.websockets.manager import manager

            event = WSEvent(
                event_type=WSEventType.COMMENT_CREATED,
                project_id=str(project_id),
                issue_id=str(issue.id),
                sender_id=str(actor.id),
                sender_name=actor.full_name or actor.email,
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload={
                    "comment_id": str(comment.id),
                    "issue_id": str(issue.id),
                    "content": comment.content,
                    "author_name": actor.full_name or actor.email,
                    "author_id": str(actor.id),
                    "created_at": comment.created_at.isoformat(),
                },
            )
            await manager.broadcast_event(str(project_id), event)
        except Exception as e:
            logger.warning(f"Failed to broadcast comment event: {e}")

        return comment

    async def list_comments(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
    ) -> List[Comment]:
        await self._check_org_access(org_id, actor.id)
        issue = await self._get_issue_in_project(org_id, project_id, issue_id)
        return await self.repo.list_by_issue(issue.id)

    async def update_comment(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        comment_id: uuid.UUID,
        actor: User,
        dto: CommentUpdate,
    ) -> Comment:
        membership = await self._check_org_access(org_id, actor.id)
        issue = await self._get_issue_in_project(org_id, project_id, issue_id)

        comment = await self.repo.get_by_id_with_author(comment_id)
        if not comment or comment.issue_id != issue.id:
            raise EntityNotFoundException("Comment", comment_id)

        # Authorization: Must be comment author OR Org OWNER/ADMIN
        if comment.author_id != actor.id and membership.role not in [OrgRole.OWNER, OrgRole.ADMIN]:
            raise ForbiddenException("Only the author or organization admins can edit this comment.")

        comment = await self.repo.update_comment(comment, dto.content)

        audit = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action=AuditAction.COMMENT_UPDATED,
            metadata_json={
                "issue_id": str(issue.id),
                "comment_id": str(comment.id),
            },
        )
        self.db.add(audit)
        await self.db.commit()
        return comment

    async def delete_comment(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        comment_id: uuid.UUID,
        actor: User,
    ) -> None:
        membership = await self._check_org_access(org_id, actor.id)
        issue = await self._get_issue_in_project(org_id, project_id, issue_id)

        comment = await self.repo.get_by_id_with_author(comment_id)
        if not comment or comment.issue_id != issue.id:
            raise EntityNotFoundException("Comment", comment_id)

        # Authorization check
        if comment.author_id != actor.id and membership.role not in [OrgRole.OWNER, OrgRole.ADMIN]:
            raise ForbiddenException("Only the author or organization admins can delete this comment.")

        await self.repo.delete_comment(comment)

        audit = AuditLog(
            organization_id=org_id,
            actor_id=actor.id,
            action=AuditAction.COMMENT_DELETED,
            metadata_json={
                "issue_id": str(issue.id),
                "comment_id": str(comment_id),
            },
        )
        self.db.add(audit)
        await self.db.commit()

    async def get_activity_timeline(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
    ) -> List[ActivityItemResponse]:
        await self._check_org_access(org_id, actor.id)
        issue = await self._get_issue_in_project(org_id, project_id, issue_id)

        # 1. Fetch comments
        comments = await self.repo.list_by_issue(issue.id)

        # 2. Fetch issue audit logs
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.organization_id == org_id,
                AuditLog.metadata_json["issue_id"].as_string() == str(issue.id),
            )
            .options(selectinload(AuditLog.actor))
            .order_by(AuditLog.created_at.asc())
        )
        res = await self.db.execute(stmt)
        audits = list(res.scalars().all())

        timeline: List[ActivityItemResponse] = []

        for c in comments:
            timeline.append(
                ActivityItemResponse(
                    id=c.id,
                    type="comment",
                    action="COMMENT_CREATED",
                    actor_id=c.author_id,
                    actor_name=c.author.full_name or c.author.email if c.author else "Unknown",
                    content=c.content,
                    metadata_json=None,
                    timestamp=c.created_at,
                )
            )

        for a in audits:
            actor_name = a.actor.full_name or a.actor.email if a.actor else "System"
            timeline.append(
                ActivityItemResponse(
                    id=a.id,
                    type="audit",
                    action=a.action.value,
                    actor_id=a.actor_id,
                    actor_name=actor_name,
                    content=None,
                    metadata_json=a.metadata_json,
                    timestamp=a.created_at,
                )
            )

        timeline.sort(key=lambda x: x.timestamp)
        return timeline
