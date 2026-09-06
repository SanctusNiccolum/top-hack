"""Логин в Telegram (phone -> code -> [password]) поверх Telethon.

Живёт отдельно от telegram_parser/ и его подпроцессной модели: это
интерактивный HTTP-flow с состоянием, которое нужно помнить МЕЖДУ запросами
(пока пользователь читает код в Telegram и вводит его на фронте) — парсер
же спроектирован как одноразовый fire-and-forget процесс без диалога.
Здесь Telethon используется на живую, прямо из backend-процесса.

Состояние логина хранится в памяти процесса (login_id -> открытый
TelegramClient). Это ок для одного backend-процесса хакатона; для
нескольких воркеров/реплик потребовалась бы внешняя стор (Redis) — см.
context_summary2.md.
"""
from __future__ import annotations

import os
import time
import uuid

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User

_LOGIN_TTL_SECONDS = 15 * 60


class _PendingLogin:
    __slots__ = ("client", "phone", "phone_code_hash", "created_at")

    def __init__(self, client: TelegramClient, phone: str, phone_code_hash: str):
        self.client = client
        self.phone = phone
        self.phone_code_hash = phone_code_hash
        self.created_at = time.monotonic()


_pending: dict[str, _PendingLogin] = {}


def _api_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError(
            "TG_API_ID / TG_API_HASH не заданы в окружении backend-сервиса"
        )

    return int(api_id), api_hash


async def _safe_disconnect(client: TelegramClient) -> None:
    try:
        await client.disconnect()
    except Exception:
        pass


async def _pop_valid(login_id: str) -> _PendingLogin:
    pending = _pending.get(login_id)

    if pending is None:
        raise ValueError("Логин-сессия не найдена или уже завершена")

    if time.monotonic() - pending.created_at > _LOGIN_TTL_SECONDS:
        del _pending[login_id]
        await _safe_disconnect(pending.client)
        raise ValueError("Логин-сессия истекла, начните заново")

    return pending


async def start_login(phone_number: str) -> str:
    api_id, api_hash = _api_credentials()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    sent = await client.send_code_request(phone_number)

    login_id = uuid.uuid4().hex
    _pending[login_id] = _PendingLogin(
        client, phone_number, sent.phone_code_hash
    )

    return login_id


async def submit_code(login_id: str, code: str) -> dict:
    pending = await _pop_valid(login_id)

    try:
        await pending.client.sign_in(
            phone=pending.phone,
            code=code,
            phone_code_hash=pending.phone_code_hash,
        )
    except SessionPasswordNeededError:
        return {
            "status": "need_password",
            "session_string": None,
            "telegram_user_id": None,
        }
    except PhoneCodeInvalidError:
        # Код введён неверно, но phone_code_hash и сессия ещё живы — не
        # трогаем _pending, чтобы можно было повторить с тем же login_id,
        # не запрашивая новое СМС.
        raise ValueError("Неверный код, попробуйте ввести ещё раз")
    except PhoneCodeExpiredError:
        # А вот это уже реально нужно начинать заново — код протух.
        del _pending[login_id]
        await _safe_disconnect(pending.client)
        raise ValueError("Код устарел, начните заново с /telegram/login/phone")

    return await _finalize(login_id, pending)


async def submit_password(login_id: str, password: str) -> dict:
    pending = await _pop_valid(login_id)

    try:
        await pending.client.sign_in(password=password)
    except PasswordHashInvalidError:
        raise ValueError("Неверный пароль")

    return await _finalize(login_id, pending)


async def _finalize(login_id: str, pending: _PendingLogin) -> dict:
    me = await pending.client.get_me()
    session_string = pending.client.session.save()

    # НЕ log_out() — это одноразово отозвало бы сессию (см.
    # telegram_parser/main.py), а она ещё нужна для /telegram/chats и
    # /telegram/analyze. Просто отключаемся от текущего сокета — сама
    # авторизация остаётся действительной.
    await _safe_disconnect(pending.client)
    del _pending[login_id]

    return {
        "status": "ok",
        "session_string": session_string,
        "telegram_user_id": me.id,
    }


async def list_chats(session_string: str) -> list[dict]:
    api_id, api_hash = _api_credentials()

    try:
        client = TelegramClient(StringSession(session_string), api_id, api_hash)
        await client.connect()
    except Exception as exc:
        # StringSession падает не только ValueError'ом — например,
        # struct.error на обрезанной/битой строке (частый случай: терминал
        # обрезал длинную строку при выводе, скопирован огрызок).
        raise ValueError(f"Некорректный session_string: {exc}") from exc

    try:
        if not await client.is_user_authorized():
            raise ValueError("session_string недействителен или истёк")

        chats = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            chats.append(
                {
                    "chat_id": dialog.id,
                    "name": dialog.name,
                    "username": getattr(entity, "username", None),
                    "type": await _classify(client, entity),
                }
            )

        return chats
    finally:
        await _safe_disconnect(client)


async def _classify(client: TelegramClient, entity) -> str:
    """own_messages — пользователь сам пишет туда (ЛС, группа, канал, где
    он админ/создатель); subscription — канал, где он только читает.
    Автоматически, без ручного выбора юзером — см. context_summary2.md.
    """
    if isinstance(entity, (User, Chat)):
        return "own_messages"

    if isinstance(entity, Channel):
        if entity.megagroup:  # супергруппа — по факту групповой чат
            return "own_messages"

        try:
            permissions = await client.get_permissions(entity, "me")
        except Exception:
            return "subscription"

        if permissions.is_admin or permissions.is_creator:
            return "own_messages"

        return "subscription"

    return "subscription"
