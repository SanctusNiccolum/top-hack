"""Entry point for the Telegram parser subprocess.

Invoked by the main `api` backend as a standalone OS process (not an
imported function) — see the requirements brief for why: an authenticated
Telegram session is sensitive enough to warrant its own process boundary.

Input contract: a single JSON payload on **stdin** (never argv/env/a temp
file — those are visible to other processes on the machine or persist on
disk; stdin isn't). Shape:

    {
        "user_id": 123,
        "session_string": "...",
        "api_id": 12345,
        "api_hash": "...",
        "chats": [
            {"chat_id": -100111111111, "type": "own_messages"},
            {"chat_id": -100222222222, "type": "subscription"}
        ]
    }

`type` is one of "own_messages" (DMs, groups, the user's own channels —
only their own messages are collected) or "subscription" (broadcast
channels they just follow — only channel metadata is collected).

The caller does NOT wait for this process to exit (fire-and-forget) —
progress and errors are reported through `parse_state` in Postgres, one
row per chat, not through stdout or the exit code. The exit code is only
a coarse "something in this run failed" signal for basic process
supervision/logging.

DB connection comes from the DATABASE_URL environment variable (ordinary
service infra config, unlike the per-user session_string above).
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

# ~3 months, per product decision. Deliberately a module-level constant so
# it's a one-line change if the retention window is revisited later.
LOOKBACK_DAYS = 90


def _read_payload() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw)


async def _do_parse(
    client: TelegramClient,
    pool,
    user_id: int,
    me_id: int,
    chat_id: int,
    chat_type: str,
    since_date: datetime,
) -> None:
    entity = await client.get_entity(chat_id)
    chat_name = getattr(entity, "title", None) or getattr(entity, "first_name", None)

    if chat_type == "subscription":
        data = await parse_subscription(client, chat_id)
        await db.upsert_subscription(pool, user_id, chat_id, data)
    else:
        messages = await parse_own_messages(client, chat_id, since_date, me_id)
        await db.upsert_messages(pool, user_id, chat_id, chat_name, chat_type, messages)


async def _process_chat(client: TelegramClient, pool, user_id: int, me_id: int, chat: dict) -> None:
    """Parse a single chat. Failures here are contained — they must not
    stop the rest of the chats in this run from being processed.
    """
    chat_id = chat["chat_id"]
    chat_type = chat["type"]

    last_parsed_at = await db.get_last_parsed_at(pool, user_id, chat_id)
    floor_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_date = max(last_parsed_at, floor_date) if last_parsed_at else floor_date

    for attempt in (1, 2):  # one retry after riding out a flood-wait
        try:
            await _do_parse(client, pool, user_id, me_id, chat_id, chat_type, since_date)
            await db.update_parse_state(
                pool, user_id, chat_id, status="success",
                last_parsed_at=datetime.now(timezone.utc),
            )
            return
        except FloodWaitError as e:
            if attempt == 2:
                await db.update_parse_state(
                    pool, user_id, chat_id, status="failed",
                    error_message=f"flood wait persisted: {e.seconds}s",
                )
                return
            await asyncio.sleep(e.seconds)
        except Exception as e:
            await db.update_parse_state(
                pool, user_id, chat_id, status="failed", error_message=str(e),
            )
            return


async def main() -> int:
    payload = _read_payload()

    user_id = payload["user_id"]
    session_string = payload["session_string"]
    api_id = payload["api_id"]
    api_hash = payload["api_hash"]
    chats = payload["chats"]

    pool = await db.get_pool()
    client = TelegramClient(StringSession(session_string), api_id, api_hash)

    exit_code = 0
    try:
        await client.connect()

        if not await client.is_user_authorized():
            await db.enqueue_ai(
                pool, user_id, status="failed",
                error_message="Telegram session is not authorized",
            )
            return 1

        me = await client.get_me()

        # StringSession, в отличие от файловой SQLite-сессии, не хранит
        # кэш "уже виденных" сущностей — каждый новый процесс парсера
        # стартует с пустым кэшем. get_entity() по голому числовому ID
        # личного чата падает с "Could not find the input entity", пока
        # Telethon не "встретит" эту сущность в рамках ТЕКУЩЕГО процесса —
        # проще всего сделать это разом через get_dialogs() один раз в
        # начале, а не для каждого чата отдельно.
        # https://docs.telethon.dev/en/stable/concepts/entities.html
        await client.get_dialogs()

        for chat in chats:
            await _process_chat(client, pool, user_id, me.id, chat)

        await db.enqueue_ai(pool, user_id, status="pending")

    except Exception as e:
        exit_code = 1
        await db.enqueue_ai(pool, user_id, status="failed", error_message=str(e))

    finally:
        # Session is one-time by design (per product decision): revoke it
        # on Telegram's side too, so a leaked session_string can't be
        # replayed after this run finishes. log_out() also disconnects.
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
