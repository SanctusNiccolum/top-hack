"""Мост к модулю tg-ai (анализ Telegram через GigaChat).

tg-ai поднят отдельным HTTP-сервисом: у него свои зависимости и свой
ключ, а главное — он ходит во внешний API, который может быть медленным
или недоступным. Держать его в одном процессе с бэкендом означало бы
делить с ним таймауты и падения.

Тексты берём из таблицы `messages`, которую наполняет telegram_parser.
Ключ там — реальный numeric Telegram ID (`user_profile.tg_user_id`), а
не внутренний user_id бэкенда.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TG_AI_URL = os.environ.get("TG_AI_URL", "http://tg-ai:8000")

# Анализ идёт через внешнюю LLM по чанкам: на сотнях сообщений это
# десятки секунд. Лимит с запасом, но не бесконечный.
REQUEST_TIMEOUT = float(os.environ.get("TG_AI_TIMEOUT", "180"))


class TelegramAIUnavailable(RuntimeError):
    """Сервис анализа не ответил."""


async def analyze_texts(telegram_user_id: int, texts: list[str]) -> dict:
    """Отдаёт результат разбора: дельта, риск, объяснение.

    Формат ответа задан модулем tg-ai (AnalyzeResponse). При недоступном
    GigaChat модуль сам возвращает 200 со `status="error"` и нулевой
    дельтой — скоринг в этом случае просто не корректируется.
    """
    payload = {"user_id": telegram_user_id, "texts": texts}

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{TG_AI_URL}/analyze/backend",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        logger.error("tg-ai недоступен: %s", exc)
        raise TelegramAIUnavailable(str(exc)) from exc
