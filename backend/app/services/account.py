# from app.core.security import hash_password
from fastapi import HTTPException, status
from app.db.models.user import UserModel
from app.db.repositories.subscription import UserSubscriptionRepository
from app.db.repositories.user import UserRepository


class AccountService:

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: UserSubscriptionRepository,
    ):
        self.user_repository = user_repository
        self.subscription_repository = subscription_repository

    async def update_account(
        self,
        user: UserModel,
        data,
    ) -> UserModel:

        update_data = data.model_dump(
            exclude_unset=True
        )

        subscriptions = update_data.pop(
            "subscriptions",
            None,
        )

        if update_data:
            await self.user_repository.update(
                user=user,
                data=update_data,
            )

        if subscriptions is not None:
            await self.subscription_repository.replace(
                user_id=user.user_id,
                subscriptions=[
                    item.value
                    for item in subscriptions
                ],
            )

        return user

    async def get_account(
        self,
        user_id: int,
    ):
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
    
    async def complete_account(
        self,
        user: UserModel,
    ) -> UserModel:

        if user.is_ended:
            return user

        required_fields = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "age": user.age,
            "city": user.city,
            "family_status": user.family_status,
            "student_status": user.student_status,
            "income_source": user.income_source,
            "income_frequency": user.income_frequency,
            "monthly_income": user.monthly_income,
            "credit_history": user.credit_history,
            "payment_overdue": user.payment_overdue,
            "payment_method": user.payment_method,
        }

        missing_fields = [
            field
            for field, value in required_fields.items()
            if value is None
        ]

        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Профиль заполнен не полностью",
                    "missing_fields": missing_fields,
                },
            )

        user.is_ended = True

        return user