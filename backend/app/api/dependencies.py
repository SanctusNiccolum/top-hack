from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.password_hash import hash_session_token
from app.db.session import get_session
from app.db.models.user import UserModel
from app.db.repositories.session import SessionRepository
from app.db.repositories.subscription import UserSubscriptionRepository
from app.db.repositories.user import UserRepository
from app.services.account import AccountService
from app.services.auth import AuthService
from app.db.repositories.report import ReportRepository
from app.services.report import ReportService


security = HTTPBearer()


async def get_user_repository(
    db: AsyncSession = Depends(get_session),
) -> UserRepository:

    return UserRepository(db)


async def get_session_repository(
    db: AsyncSession = Depends(get_session),
) -> SessionRepository:

    return SessionRepository(db)


async def get_subscription_repository(
    db: AsyncSession = Depends(get_session),
) -> UserSubscriptionRepository:

    return UserSubscriptionRepository(db)


async def get_auth_service(
    user_repository: UserRepository = Depends(
        get_user_repository
    ),
    session_repository: SessionRepository = Depends(
        get_session_repository
    ),
) -> AuthService:

    return AuthService(
        user_repository=user_repository,
        session_repository=session_repository,
    )


async def get_account_service(
    user_repository: UserRepository = Depends(
        get_user_repository
    ),
    subscription_repository: UserSubscriptionRepository = Depends(
        get_subscription_repository
    ),
) -> AccountService:

    return AccountService(
        user_repository=user_repository,
        subscription_repository=subscription_repository,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
    db: AsyncSession = Depends(get_session),
) -> UserModel:

    raw_token = credentials.credentials

    token_hash = hash_session_token(
        raw_token
    )

    session_repository = SessionRepository(db)

    session = await session_repository.get_by_token_hash(
        token_hash
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия",
        )

    now = datetime.now(timezone.utc)

    if session.expires_at <= now:
        await session_repository.revoke(session)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла",
        )

    user_repository = UserRepository(db)

    user = await user_repository.get_by_id(
        session.user_id
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    return user

async def get_report_service(
    db: AsyncSession = Depends(get_session),
) -> ReportService:

    return ReportService(
        report_repository=ReportRepository(db),
        subscription_repository=UserSubscriptionRepository(db),
    )