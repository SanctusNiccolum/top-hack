from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_user_repository
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


@router.post(
    "/analyze",
    response_model=TelegramAnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze(
    data: TelegramAnalyzeRequest,
    # Авторизация переиспользует общую сессионную схему сервиса — это не
    # telegram-логин, а обычный bearer-токен нашего API. Сам parser не
    # знает про current_user.user_id: он всегда определяет свой user_id из
    # переданной Telegram-сессии (me.id), это осознанное решение автора
    # парсера, не баг — см. tg_user_id на UserModel для связки задним числом.
    current_user: UserModel = Depends(get_current_user),
):
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
