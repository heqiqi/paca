"""Security utilities: JWT tokens, password hashing, encryption."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: UUID, extra_claims: dict[str, Any] | None = None) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "kind": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(subject: UUID, family_id: str, remember_me: bool = False) -> tuple[str, timedelta]:
    """Create a JWT refresh token with family tracking for rotation.

    Returns tuple of (token_string, effective_ttl).
    """
    if remember_me:
        ttl = timedelta(days=settings.jwt_refresh_ttl_days)
    else:
        ttl = timedelta(hours=settings.jwt_refresh_session_ttl_hours)

    expire = datetime.now(UTC) + ttl
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "kind": "refresh",
        "family_id": family_id,
    }
    token = jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)
    return token, ttl


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_family_id() -> str:
    """Generate a unique family ID for refresh token rotation."""
    return secrets.token_hex(16)


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of an API key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return secrets.token_hex(32)
