"""Entry point for the Telegram parser subprocess.

Invoked by the main `api` backend as a standalone OS process (not an
imported function) — an authenticated Telegram session is sensitive
enough to warrant its own process boundary.

Input contract: a single JSON payload on **stdin** (never argv/env/a temp
file — those are visible to other processes on the machine or persist on
disk; stdin isn't). Shape:

    {
        "session_string": "...",
        "api_id": 12345,
        "api_hash": "...",
        "chat_ids": [-100111111111, 5270187642, -100222222222]
    }

Note there is no `user_id` in the input and no `type` per chat:

- `user_id` is NOT taken from the caller — it's derived from the logged-in
  account itself (`me.id`, the real numeric Telegram ID) right after
  connecting. A caller-supplied placeholder ("1" for every test run, etc.)
  is exactly the kind of thing that silently corrupts data once more than
  one real account goes through this, so the parser determines it itself
  from the one source that's actually guaranteed correct.
- For every chat_id, the parser always attempts BOTH extractions —
  own-messages (from_id == me) and subscription metadata
  (title/username/about). Whichever produces something real is kept;
  whichever doesn't apply to that entity (no "about" for a personal DM, no
  own messages in a channel you only read) is simply empty. This avoids
  the earlier misclassification problem where a private group the user
  was technically a "subscriber" of, but actively posted in, came back
  empty when forced through the wrong single extraction path.

Output: writes directly to PostgreSQL (see db.py) — `messages`,
`subscriptions`, `parse_state` (per-chat status/errors, and incremental
last-parsed-at), and `ai_queue` (readiness signal for the AI service,
plain table instead of a broker — see plan.md for why). The caller does
NOT wait for this process to exit (fire-and-forget); `parse_state` and
`ai_queue` are the whole "done" signal, not stdout/exit code.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from . import db
from .telegram_client import parse_own_messages, parse_subscription

LOOKBACK_DAYS = 90  # ~3 месяца, продуктовое решение


def _read_payload() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw)


async def _extract_messages(client, pool, user_id: int, chat_id: int, chat_name, me_id: int,
                             since_date, errors: list[str]) -> None:
    for attempt in (1, 2):  # один повтор после flood-wait
        try:
            messages = await parse_own_messages(client, chat_id, since_date, me_id)
            await db.upsert_messages(pool, user_id, chat_id, chat_name, "chat", messages)
            return
        except FloodWaitError as e:
            if attempt == 2:
                errors.append(f"messages: flood wait persisted ({e.seconds}s)")
                return
            await asyncio.sleep(e.seconds)
        except Exception as e:
            errors.append(f"messages: {e}")
            return


async def _extract_subscription(client, pool, user_id: int, chat_id: int, errors: list[str]) -> None:
    for attempt in (1, 2):
        try:
            sub = await parse_subscription(client, chat_id)
            if sub.get("channel_name"):  # личный чат резолвится в channel_name=None — пропускаем
                await db.upsert_subscription(pool, user_id, chat_id, sub)
            return
        except FloodWaitError as e:
            if attempt == 2:
                errors.append(f"subscription: flood wait persisted ({e.seconds}s)")
                return
            await asyncio.sleep(e.seconds)
        except Exception as e:
            errors.append(f"subscription: {e}")
            return


async def _process_chat(client, pool, user_id: int, me_id: int, chat_id: int) -> None:
    errors: list[str] = []

    try:
        entity = await client.get_entity(chat_id)
        chat_name = getattr(entity, "title", None) or getattr(entity, "first_name", None)
    except Exception as e:
        await db.update_parse_state(pool, user_id, chat_id, status="failed", error_message=f"entity: {e}")
        return

    last_parsed_at = await db.get_last_parsed_at(pool, user_id, chat_id)
    floor_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_date = max(last_parsed_at, floor_date) if last_parsed_at else floor_date

    await _extract_messages(client, pool, user_id, chat_id, chat_name, me_id, since_date, errors)
    await _extract_subscription(client, pool, user_id, chat_id, errors)

    if errors:
        await db.update_parse_state(pool, user_id, chat_id, status="failed", error_message="; ".join(errors))
    else:
        await db.update_parse_state(
            pool, user_id, chat_id, status="success", last_parsed_at=datetime.now(timezone.utc),
        )


async def main() -> int:
    payload = _read_payload()

    session_string = payload["session_string"]
    api_id = payload["api_id"]
    api_hash = payload["api_hash"]
    chat_ids = payload["chat_ids"]

    pool = await db.get_pool()
    client = TelegramClient(StringSession(session_string), api_id, api_hash)

    exit_code = 0
    try:
        await client.connect()

        if not await client.is_user_authorized():
            return 1  # user_id ещё не известен (не залогинены) — писать в ai_queue некому

        me = await client.get_me()
        user_id = me.id  # реальный Telegram ID, а не то, что передал вызывающий код

        # StringSession несёт только ключ авторизации, не кэш "уже виденных"
        # сущностей — каждый новый процесс парсера стартует с пустым кэшем.
        # get_entity() по голому числовому ID падает, пока Telethon не
        # "встретит" сущность в рамках ТЕКУЩЕГО процесса — get_dialogs()
        # прогревает кэш разом для всех чатов аккаунта.
        await client.get_dialogs()

        for chat_id in chat_ids:
            await _process_chat(client, pool, user_id, me.id, chat_id)

        await db.enqueue_ai(pool, user_id, status="pending")

    except Exception as e:
        exit_code = 1
        try:
            await db.enqueue_ai(pool, user_id, status="failed", error_message=str(e))
        except NameError:
            pass  # упали раньше, чем узнали user_id — писать некуда

    finally:
        # Сессия одноразовая по дизайну: отзываем её при ЛЮБОМ исходе, чтобы
        # утёкший session_string нельзя было переиспользовать после запуска.
        try:
            await client.log_out()
        except Exception:
            try:
                await client.disconnect()
            except Exception:
                pass
        await pool.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
