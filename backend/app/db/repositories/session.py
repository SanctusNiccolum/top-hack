from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import AccountSessionModel


class SessionRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> AccountSessionModel:

        session = AccountSessionModel(
            session_id=str(uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )

        self.db.add(session)

        await self.db.flush()

        return session

    async def get_by_token_hash(
        self,
        token_hash: str,
    ) -> AccountSessionModel | None:

        result = await self.db.execute(
            select(AccountSessionModel).where(
                AccountSessionModel.token_hash == token_hash,
                AccountSessionModel.revoked.is_(False),
            )
        )

        return result.scalar_one_or_none()

    async def revoke(
        self,
        session: AccountSessionModel,
    ) -> None:

        session.revoked = True

        await self.db.flush()