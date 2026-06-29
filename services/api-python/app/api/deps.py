"""FastAPI dependencies for authentication and authorization."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token, hash_api_key
from app.models.api_key import APIKey
from app.models.user import User
from sqlalchemy import select


class CurrentUser:
    """Authenticated user context."""

    def __init__(self, user_id: UUID, is_api_key: bool = False, agent_id: UUID | None = None):
        self.user_id = user_id
        self.is_api_key = is_api_key
        self.agent_id = agent_id


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-ID"),
) -> CurrentUser:
    """Extract and validate authentication from cookie, Bearer token, or API key."""
    token_str = ""
    is_api_key = False

    # 1. Cookie
    if access_token:
        token_str = access_token

    # 2. Authorization header
    if not token_str and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2:
            scheme = parts[0].lower()
            if scheme == "bearer":
                token_str = parts[1]
            elif scheme == "apikey":
                token_str = parts[1]
                is_api_key = True

    # 3. X-API-Key header
    if not token_str and x_api_key:
        token_str = x_api_key
        is_api_key = True

    if not token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication")

    # API key authentication
    if is_api_key:
        # Check static agent API key first
        if settings.agent_api_key and token_str == settings.agent_api_key:
            agent_id = None
            if x_agent_id:
                try:
                    agent_id = UUID(x_agent_id)
                except ValueError:
                    pass
            # Agent bot user has a fixed UUID
            agent_bot_user_id = UUID("00000000-0000-0000-0000-000000000002")
            return CurrentUser(user_id=agent_bot_user_id, is_api_key=True, agent_id=agent_id)

        # Database API key lookup
        key_hash = hash_api_key(token_str)
        result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        api_key = result.scalar_one_or_none()

        if api_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        if api_key.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has been revoked")
        if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has expired")

        # Update last_used_at
        api_key.last_used_at = datetime.now(UTC)
        await db.flush()

        return CurrentUser(user_id=api_key.user_id, is_api_key=True)

    # JWT authentication
    payload = decode_token(token_str)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("kind") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expected access token")

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    return CurrentUser(user_id=user_id, is_api_key=False)


async def get_optional_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-ID"),
) -> CurrentUser | None:
    """Like get_current_user but returns None instead of raising on missing auth."""
    try:
        return await get_current_user(request, db, access_token, authorization, x_api_key, x_agent_id)
    except HTTPException:
        return None


async def require_jwt_auth(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Reject API key auth — require JWT/cookie session."""
    if current_user.is_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires session authentication and does not accept API key credentials",
        )
    return current_user


async def get_user_from_db(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Load the full User ORM object for the authenticated user."""
    result = await db.execute(select(User).where(User.id == current_user.user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
