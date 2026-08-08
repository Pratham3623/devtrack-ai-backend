import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models.board import Board, BoardColumn
from app.domain.models.enums import IssueStatus
from app.repositories.base_repository import BaseRepository

_POSITION_GAP = 1000
_REINDEX_THRESHOLD = 10


class BoardRepository(BaseRepository[Board]):
    """Data access layer for Boards and BoardColumns."""

    def __init__(self, db: AsyncSession):
        super().__init__(Board, db)

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    async def create_board(self, project_id: uuid.UUID, name: str, is_default: bool) -> Board:
        board = Board(project_id=project_id, name=name, is_default=is_default)
        self.db.add(board)
        await self.db.flush()
        await self.db.refresh(board)
        return board

    async def get_board_with_columns(self, board_id: uuid.UUID) -> Optional[Board]:
        stmt = (
            select(Board)
            .where(Board.id == board_id)
            .options(selectinload(Board.columns))
        )
        res = await self.db.execute(stmt)
        board = res.scalar_one_or_none()
        if board:
            board.columns.sort(key=lambda c: c.position)
        return board

    async def get_boards_for_project(self, project_id: uuid.UUID) -> List[Board]:
        stmt = (
            select(Board)
            .where(Board.project_id == project_id)
            .options(selectinload(Board.columns))
            .order_by(Board.created_at.asc())
        )
        res = await self.db.execute(stmt)
        boards = list(res.scalars().all())
        for board in boards:
            board.columns.sort(key=lambda c: c.position)
        return boards

    async def clear_default_flag(self, project_id: uuid.UUID) -> None:
        """Remove is_default from all boards in a project (called before setting a new default)."""
        stmt = select(Board).where(Board.project_id == project_id, Board.is_default == True)
        res = await self.db.execute(stmt)
        for board in res.scalars().all():
            board.is_default = False
        await self.db.flush()

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    async def get_column(self, column_id: uuid.UUID) -> Optional[BoardColumn]:
        stmt = select(BoardColumn).where(BoardColumn.id == column_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_column_by_status(
        self, board_id: uuid.UUID, mapped_status: IssueStatus
    ) -> Optional[BoardColumn]:
        stmt = select(BoardColumn).where(
            BoardColumn.board_id == board_id,
            BoardColumn.mapped_status == mapped_status,
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def status_used_in_board(
        self, board_id: uuid.UUID, mapped_status: IssueStatus
    ) -> bool:
        col = await self.get_column_by_status(board_id, mapped_status)
        return col is not None

    async def get_max_position(self, board_id: uuid.UUID) -> int:
        stmt = select(BoardColumn.position).where(BoardColumn.board_id == board_id)
        res = await self.db.execute(stmt)
        positions = res.scalars().all()
        return max(positions) if positions else 0

    async def create_column(
        self,
        board_id: uuid.UUID,
        name: str,
        mapped_status: IssueStatus,
    ) -> BoardColumn:
        next_pos = await self.get_max_position(board_id) + _POSITION_GAP
        col = BoardColumn(
            board_id=board_id,
            name=name,
            mapped_status=mapped_status,
            position=next_pos,
        )
        self.db.add(col)
        await self.db.flush()
        await self.db.refresh(col)
        return col

    async def reorder_columns(
        self, board_id: uuid.UUID, ordered_ids: List[uuid.UUID]
    ) -> List[BoardColumn]:
        """
        Reassign gap-based positions for columns according to caller-supplied order.
        Acquires a pessimistic lock on the Board row to prevent concurrent reorder races.
        Reindexes to multiples of _POSITION_GAP.
        """
        # Lock the parent board row for duration of transaction
        lock_stmt = select(Board.id).where(Board.id == board_id).with_for_update()
        await self.db.execute(lock_stmt)

        # Fetch all columns for this board keyed by id
        stmt = select(BoardColumn).where(BoardColumn.board_id == board_id)
        res = await self.db.execute(stmt)
        col_map = {c.id: c for c in res.scalars().all()}

        # Assign new positions
        updated: List[BoardColumn] = []
        for idx, col_id in enumerate(ordered_ids):
            col = col_map.get(col_id)
            if col:
                col.position = (idx + 1) * _POSITION_GAP
                updated.append(col)

        await self.db.flush()
        return sorted(updated, key=lambda c: c.position)

    async def delete_column(self, column: BoardColumn) -> None:
        await self.db.delete(column)
        await self.db.flush()
