import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models.enums import IssuePriority, IssueStatus


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="Issue title summary")
    description: Optional[str] = Field(None, description="Detailed markdown description")
    status: IssueStatus = Field(default=IssueStatus.TODO, description="Workflow status")
    priority: IssuePriority = Field(default=IssuePriority.MEDIUM, description="Priority level")
    assignee_id: Optional[uuid.UUID] = Field(None, description="Assigned user ID")

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Issue title cannot be empty or whitespace only.")
        return s


class IssueUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    assignee_id: Optional[uuid.UUID] = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Issue title cannot be empty or whitespace only.")
            return s
        return v


class IssueCreateRequest(IssueCreate):
    pass


class IssueUpdateRequest(IssueUpdate):
    pass


class IssueStatusUpdateRequest(BaseModel):
    status: IssueStatus = Field(..., description="New issue status")


class IssuePriorityUpdateRequest(BaseModel):
    priority: IssuePriority = Field(..., description="New issue priority")


class IssueAssignRequest(BaseModel):
    assignee_id: Optional[uuid.UUID] = Field(None, description="Target assignee User UUID")


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    issue_number: int
    identifier: str
    title: str
    description: Optional[str] = None
    status: IssueStatus
    priority: IssuePriority
    reporter_id: uuid.UUID
    assignee_id: Optional[uuid.UUID] = None
    is_archived: bool
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class IssuePaginatedResponse(BaseModel):
    items: List[IssueResponse]
    total: int
    page: int
    size: int
    pages: int
