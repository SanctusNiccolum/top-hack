from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_user_repository
from app.db.models.consent import ConsentModel
from app.db.models.user import UserModel
from app.db.repositories.user import UserRepository
from app.db.session import get_session
from app.telegram_analysis import login as telegram_login
from app.telegram_analysis.runner import start_parser
from app.telegram_analysis.schemas import (
    TelegramAnalyzeRequest,
    TelegramAnalyzeResponse,
    TelegramChatsRequest,
    TelegramChatsResponse,
    TelegramChatStatus,
    TelegramStatusResponse,
    TelegramLoginCodeRequest,
    TelegramLoginPasswordRequest,
    TelegramLoginPhoneRequest,
    TelegramLoginPhoneResponse,
    TelegramLoginResult,
)

router = APIRouter(
    prefix="/telegram",
    tags=["Telegram"],
)


async def _link_tg_user_id(
    user_repository: UserRepository,
    db: AsyncSession,
    current_user: UserModel,
    telegram_user_id: int,
) -> None:
    # tg_user_id уникален на всю таблицу — если этот Telegram-аккаунт уже
    # привязан к ДРУГОМУ user_profile (частый случай при тестировании
    # разными тестовыми аккаунтами одним и тем же реальным Telegram),
    # словим конфликт здесь, а не отдадим голый 500.
    try:
        await user_repository.update(
            current_user,
            {"tg_user_id": telegram_user_id},
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Этот Telegram-аккаунт уже привязан к другому "
                "пользователю сервиса"
            ),
        )


@router.post(
    "/login/phone",
    response_model=TelegramLoginPhoneResponse,
)
async def login_phone(
    data: TelegramLoginPhoneRequest,
    current_user: UserModel = Depends(get_current_user),
):
    try:
        login_id = await telegram_login.start_login(data.phone_number)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return TelegramLoginPhoneResponse(login_id=login_id)


@router.post(
    "/login/code",
    response_model=TelegramLoginResult,
)
async def login_code(
    data: TelegramLoginCodeRequest,
    current_user: UserModel = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    try:
        result = await telegram_login.submit_code(
            data.login_id,
            data.code,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if result["status"] == "ok":
        await _link_tg_user_id(
            user_repository, db, current_user, result["telegram_user_id"]
        )

    return TelegramLoginResult(**result)


@router.post(
    "/login/password",
    response_model=TelegramLoginResult,
)
async def login_password(
    data: TelegramLoginPasswordRequest,
    current_user: UserModel = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_session),
):
    try:
        result = await telegram_login.submit_password(
            data.login_id,
            data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    await _link_tg_user_id(
        user_repository, db, current_user, result["telegram_user_id"]
    )

    return TelegramLoginResult(**result)


@router.post(
    "/chats",
    response_model=TelegramChatsResponse,
)
async def chats(
    data: TelegramChatsRequest,
    current_user: UserModel = Depends(get_current_user),
):
    try:
        chats_list = await telegram_login.list_chats(data.session_string)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return TelegramChatsResponse(chats=chats_list)


@router.get(
    "/status",
    response_model=TelegramStatusResponse,
)
async def analyze_status(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Прогресс разбора чатов текущего пользователя.

    Читает таблицы, которые пишет telegram_parser. Связка идёт через
    user_profile.tg_user_id — в таблицах парсера ключ это НЕ наш
    внутренний user_id, а реальный numeric Telegram ID.
    """
    if current_user.tg_user_id is None:
        return TelegramStatusResponse(
            status="not_started",
            chats=[],
            messages_collected=0,
            subscriptions_collected=0,
        )

    tg_id = current_user.tg_user_id

    rows = (
        await db.execute(
            text(
                "SELECT chat_id, status, error_message "
                "FROM parse_state WHERE user_id = :tg_id"
            ),
            {"tg_id": tg_id},
        )
    ).all()

    messages_count = (
        await db.execute(
            text("SELECT count(*) FROM messages WHERE user_id = :tg_id"),
            {"tg_id": tg_id},
        )
    ).scalar_one()

    subscriptions_count = (
        await db.execute(
            text("SELECT count(*) FROM subscriptions WHERE user_id = :tg_id"),
            {"tg_id": tg_id},
        )
    ).scalar_one()

    chats = [
        TelegramChatStatus(
            chat_id=row.chat_id,
            status=row.status,
            error_message=row.error_message,
        )
        for row in rows
    ]

    if not chats:
        # Логин прошёл (tg_user_id есть), но парсер ещё не создал ни одной
        # строки — либо он только стартовал, либо анализ не запускали.
        overall = "not_started"
    elif any(chat.status is None for chat in chats):
        overall = "in_progress"
    elif all(chat.status == "failed" for chat in chats):
        overall = "failed"
    else:
        overall = "done"

    return TelegramStatusResponse(
        status=overall,
        chats=chats,
        messages_collected=messages_count,
        subscriptions_collected=subscriptions_count,
    )


@router.post(
    "/analyze",
    response_model=TelegramAnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze(
    data: TelegramAnalyzeRequest,
    db: AsyncSession = Depends(get_session),
    # Авторизация переиспользует общую сессионную схему сервиса — это не
    # telegram-логин, а обычный bearer-токен нашего API. Сам parser не
    # знает про current_user.user_id: он всегда определяет свой user_id из
    # переданной Telegram-сессии (me.id), это осознанное решение автора
    # парсера, не баг — см. tg_user_id на UserModel для связки задним числом.
    current_user: UserModel = Depends(get_current_user),
):
    # Разбор личной переписки допустим только по явному согласию — без
    # действующей записи в consent анализ не запускаем.
    consent = await db.execute(
        select(ConsentModel).where(
            ConsentModel.user_id == current_user.user_id,
            ConsentModel.consent_type == "telegram_analysis",
            ConsentModel.revoked_at.is_(None),
        )
    )

    if consent.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Нет согласия на анализ Telegram. Сначала вызовите "
                'POST /consent {"consent_type": "telegram_analysis"}'
            ),
        )

    try:
        await start_parser(
            session_string=data.session_string,
            chat_ids=data.chat_ids,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    return TelegramAnalyzeResponse(status="started")
