from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.report import ReportModel
from app.services.score_combination import combine_scores


class ReportRepository:

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    async def get_by_user_id(
        self,
        user_id: int,
    ) -> ReportModel | None:

        result = await self.db.execute(
            select(ReportModel).where(
                ReportModel.user_id == user_id
            )
        )

        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        user_id: int,
        date: datetime,
        survey_score: Decimal | None = None,
        statement_score: Decimal | None = None,
        telegram_score: Decimal | None = None,
        comment_from_ai: str | None = None,
    ) -> ReportModel:
        """Обновляет ТОЛЬКО переданные ветки, остальные оставляет как есть.

        Ветки считаются в разное время и разными эндпоинтами (анкета,
        выписка, telegram), поэтому перезаписывать отчёт целиком нельзя:
        загрузка выписки не должна стирать уже посчитанную анкету.
        """
        report = await self.get_by_user_id(user_id)

        if report is None:
            report = ReportModel(
                user_id=user_id,
                score=Decimal("0"),
                date=date,
            )
            self.db.add(report)

        if survey_score is not None:
            report.survey_score = survey_score

        if statement_score is not None:
            report.statement_score = statement_score

        if telegram_score is not None:
            report.telegram_score = telegram_score

        if comment_from_ai is not None:
            report.comment_from_ai = comment_from_ai

        combined = combine_scores(
            report.survey_score,
            report.statement_score,
            report.telegram_score,
        )

        if combined is not None:
            report.score = combined

        report.date = date

        await self.db.flush()

        return report
