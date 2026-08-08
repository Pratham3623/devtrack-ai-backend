import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.domain.models.user import User
from app.domain.schemas.board import (
    BoardColumnResponse,
    BoardCreateRequest,
    BoardListResponse,
    BoardResponse,
    BoardUpdateRequest,
    ColumnCreateRequest,
    ColumnRenameRequest,
    ColumnReorderRequest,
    IssueMoveRequest,
)
from app.domain.schemas.issue import IssueResponse
from app.services.board_service import BoardService

router = APIRouter()


@router.post(
    "/{org_id}/projects/{project_id}/boards",
    response_model=BoardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Board",
)
async def create_board(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    dto: BoardCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    service = BoardService(db)
    board = await service.create_board(org_id, project_id, current_user, dto)
    return BoardResponse.model_validate(board)


@router.get(
    "/{org_id}/projects/{project_id}/boards",
    response_model=List[BoardListResponse],
    summary="List Boards for Project",
)
async def list_boards(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[BoardListResponse]:
    service = BoardService(db)
    boards = await service.list_boards(org_id, project_id, current_user)
    return [BoardListResponse.model_validate(b) for b in boards]


@router.get(
    "/{org_id}/projects/{project_id}/boards/{board_id}",
    response_model=BoardResponse,
    summary="Get Board with Columns",
)
async def get_board(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    service = BoardService(db)
    board = await service.get_board(org_id, project_id, board_id, current_user)
    return BoardResponse.model_validate(board)


@router.patch(
    "/{org_id}/projects/{project_id}/boards/{board_id}",
    response_model=BoardResponse,
    summary="Update Board",
)
async def update_board(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    dto: BoardUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    service = BoardService(db)
    board = await service.update_board(org_id, project_id, board_id, current_user, dto)
    return BoardResponse.model_validate(board)


# ---------------------------------------------------------------------------
# Column endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/projects/{project_id}/boards/{board_id}/columns",
    response_model=BoardColumnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Column",
)
async def create_column(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    dto: ColumnCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardColumnResponse:
    service = BoardService(db)
    col = await service.create_column(org_id, project_id, board_id, current_user, dto)
    return BoardColumnResponse.model_validate(col)


@router.patch(
    "/{org_id}/projects/{project_id}/boards/{board_id}/columns/{column_id}",
    response_model=BoardColumnResponse,
    summary="Rename Column",
)
async def rename_column(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    dto: ColumnRenameRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardColumnResponse:
    service = BoardService(db)
    col = await service.rename_column(org_id, project_id, board_id, column_id, current_user, dto)
    return BoardColumnResponse.model_validate(col)


@router.put(
    "/{org_id}/projects/{project_id}/boards/{board_id}/columns/reorder",
    response_model=BoardResponse,
    summary="Reorder Columns",
)
async def reorder_columns(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    dto: ColumnReorderRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> BoardResponse:
    service = BoardService(db)
    board = await service.reorder_columns(org_id, project_id, board_id, current_user, dto)
    return BoardResponse.model_validate(board)


@router.delete(
    "/{org_id}/projects/{project_id}/boards/{board_id}/columns/{column_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Column (safe — blocked if active issues exist)",
)
async def delete_column(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = BoardService(db)
    await service.delete_column(org_id, project_id, board_id, column_id, current_user)


# ---------------------------------------------------------------------------
# Issue movement
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/projects/{project_id}/boards/{board_id}/issues/{issue_id}/move",
    response_model=IssueResponse,
    summary="Move Issue to Column (updates Issue.status)",
)
async def move_issue(
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    board_id: uuid.UUID,
    issue_id: uuid.UUID,
    dto: IssueMoveRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> IssueResponse:
    service = BoardService(db)
    issue = await service.move_issue(org_id, project_id, board_id, issue_id, current_user, dto)
    return IssueResponse.model_validate(issue)
