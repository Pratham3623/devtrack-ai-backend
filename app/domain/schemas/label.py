import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="Label display name")
    color: str = Field("#6366f1", min_length=4, max_length=7, description="Hex color string")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Label name cannot be blank.")
        return s


class LabelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    color: Optional[str] = Field(None, min_length=4, max_length=7)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Label name cannot be blank.")
            return s
        return v


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    color: str
    created_at: datetime
    updated_at: datetime


class IssueLabelAssignRequest(BaseModel):
    label_id: uuid.UUID = Field(..., description="Target Label UUID to assign")
