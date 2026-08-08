import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models.enums import IssueStatus


# ---------------------------------------------------------------------------
# Board Column schemas
# ---------------------------------------------------------------------------

class ColumnCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Column display name")
    mapped_status: IssueStatus = Field(..., description="IssueStatus this column represents")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Column name cannot be blank.")
        return s


class ColumnRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Column name cannot be blank.")
        return s


class ColumnReorderRequest(BaseModel):
    """Send the full ordered list of column UUIDs; service recomputes gap-positions."""
    ordered_column_ids: List[uuid.UUID] = Field(..., min_length=1)


class IssueMoveRequest(BaseModel):
    """Move an issue to a board column (updates Issue.status to column.mapped_status)."""
    column_id: uuid.UUID = Field(..., description="Target BoardColumn UUID")


class BoardColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    mapped_status: IssueStatus
    position: int
    is_hidden: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Board schemas
# ---------------------------------------------------------------------------

class BoardCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Board name")
    is_default: bool = Field(default=False, description="Mark as the default board for the project")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Board name cannot be blank.")
        return s


class BoardUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Board name cannot be blank.")
            return s
        return v


class BoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    is_default: bool
    columns: List[BoardColumnResponse] = []
    created_at: datetime
    updated_at: datetime


class BoardListResponse(BaseModel):
    """Lightweight board list entry (no columns embedded)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
