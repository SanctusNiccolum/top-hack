import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.models.user import UserModel
from app.db.repositories.report import ReportRepository
from app.db.session import get_session
from app.statement_scoring.runner import (
    StatementScoringError,
    score_statement,
)
from app.statement_scoring.schemas import StatementUploadResponse

router = APIRouter(
    prefix="/statement",
    tags=["Statement"],
)

# Выписки просто лежат на диске (в контейнере — на volume), без S3/minio:
# для объёмов проекта этого достаточно.
UPLOAD_DIR = Path(os.environ.get("STATEMENT_UPLOAD_DIR", "/app/uploads"))

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _safe_name(filename: str | None) -> str:
    """Имя файла приходит от клиента — берём из него только безобидную
    часть, чтобы не словить путь вида ../../etc/passwd.
    """
    base = Path(filename or "statement.pdf").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return cleaned[:80] or "statement.pdf"


@router.post(
    "/upload",
    response_model=StatementUploadResponse,
)
async def upload_statement(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл пустой",
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл больше 20 МБ",
        )

    # Проверяем сигнатуру, а не расширение: расширение клиент может
    # написать любое, а pdfplumber всё равно упадёт на не-PDF.
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Это не PDF-файл",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    stored_path = (
        UPLOAD_DIR
        / f"{current_user.user_id}_{stamp}_{_safe_name(file.filename)}"
    )
    stored_path.write_bytes(content)

    try:
        result = await score_statement(stored_path)
    except StatementScoringError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Не удалось разобрать выписку: {exc}",
        )

    report_repository = ReportRepository(db)

    await report_repository.create_or_update(
        user_id=current_user.user_id,
        statement_score=Decimal(str(result["final_score"])),
        comment_from_ai=result["ai_comment"],
        date=datetime.now(timezone.utc),
    )

    await db.commit()

    return StatementUploadResponse(
        statement_score=Decimal(str(result["final_score"])),
        statement_score_raw=Decimal(str(result["raw_score"])),
        ai_comment=result["ai_comment"],
        stored_file=stored_path.name,
    )
