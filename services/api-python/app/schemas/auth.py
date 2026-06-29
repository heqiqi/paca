"""Auth request/response schemas."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)
    remember_me: bool = Field(default=False)


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
