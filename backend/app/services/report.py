from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status

from app.db.models.user import UserModel
from app.db.repositories.report import ReportRepository
from app.db.repositories.subscription import UserSubscriptionRepository
from app.api.schemas.report import ReportCreateRequest
from app.services.scoring import ScoringService


class ReportService:

    def __init__(
        self,
        report_repository: ReportRepository,
        subscription_repository: UserSubscriptionRepository,
    ):
        self.report_repository = report_repository
        self.subscription_repository = (
            subscription_repository
        )

    async def create_report(
        self,
        user: UserModel,
        data: ReportCreateRequest,
    ):

        # Нельзя строить отчёт по незавершённой анкете.
        if not user.is_ended:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Анкета ещё не завершена",
            )

        subscriptions = (
            await self.subscription_repository.get_by_user(
                user.user_id
            )
        )

        try:
            score = ScoringService.calculate(
                user=user,
                subscriptions=subscriptions,
                monthly_payments=data.monthly_payments,
                npd_certificate_attached=(
                    data.npd_certificate_attached
                ),
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        report = (
            await self.report_repository.create_or_update(
                user_id=user.user_id,
                survey_score=score,
                date=datetime.now(timezone.utc),
            )
        )

        return report