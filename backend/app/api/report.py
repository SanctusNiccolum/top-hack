from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_report_service,
)
from app.db.session import get_session
from app.db.models.user import UserModel
from app.api.schemas.report import (
    ReportCreateRequest,
    ReportResponse,
)
from app.services.report import ReportService


router = APIRouter(
    prefix="/report",
    tags=["Report"],
)


@router.post(
    "",
    response_model=ReportResponse,
)
async def create_report(
    data: ReportCreateRequest,
    current_user: UserModel = Depends(
        get_current_user
    ),
    service: ReportService = Depends(
        get_report_service
    ),
    db: AsyncSession = Depends(get_session),
):
    report = await service.create_report(
        user=current_user,
        data=data,
    )

    await db.commit()

    return ReportResponse(
        user_id=report.user_id,
        score=report.score,
        date=report.date,
        comment_from_ai=report.comment_from_ai,
        survey_score=report.survey_score,
        statement_score=report.statement_score,
        telegram_delta=report.telegram_delta,
        telegram_risk=report.telegram_risk,
        telegram_comment=report.telegram_comment,
        telegram_factors=report.telegram_factors,
    )