from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.report import ReportModel


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

    async def create(
        self,
        user_id: int,
        score,
        date: datetime,
    ) -> ReportModel:

        report = ReportModel(
            user_id=user_id,
            score=score,
            date=date,
            comment_from_ai=None,
        )

        self.db.add(report)

        await self.db.flush()

        return report

    async def update(
        self,
        report: ReportModel,
        score,
        date: datetime,
    ) -> ReportModel:

        report.score = score
        report.date = date

        # Пока AI-комментария нет.
        # При следующем пересчёте старый комментарий
        # не сохраняем.
        report.comment_from_ai = None

        await self.db.flush()

        return report

    async def create_or_update(
        self,
        user_id: int,
        score,
        date: datetime,
    ) -> ReportModel:

        report = await self.get_by_user_id(
            user_id
        )

        if report is None:
            return await self.create(
                user_id=user_id,
                score=score,
                date=date,
            )

        return await self.update(
            report=report,
            score=score,
            date=date,
        )