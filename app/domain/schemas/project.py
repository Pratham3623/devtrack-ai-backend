import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.enums import ProjectRole, ProjectTemplateType
from app.domain.schemas.auth import UserResponse


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    key: Optional[str] = Field(None, min_length=2, max_length=32)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    template_type: ProjectTemplateType = ProjectTemplateType.KANBAN
    settings_json: Optional[Dict[str, Any]] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    key: Optional[str] = Field(None, min_length=2, max_length=32)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    is_archived: Optional[bool] = None
    settings_json: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    key: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    owner_id: uuid.UUID
    template_type: ProjectTemplateType
    is_archived: bool
    archived_at: Optional[datetime] = None
    settings_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class ProjectPaginatedResponse(BaseModel):
    items: List[ProjectResponse]
    total: int
    page: int
    size: int
    pages: int


class ProjectMemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: ProjectRole = ProjectRole.CONTRIBUTOR


class ProjectMemberRoleUpdateRequest(BaseModel):
    role: ProjectRole


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectRole
    joined_at: datetime
    user: UserResponse


class ProjectTemplateResponse(BaseModel):
    template_type: ProjectTemplateType
    name: str
    description: str
    default_columns: List[str]
    default_settings: Dict[str, Any]


class ProjectDashboardResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    project_key: str
    total_members: int
    open_issues_count: int
    completed_issues_count: int
    health_score: int  # 0-100
    completion_percentage: float
    workflow_columns: List[str]


class ProjectAnalyticsResponse(BaseModel):
    project_id: uuid.UUID
    velocity_trend: List[Dict[str, Any]]
    issue_status_distribution: Dict[str, int]
    member_workload: List[Dict[str, Any]]
    created_vs_resolved: Dict[str, int]
