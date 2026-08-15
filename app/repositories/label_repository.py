import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.label import Label, issue_labels
from app.repositories.base_repository import BaseRepository


class LabelRepository(BaseRepository[Label]):
    """Data access layer for Project Labels and Issue-Label associations."""

    def __init__(self, db: AsyncSession):
        super().__init__(Label, db)

    async def create_label(self, project_id: uuid.UUID, name: str, color: str) -> Label:
        label = Label(project_id=project_id, name=name, color=color)
        self.db.add(label)
        await self.db.flush()
        await self.db.refresh(label)
        return label

    async def list_by_project(self, project_id: uuid.UUID) -> List[Label]:
        stmt = (
            select(Label)
            .where(Label.project_id == project_id)
            .order_by(Label.name.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> Optional[Label]:
        stmt = select(Label).where(Label.project_id == project_id, Label.name == name)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_label(self, label: Label, name: Optional[str] = None, color: Optional[str] = None) -> Label:
        if name is not None:
            label.name = name
        if color is not None:
            label.color = color
        await self.db.flush()
        await self.db.refresh(label)
        return label

    async def delete_label(self, label: Label) -> None:
        await self.db.delete(label)
        await self.db.flush()

    async def get_issue_labels(self, issue_id: uuid.UUID) -> List[Label]:
        stmt = (
            select(Label)
            .join(issue_labels, Label.id == issue_labels.c.label_id)
            .where(issue_labels.c.issue_id == issue_id)
            .order_by(Label.name.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def is_label_assigned_to_issue(self, issue_id: uuid.UUID, label_id: uuid.UUID) -> bool:
        stmt = select(issue_labels).where(
            issue_labels.c.issue_id == issue_id,
            issue_labels.c.label_id == label_id,
        )
        res = await self.db.execute(stmt)
        return res.first() is not None

    async def assign_label_to_issue(self, issue_id: uuid.UUID, label_id: uuid.UUID) -> None:
        if not await self.is_label_assigned_to_issue(issue_id, label_id):
            stmt = issue_labels.insert().values(issue_id=issue_id, label_id=label_id)
            await self.db.execute(stmt)
            await self.db.flush()

    async def remove_label_from_issue(self, issue_id: uuid.UUID, label_id: uuid.UUID) -> None:
        stmt = issue_labels.delete().where(
            issue_labels.c.issue_id == issue_id,
            issue_labels.c.label_id == label_id,
        )
        await self.db.execute(stmt)
        await self.db.flush()
