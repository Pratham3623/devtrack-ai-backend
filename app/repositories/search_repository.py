import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select, or_, text, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.comment import Comment
from app.domain.models.issue import Issue
from app.domain.models.organization import OrgMember
from app.domain.models.project import Project
from app.domain.models.saved_search import SavedSearch
from app.domain.models.user import User
from app.repositories.base_repository import BaseRepository


class SearchRepository(BaseRepository[SavedSearch]):
    """Repository handling global multi-entity search and saved search presets."""

    def __init__(self, db: AsyncSession):
        super().__init__(SavedSearch, db)

    async def global_search(
        self,
        org_id: uuid.UUID,
        query: str,
        entity_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
        limit: int = 30,
    ) -> Tuple[List[Dict[str, Any]], float]:
        """
        Executes enterprise search across Projects, Issues, Comments, and Members.
        Supports PostgreSQL full-text / ILIKE search with strict tenant scoping.
        """
        start_time = time.time()
        pattern = f"%{query}%"
        results: List[Dict[str, Any]] = []

        allowed_entities = entity_types or ["issue", "project", "comment", "member"]

        # 1. Search Issues
        if "issue" in allowed_entities:
            stmt = select(Issue).join(Project, Issue.project_id == Project.id).where(
                Project.organization_id == org_id,
                Issue.is_archived == False,
            )
            if project_id:
                stmt = stmt.where(Issue.project_id == project_id)
            if status:
                stmt = stmt.where(Issue.status == status)
            if priority:
                stmt = stmt.where(Issue.priority == priority)

            if query:
                stmt = stmt.where(
                    or_(
                        Issue.title.ilike(pattern),
                        Issue.description.ilike(pattern),
                        func.cast(Issue.issue_number, String).ilike(pattern),
                    )
                )

            stmt = stmt.options(selectinload(Issue.project)).order_by(Issue.created_at.desc()).limit(limit)
            res = await self.db.execute(stmt)
            issues = res.scalars().all()

            for i in issues:
                proj_key = i.project.key if i.project else "PROJ"
                identifier = f"{proj_key}-{i.issue_number}"
                stat_val = getattr(i.status, "value", str(i.status))
                prio_val = getattr(i.priority, "value", str(i.priority))
                results.append({
                    "entity_type": "issue",
                    "entity_id": i.id,
                    "title": f"[{identifier}] {i.title}",
                    "subtitle": f"Status: {stat_val} | Priority: {prio_val}",
                    "snippet": (i.description[:120] + "...") if i.description and len(i.description) > 120 else (i.description or ""),
                    "url": f"/ui?project={i.project_id}&issue={i.id}",
                    "metadata": {"issue_number": i.issue_number, "status": stat_val, "priority": prio_val},
                })

        # 2. Search Projects
        if "project" in allowed_entities:
            stmt = select(Project).where(
                Project.organization_id == org_id,
                Project.is_archived == False,
            )
            if query:
                stmt = stmt.where(
                    or_(
                        Project.name.ilike(pattern),
                        Project.key.ilike(pattern),
                        Project.description.ilike(pattern),
                    )
                )
            stmt = stmt.order_by(Project.created_at.desc()).limit(limit)
            res = await self.db.execute(stmt)
            projects = res.scalars().all()

            for p in projects:
                tmpl_val = getattr(p.template_type, "value", str(p.template_type))
                results.append({
                    "entity_type": "project",
                    "entity_id": p.id,
                    "title": f"{p.name} ({p.key})",
                    "subtitle": f"Template: {tmpl_val}",
                    "snippet": p.description or "",
                    "url": f"/ui?project={p.id}",
                    "metadata": {"key": p.key, "template": tmpl_val},
                })

        # 3. Search Comments
        if "comment" in allowed_entities and query:
            stmt = (
                select(Comment)
                .join(Issue, Comment.issue_id == Issue.id)
                .join(Project, Issue.project_id == Project.id)
                .where(
                    Project.organization_id == org_id,
                    Comment.content.ilike(pattern),
                )
                .options(selectinload(Comment.issue).selectinload(Issue.project))
                .order_by(Comment.created_at.desc())
                .limit(limit)
            )
            res = await self.db.execute(stmt)
            comments = res.scalars().all()

            for c in comments:
                issue_title = c.issue.title if c.issue else "Issue"
                results.append({
                    "entity_type": "comment",
                    "entity_id": c.id,
                    "title": f"Comment on '{issue_title}'",
                    "subtitle": f"By {c.author_id}",
                    "snippet": (c.content[:120] + "...") if len(c.content) > 120 else c.content,
                    "url": f"/ui?issue={c.issue_id}&comment={c.id}",
                    "metadata": {"issue_id": str(c.issue_id)},
                })


        # 4. Search Members
        if "member" in allowed_entities and query:
            stmt = (
                select(User)
                .join(OrgMember, User.id == OrgMember.user_id)
                .where(
                    OrgMember.organization_id == org_id,
                    or_(
                        User.full_name.ilike(pattern),
                        User.email.ilike(pattern),
                    ),
                )
                .limit(limit)
            )
            res = await self.db.execute(stmt)
            users = res.scalars().all()

            for u in users:
                results.append({
                    "entity_type": "member",
                    "entity_id": u.id,
                    "title": u.full_name or u.email,
                    "subtitle": u.email,
                    "snippet": f"Role: {u.role}",
                    "url": f"/ui?member={u.id}",
                    "metadata": {"email": u.email},
                })

        exec_time_ms = round((time.time() - start_time) * 1000, 2)
        return results, exec_time_ms

    async def create_saved_search(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str,
        query_params: Dict[str, Any],
        is_shared: bool = False,
    ) -> SavedSearch:
        saved = SavedSearch(
            organization_id=org_id,
            user_id=user_id,
            name=name,
            query_params=query_params,
            is_shared=is_shared,
        )
        self.db.add(saved)
        await self.db.commit()
        await self.db.refresh(saved)
        return saved

    async def list_saved_searches(self, org_id: uuid.UUID, user_id: uuid.UUID) -> List[SavedSearch]:
        stmt = (
            select(SavedSearch)
            .where(
                SavedSearch.organization_id == org_id,
                or_(SavedSearch.user_id == user_id, SavedSearch.is_shared == True),
            )
            .order_by(SavedSearch.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_saved_search(self, org_id: uuid.UUID, saved_id: uuid.UUID) -> Optional[SavedSearch]:
        stmt = select(SavedSearch).where(
            SavedSearch.organization_id == org_id,
            SavedSearch.id == saved_id,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()
