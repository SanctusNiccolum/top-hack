"""Экспорт текстов пользователя из Postgres в плоский JSON для ИИ-сервиса.

Отдельный шаг ПОСЛЕ парсинга — main.py пишет в БД как обычно, а это уже
берёт оттуда сообщения по user_id и приводит к виду:

    {"user_id": 5270187642, "texts": ["...", "...", ...]}

Запуск:
    DATABASE_URL="postgresql://..." python -m telegram_parser.export_texts <user_id>

Печатает JSON в stdout (можно перенаправить в файл или сразу передать
дальше по пайплайну).
"""
from __future__ import annotations

import asyncio
import json
import sys

from . import db

if sys.platform == "win32":
    # ProactorEventLoop (дефолт на Windows) периодически рвёт именно такие
    # сетевые соединения с ConnectionResetError: [WinError 64] — известная
    # особенность asyncio на Windows, всплывает не только с asyncpg.
    # SelectorEventLoop этой проблемы не имеет.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def export_user_texts(user_id: int) -> dict:
    pool = await db.get_pool()
    try:
        texts = await db.get_texts_for_user(pool, user_id)
    finally:
        await pool.close()
    return {"user_id": user_id, "texts": texts}


async def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: python -m telegram_parser.export_texts <user_id>\n")
        return 1
    user_id = int(sys.argv[1])
    result = await export_user_texts(user_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
