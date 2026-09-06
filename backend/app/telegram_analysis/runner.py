"""Вызов telegram_parser (см. /telegram_parser в корне репозитория) как
обычного OS-подпроцесса — не импортом. Это единственный модуль в backend,
который вообще знает о существовании парсера; больше нигде в app/ не
должно быть импортов telethon или знаний о его схеме БД.

Контракт входа (JSON на stdin) задан самим парсером в
telegram_parser/telegram_parser/main.py и здесь не переопределяется.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Годится для локального запуска backend без Docker (uvicorn запущен из
# backend/, репозиторий не переносился) — parents[3] от этого файла как раз
# указывает на корень репозитория. В контейнере путь другой (см.
# Dockerfile: пакет парсера лежит рядом, в /app/telegram_parser), поэтому
# там cwd переопределяется переменной окружения TELEGRAM_PARSER_CWD
# (docker-compose.yaml).
_DEFAULT_PARSER_CWD = Path(__file__).resolve().parents[3] / "telegram_parser"

PARSER_CWD = Path(
    os.environ.get("TELEGRAM_PARSER_CWD", str(_DEFAULT_PARSER_CWD))
)


def _asyncpg_dsn(sqlalchemy_url: str) -> str:
    """DATABASE_URL бэкенда — это SQLAlchemy DSN вида
    postgresql+asyncpg://..., а парсер вызывает asyncpg.create_pool()
    напрямую, который синтаксис "+driver" не понимает и упадёт на connect.
    Отдаём парсеру ту же строку, но без диалект-суффикса.
    """
    return re.sub(r"^postgresql\+\w+://", "postgresql://", sqlalchemy_url)


async def start_parser(session_string: str, chat_ids: list[int]) -> None:
    """Fire-and-forget: запускает парсер и НЕ дожидается его завершения —
    так же, как задумано в самом парсере (см. main.py: статус смотреть в
    parse_state/ai_queue, а не по коду возврата процесса).
    """
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    database_url = os.environ.get("DATABASE_URL")

    if not api_id or not api_hash:
        raise RuntimeError(
            "TG_API_ID / TG_API_HASH не заданы в окружении backend-сервиса"
        )

    if not database_url:
        raise RuntimeError("DATABASE_URL не задан в окружении backend-сервиса")

    payload = json.dumps(
        {
            "session_string": session_string,
            "api_id": int(api_id),
            "api_hash": api_hash,
            "chat_ids": chat_ids,
        }
    ).encode("utf-8")

    env = os.environ.copy()
    env["DATABASE_URL"] = _asyncpg_dsn(database_url)

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "telegram_parser.main",
        cwd=str(PARSER_CWD),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Не await'им здесь — иначе HTTP-ответ ждал бы весь парсинг чатов за 3
    # месяца. Задача переживает возврат из эндпоинта и сама реапит процесс.
    asyncio.create_task(_wait_and_log(process, payload))


async def _wait_and_log(
    process: asyncio.subprocess.Process, payload: bytes
) -> None:
    _stdout, stderr = await process.communicate(payload)

    if process.returncode != 0:
        logger.error(
            "telegram_parser завершился с кодом %s: %s",
            process.returncode,
            stderr.decode("utf-8", "replace"),
        )
