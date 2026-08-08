import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.models.enums import AuditAction, InvitationStatus, OrgRole, TeamRole
from app.domain.schemas.auth import UserResponse


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(None, min_length=2, max_length=255)
    logo_url: Optional[str] = None


class OrganizationUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    logo_url: Optional[str] = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    owner_id: uuid.UUID
    plan_tier: str
    created_at: datetime


class OrgMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: OrgRole
    joined_at: datetime
    user: UserResponse


class OrgMemberRoleUpdateRequest(BaseModel):
    role: OrgRole


class TransferOwnershipRequest(BaseModel):
    new_owner_id: uuid.UUID


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: EmailStr
    role: OrgRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime


class AddTeamMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: TeamRole = TeamRole.MEMBER


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    actor_id: uuid.UUID
    action: AuditAction
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    actor: Optional[UserResponse] = None
