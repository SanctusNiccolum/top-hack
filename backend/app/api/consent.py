from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.api.schemas.consent import (
    ConsentGrantRequest,
    ConsentResponse,
)
from app.db.models.consent import ConsentModel
from app.db.models.user import UserModel
from app.db.session import get_session

router = APIRouter(
    prefix="/consent",
    tags=["Consent"],
)

ALLOWED_TYPES = {
    "telegram_analysis",
    "bank_statement",
    "personal_data",
}


@router.post(
    "",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_consent(
    data: ConsentGrantRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    if data.consent_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Неизвестный тип согласия. Допустимые: "
                + ", ".join(sorted(ALLOWED_TYPES))
            ),
        )

    consent = ConsentModel(
        user_id=current_user.user_id,
        consent_type=data.consent_type,
        granted_at=datetime.now(timezone.utc),
        document_version=data.document_version,
        source_ip=request.client.host if request.client else None,
    )

    db.add(consent)
    await db.commit()
    await db.refresh(consent)

    return ConsentResponse.model_validate(consent)


@router.get(
    "",
    response_model=list[ConsentResponse],
)
async def list_consents(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(
        select(ConsentModel)
        .where(ConsentModel.user_id == current_user.user_id)
        .order_by(ConsentModel.granted_at.desc())
    )

    return [
        ConsentResponse.model_validate(row)
        for row in result.scalars().all()
    ]


@router.delete(
    "/{consent_type}",
    response_model=ConsentResponse,
)
async def revoke_consent(
    consent_type: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Отзыв согласия. Запись не удаляется — проставляется revoked_at,
    чтобы история осталась предъявляемой."""
    result = await db.execute(
        select(ConsentModel)
        .where(
            ConsentModel.user_id == current_user.user_id,
            ConsentModel.consent_type == consent_type,
            ConsentModel.revoked_at.is_(None),
        )
        .order_by(ConsentModel.granted_at.desc())
    )

    consent = result.scalars().first()

    if consent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Действующего согласия такого типа не найдено",
        )

    consent.revoked_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(consent)

    return ConsentResponse.model_validate(consent)
