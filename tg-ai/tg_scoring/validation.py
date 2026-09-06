"""
Валидация сигналов между LLM и агрегатором (§5-6 спеки).

Самый дешёвый и самый результативный слой во всём модуле. Три проверки
ловят и галлюцинации, и последствия инъекций, не требуя ни одной правки
промпта:

  * категория обязана быть из закрытого enum;
  * message_id обязан существовать в этом чанке;
  * quote обязана быть дословной подстрокой текста сообщения.

Третья — ключевая. Модель, которая придумала сигнал, почти никогда не
может подкрепить его дословной цитатой.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .categories import BY_KEY, Polarity
from .config import ScoringConfig
from .schemas import ChunkResult, InputMessage, RawSignal


@dataclass
class AcceptedSignal:
    message_id: str
    category: str
    confidence: float
    modality: str
    quote: str


@dataclass
class ValidationReport:
    accepted: list[AcceptedSignal] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)
    messages_with_signal: set[str] = field(default_factory=set)

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("ё", "е")).strip()


def quote_matches(quote: str, text: str) -> bool:
    if not quote.strip():
        return False
    return _norm(quote) in _norm(text)


def validate_signals(
    chunk_results: list[ChunkResult],
    messages_by_id: dict[str, InputMessage],
    config: ScoringConfig,
) -> ValidationReport:
    report = ValidationReport()

    for chunk in chunk_results:
        for signal in chunk.signals:
            reason = _reject_reason(signal, messages_by_id, config)
            if reason:
                report.reject(reason)
                continue

            message = messages_by_id[signal.message_id]
            report.accepted.append(
                AcceptedSignal(
                    message_id=signal.message_id,
                    category=signal.category,
                    confidence=signal.confidence,
                    modality=signal.modality,
                    quote=signal.quote,
                )
            )
            report.messages_with_signal.add(signal.message_id)

    return report


def _reject_reason(
    signal: RawSignal,
    messages_by_id: dict[str, InputMessage],
    config: ScoringConfig,
) -> str | None:
    category = BY_KEY.get(signal.category)
    if category is None:
        # сюда же попадает всё, что модель попыталась вернуть по
        # запрещённым темам — они просто не входят в enum
        return "denied_or_unknown_category"

    message = messages_by_id.get(signal.message_id)
    if message is None:
        return "unknown_message_id"

    if message.is_forward:
        return "forwarded"
    if not signal.about_author:
        return "not_about_author"
    if signal.negated:
        # отрицание обнуляет сигнал и НЕ инвертирует его: отсутствие порока
        # не заслуга, а плюс за «не играю в казино» — тривиальная накрутка
        return "negated"
    if config.modality_multipliers.get(signal.modality, 0.0) <= 0.0:
        return "modality_zero"

    threshold = (
        config.min_confidence_positive
        if category.polarity is Polarity.POSITIVE
        else config.min_confidence_negative
    )
    if signal.confidence < threshold:
        return "low_confidence"

    if not quote_matches(signal.quote, message.text):
        return "quote_mismatch"

    return None
