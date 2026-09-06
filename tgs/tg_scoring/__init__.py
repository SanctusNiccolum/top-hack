"""Модуль альтернативного скоринга по Telegram-каналу."""

from .config import Settings, get_settings
from .pipeline import analyze
from .schemas import AnalyzeRequest, AnalyzeResponse

__all__ = ["analyze", "AnalyzeRequest", "AnalyzeResponse", "Settings", "get_settings"]
__version__ = "1.0.0"
