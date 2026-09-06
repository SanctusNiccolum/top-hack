from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.security.password_hash import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.repositories.session import SessionRepository
from app.db.repositories.user import UserRepository


class AuthService:

    SESSION_LIFETIME = timedelta(days=30)

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: SessionRepository,
    ):
        self.user_repository = user_repository
        self.session_repository = session_repository

    async def register(
        self,
        phone_number: str,
        password: str,
    ):
        existing_user = await self.user_repository.get_by_phone(
            phone_number
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким номером уже существует",
            )

        password_hash = hash_password(password)

        user = await self.user_repository.create(
            phone_number=phone_number,
            password_hash=password_hash,
        )

        session_token = generate_session_token()

        token_hash = hash_session_token(
            session_token
        )

        expires_at = (
            datetime.now(timezone.utc)
            + self.SESSION_LIFETIME
        )

        await self.session_repository.create(
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        return user, session_token

    async def login(
        self,
        phone_number: str,
        password: str,
    ):
        user = await self.user_repository.get_by_phone(
            phone_number
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный номер телефона или пароль",
            )

        password_valid = verify_password(
            password,
            user.password,
        )

        if not password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный номер телефона или пароль",
            )

        session_token = generate_session_token()

        token_hash = hash_session_token(
            session_token
        )

        expires_at = (
            datetime.now(timezone.utc)
            + self.SESSION_LIFETIME
        )

        await self.session_repository.create(
            user_id=user.user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        return user, session_token