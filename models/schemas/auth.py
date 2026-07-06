import uuid

from pydantic import BaseModel, ConfigDict


class SignupRequest(BaseModel):
    # Both mandatory for direct password signup — OAuth signup is exempt (a provider only
    # ever hands back an email; phone number and password can be added afterward via
    # link_phone / set_password).
    email: str
    phone_number: str
    password: str


class LoginRequest(BaseModel):
    identifier: str  # email or phone_number
    password: str


class LinkEmailRequest(BaseModel):
    email: str


class LinkPhoneRequest(BaseModel):
    phone_number: str


class SetPasswordRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    phone_number: str | None
    is_alpha_tester: bool
    is_guest: bool
    has_password: bool
