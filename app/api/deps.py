import uuid
from typing import Callable, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.models.enums import UserRole
from app.domain.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract Bearer JWT, validate signature, and return current authenticated User."""
    payload = decode_access_token(token)
    user_id_str: str = payload.get("sub")

    if not user_id_str:
        raise UnauthorizedException("Could not validate credentials.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedException("Invalid user identifier in token.")

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User not found.")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Check if current authenticated user is active."""
    if not current_user.is_active:
        raise ForbiddenException("Inactive user account.")
    return current_user


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""

    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            allowed_str = ", ".join([r.value for r in allowed_roles])
            raise ForbiddenException(
                f"User role '{current_user.role.value}' does not have permission. Required: [{allowed_str}]."
            )
        return current_user

    return role_checker
