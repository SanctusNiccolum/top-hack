"""
Клиент GigaChat: OAuth + chat/completions с ретраем.

Про TLS. Сертификаты Сбера подписаны «Russian Trusted Root CA», которого
нет в стандартном хранилище Windows и в certifi. Варианты в порядке
предпочтения:
  1. скачать корневой сертификат и указать путь в GIGACHAT_VERIFY_SSL;
  2. GIGACHAT_VERIFY_SSL=false — только для локальной отладки.
"""

from __future__ import annotations

import time
import uuid

import requests

from ..chunking import Chunk
from ..config import Settings
from ..prompts import REPAIR_PROMPT, build_messages
from ..schemas import ChunkResult
from .base import ChunkFailure, LLMError, parse_chunk_response


class GigaChatProvider:
    name = "gigachat"

    def __init__(self, settings: Settings):
        if not settings.gigachat_auth_key:
            raise LLMError(
                "GIGACHAT_AUTH_KEY не задан. Скопируй .env.example в .env и "
                "подставь ключ авторизации из личного кабинета GigaChat."
            )
        self.s = settings
        self.name = settings.gigachat_model
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._session = requests.Session()

        if settings.verify_ssl is False:
            # заглушаем предупреждение один раз, чтобы не засорять логи
            import urllib3

            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ---------------- авторизация ----------------

    def _get_token(self) -> str:
        # обновляем за 60 секунд до истечения — токен живёт 30 минут
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        try:
            response = self._session.post(
                self.s.gigachat_oauth_url,
                headers={
                    "Authorization": f"Basic {self.s.gigachat_auth_key}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                data={"scope": self.s.gigachat_scope},
                verify=self.s.verify_ssl,
                timeout=self.s.timeout_s,
            )
        except requests.RequestException as exc:
            raise LLMError(f"не удалось получить токен GigaChat: {exc}") from exc

        if response.status_code != 200:
            raise LLMError(
                f"OAuth вернул {response.status_code}: {response.text[:300]}. "
                "Проверь GIGACHAT_AUTH_KEY и GIGACHAT_SCOPE."
            )

        payload = response.json()
        self._token = payload["access_token"]
        # expires_at приходит в миллисекундах epoch
        self._token_expires_at = float(payload.get("expires_at", 0)) / 1000 or (
            time.time() + 1500
        )
        return self._token

    # ---------------- вызов модели ----------------

    def _complete(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self._session.post(
                self.s.gigachat_api_url,
                headers={
                    "Authorization": f"Bearer {self._get_token()}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": self.s.gigachat_model,
                    "messages": messages,
                    "temperature": self.s.temperature,
                    "top_p": self.s.top_p,
                    "repetition_penalty": 1.0,
                    "stream": False,
                },
                verify=self.s.verify_ssl,
                timeout=self.s.timeout_s,
            )
        except requests.RequestException as exc:
            raise LLMError(f"запрос к GigaChat не прошёл: {exc}") from exc

        if response.status_code == 401:
            self._token = None  # токен протух — пусть следующий вызов обновит
            raise LLMError("GigaChat вернул 401: токен недействителен")
        if response.status_code != 200:
            raise LLMError(f"GigaChat вернул {response.status_code}: {response.text[:300]}")

        return response.json()["choices"][0]["message"]["content"]

    def list_models(self) -> list[str]:
        """Какие модели реально доступны этому ключу. Нужна для команды
        `cli.py check`: избавляет от угадывания идентификатора модели."""
        try:
            response = self._session.get(
                self.s.gigachat_models_url,
                headers={"Authorization": f"Bearer {self._get_token()}", "Accept": "application/json"},
                verify=self.s.verify_ssl,
                timeout=self.s.timeout_s,
            )
        except requests.RequestException as exc:
            raise LLMError(f"запрос списка моделей не прошёл: {exc}") from exc

        if response.status_code != 200:
            raise LLMError(f"список моделей: {response.status_code} {response.text[:200]}")
        return [m["id"] for m in response.json().get("data", [])]

    def ping(self) -> str:
        """Минимальный запрос к модели — проверка, что связка ключ + модель
        + сертификаты работает целиком."""
        return self._complete([{"role": "user", "content": "Ответь одним словом: тест"}])

    def analyze_chunk(self, chunk: Chunk) -> ChunkResult:
        messages = build_messages(chunk)
        raw = self._complete(messages)

        try:
            return parse_chunk_response(raw, chunk)
        except ChunkFailure:
            if self.s.max_retries < 1:
                raise
            # один ретрай с repair-промптом: модель видит свой сломанный
            # ответ и переписывает его. Дальше чанк помечается failed и
            # учитывается в coverage, а не молча теряется.
            repair = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": REPAIR_PROMPT},
            ]
            return parse_chunk_response(self._complete(repair), chunk)
