"""
Расчёт дельты и уровня риска (§5 спеки).

Здесь и только здесь появляются числа. LLM в этот файл не заглядывает.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .categories import BY_KEY, HARD_RISK_KEYS
from .config import ScoringConfig
from .schemas import Factor, RiskLevel
from .validation import AcceptedSignal


@dataclass
class CategoryScore:
    category: str
    n_eff: float
    saturation: float
    contribution: float
    evidence_count: int


@dataclass
class ScoreResult:
    score_delta: float
    delta_raw: float
    coverage_factor: float
    risk_level: RiskLevel
    hard_negative: float
    categories: list[CategoryScore] = field(default_factory=list)

    def factors(self) -> list[Factor]:
        """Один список с подписанным вкладом, отсортированный по модулю:
        фронту сразу видно топ причин, склеивать два списка не нужно."""
        return [
            Factor(
                category=c.category,
                contribution=round(c.contribution, 1),
                evidence_count=c.evidence_count,
            )
            for c in sorted(self.categories, key=lambda c: -abs(c.contribution))
            if round(c.contribution, 1) != 0.0
        ]

    def risk_flags(self) -> list[Factor]:
        return [f for f in self.factors() if f.category in HARD_RISK_KEYS and f.contribution < 0]


def signal_weight(signal: AcceptedSignal, config: ScoringConfig) -> float:
    """Вес одного сигнала: уверенность модели, поправленная на модальность.

    Множителя свежести здесь нет. Окно анализа и так 90 дней, а внутри
    него экспоненциальный спад давал разброс 1.0 -> 0.37 — то есть
    «уволили в начале окна» весило втрое меньше «уволили вчера», хотя для
    кредитного решения это события одного порядка. Если окно когда-нибудь
    расширят до года, вернуть свежесть — это одна строка здесь и одно
    поле в контракте.
    """
    modality = config.modality_multipliers.get(signal.modality, 0.0)
    return signal.confidence * modality


def coverage_factor(n_clean: int, config: ScoringConfig) -> float:
    """Штраф за малый объём данных.

    Человек с 15 сообщениями в канале не должен получать ±25 — доверять
    там нечему. 640 сообщений -> 1.0; 50 -> 0.58; 20 -> 0.37.
    """
    if n_clean <= 0:
        return 0.0
    return min(1.0, math.sqrt(n_clean / config.coverage_target_messages))


def aggregate(
    signals: list[AcceptedSignal],
    messages_after_cleaning: int,
    config: ScoringConfig,
    failed_chunk_ratio: float = 0.0,
) -> ScoreResult:
    by_category: dict[str, list[AcceptedSignal]] = {}
    for s in signals:
        by_category.setdefault(s.category, []).append(s)

    scores: list[CategoryScore] = []
    for key, group in by_category.items():
        category = BY_KEY[key]
        n_eff = sum(signal_weight(s, config) for s in group)
        # насыщение: без него сорок упоминаний работы дают +320, и человек,
        # который просто много пишет, автоматически упирается в потолок
        saturation = 1.0 - math.exp(-n_eff / config.saturation_k)
        scores.append(
            CategoryScore(
                category=key,
                n_eff=n_eff,
                saturation=saturation,
                contribution=category.weight * saturation,
                evidence_count=len(group),
            )
        )

    delta_raw = sum(c.contribution for c in scores)
    # tanh гарантирует, что из диапазона не выйти ни при каком входе,
    # и делает границу мягкой, сохраняя чувствительность в середине шкалы
    delta_scaled = config.delta_limit * math.tanh(delta_raw / config.tanh_scale)
    coverage = coverage_factor(messages_after_cleaning, config)
    score_delta = round(delta_scaled * coverage, 1)

    hard_negative = abs(
        sum(c.contribution for c in scores if c.category in HARD_RISK_KEYS and c.contribution < 0)
    )

    if (
        messages_after_cleaning < config.min_messages_for_verdict
        or failed_chunk_ratio > config.max_failed_chunk_ratio
    ):
        risk = RiskLevel.INSUFFICIENT_DATA
    elif hard_negative >= config.risk_high_threshold:
        risk = RiskLevel.HIGH
    elif hard_negative >= config.risk_medium_threshold:
        risk = RiskLevel.MEDIUM
    else:
        risk = RiskLevel.LOW

    return ScoreResult(
        score_delta=score_delta,
        delta_raw=delta_raw,
        coverage_factor=round(coverage, 3),
        risk_level=risk,
        hard_negative=hard_negative,
        categories=scores,
    )
