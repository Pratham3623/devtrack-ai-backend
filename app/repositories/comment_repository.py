import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.comment import Comment
from app.repositories.base_repository import BaseRepository


class CommentRepository(BaseRepository[Comment]):
    """Data access operations for Issue Comments."""

    def __init__(self, db: AsyncSession):
        super().__init__(Comment, db)

    async def create_comment(
        self, issue_id: uuid.UUID, author_id: uuid.UUID, content: str
    ) -> Comment:
        comment = Comment(issue_id=issue_id, author_id=author_id, content=content)
        self.db.add(comment)
        await self.db.flush()
        return await self.get_by_id_with_author(comment.id)

    async def get_by_id_with_author(self, comment_id: uuid.UUID) -> Optional[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.id == comment_id)
            .options(selectinload(Comment.author))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_issue(self, issue_id: uuid.UUID) -> List[Comment]:
        stmt = (
            select(Comment)
            .where(Comment.issue_id == issue_id)
            .options(selectinload(Comment.author))
            .order_by(Comment.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def update_comment(self, comment: Comment, content: str) -> Comment:
        comment.content = content
        await self.db.flush()
        return await self.get_by_id_with_author(comment.id)

    async def delete_comment(self, comment: Comment) -> None:
        await self.db.delete(comment)
        await self.db.flush()
