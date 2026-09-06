"""Настройки модуля. Читаются из .env / переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # python-dotenv не обязателен, если переменные заданы снаружи
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None or not raw.strip() else int(raw)


@dataclass(frozen=True)
class ScoringConfig:
    """Параметры формулы (§5 спеки). Меняются вместе с ruleset_version."""

    # порог уверенности: для негативных выше — ложный минус дороже ложного плюса
    min_confidence_positive: float = 0.60
    min_confidence_negative: float = 0.70

    # множители модальности
    modality_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "fact": 1.0,
            "intention": 0.4,
            "hypothetical": 0.15,
            "quote_or_joke": 0.0,
        }
    )

    # sat = 1 - exp(-n_eff / k).
    # k=3.0, а не 2.0: после отказа от взвешивания по свежести каждый
    # сигнал стал весить примерно вдвое больше (раньше множитель свежести
    # съедал 30-50%), и на прежнем k все категории насыщались заметно
    # быстрее. k=3.0 возвращает шкалу к исходной калибровке.
    saturation_k: float = 3.0
    # delta = 25 * tanh(delta_raw / tanh_scale).
    # ГЛАВНАЯ ручка строгости. Меньше значение — круче кривая, то есть тот
    # же набор сигналов даёт большую по модулю дельту. Пропорции между
    # категориями при этом не едут, меняется только общий масштаб.
    tanh_scale: float = 20.0
    delta_limit: float = 25.0

    # coverage = min(1, sqrt(N / coverage_target_messages)).
    # Этот множитель применяется к ГОТОВОЙ дельте, поэтому он, а не порог
    # ниже, решает, будет ли на маленькой выборке видно хоть что-то.
    coverage_target_messages: int = 150

    # Ниже этого числа сообщений (ПОСЛЕ очистки) модуль возвращает
    # insufficient_data и нулевую дельту вместо того, чтобы гадать.
    min_messages_for_verdict: int = 10
    max_failed_chunk_ratio: float = 0.25

    risk_high_threshold: float = 9.0       # по модулю жёсткого негатива
    risk_medium_threshold: float = 4.0


@dataclass(frozen=True)
class Settings:
    # --- GigaChat ---
    gigachat_auth_key: str = field(default_factory=lambda: os.getenv("GIGACHAT_AUTH_KEY", ""))
    gigachat_scope: str = field(default_factory=lambda: os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"))
    gigachat_model: str = field(default_factory=lambda: os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro"))
    gigachat_oauth_url: str = field(
        default_factory=lambda: os.getenv(
            "GIGACHAT_OAUTH_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        )
    )
    # С 17 июля 2026 для новых подключений используется https://api.giga.chat
    # Старый адрес gigachat.devices.sberbank.ru продолжает работать у тех,
    # кто подключился раньше, но новые интеграции туда не заводят.
    gigachat_base_url: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_BASE_URL", "https://api.giga.chat").rstrip("/")
    )
    gigachat_api_url_override: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_API_URL", "")
    )
    gigachat_verify_ssl_raw: str = field(
        default_factory=lambda: os.getenv("GIGACHAT_VERIFY_SSL", "false")
    )

    # --- пайплайн ---
    ruleset_version: str = field(default_factory=lambda: os.getenv("RULESET_VERSION", "1.0.0"))
    chunk_size: int = field(default_factory=lambda: _env_int("CHUNK_SIZE", 40))
    temperature: float = field(default_factory=lambda: _env_float("LLM_TEMPERATURE", 0.1))
    top_p: float = field(default_factory=lambda: _env_float("LLM_TOP_P", 0.1))
    max_retries: int = field(default_factory=lambda: _env_int("LLM_MAX_RETRIES", 1))
    timeout_s: int = field(default_factory=lambda: _env_int("LLM_TIMEOUT_S", 60))

    prefilter_control_ratio: float = field(
        default_factory=lambda: _env_float("PREFILTER_CONTROL_RATIO", 0.10)
    )
    prefilter_seed: int = field(default_factory=lambda: _env_int("PREFILTER_SEED", 42))

    pii_use_ner: bool = field(default_factory=lambda: _env_bool("PII_USE_NER", False))
    prefilter_use_vectors: bool = field(
        default_factory=lambda: _env_bool("PREFILTER_USE_VECTORS", False)
    )

    scoring: ScoringConfig = field(
        default_factory=lambda: ScoringConfig(
            min_messages_for_verdict=_env_int("MIN_MESSAGES_FOR_VERDICT", 10),
            coverage_target_messages=_env_int("COVERAGE_TARGET_MESSAGES", 150),
            tanh_scale=_env_float("TANH_SCALE", 20.0),
            saturation_k=_env_float("SATURATION_K", 3.0),
            min_confidence_positive=_env_float("MIN_CONFIDENCE_POSITIVE", 0.60),
            min_confidence_negative=_env_float("MIN_CONFIDENCE_NEGATIVE", 0.70),
        )
    )

    @property
    def gigachat_api_url(self) -> str:
        return self.gigachat_api_url_override or f"{self.gigachat_base_url}/v1/chat/completions"

    @property
    def gigachat_models_url(self) -> str:
        return f"{self.gigachat_base_url}/v1/models"

    @property
    def verify_ssl(self) -> bool | str:
        """requests принимает bool или путь к CA-бандлу."""
        raw = self.gigachat_verify_ssl_raw.strip()
        if raw.lower() in {"", "false", "0", "no", "off"}:
            return False
        if raw.lower() in {"true", "1", "yes", "on"}:
            return True
        return raw  # путь к сертификату


def get_settings() -> Settings:
    return Settings()
