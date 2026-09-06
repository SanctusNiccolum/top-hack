from app.db.repositories.user import UserRepository
from app.db.models.user import UserModel
from backend.app.security.password_hash import hash_password
from backend.app.api.schemas.account import AccountUpdateRequest
from app.db.repositories.subscription import UserSubscriptionRepository


class UpdateAccountUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: UserSubscriptionRepository,
    ):
        self.user_repository = user_repository
        self.subscription_repository = subscription_repository

    async def execute(
        self,
        user_id: int,
        data: AccountUpdateRequest,
    ) -> UserModel:

        user = await self.user_repository.get_by_id(
            user_id
        )

        if user is None:
            raise ValueError(
                "Пользователь не найден"
            )

        update_data = data.model_dump(
            exclude_unset=True
        )

        subscriptions = update_data.pop(
            "subscriptions",
            None,
        )

        password = update_data.pop(
            "password",
            None,
        )

        if password is not None:
            update_data["password"] = hash_password(
                password
            )

        user = await self.user_repository.update(
            user,
            update_data,
        )

        if subscriptions is not None:

            await self.subscription_repository.replace(
                user_id=user_id,
                subscriptions=[
                    subscription.value
                    for subscription in subscriptions
                ],
            )

        return user
    

class GetAccountUseCase:

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: UserSubscriptionRepository,
    ):
        self.user_repository = user_repository
        self.subscription_repository = subscription_repository

    async def execute(
        self,
        user_id: int,
    ) -> tuple[UserModel, list[str]]:

        user = await self.user_repository.get_by_id(
            user_id
        )

        if user is None:
            raise ValueError(
                "Пользователь не найден"
            )

        subscriptions = (
            await self.subscription_repository.get_by_user(
                user_id
            )
        )

        return user, subscriptions
    
