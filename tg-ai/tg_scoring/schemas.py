"""
Контракты вход/выход (§2, §3, §6 спеки).

Три границы:
  бэкенд -> модуль : AnalyzeRequest
  LLM    -> модуль : ChunkResult
  модуль -> бэкенд : AnalyzeResponse
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
#  Вход: бэкенд -> модуль
# ============================================================

class Consent(BaseModel):
    granted: bool
    granted_at: str | None = None
    scope: list[str] = Field(default_factory=list)


class Source(BaseModel):
    kind: Literal["channel", "chat"] = "channel"
    period_days: int = 90
    messages_raw: int | None = None
    messages_after_cleaning: int | None = None
    lang_primary: str = "ru"


class InputMessage(BaseModel):
    id: str
    text: str
    # Времени в контракте нет намеренно. Окно анализа — 90 дней, и внутри
    # такого короткого окна взвешивать сигналы по свежести смысла мало:
    # разброс множителя получался больше, чем реальная разница между
    # «месяц назад» и «вчера». Отсечение по окну делает бэкенд на выгрузке.
    is_forward: bool = False
    is_reply: bool = False
    char_len: int | None = None


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request_id: str
    consent: Consent
    source: Source = Field(default_factory=Source)
    messages: list[InputMessage]
    ruleset_version: str | None = None


# ============================================================
#  Выход LLM: один чанк
# ============================================================

class Modality(str, Enum):
    FACT = "fact"
    INTENTION = "intention"
    HYPOTHETICAL = "hypothetical"
    QUOTE_OR_JOKE = "quote_or_joke"


class RawSignal(BaseModel):
    """Сигнал в том виде, в каком его вернула модель. Ещё не проверен."""

    model_config = ConfigDict(extra="ignore")

    message_id: str
    category: str
    confidence: float
    about_author: bool = True
    modality: str = Modality.FACT.value
    negated: bool = False
    quote: str = ""


class ChunkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: int
    signals: list[RawSignal] = Field(default_factory=list)
    reviewed_ids: list[str] = Field(default_factory=list)
    no_signal_count: int = 0


# ============================================================
#  Выход: модуль -> бэкенд
# ============================================================

class Status(str, Enum):
    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    NO_CONSENT = "no_consent"
    ERROR = "error"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INSUFFICIENT_DATA = "insufficient_data"


class Factor(BaseModel):
    category: str
    contribution: float
    evidence_count: int


class Coverage(BaseModel):
    messages_analyzed: int
    messages_with_signal: int
    period_days: int
    coverage_factor: float


class Meta(BaseModel):
    ruleset_version: str
    model: str
    chunks_total: int
    chunks_failed: int
    messages_sent_to_llm: int
    signals_rejected: dict[str, int]
    processed_at: str
    duration_ms: int


class AnalyzeResponse(BaseModel):
    request_id: str
    status: Status
    score_delta: float
    confidence: float
    risk_level: RiskLevel
    risk_flags: list[Factor] = Field(default_factory=list)
    factors: list[Factor] = Field(default_factory=list)
    explanation_ru: str = ""
    coverage: Coverage | None = None
    meta: Meta | None = None
    error: str | None = None
