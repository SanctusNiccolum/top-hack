"""
Адаптер формата бэкенда: {"user_id": ..., "texts": [...]} -> AnalyzeRequest.

Формат плоский: массив строк без идентификаторов, без дат и без пометок
об авторстве. Что из этого важно и почему:

`id` — генерируется по позиции в массиве. Это нормально: идентификатор
нужен модулю только чтобы связать сигнал с сообщением внутри чанка и
проверить, что модель не сослалась на несуществующее сообщение.

`date` — не нужна. Окно 90 дней, взвешивания по свежести в формуле нет.

`is_forward` / `is_reply` — по договорённости бэкенд отдаёт только
собственные сообщения пользователя (`is_forward = false`), поэтому в
payload их нет и адаптер проставляет `False`.

Проверку на `is_forward` в валидаторе при этом НЕ убрали, и намеренно.
Она стоит одно сравнение булева поля, а страхует сразу от двух вещей:
конвертер из выгрузки Telegram Desktop (`telegram_export.py`) настоящие
пересланные сообщения размечает, и если однажды поменяется фильтр на
стороне парсера, модуль не начнёт молча засчитывать чужие посты как
собственные. Гарантии на стороне соседнего сервиса имеют свойство
тихо меняться; проверка, которая ничего не стоит, — самая дешёвая
страховка из возможных.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .schemas import AnalyzeRequest, Consent, InputMessage, Source


def from_backend_payload(
    payload: dict[str, Any],
    *,
    request_id: str | None = None,
    consent_granted: bool = True,
    period_days: int = 90,
    source_kind: str = "chat",
) -> tuple[AnalyzeRequest, list[str]]:
    """Плоский payload -> AnalyzeRequest. Возвращает запрос и предупреждения."""
    texts = payload.get("texts")
    if not isinstance(texts, list):
        raise ValueError('в payload нет массива "texts"')

    warnings: list[str] = []
    messages: list[InputMessage] = []
    skipped_non_string = 0

    for index, raw in enumerate(texts, start=1):
        if not isinstance(raw, str):
            skipped_non_string += 1
            continue
        text = raw.strip()
        if not text:
            continue
        messages.append(
            InputMessage(
                id=f"m_{index:04d}",
                text=text,
                # Данных об авторстве в формате нет. False здесь означает
                # «считаем сообщение авторским» — оптимистичное допущение,
                # и оно же самое опасное: пересланный пост про казино будет
                # отнесён пользователю, если модель не пометит about_author.
                is_forward=False,
                is_reply=False,
                char_len=len(text),
            )
        )

    if skipped_non_string:
        warnings.append(f"пропущено не-строковых элементов в texts: {skipped_non_string}")

    user_id = payload.get("user_id")
    if request_id is None:
        # По умолчанию привязываемся к user_id, чтобы бэкенду было чем
        # сопоставить ответ. В проде лучше передавать свой непрозрачный id:
        # user_id телеграма — постоянный идентификатор личности, и ему не
        # место в логах рядом с финансовыми выводами.
        request_id = f"u{user_id}" if user_id is not None else str(uuid.uuid4())

    request = AnalyzeRequest(
        request_id=request_id,
        consent=Consent(granted=consent_granted, scope=["own_messages"]),
        source=Source(
            kind=source_kind,
            period_days=period_days,
            messages_raw=len(texts),
            messages_after_cleaning=len(messages),
            lang_primary="ru",
        ),
        messages=messages,
    )
    return request, warnings


def from_backend_file(path: str | Path, **kwargs: Any) -> tuple[AnalyzeRequest, list[str]]:
    return from_backend_payload(json.loads(Path(path).read_text(encoding="utf-8")), **kwargs)
