from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_account_service,
    get_auth_service,
    get_current_user,
)
from app.db.session import get_session
from app.db.models.user import UserModel
from app.api.schemas.account import (
    AccountResponse,
    AccountUpdateRequest,
)
from app.api.schemas.auth import (
    AuthResponse,
    RegisterRequest,
)
from app.services.account import AccountService
from app.services.auth import AuthService


router = APIRouter(
    prefix="/account",
    tags=["Account"],
)


@router.post(
    "",
    response_model=AuthResponse,
)
async def register(
    data: RegisterRequest,
    service: AuthService = Depends(
        get_auth_service
    ),
    db: AsyncSession = Depends(get_session),
):
    user, session_token = await service.register(
        phone_number=data.phone_number,
        password=data.password,
    )

    await db.commit()

    return AuthResponse(
        user_id=user.user_id,
        session_token=session_token,
        is_ended=user.is_ended,
    )

@router.put(
    "",
    response_model=AccountResponse,
)
async def update_account(
    data: AccountUpdateRequest,
    current_user: UserModel = Depends(
        get_current_user
    ),
    service: AccountService = Depends(
        get_account_service
    ),
    db: AsyncSession = Depends(get_session),
):
    user = await service.update_account(
        user=current_user,
        data=data,
    )

    await db.commit()

    subscriptions = (
        await service.subscription_repository.get_by_user(
            user.user_id
        )
    )

    return AccountResponse(
        **user.__dict__,
        subscriptions=subscriptions,
    )

@router.get(
    "",
    response_model=AccountResponse,
)
async def get_account(
    current_user: UserModel = Depends(
        get_current_user
    ),
    service: AccountService = Depends(
        get_account_service
    ),
):
    user, subscriptions = (
        await service.get_account(
            current_user.user_id
        )
    )

    return AccountResponse(
        **user.__dict__,
        subscriptions=subscriptions,
    )

@router.post(
    "/complete",
    response_model=AccountResponse,
)
async def complete_account(
    current_user: UserModel = Depends(
        get_current_user
    ),
    service: AccountService = Depends(
        get_account_service
    ),
    db: AsyncSession = Depends(get_session),
):
    user = await service.complete_account(
        current_user
    )

    await db.commit()

    user, subscriptions = (
        await service.get_account(
            user.user_id
        )
    )

    return AccountResponse(
        **user.__dict__,
        subscriptions=subscriptions,
    )