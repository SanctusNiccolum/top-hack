from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    monthly_payments: Decimal = Field(
        default=Decimal("0"),
        ge=0,
    )

    npd_certificate_attached: bool = False


class ReportResponse(BaseModel):
    user_id: int
    # Итоговый скор — взвешенная комбинация веток ниже.
    score: Decimal
    date: datetime
    comment_from_ai: str | None

    # Разбивка по веткам (NULL — ветка ещё не считалась). Нужна фронту,
    # чтобы показать, из чего сложился итог.
    survey_score: Decimal | None = None
    statement_score: Decimal | None = None
    # Telegram — поправка −25..+25, а не балл: она прибавляется к
    # среднему двух веток выше.
    telegram_delta: Decimal | None = None
    telegram_risk: str | None = None
    telegram_comment: str | None = None
    # [{category, contribution, evidence_count}] — из чего сложилась поправка
    telegram_factors: list | None = None