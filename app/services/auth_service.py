import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BaseAppException, EntityNotFoundException, UnauthorizedException, ValidationException
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.models.enums import OAuthProvider, UserRole
from app.domain.models.refresh_token import RefreshToken
from app.domain.models.user import User
from app.domain.schemas.auth import (
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, dto: UserRegisterRequest) -> Tuple[User, str]:
        """Register a new user account."""
        # Check if email exists
        stmt = select(User).where(User.email == dto.email.lower())
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise ValidationException(f"User with email '{dto.email}' already exists.")

        verification_token = generate_opaque_token()
        hashed_verif_token = hash_token(verification_token)

        user = User(
            email=dto.email.lower(),
            hashed_password=hash_password(dto.password),
            full_name=dto.full_name,
            role=UserRole.MEMBER,
            is_active=True,
            is_verified=False,
            verification_token=hashed_verif_token,
            oauth_provider=OAuthProvider.LOCAL,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User registered successfully: {user.email} (ID: {user.id})")
        return user, verification_token

    async def verify_email(self, raw_token: str) -> User:
        """Verify user's email address using raw verification token."""
        hashed_token = hash_token(raw_token)
        stmt = select(User).where(User.verification_token == hashed_token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValidationException("Invalid or expired verification token.")

        user.is_verified = True
        user.verification_token = None
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User email verified: {user.email}")
        return user

    async def login_user(
        self, email: str, password: str, device_info: Optional[str] = None, ip_address: Optional[str] = None
    ) -> TokenResponse:
        """Authenticate password login and issue Access + Refresh Token pair."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedException("User account is disabled.")

        # Create Refresh Token
        raw_refresh_token = generate_opaque_token()
        hashed_refresh = hash_token(raw_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_entity = RefreshToken(
            user_id=user.id,
            token_hash=hashed_refresh,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(refresh_entity)
        await self.db.commit()

        # Create Access Token
        access_token = create_access_token(subject=str(user.id), role=user.role.value)

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    async def refresh_access_token(self, raw_refresh_token: str) -> TokenResponse:
        """Validate raw refresh token, rotate session, and issue new access token."""
        hashed_token = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed_token)
        result = await self.db.execute(stmt)
        token_entity = result.scalar_one_or_none()

        if not token_entity:
            raise UnauthorizedException("Invalid refresh token.")

        if token_entity.is_revoked:
            raise UnauthorizedException("Refresh token has been revoked.")

        now = datetime.now(timezone.utc)
        if token_entity.expires_at.tzinfo is None:
            token_expires = token_entity.expires_at.replace(tzinfo=timezone.utc)
        else:
            token_expires = token_entity.expires_at

        if token_expires < now:
            raise UnauthorizedException("Refresh token has expired.")

        # Fetch user
        stmt_user = select(User).where(User.id == token_entity.user_id)
        res_user = await self.db.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user or not user.is_active:
            raise UnauthorizedException("User account is inactive or missing.")

        # Rotate Refresh Token
        token_entity.is_revoked = True
        new_raw_refresh = generate_opaque_token()
        new_hashed_refresh = hash_token(new_raw_refresh)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        new_refresh_entity = RefreshToken(
            user_id=user.id,
            token_hash=new_hashed_refresh,
            device_info=token_entity.device_info,
            ip_address=token_entity.ip_address,
            expires_at=new_expires_at,
            is_revoked=False,
        )
        self.db.add(new_refresh_entity)
        await self.db.commit()

        access_token = create_access_token(subject=str(user.id), role=user.role.value)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_raw_refresh,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    async def logout_user(self, raw_refresh_token: str) -> None:
        """Revoke active refresh token session."""
        hashed_token = hash_token(raw_refresh_token)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == hashed_token)
        result = await self.db.execute(stmt)
        token_entity = result.scalar_one_or_none()

        if token_entity:
            token_entity.is_revoked = True
            await self.db.commit()
            logger.info(f"Revoked refresh token for user {token_entity.user_id}")

    async def request_password_reset(self, email: str) -> Optional[str]:
        """Generate time-bound password reset token."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        reset_token = generate_opaque_token()
        user.reset_token = hash_token(reset_token)
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )

        await self.db.commit()
        logger.info(f"Generated password reset token for {user.email}")
        return reset_token

    async def reset_password(self, raw_token: str, new_password: str) -> User:
        """Reset user password using valid token."""
        hashed_reset_token = hash_token(raw_token)
        stmt = select(User).where(User.reset_token == hashed_reset_token)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValidationException("Invalid or expired password reset token.")

        now = datetime.now(timezone.utc)
        if user.reset_token_expires_at is None:
            raise ValidationException("Reset token has expired.")

        expires_at = user.reset_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            raise ValidationException("Password reset token has expired.")

        user.hashed_password = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"Password reset successfully for user: {user.email}")
        return user

    async def authenticate_github_oauth(self, code: str) -> TokenResponse:
        """Exchange GitHub OAuth code for access token and create/login user."""
        async with httpx.AsyncClient() as client:
            token_url = "https://github.com/login/oauth/authorize"
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
            )
            if token_resp.status_code != 200 or "access_token" not in token_resp.json():
                raise UnauthorizedException("Failed to exchange code with GitHub.")

            gh_access_token = token_resp.json()["access_token"]

            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {gh_access_token}"},
            )
            if user_resp.status_code != 200:
                raise UnauthorizedException("Failed to fetch user profile from GitHub.")

            gh_user = user_resp.json()
            gh_id = str(gh_user["id"])
            email = gh_user.get("email")

            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {gh_access_token}"},
                )
                if emails_resp.status_code == 200:
                    for em in emails_resp.json():
                        if em.get("primary") and em.get("verified"):
                            email = em["email"]
                            break

            if not email:
                email = f"gh_{gh_id}@devtrack.ai"

        # Check existing user by oauth_id or email
        stmt = select(User).where((User.oauth_id == gh_id) | (User.email == email))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                email=email.lower(),
                full_name=gh_user.get("name") or gh_user.get("login") or "GitHub User",
                avatar_url=gh_user.get("avatar_url"),
                role=UserRole.MEMBER,
                is_active=True,
                is_verified=True,
                oauth_provider=OAuthProvider.GITHUB,
                oauth_id=gh_id,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return await self._create_tokens_for_user(user, device_info="GitHub OAuth")

    async def _create_tokens_for_user(self, user: User, device_info: str = "OAuth Login") -> TokenResponse:
        raw_refresh_token = generate_opaque_token()
        hashed_refresh = hash_token(raw_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        refresh_entity = RefreshToken(
            user_id=user.id,
            token_hash=hashed_refresh,
            device_info=device_info,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(refresh_entity)
        await self.db.commit()

        access_token = create_access_token(subject=str(user.id), role=user.role.value)

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )
