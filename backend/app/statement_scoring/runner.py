"""Вызов statement_scoring (см. /statement_scoring в корне репозитория)
как OS-подпроцесса — тот же приём, что и с telegram_parser.

Почему подпроцессом, а не импортом: их `src/` — не пакет (нет
__init__.py), а импорты внутри плоские (`from features import ...`,
`from parser import ...`). Импортировать это из FastAPI можно только
через возню с sys.path, плюс модуль `parser` — опасное имя, легко
затенить чужой. Подпроцесс с cwd=src/ решает и то, и другое, и заодно
изолирует их тяжёлые зависимости (pandas/pdfplumber/sklearn) от кода
бэкенда.

В отличие от парсера Telegram здесь вызов СИНХРОННЫЙ: расчёт быстрый
(без сети), поэтому эндпоинт просто дожидается результата и сразу
отдаёт скор, без fire-and-forget и опроса статуса.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Локальный запуск backend без Docker; в контейнере переопределяется
# переменной STATEMENT_SCORING_DIR=/app/statement_scoring/src.
_DEFAULT_DIR = (
    Path(__file__).resolve().parents[3] / "statement_scoring" / "src"
)

SCORING_DIR = Path(
    os.environ.get("STATEMENT_SCORING_DIR", str(_DEFAULT_DIR))
)

# score.py считает скор в шкале 0..25, а анкетная ветка бэкенда — 0..100.
# Приводим к общей шкале, иначе ветки нельзя складывать между собой.
STATEMENT_SCORE_MAX = 25.0


class StatementScoringError(RuntimeError):
    """Выписку не удалось разобрать или посчитать."""


def _human_error(stderr: str) -> str:
    """Превращает traceback подпроцесса в фразу, которую не стыдно
    показать пользователю."""
    last_line = ""
    for line in reversed(stderr.splitlines()):
        if line.strip() and not line.startswith((" ", "\t")):
            last_line = line.strip()
            break

    # Файл вообще не открылся как PDF (битый, обрезанный, не тот формат).
    if "PDFSyntaxError" in stderr or "PSSyntaxError" in stderr:
        return (
            "Файл повреждён или не является корректным PDF. "
            "Выгрузите выписку из банковского приложения заново."
        )

    # Парсер отработал, но не нашёл ни одной операции — обычно это скан
    # (картинка без текстового слоя) или выписка другого банка.
    if "Не удалось извлечь ни одной операции" in stderr:
        return (
            "В файле не найдено ни одной операции. Убедитесь, что это "
            "выписка за 3 месяца в формате PDF с текстом, а не скан или "
            "фотография."
        )

    # Сообщение исключения без имени класса — оно обычно осмысленное.
    if ": " in last_line:
        return last_line.split(": ", 1)[1]

    return last_line or "Не удалось обработать выписку"


async def score_statement(pdf_path: Path) -> dict:
    """Возвращает {'final_score': float (0..100), 'ai_comment': str}."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "score.py",
        str(pdf_path),
        "--server",
        cwd=str(SCORING_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        details = stderr.decode("utf-8", "replace").strip()

        # Полный traceback — в лог, пользователю — одна внятная фраза:
        # traceback бесполезен фронту и светит внутренние пути наружу.
        logger.error("statement_scoring упал:\n%s", details)

        raise StatementScoringError(_human_error(details))

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise StatementScoringError(
            f"Не удалось разобрать ответ statement_scoring: {exc}"
        ) from exc

    raw_score = float(payload["final_score"])

    return {
        "final_score": round(raw_score / STATEMENT_SCORE_MAX * 100, 2),
        "raw_score": raw_score,
        "ai_comment": payload.get("ai_comment", ""),
    }
