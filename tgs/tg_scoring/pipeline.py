"""Оркестрация: вход бэкенда -> ответ бэкенду."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable

from .aggregator import aggregate
from .chunking import make_chunks
from .cleaning import clean_messages
from .config import Settings, get_settings
from .explain import build_explanation
from .llm.base import ChunkFailure, LLMError, LLMProvider
from .prefilter import build_vector_filter, run_prefilter
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ChunkResult,
    Coverage,
    Meta,
    RiskLevel,
    Status,
)
from .validation import validate_signals

log = logging.getLogger("tg_scoring")

# если модель «потеряла» больше трети чанка, ответ считается неполным
MIN_REVIEWED_RATIO = 0.66


def analyze(
    request: AnalyzeRequest,
    provider: LLMProvider,
    settings: Settings | None = None,
    on_signals: Callable[[list], None] | None = None,
) -> AnalyzeResponse:
    """`on_signals` получает список принятых сигналов после валидации.

    Нужен, чтобы сохранить их на диск и потом подбирать веса и пороги
    офлайн, не гоняя LLM заново: разметка — дорогая часть, арифметика —
    бесплатная. См. `cli.py tune`.
    """
    settings = settings or get_settings()
    config = settings.scoring
    started = time.perf_counter()

    def finish(
        status: Status,
        *,
        score_delta: float = 0.0,
        confidence: float = 0.0,
        risk: RiskLevel = RiskLevel.INSUFFICIENT_DATA,
        coverage: Coverage | None = None,
        meta: Meta | None = None,
        factors=None,
        risk_flags=None,
        error: str | None = None,
    ) -> AnalyzeResponse:
        factors = factors or []
        return AnalyzeResponse(
            request_id=request.request_id,
            status=status,
            score_delta=score_delta,
            confidence=round(confidence, 2),
            risk_level=risk,
            risk_flags=risk_flags or [],
            factors=factors,
            explanation_ru=build_explanation(status, factors, risk),
            coverage=coverage,
            meta=meta,
            error=error,
        )

    # ---- 0. согласие ----
    if not request.consent.granted:
        return finish(Status.NO_CONSENT)

    # ---- 1. очистка ----
    cleaned = clean_messages(request.messages, use_ner=settings.pii_use_ner)
    n_clean = len(cleaned.messages)
    log.info("очистка: %s -> %s (%s)", cleaned.stats.total_in, n_clean, cleaned.stats.dropped)

    base_coverage = Coverage(
        messages_analyzed=n_clean,
        messages_with_signal=0,
        period_days=request.source.period_days,
        coverage_factor=0.0,
    )

    if n_clean < config.min_messages_for_verdict:
        return finish(Status.INSUFFICIENT_DATA, coverage=base_coverage)

    # ---- 2. пре-фильтр ----
    vector_filter = build_vector_filter(settings.prefilter_use_vectors)
    prefiltered = run_prefilter(
        cleaned.messages,
        control_ratio=settings.prefilter_control_ratio,
        seed=settings.prefilter_seed,
        vector_filter=vector_filter,
    )
    log.info(
        "пре-фильтр: %s -> %s (маркеры %s, вектора %s, контроль %s)",
        prefiltered.total,
        len(prefiltered.selected),
        prefiltered.by_marker,
        prefiltered.by_vector,
        prefiltered.by_control,
    )

    # ---- 3. LLM по чанкам ----
    chunks = make_chunks(prefiltered.selected, settings.chunk_size)
    results: list[ChunkResult] = []
    failed = 0

    for chunk in chunks:
        try:
            result = provider.analyze_chunk(chunk)
            reviewed = len(set(result.reviewed_ids) & chunk.ids)
            if chunk.messages and reviewed / len(chunk.messages) < MIN_REVIEWED_RATIO:
                # модель просмотрела не весь чанк — один переспрос,
                # иначе часть сообщений молча выпадет из анализа
                log.warning("чанк %s просмотрен частично (%s/%s), переспрашиваю",
                            chunk.chunk_id, reviewed, len(chunk.messages))
                result = provider.analyze_chunk(chunk)
            results.append(result)
        except (ChunkFailure, LLMError) as exc:
            failed += 1
            log.warning("чанк %s не обработан: %s", chunk.chunk_id, exc)

    if chunks and failed == len(chunks):
        return finish(
            Status.ERROR,
            coverage=base_coverage,
            error="ни один чанк не удалось обработать — проверь доступ к GigaChat",
        )

    failed_ratio = failed / len(chunks) if chunks else 0.0

    # ---- 4. валидация ----
    messages_by_id = {m.id: m for m in cleaned.messages}
    report = validate_signals(results, messages_by_id, config)
    if on_signals is not None:
        on_signals(report.accepted)
    log.info("сигналов принято: %s, отклонено: %s", len(report.accepted), report.rejected)

    # ---- 5. агрегация ----
    score = aggregate(report.accepted, n_clean, config, failed_chunk_ratio=failed_ratio)
    factors = score.factors()

    mean_conf = (
        sum(s.confidence for s in report.accepted) / len(report.accepted)
        if report.accepted
        else 1.0
    )
    confidence = score.coverage_factor * (1.0 - failed_ratio) * mean_conf

    status = (
        Status.INSUFFICIENT_DATA
        if score.risk_level is RiskLevel.INSUFFICIENT_DATA
        else Status.OK
    )
    score_delta = 0.0 if status is Status.INSUFFICIENT_DATA else score.score_delta

    coverage = Coverage(
        messages_analyzed=n_clean,
        messages_with_signal=len(report.messages_with_signal),
        period_days=request.source.period_days,
        coverage_factor=score.coverage_factor,
    )
    meta = Meta(
        ruleset_version=request.ruleset_version or settings.ruleset_version,
        model=getattr(provider, "name", "unknown"),
        chunks_total=len(chunks),
        chunks_failed=failed,
        messages_sent_to_llm=len(prefiltered.selected),
        signals_rejected=dict(sorted(report.rejected.items())),
        processed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )

    return finish(
        status,
        score_delta=score_delta,
        confidence=confidence,
        risk=score.risk_level,
        coverage=coverage,
        meta=meta,
        factors=factors,
        risk_flags=score.risk_flags(),
    )
