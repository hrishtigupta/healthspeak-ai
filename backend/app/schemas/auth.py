"""Login / logout shapes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import PASSWORD_MAX_LENGTH, UserOut


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Email address or phone number, matching the existing login form.
    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserOut
