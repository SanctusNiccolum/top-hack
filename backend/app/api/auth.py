from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.api.schemas.auth import (
    AuthResponse,
    LoginRequest,
)
from app.services.auth import AuthService
from app.api.dependencies import get_auth_service


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


# @router.post(
#     "/register",
#     response_model=AuthResponse,
# )
# async def register(
#     data: RegisterRequest,
#     service: AuthService = Depends(
#         get_auth_service
#     ),
#     db: AsyncSession = Depends(get_db),
# ):
#     user, session_token = await service.register(
#         phone_number=data.phone_number,
#         password=data.password,
#     )

#     await db.commit()

#     return AuthResponse(
#         user_id=user.user_id,
#         session_token=session_token,
#         is_ended=user.is_ended,
#     )


@router.post(
    "/login",
    response_model=AuthResponse,
)
async def login(
    data: LoginRequest,
    service: AuthService = Depends(
        get_auth_service
    ),
    db: AsyncSession = Depends(get_session),
):
    user, session_token = await service.login(
        phone_number=data.phone_number,
        password=data.password,
    )

    await db.commit()

    return AuthResponse(
        user_id=user.user_id,
        session_token=session_token,
        is_ended=user.is_ended,
    )