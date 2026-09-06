from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone_number: str = Field(
        min_length=5,
        max_length=20,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    phone_number: str = Field(
        min_length=5,
        max_length=20,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class AuthResponse(BaseModel):
    user_id: int
    session_token: str
    is_ended: bool