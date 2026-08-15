import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.dependency import DependencyType
from app.domain.models.enums import IssuePriority, IssueStatus


class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512, description="Subtask title")
    description: Optional[str] = None
    status: IssueStatus = Field(default=IssueStatus.TODO)
    priority: IssuePriority = Field(default=IssuePriority.MEDIUM)
    assignee_id: Optional[uuid.UUID] = None


class SubtaskProgressResponse(BaseModel):
    total_subtasks: int
    completed_subtasks: int
    completion_percentage: float


class DependencyCreate(BaseModel):
    target_issue_id: uuid.UUID = Field(..., description="Target issue UUID")
    dependency_type: DependencyType = Field(..., description="BLOCKS, BLOCKED_BY, or RELATES_TO")


class LinkedIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_number: int
    identifier: str
    title: str
    status: IssueStatus
    priority: IssuePriority


class DependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    target_issue_id: uuid.UUID
    dependency_type: DependencyType
    target_issue: Optional[LinkedIssueResponse] = None
    created_at: datetime
