import uuid
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.logging import logger
from app.domain.models.board import Board, BoardColumn
from app.domain.models.enums import IssueStatus, OrgRole
from app.domain.models.issue import Issue
from app.domain.models.project import Project
from app.domain.schemas.board import (
    BoardCreateRequest,
    BoardUpdateRequest,
    ColumnCreateRequest,
    ColumnRenameRequest,
    ColumnReorderRequest,
    IssueMoveRequest,
)
from app.domain.models.user import User
from app.repositories.board_repository import BoardRepository
from app.repositories.issue_repository import IssueRepository
from app.repositories.org_repository import OrganizationRepository
from app.repositories.project_repository import ProjectRepository


class BoardService:
    """Business logic, authorization, and workflow for Kanban Boards and Columns."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BoardRepository(db)
        self.issue_repo = IssueRepository(db)
        self.project_repo = ProjectRepository(db)
        self.org_repo = OrganizationRepository(db)

    # ------------------------------------------------------------------
    # Auth helpers (mirror IssueService pattern)
    # ------------------------------------------------------------------

    async def _check_org_access(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        allowed_roles: Optional[List[OrgRole]] = None,
    ):
        membership = await self.org_repo.get_membership(org_id, user_id)
        if not membership:
            raise ForbiddenException("User is not a member of this organization.")
        if allowed_roles and membership.role not in allowed_roles:
            roles_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenException(f"Organization role in [{roles_str}] required.")
        return membership

    async def _get_project_in_org(self, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if not project or project.organization_id != org_id:
            raise EntityNotFoundException("Project", project_id)
        return project

    async def _get_board_in_project(self, project_id: uuid.UUID, board_id: uuid.UUID) -> Board:
        board = await self.repo.get_board_with_columns(board_id)
        if not board or board.project_id != project_id:
            raise EntityNotFoundException("Board", board_id)
        return board

    async def _get_column_in_board(self, board_id: uuid.UUID, column_id: uuid.UUID) -> BoardColumn:
        col = await self.repo.get_column(column_id)
        if not col or col.board_id != board_id:
            raise EntityNotFoundException("BoardColumn", column_id)
        return col

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    async def create_board(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
        dto: BoardCreateRequest,
    ) -> Board:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)

        if dto.is_default:
            # Clear existing default flag for this project
            await self.repo.clear_default_flag(project_id)

        board = await self.repo.create_board(
            project_id=project_id,
            name=dto.name,
            is_default=dto.is_default,
        )
        await self.db.commit()
        # Re-fetch with selectinload so columns are eagerly loaded for serialization
        board = await self.repo.get_board_with_columns(board.id)
        logger.info(f"Board '{board.name}' created in project {project_id} by user {actor.id}")
        return board

    async def get_board(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        actor: User,
    ) -> Board:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        return await self._get_board_in_project(project_id, board_id)

    async def list_boards(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor: User,
    ) -> List[Board]:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        return await self.repo.get_boards_for_project(project_id)

    async def update_board(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        actor: User,
        dto: BoardUpdateRequest,
    ) -> Board:
        await self._check_org_access(org_id, actor.id)
        board = await self.get_board(org_id, project_id, board_id, actor)

        if dto.name is not None:
            board.name = dto.name

        await self.db.commit()
        # Re-fetch with selectinload so columns are eagerly loaded
        return await self.repo.get_board_with_columns(board.id)

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    async def create_column(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        actor: User,
        dto: ColumnCreateRequest,
    ) -> BoardColumn:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        board = await self._get_board_in_project(project_id, board_id)

        if await self.repo.status_used_in_board(board.id, dto.mapped_status):
            raise ValidationException(
                f"Status '{dto.mapped_status.value}' is already mapped to a column in this board."
            )

        col = await self.repo.create_column(
            board_id=board.id,
            name=dto.name,
            mapped_status=dto.mapped_status,
        )
        await self.db.commit()
        await self.db.refresh(col)
        logger.info(f"Column '{col.name}' ({dto.mapped_status.value}) created in board {board_id}")
        return col

    async def rename_column(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        column_id: uuid.UUID,
        actor: User,
        dto: ColumnRenameRequest,
    ) -> BoardColumn:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        await self._get_board_in_project(project_id, board_id)
        col = await self._get_column_in_board(board_id, column_id)

        col.name = dto.name
        await self.db.commit()
        await self.db.refresh(col)
        return col

    async def reorder_columns(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        actor: User,
        dto: ColumnReorderRequest,
    ) -> Board:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        board = await self._get_board_in_project(project_id, board_id)

        # Validate that all supplied IDs belong to this board
        board_col_ids = {c.id for c in board.columns}
        for cid in dto.ordered_column_ids:
            if cid not in board_col_ids:
                raise ValidationException(f"Column {cid} does not belong to board {board_id}.")

        await self.repo.reorder_columns(board.id, dto.ordered_column_ids)
        await self.db.commit()

        # Return refreshed board with columns
        return await self._get_board_in_project(project_id, board_id)

    async def delete_column(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        column_id: uuid.UUID,
        actor: User,
    ) -> None:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        await self._get_board_in_project(project_id, board_id)
        col = await self._get_column_in_board(board_id, column_id)

        # Block deletion if non-archived issues are in this status
        count_stmt = (
            select(func.count())
            .where(
                Issue.project_id == project_id,
                Issue.status == col.mapped_status,
                Issue.is_archived == False,
            )
        )
        res = await self.db.execute(count_stmt)
        active_count = res.scalar() or 0
        if active_count > 0:
            raise ValidationException(
                f"Cannot delete column '{col.name}': {active_count} active issue(s) are in "
                f"status '{col.mapped_status.value}'. Move or archive them first."
            )

        await self.repo.delete_column(col)
        await self.db.commit()
        logger.info(f"Column {column_id} deleted from board {board_id} by user {actor.id}")

    # ------------------------------------------------------------------
    # Issue movement
    # ------------------------------------------------------------------

    async def move_issue(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        board_id: uuid.UUID,
        issue_id: uuid.UUID,
        actor: User,
        dto: IssueMoveRequest,
    ) -> Issue:
        await self._check_org_access(org_id, actor.id)
        await self._get_project_in_org(org_id, project_id)
        await self._get_board_in_project(project_id, board_id)
        col = await self._get_column_in_board(board_id, dto.column_id)

        # Fetch the issue (verify it belongs to this project)
        issue = await self.issue_repo.get_with_project(issue_id)
        if not issue or issue.project_id != project_id:
            raise EntityNotFoundException("Issue", issue_id)

        old_status = issue.status
        issue.status = col.mapped_status
        await self.db.commit()
        await self.db.refresh(issue)
        logger.info(
            f"Issue {issue_id} moved from '{old_status.value}' to "
            f"'{col.mapped_status.value}' via board {board_id} by user {actor.id}"
        )

        # Broadcast live board update over WebSockets
        try:
            from datetime import datetime, timezone
            from app.core.websockets.events import WSEvent, WSEventType
            from app.core.websockets.manager import manager

            event = WSEvent(
                event_type=WSEventType.ISSUE_MOVED,
                project_id=str(project_id),
                issue_id=str(issue.id),
                sender_id=str(actor.id),
                sender_name=actor.full_name or actor.email,
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload={
                    "issue_id": str(issue.id),
                    "old_status": old_status.value,
                    "new_status": col.mapped_status.value,
                    "column_id": str(col.id),
                },
            )
            await manager.broadcast_event(str(project_id), event)
        except Exception as e:
            logger.warning(f"Failed to broadcast issue move event: {e}")

        return issue
