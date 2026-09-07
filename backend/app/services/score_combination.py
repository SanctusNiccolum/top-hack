"""Сведение веток скоринга в один итоговый балл.

Ветки считаются независимо и в разных местах:
  - анкета   — app/services/scoring.py            (шкала 0..100)
  - выписка  — statement_scoring/ (подпроцесс)    (0..25, приводится к 0..100)
  - telegram — tg-ai/ (HTTP-сервис на GigaChat)   (ПОПРАВКА −25..+25)

Telegram устроен принципиально иначе, чем две другие ветки, и это не
случайность: он не даёт самостоятельной оценки платёжеспособности, а
корректирует её («часто пишете о проектах — +10 баллов», гэмблинг —
минус). Поэтому он не усредняется наравне с остальными, а прибавляется
к их среднему. Если бы он был третьей усредняемой веткой, нейтральный
Telegram (дельта 0, переведённая в 50 баллов) тянул бы вниз хорошего
заёмщика — то есть отсутствие плохих новостей выглядело бы как плохая
новость.

Вес считается только по тем базовым веткам, которые реально посчитаны:
если пользователь не загрузил выписку, её вес переходит на анкету, а не
обнуляет часть итога.
"""
from decimal import Decimal, ROUND_HALF_UP

# Базовые ветки — обе про деньги и обе самодостаточны, поэтому равные.
WEIGHTS = {
    "survey": Decimal("0.5"),
    "statement": Decimal("0.5"),
}

SCORE_MIN = Decimal("0")
SCORE_MAX = Decimal("100")


def combine_scores(
    survey_score: Decimal | None,
    statement_score: Decimal | None,
    telegram_delta: Decimal | None = None,
) -> Decimal | None:
    """Итоговый скор 0..100, или None, если нет ни одной базовой ветки.

    telegram_delta — поправка в диапазоне −25..+25, прибавляется к
    средневзвешенному базовых веток. Итог обрезается в [0, 100]: без
    этого 95 + 25 дало бы 120, а 10 − 25 ушло бы в минус.
    """
    branches = {
        "survey": survey_score,
        "statement": statement_score,
    }

    available = {
        name: Decimal(str(value))
        for name, value in branches.items()
        if value is not None
    }

    if not available:
        # Одной только поправки Telegram недостаточно: корректировать
        # нечего, пока нет ни анкеты, ни выписки.
        return None

    total_weight = sum(
        (WEIGHTS[name] for name in available),
        Decimal("0"),
    )

    weighted = sum(
        (value * WEIGHTS[name] for name, value in available.items()),
        Decimal("0"),
    )

    score = weighted / total_weight

    if telegram_delta is not None:
        score += Decimal(str(telegram_delta))

    score = max(SCORE_MIN, min(SCORE_MAX, score))

    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
