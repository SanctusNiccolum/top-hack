from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserModel


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        phone_number: str,
        password_hash: str,
    ) -> UserModel:

        user = UserModel(
            phone_number=phone_number,
            password=password_hash,
            is_ended=False,
        )

        self.db.add(user)

        await self.db.flush()

        return user

    async def get_by_id(
        self,
        user_id: int,
    ) -> UserModel | None:

        result = await self.db.execute(
            select(UserModel).where(
                UserModel.user_id == user_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_phone(
        self,
        phone_number: str,
    ) -> UserModel | None:

        result = await self.db.execute(
            select(UserModel).where(
                UserModel.phone_number == phone_number
            )
        )

        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        email: str,
    ) -> UserModel | None:

        result = await self.db.execute(
            select(UserModel).where(
                UserModel.email == email
            )
        )

        return result.scalar_one_or_none()

    async def update(
        self,
        user: UserModel,
        data: dict,
    ) -> UserModel:

        for field, value in data.items():
            setattr(user, field, value)

        await self.db.flush()

        return user