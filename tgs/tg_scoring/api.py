"""
HTTP-обёртка для бэкенда.

Запуск:
    uvicorn tg_scoring.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .config import get_settings
from .llm import GigaChatProvider, LLMError
from .pipeline import analyze
from .schemas import AnalyzeRequest, AnalyzeResponse, RiskLevel, Status

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Telegram Scoring Module",
    version="1.0.0",
    description="Дельта кредитного рейтинга по публичному Telegram-каналу пользователя",
)

_provider: GigaChatProvider | None = None


def get_provider() -> GigaChatProvider:
    """Ленивая инициализация: провайдер создаётся при первом запросе,
    а не на импорте — иначе сервис не поднимется без ключа."""
    global _provider
    if _provider is None:
        _provider = GigaChatProvider(get_settings())
    return _provider


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "ruleset_version": settings.ruleset_version,
        "model": settings.gigachat_model,
        "gigachat_key_configured": bool(settings.gigachat_auth_key),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    settings = get_settings()
    try:
        provider = get_provider()
    except LLMError as exc:
        # 200 с status=error, а не 5xx: для бэкенда недоступность этого
        # модуля — штатная ситуация, скоринг должен считаться и без него
        return AnalyzeResponse(
            request_id=request.request_id,
            status=Status.ERROR,
            score_delta=0.0,
            confidence=0.0,
            risk_level=RiskLevel.INSUFFICIENT_DATA,
            explanation_ru="Анализ не удалось завершить, оценка по этому источнику не изменена.",
            error=str(exc),
        )
    return analyze(request, provider, settings)
