"""Разбиение на чанки для LLM."""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import InputMessage


@dataclass
class Chunk:
    chunk_id: int
    messages: list[InputMessage]

    @property
    def ids(self) -> set[str]:
        return {m.id for m in self.messages}


def make_chunks(messages: list[InputMessage], size: int = 40) -> list[Chunk]:
    """Чанк меряется в СООБЩЕНИЯХ, а не в токенах: так `no_signal_count`
    и `reviewed_ids` сверяются с составом чанка тривиально, а длину
    отдельного сообщения уже ограничила очистка (1500 символов)."""
    if size <= 0:
        raise ValueError("size должен быть положительным")
    return [
        Chunk(chunk_id=i, messages=messages[offset : offset + size])
        for i, offset in enumerate(range(0, len(messages), size))
    ]
