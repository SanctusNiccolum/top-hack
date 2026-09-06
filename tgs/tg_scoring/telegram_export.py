"""
Конвертер экспорта Telegram в формат входа модуля.

Принимает `result.json` из Telegram Desktop (Настройки → Продвинутые →
Экспорт данных, формат JSON) и отдаёт готовый AnalyzeRequest.

Три места, где такие конвертеры обычно ломаются:

1. Поле `text` бывает СТРОКОЙ, а бывает СПИСКОМ из строк и объектов
   {"type": "bold", "text": "..."} — форматирование Telegram режет
   сообщение на куски. str() по такому списку даёт "[object Object]".
2. Служебные сообщения (вступил, закрепил, сменил фото) приходят с
   `type: "service"` и пустым текстом — их надо выбрасывать до анализа.
3. В личных чатах и группах сообщения перемешаны с чужими. Для скоринга
   нужны только сообщения самого пользователя — иначе в рейтинг попадёт
   чужая жизнь.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import AnalyzeRequest, Consent, InputMessage, Source

CHANNEL_TYPES = {"public_channel", "private_channel", "channel"}


def flatten_text(message: dict[str, Any]) -> str:
    """Собирает текст сообщения из любого из двух представлений.

    Предпочитаем `text_entities`: это всегда список однородных объектов,
    тогда как `text` может быть строкой или смешанным списком.
    """
    entities = message.get("text_entities")
    if isinstance(entities, list) and entities:
        parts: list[str] = []
        for entity in entities:
            if not isinstance(entity, dict):
                parts.append(str(entity))
                continue
            parts.append(entity.get("text", ""))
            # у text_link видимый текст и адрес разные, а домен — сигнал
            # (1xbet.ru), поэтому адрес дописываем рядом
            if entity.get("type") == "text_link" and entity.get("href"):
                parts.append(f" {entity['href']} ")
        return "".join(parts).strip()

    raw = message.get("text", "")
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = []
        for part in raw:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
                if part.get("type") == "text_link" and part.get("href"):
                    parts.append(f" {part['href']} ")
        return "".join(parts).strip()
    return ""


def message_datetime(message: dict[str, Any]) -> datetime | None:
    unixtime = message.get("date_unixtime")
    if unixtime:
        try:
            return datetime.fromtimestamp(int(unixtime), tz=timezone.utc)
        except (TypeError, ValueError):
            pass
    raw = message.get("date")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def detect_main_author(messages: list[dict[str, Any]]) -> str | None:
    """Самый частый автор. Для личного канала это владелец; для чата —
    обычно тоже пользователь, но результат стоит перепроверить глазами."""
    counter = Counter(
        str(m.get("from_id") or m.get("from") or "")
        for m in messages
        if m.get("type") != "service" and (m.get("from_id") or m.get("from"))
    )
    return counter.most_common(1)[0][0] if counter else None


def convert(
    export: dict[str, Any],
    *,
    period_days: int = 90,
    author: str | None = None,
    auto_author: bool = True,
    anchor: str = "now",
    request_id: str | None = None,
    consent_granted: bool = True,
) -> tuple[AnalyzeRequest, dict[str, int]]:
    """Экспорт -> AnalyzeRequest. Возвращает запрос и статистику отсева."""
    raw_messages = export.get("messages", [])
    if not isinstance(raw_messages, list):
        raise ValueError("в файле нет списка messages — это точно экспорт Telegram?")

    export_kind = str(export.get("type", ""))
    is_channel = export_kind in CHANNEL_TYPES

    # В канале автор один — фильтровать не нужно. В чате нужно обязательно,
    # иначе в скоринг попадут чужие сообщения.
    target_author = author
    if target_author is None and auto_author and not is_channel:
        target_author = detect_main_author(raw_messages)

    dates = [d for d in (message_datetime(m) for m in raw_messages) if d]
    if anchor == "last" and dates:
        reference = max(dates)
    else:
        reference = datetime.now(timezone.utc)

    stats = {"total": len(raw_messages), "service": 0, "empty": 0,
             "other_author": 0, "too_old": 0, "kept": 0}
    result: list[tuple[int, InputMessage]] = []

    for message in raw_messages:
        if message.get("type") == "service" or "action" in message:
            stats["service"] += 1
            continue

        if target_author is not None:
            who = str(message.get("from_id") or message.get("from") or "")
            if who != target_author:
                stats["other_author"] += 1
                continue

        text = flatten_text(message)
        if not text:
            stats["empty"] += 1  # медиа без подписи, стикеры, кружки
            continue

        when = message_datetime(message)
        days_ago = max(0, (reference - when).days) if when else period_days
        if days_ago > period_days:
            stats["too_old"] += 1
            continue

        result.append(
            (
                days_ago,
                InputMessage(
                    id=f"m_{message.get('id', len(result) + 1)}",
                    text=text,
                    is_forward=bool(message.get("forwarded_from")),
                    is_reply=bool(message.get("reply_to_message_id")),
                    char_len=len(text),
                ),
            )
        )

    stats["kept"] = len(result)
    # Даты нужны только чтобы отсечь всё старше окна и разложить сообщения
    # по хронологии. В сам контракт время не попадает.
    result.sort(key=lambda pair: -pair[0])
    messages = [m for _, m in result]

    request = AnalyzeRequest(
        request_id=request_id or str(uuid.uuid4()),
        consent=Consent(
            granted=consent_granted,
            granted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            scope=["public_channel", "own_messages"],
        ),
        source=Source(
            kind="channel" if is_channel else "chat",
            period_days=period_days,
            messages_raw=len(raw_messages),
            messages_after_cleaning=len(result),
            lang_primary="ru",
        ),
        messages=messages,
    )
    return request, stats


def convert_file(path: str | Path, **kwargs: Any) -> tuple[AnalyzeRequest, dict[str, int]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return convert(data, **kwargs)
