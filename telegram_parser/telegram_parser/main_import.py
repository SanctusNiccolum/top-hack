"""Точка входа для ИМПОРТ-режима (без Telegram API).

Вход на stdin (JSON):
    {
        "user_id": 123,
        "export_path": "/data/exports/123/result.json",
        "chat_ids": [111111111, 222222222]
    }

`export_path` — путь к result.json из официального экспорта Telegram
Desktop (должен быть доступен процессу — общий volume в Docker).
`chat_ids` — какие чаты из экспорта пользователь разрешил использовать
(остальные из файла просто игнорируются, даже если там есть).

Пишет в те же таблицы, что и live-версия (main.py): messages,
subscriptions, parse_state, ai_queue — с той же семантикой per-chat
статуса и fire-and-forget вызова. См. import_parser.py про то, что
отличается по данным (нет username/about у подписок).
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from . import db
from .import_parser import (
    classify_chat_type,
    extract_own_messages,
    extract_subscription_meta,
)

LOOKBACK_DAYS = 90  # тот же продуктовый лимит, что и в live-версии


def _read_payload() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw)


def _index_chats_by_id(export: dict) -> dict[int, dict]:
    chats = export.get("chats", {}).get("list", [])
    return {c["id"]: c for c in chats}


async def _process_one_chat(pool, user_id: int, owner_tg_id: int, chat: dict) -> None:
    chat_id = chat["id"]
    chat_name = chat.get("name")
    our_type = classify_chat_type(chat.get("type", ""))

    try:
        if our_type == "subscription":
            data = extract_subscription_meta(chat)
            await db.upsert_subscription(pool, user_id, chat_id, data)

        elif our_type == "own_messages":
            last_parsed_at = await db.get_last_parsed_at(pool, user_id, chat_id)
            floor_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
            since_date = max(last_parsed_at, floor_date) if last_parsed_at else floor_date

            messages = extract_own_messages(chat, owner_tg_id, since_date)
            await db.upsert_messages(pool, user_id, chat_id, chat_name, "own_messages", messages)

        else:
            await db.update_parse_state(
                pool, user_id, chat_id, status="failed",
                error_message=f"неизвестный тип чата в экспорте: {chat.get('type')!r}",
            )
            return

        await db.update_parse_state(
            pool, user_id, chat_id, status="success",
            last_parsed_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        await db.update_parse_state(pool, user_id, chat_id, status="failed", error_message=str(e))


async def main() -> int:
    payload = _read_payload()
    user_id = payload["user_id"]
    export_path = payload["export_path"]
    requested_chat_ids = payload["chat_ids"]

    pool = await db.get_pool()

    try:
        with open(export_path, encoding="utf-8") as f:
            export = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        await db.enqueue_ai(pool, user_id, status="failed", error_message=f"не удалось прочитать экспорт: {e}")
        await pool.close()
        return 1

    owner_tg_id = export.get("personal_information", {}).get("user_id")
    if owner_tg_id is None:
        await db.enqueue_ai(pool, user_id, status="failed",
                             error_message="в экспорте нет personal_information.user_id")
        await pool.close()
        return 1

    chats_by_id = _index_chats_by_id(export)

    for chat_id in requested_chat_ids:
        chat = chats_by_id.get(chat_id)
        if chat is None:
            await db.update_parse_state(
                pool, user_id, chat_id, status="failed",
                error_message="chat_id не найден в экспорте",
            )
            continue
        await _process_one_chat(pool, user_id, owner_tg_id, chat)

    await db.enqueue_ai(pool, user_id, status="pending")
    await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
