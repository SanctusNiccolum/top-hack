from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserSubscriptionModel


class UserSubscriptionRepository:

    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session = session

    async def get_by_user(
        self,
        user_id: int,
    ) -> list[str]:

        result = await self.session.execute(
            select(
                UserSubscriptionModel.subscription_type
            )
            .where(
                UserSubscriptionModel.user_id == user_id
            )
        )

        return list(result.scalars().all())

    async def replace(
        self,
        user_id: int,
        subscriptions: list[str],
    ) -> None:

        await self.session.execute(
            delete(UserSubscriptionModel)
            .where(
                UserSubscriptionModel.user_id == user_id
            )
        )

        for subscription in subscriptions:
            self.session.add(
                UserSubscriptionModel(
                    user_id=user_id,
                    subscription_type=subscription,
                )
            )

        await self.session.flush()