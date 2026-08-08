from typing import Any, Dict
from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_role
from app.core.config import settings
from app.db.session import get_db
from app.domain.models.enums import UserRole
from app.domain.models.user import User
from app.domain.schemas.auth import (
    ForgotPasswordRequest,
    OAuthCallbackRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserVerifyEmailRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Register New User Account",
)
async def register(
    dto: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = AuthService(db)
    user, verif_token = await service.register_user(dto)
    return {
        "message": "User registered successfully. Please verify your email.",
        "user_id": str(user.id),
        "email": user.email,
        "verification_token": verif_token,  # Included for dev testing
    }


@router.post(
    "/verify-email",
    response_model=Dict[str, str],
    status_code=status.HTTP_200_OK,
    summary="Verify User Email",
)
async def verify_email(
    dto: UserVerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = AuthService(db)
    user = await service.verify_email(dto.token)
    return {"message": f"Email address '{user.email}' verified successfully."}


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login (Password Authentication)",
)
async def login(
    dto: UserLoginRequest,
    request: Request,
    user_agent: str = Header(None, alias="User-Agent"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)
    client_ip = request.client.host if request.client else None
    return await service.login_user(
        email=dto.email,
        password=dto.password,
        device_info=user_agent,
        ip_address=client_ip,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate Refresh Token & Issue Access Token",
)
async def refresh_token(
    dto: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)
    return await service.refresh_access_token(dto.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout User & Revoke Session Token",
)
async def logout(
    dto: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = AuthService(db)
    await service.logout_user(dto.refresh_token)
    return {"message": "Logged out successfully."}


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request Password Reset Token",
)
async def forgot_password(
    dto: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = AuthService(db)
    reset_token = await service.request_password_reset(dto.email)
    return {
        "message": "If the email is registered, a password reset link has been issued.",
        "reset_token": reset_token,  # Included for dev testing
    }


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Confirm Password Reset",
)
async def reset_password(
    dto: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, str]:
    service = AuthService(db)
    user = await service.reset_password(dto.token, dto.new_password)
    return {"message": f"Password reset successfully for '{user.email}'."}


@router.get(
    "/oauth/github/url",
    summary="Get GitHub OAuth Authorization Redirect URL",
)
async def get_github_oauth_url() -> Dict[str, str]:
    redirect_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={settings.GITHUB_CLIENT_ID}&scope=user:email"
    )
    return {"url": redirect_url}


@router.post(
    "/oauth/github/callback",
    response_model=TokenResponse,
    summary="GitHub OAuth Callback Exchange",
)
async def github_oauth_callback(
    dto: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)
    return await service.authenticate_github_oauth(dto.code)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current Authenticated User Profile",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get(
    "/admin-only",
    summary="RBAC Demonstration: Admin Only Route",
)
async def admin_only_endpoint(
    current_user: User = Depends(require_role([UserRole.ADMIN])),
) -> Dict[str, str]:
    return {"message": f"Welcome Admin {current_user.full_name}! Access granted."}
