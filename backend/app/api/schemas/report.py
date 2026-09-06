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
    score: Decimal
    date: datetime
    comment_from_ai: str | None