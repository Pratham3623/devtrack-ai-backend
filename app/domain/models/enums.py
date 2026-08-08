from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"
    GUEST = "GUEST"


class OAuthProvider(str, Enum):
    LOCAL = "local"
    GITHUB = "github"
    GOOGLE = "google"


class OrgRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    GUEST = "GUEST"


class TeamRole(str, Enum):
    LEAD = "LEAD"
    MEMBER = "MEMBER"


class InvitationStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class AuditAction(str, Enum):
    ORG_CREATED = "ORG_CREATED"
    ORG_UPDATED = "ORG_UPDATED"
    MEMBER_INVITED = "MEMBER_INVITED"
    MEMBER_JOINED = "MEMBER_JOINED"
    ROLE_UPDATED = "ROLE_UPDATED"
    MEMBER_REMOVED = "MEMBER_REMOVED"
    OWNERSHIP_TRANSFERRED = "OWNERSHIP_TRANSFERRED"
    TEAM_CREATED = "TEAM_CREATED"
    TEAM_MEMBER_ADDED = "TEAM_MEMBER_ADDED"
