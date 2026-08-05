from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: str
    totp_enabled: bool
    client_ids: list[str] = []

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str | None = None
    token_type: str = "bearer"
    user: UserOut | None = None
    challenge_token: str | None = None
    requires_2fa: bool = False
    requires_2fa_setup: bool = False


class TwoFactorChallengeRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=32)


class TwoFactorSetupRequest(BaseModel):
    challenge_token: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_code_data_url: str


class TwoFactorLoginResponse(LoginResponse):
    recovery_codes: list[str] | None = None


class UserAdminOut(UserOut):
    is_active: bool


class UserAccessUpdate(BaseModel):
    role: Literal["admin", "operator"]
    is_active: bool
    client_ids: list[str] = []
