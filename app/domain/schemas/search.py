import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SavedSearchCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    query_params: Dict[str, Any] = Field(default_factory=dict)
    is_shared: bool = False


class SavedSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    query_params: Dict[str, Any]
    is_shared: bool
    created_at: datetime


class GlobalSearchResultItem(BaseModel):
    entity_type: str  # "issue", "project", "comment", "member"
    entity_id: uuid.UUID
    title: str
    subtitle: Optional[str] = None
    snippet: Optional[str] = None
    url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GlobalSearchResponse(BaseModel):
    query: str
    total_results: int
    items: List[GlobalSearchResultItem]
    execution_time_ms: float
