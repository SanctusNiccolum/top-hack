"""Точка входа для ИМПОРТ-режима (без Telegram API).

Резервный путь на случай, если у кого-то в команде обход блокировки
my.telegram.org (см. plan.md) не сработает. Вместо live-подключения читает
`result.json` — официальный экспорт Telegram Desktop.

Вход на stdin (JSON):
    {
        "export_path": "/data/exports/.../result.json",
        "chat_ids": [111111111, 222222222]
    }

user_id не передаётся отдельно — берётся из самого экспорта
(personal_information.user_id), тем же принципом, что и в live-режиме
(main.py): user_id — это реальный Telegram ID владельца, а не то, что
вручную вписал вызывающий код.

Как и в main.py: без ручной классификации own_messages/subscription — для
каждого запрошенного chat_id пробуем извлечь и сообщения, и метаданные
подписки одновременно. Пишет в те же таблицы, что и live-режим
(messages/subscriptions/parse_state/ai_queue) — см. import_parser.py про
то, чем это отличается по данным (нет username/about у подписок).
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from . import db
from .import_parser import extract_own_messages, extract_subscription_meta

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
    errors: list[str] = []

    last_parsed_at = await db.get_last_parsed_at(pool, user_id, chat_id)
    floor_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    since_date = max(last_parsed_at, floor_date) if last_parsed_at else floor_date

    try:
        messages = extract_own_messages(chat, owner_tg_id, since_date)
        await db.upsert_messages(pool, user_id, chat_id, chat_name, "chat", messages)
    except Exception as e:
        errors.append(f"messages: {e}")

    try:
        sub = extract_subscription_meta(chat)
        if sub.get("channel_name"):
            await db.upsert_subscription(pool, user_id, chat_id, sub)
    except Exception as e:
        errors.append(f"subscription: {e}")

    if errors:
        await db.update_parse_state(pool, user_id, chat_id, status="failed", error_message="; ".join(errors))
    else:
        await db.update_parse_state(
            pool, user_id, chat_id, status="success", last_parsed_at=datetime.now(timezone.utc),
        )


async def main() -> int:
    payload = _read_payload()
    export_path = payload["export_path"]
    requested_chat_ids = payload["chat_ids"]

    pool = await db.get_pool()

    try:
        with open(export_path, encoding="utf-8") as f:
            export = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"не удалось прочитать экспорт: {e}\n")
        await pool.close()
        return 1

    owner_tg_id = export.get("personal_information", {}).get("user_id")
    if owner_tg_id is None:
        sys.stderr.write("в экспорте нет personal_information.user_id\n")
        await pool.close()
        return 1

    user_id = owner_tg_id  # реальный Telegram ID владельца, не placeholder
    chats_by_id = _index_chats_by_id(export)

    for chat_id in requested_chat_ids:
        chat = chats_by_id.get(chat_id)
        if chat is None:
            await db.update_parse_state(
                pool, user_id, chat_id, status="failed", error_message="chat_id не найден в экспорте",
            )
            continue
        await _process_one_chat(pool, user_id, owner_tg_id, chat)

    await db.enqueue_ai(pool, user_id, status="pending")
    await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
