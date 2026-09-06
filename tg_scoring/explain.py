"""
Объяснение для пользователя (§6 спеки).

Собирается из шаблонов, а не генерируется свободно. Свободная генерация —
самое вероятное место, где модуль соврёт про причины решения; шаблон с
подстановкой числа упоминаний врать не умеет.

Если захочется живого языка — сделай отдельный лёгкий вызов LLM, который
ПЕРЕФРАЗИРУЕТ готовый текст отсюда, не имея доступа к исходным сообщениям.

Формулировки намеренно описывают поведение, а не ставят диагноз:
«регулярные упоминания ставок», но не «признаки игровой зависимости» —
второе относится к здоровью, а это запрещённая тема (см. categories.py).
"""

from __future__ import annotations

from .categories import BY_KEY
from .schemas import Factor, RiskLevel, Status

PHRASES: dict[str, str] = {
    "employment_stable": "упоминания постоянной работы",
    "obligation_fulfilled": "упоминания о погашенных кредитах",
    "income_regular": "регулярные поступления дохода",
    "financial_planning": "признаки планирования накоплений",
    "business_activity": "деловую активность с собственными заказами",
    "education_active": "активную учёбу",
    "long_horizon_planning": "долгосрочные планы",
    "gambling": "регулярные упоминания ставок",
    "debt_distress": "упоминания сложностей с текущими платежами",
    "microloan_reliance": "обращения к микрозаймам",
    "income_instability": "признаки нестабильного дохода",
    "job_loss": "упоминания потери работы",
    "impulsive_spending": "импульсивные траты сразу после поступления средств",
    "high_risk_speculation": "участие в высокорисковых финансовых операциях",
}

_RISK_TAIL = {
    RiskLevel.HIGH: " Совокупность этих признаков заметно повышает оценку риска.",
    RiskLevel.MEDIUM: " Эти признаки умеренно повышают оценку риска.",
    RiskLevel.LOW: "",
    RiskLevel.INSUFFICIENT_DATA: "",
}


# Фразы намеренно без запятых и без союза "и" внутри: иначе перечисление
# из двух элементов читается как "ставок и азартных игр и траты".
def _enumerate(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " и " + phrases[-1]


def build_explanation(
    status: Status,
    factors: list[Factor],
    risk_level: RiskLevel,
    max_factors: int = 3,
) -> str:
    if status is Status.NO_CONSENT:
        return "Анализ не проводился: пользователь не дал согласия на обработку канала."
    if status is Status.INSUFFICIENT_DATA:
        return (
            "Сообщений за последние три месяца слишком мало, чтобы делать выводы. "
            "Оценка по этому источнику не изменена."
        )
    if status is Status.ERROR:
        return "Анализ не удалось завершить, оценка по этому источнику не изменена."
    if not factors:
        return (
            "Значимых финансовых сигналов в канале не найдено. "
            "Оценка по этому источнику не изменена."
        )

    top = factors[:max_factors]
    positive = [PHRASES.get(f.category, BY_KEY[f.category].title_ru) for f in top if f.contribution > 0]
    negative = [PHRASES.get(f.category, BY_KEY[f.category].title_ru) for f in top if f.contribution < 0]

    parts: list[str] = []
    if positive:
        parts.append(f"За последние три месяца мы нашли {_enumerate(positive)} — это повышает оценку.")
    if negative:
        lead = "При этом встречаются" if positive else "За последние три месяца встречаются"
        parts.append(f"{lead} {_enumerate(negative)} — это снижает оценку.")

    return " ".join(parts) + _RISK_TAIL.get(risk_level, "")
