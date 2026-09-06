"""Сведение трёх веток скоринга в один итоговый балл.

Ветки считаются независимо и в разных местах:
  - анкета   — app/services/scoring.py            (шкала 0..100)
  - выписка  — statement_scoring/ (подпроцесс)    (0..25, приводится к 0..100)
  - telegram — по данным telegram_parser          (0..100)

Здесь они складываются в одно число. Ключевая деталь: вес считается
только по тем веткам, которые реально посчитаны. Если пользователь не
загрузил выписку, её вес распределяется между остальными ветками, а не
обнуляет часть итога — иначе отсутствие данных выглядело бы как плохой
результат.
"""
from decimal import Decimal, ROUND_HALF_UP

# Подобраны как разумный старт: объективные банковские данные (выписка)
# и анкета весят одинаково, Telegram — вспомогательная корректировка.
WEIGHTS = {
    "survey": Decimal("0.4"),
    "statement": Decimal("0.4"),
    "telegram": Decimal("0.2"),
}


def combine_scores(
    survey_score: Decimal | None,
    statement_score: Decimal | None,
    telegram_score: Decimal | None,
) -> Decimal | None:
    """Возвращает итоговый скор 0..100 или None, если нет ни одной ветки."""
    branches = {
        "survey": survey_score,
        "statement": statement_score,
        "telegram": telegram_score,
    }

    available = {
        name: Decimal(str(value))
        for name, value in branches.items()
        if value is not None
    }

    if not available:
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

    score = max(Decimal("0"), min(Decimal("100"), score))

    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
