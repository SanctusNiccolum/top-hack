"""Интерфейс LLM-провайдера и разбор ответа."""

from __future__ import annotations

import json
import re
from typing import Protocol

from ..chunking import Chunk
from ..schemas import ChunkResult


class LLMError(RuntimeError):
    """Ошибка транспорта или авторизации."""


class ChunkFailure(RuntimeError):
    """Чанк не удалось разобрать даже после ретрая."""


class LLMProvider(Protocol):
    name: str

    def analyze_chunk(self, chunk: Chunk) -> ChunkResult:
        ...


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_chunk_response(raw: str, chunk: Chunk) -> ChunkResult:
    """Строгий парсер с одной поблажкой: модели любят обернуть JSON в
    markdown-фенс или добавить фразу до/после. Снимаем фенс и берём
    внешние фигурные скобки — дальше только валидный JSON."""
    text = _FENCE.sub("", raw.strip())
    if not text.startswith("{"):
        match = _JSON_BLOCK.search(text)
        if not match:
            raise ChunkFailure("в ответе нет JSON-объекта")
        text = match.group(0)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChunkFailure(f"невалидный JSON: {exc}") from exc

    payload.setdefault("chunk_id", chunk.chunk_id)
    try:
        return ChunkResult.model_validate(payload)
    except Exception as exc:
        raise ChunkFailure(f"структура ответа не соответствует схеме: {exc}") from exc
