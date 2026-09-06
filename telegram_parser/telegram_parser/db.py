"""Postgres access layer (asyncpg).

The parser writes directly to the database — it does not return data to
its caller for the caller to persist. Connection string comes from the
DATABASE_URL environment variable (standard practice for service-level
infra config, as opposed to the per-invocation session_string, which is
passed via stdin — see main.py's docstring for why those two are handled
differently).
"""
from __future__ import annotations

import os
from datetime import datetime

import asyncpg


async def get_pool() -> asyncpg.Pool:
    dsn = os.environ["DATABASE_URL"]
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def get_last_parsed_at(pool: asyncpg.Pool, user_id: int, chat_id: int) -> datetime | None:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT last_parsed_at FROM parse_state WHERE user_id = $1 AND chat_id = $2",
            user_id, chat_id,
        )


async def upsert_messages(
    pool: asyncpg.Pool,
    user_id: int,
    chat_id: int,
    chat_name: str | None,
    chat_type: str,
    messages: list[dict],
) -> None:
    """Insert new messages, silently skipping ones already collected
    (ON CONFLICT on the (chat_id, tg_msg_id) unique constraint) — this is
    what makes incremental re-parsing idempotent.
    """
    if not messages:
        return
    rows = [
        (
            m["tg_msg_id"], user_id, chat_id, chat_name, chat_type,
            m["datetime"], m["text"], m["is_forward"], m["is_reply"],
        )
        for m in messages
    ]
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO messages
                (tg_msg_id, user_id, chat_id, chat_name, chat_type, datetime, text, is_forward, is_reply)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (chat_id, tg_msg_id) DO NOTHING
            """,
            rows,
        )


async def upsert_subscription(pool: asyncpg.Pool, user_id: int, chat_id: int, data: dict) -> None:
    """Store (or refresh) a subscription, matching it against trusted_channels
    by username — never by the (freely renameable) display title.
    """
    async with pool.acquire() as conn:
        trusted_id = None
        if data.get("username"):
            trusted_id = await conn.fetchval(
                "SELECT trusted_channel_id FROM trusted_channels WHERE username = $1",
                data["username"],
            )
        await conn.execute(
            """
            INSERT INTO subscriptions
                (user_id, chat_id, channel_name, username, about, trusted_channel_id, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, now())
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                channel_name = EXCLUDED.channel_name,
                username = EXCLUDED.username,
                about = EXCLUDED.about,
                trusted_channel_id = EXCLUDED.trusted_channel_id,
                detected_at = now()
            """,
            user_id, chat_id, data.get("channel_name"), data.get("username"),
            data.get("about"), trusted_id,
        )


async def update_parse_state(
    pool: asyncpg.Pool,
    user_id: int,
    chat_id: int,
    status: str,
    last_parsed_at: datetime | None = None,
    error_message: str | None = None,
) -> None:
    """Record the outcome of parsing ONE chat. Granular per-chat status is
    the primary error-reporting channel for this system (not the process
    exit code) — one chat failing must be diagnosable without guessing
    which of several chats in the run was the problem.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO parse_state (user_id, chat_id, last_parsed_at, status, error_message)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET
                last_parsed_at = COALESCE(EXCLUDED.last_parsed_at, parse_state.last_parsed_at),
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message
            """,
            user_id, chat_id, last_parsed_at, status, error_message,
        )


async def enqueue_ai(
    pool: asyncpg.Pool,
    user_id: int,
    status: str = "pending",
    error_message: str | None = None,
) -> None:
    """Signal that this user's data is ready for the AI service to pick up.
    Plain Postgres table instead of a broker — see requirements brief for
    the reasoning (scale doesn't warrant one, and a table gives a free
    audit trail instead of losing history on consume).
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ai_queue (user_id, status, created_at, error_message)
            VALUES ($1, $2, now(), $3)
            """,
            user_id, status, error_message,
        )
