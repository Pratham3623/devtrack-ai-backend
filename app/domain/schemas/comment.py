import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000, description="Comment text markdown")

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Comment content cannot be empty or whitespace only.")
        return s


class CommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Comment content cannot be empty or whitespace only.")
        return s


class CommentAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: Optional[str] = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    author_id: uuid.UUID
    content: str
    author: Optional[CommentAuthorResponse] = None
    created_at: datetime
    updated_at: datetime


class ActivityItemResponse(BaseModel):
    id: uuid.UUID
    type: str  # 'comment' or 'audit'
    action: str
    actor_id: uuid.UUID
    actor_name: str
    content: Optional[str] = None
    metadata_json: Optional[dict] = None
    timestamp: datetime
