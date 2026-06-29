"""Authentication endpoints: login, refresh, logout."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_family_id,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_token_cookies(response: Response, access_token: str, refresh_token: str, refresh_ttl_seconds: int):
    """Set HttpOnly cookies for access and refresh tokens."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_access_ttl_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        path="/api/v1/auth/refresh",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=refresh_ttl_seconds,
    )


def _clear_cookies(response: Response):
    """Clear auth cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")


@router.post("/login", response_model=MessageResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate user and set token cookies."""
    result = await db.execute(
        select(User).where(User.username == body.username, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Generate tokens
    family_id = generate_family_id()
    access_token = create_access_token(user.id)
    refresh_token, refresh_ttl = create_refresh_token(user.id, family_id, body.remember_me)

    _set_token_cookies(response, access_token, refresh_token, int(refresh_ttl.total_seconds()))
    return MessageResponse(message="logged in")


@router.post("/refresh", response_model=MessageResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh cookie."""
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    payload = decode_token(refresh_cookie)
    if payload is None or payload.get("kind") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        from uuid import UUID
        user_id = UUID(payload["sub"])
        family_id = payload["family_id"]
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Verify user still exists
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Issue new token pair with same family
    access_token = create_access_token(user.id)
    refresh_token, refresh_ttl = create_refresh_token(user.id, family_id, remember_me=True)

    _set_token_cookies(response, access_token, refresh_token, int(refresh_ttl.total_seconds()))
    return MessageResponse(message="token refreshed")


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, current_user: CurrentUser = Depends(get_current_user)):
    """Logout and clear cookies."""
    _clear_cookies(response)
    return MessageResponse(message="logged out")
