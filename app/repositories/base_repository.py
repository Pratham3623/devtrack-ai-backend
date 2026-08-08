import uuid
from typing import Any, Generic, List, Optional, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async repository providing foundational CRUD operations."""

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id_val: uuid.UUID) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id_val)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, entity: ModelType) -> ModelType:
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: ModelType) -> None:
        await self.db.delete(entity)
        await self.db.commit()
