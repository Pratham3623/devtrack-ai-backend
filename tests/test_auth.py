import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.models.enums import UserRole
from app.domain.models.user import User


# ==========================================
# 1. UNIT TESTS: CRYPTOGRAPHY & JWT TOKENS
# ==========================================

def test_password_hashing_and_verification():
    raw_pass = "SecurePass123!"
    hashed = hash_password(raw_pass)

    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_create_and_decode_jwt_access_token():
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    role = UserRole.ADMIN.value

    token = create_access_token(subject=user_id, role=role)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded["sub"] == user_id
    assert decoded["role"] == role
    assert decoded["type"] == "access"


# ==========================================
# 2. INTEGRATION TESTS: AUTH ENDPOINTS
# ==========================================

@pytest.mark.asyncio
async def test_user_registration_success(async_client: AsyncClient):
    payload = {
        "email": "alex@devtrack.ai",
        "password": "Password123!",
        "full_name": "Alex Rivera",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alex@devtrack.ai"
    assert "verification_token" in data


@pytest.mark.asyncio
async def test_duplicate_email_registration_fails(async_client: AsyncClient):
    payload = {
        "email": "duplicate@devtrack.ai",
        "password": "Password123!",
        "full_name": "Duplicate User",
    }
    resp1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 422
    assert "already exists" in resp2.json()["error"]["message"]


@pytest.mark.asyncio
async def test_email_verification_flow(async_client: AsyncClient):
    # 1. Register
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "verify@devtrack.ai", "password": "Password123!", "full_name": "Verify User"},
    )
    verif_token = reg_resp.json()["verification_token"]

    # 2. Verify Email
    verif_resp = await async_client.post(
        "/api/v1/auth/verify-email",
        json={"token": verif_token},
    )
    assert verif_resp.status_code == 200
    assert "verified successfully" in verif_resp.json()["message"]


@pytest.mark.asyncio
async def test_user_login_success(async_client: AsyncClient):
    # Register user
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "login@devtrack.ai", "password": "Password123!", "full_name": "Login User"},
    )

    # Login
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "login@devtrack.ai", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["user"]["email"] == "login@devtrack.ai"


@pytest.mark.asyncio
async def test_token_refresh_and_session_rotation(async_client: AsyncClient):
    # Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@devtrack.ai", "password": "Password123!", "full_name": "Refresh User"},
    )
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@devtrack.ai", "password": "Password123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Refresh Access Token
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert "access_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_token  # Session rotated

    # Attempt reusing old refresh token (should fail)
    reuse_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(async_client: AsyncClient):
    # Register & Login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "logout@devtrack.ai", "password": "Password123!", "full_name": "Logout User"},
    )
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@devtrack.ai", "password": "Password123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200

    # Refresh after logout should fail
    refresh_resp = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_forgot_password_and_reset_flow(async_client: AsyncClient):
    # Register
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "reset@devtrack.ai", "password": "OldPassword123!", "full_name": "Reset User"},
    )

    # Request Forgot Password
    forgot_resp = await async_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@devtrack.ai"},
    )
    assert forgot_resp.status_code == 200
    reset_token = forgot_resp.json()["reset_token"]

    # Complete Password Reset
    reset_resp = await async_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_token, "new_password": "NewSuperPassword123!"},
    )
    assert reset_resp.status_code == 200

    # Login with new password
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "reset@devtrack.ai", "password": "NewSuperPassword123!"},
    )
    assert login_resp.status_code == 200


# ==========================================
# 3. INTEGRATION TESTS: RBAC & PROTECTED ROUTES
# ==========================================

@pytest.mark.asyncio
async def test_rbac_access_control_member_vs_admin(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Register normal MEMBER user
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "member@devtrack.ai", "password": "Password123!", "full_name": "Member User"},
    )
    login_member = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "member@devtrack.ai", "password": "Password123!"},
    )
    member_token = login_member.json()["access_token"]

    # Member accesses /me (Success)
    me_resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "member@devtrack.ai"

    # Member accesses /admin-only (Fails with 403 Forbidden)
    admin_forbidden = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert admin_forbidden.status_code == 403

    # 2. Register and elevate ADMIN user directly in DB
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "admin@devtrack.ai", "password": "Password123!", "full_name": "Admin User"},
    )
    from sqlalchemy import select
    res = await db_session.execute(select(User).where(User.email == "admin@devtrack.ai"))
    admin_user = res.scalar_one()
    admin_user.role = UserRole.ADMIN
    await db_session.commit()

    login_admin = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@devtrack.ai", "password": "Password123!"},
    )
    admin_token = login_admin.json()["access_token"]

    # Admin accesses /admin-only (Success 200 OK)
    admin_success = await async_client.get(
        "/api/v1/auth/admin-only",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_success.status_code == 200
    assert "Access granted" in admin_success.json()["message"]
