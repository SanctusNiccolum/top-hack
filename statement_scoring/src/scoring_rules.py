# -*- coding: utf-8 -*-
"""
scoring_rules.py — расчёт платёжеспособности по признакам из features.py.

Формула повторяет архитектуру анкетной ветки скоринга (трёхслойный
расчёт: доход → база по ПДН → корректирующие коэффициенты), только на
вход вместо ответов анкеты идут признаки, извлечённые из выписки:

    Слой 1 (доход):
        Дч_скорр = avg_monthly_income × K_доход

    Слой 2 (база):
        ПДН = estimated_monthly_debt_payment / Дч_скорр × 100
        База = clamp(100 − ПДН, 0, 100)

    Слой 3 (коэффициенты надёжности):
        K_итог = произведение коэффициентов ниже

    Итог:
        Скор = clamp(База × K_итог, 0, 100)

Часть коэффициентов Слоя 3 — прямые аналоги вопросов анкеты и взяты с
теми же значениями (регулярность дохода, кредитная история,
просрочки): соответствующий вопрос анкеты и соответствующий признак
выписки измеряют одно и то же с разных сторон. Остальные коэффициенты
(структура счёта, норма сбережений) введены отдельно — в анкете для
них нет и не может быть аналогичного вопроса, они видны только по
факту движений по счёту.
Скор возвращается в диапазоне 0–25 (не 0–100). Внутренние величины
слоя 2 (ПДН, база) остаются в процентах 0–100, как и положено ПДН —
в проценты переводится только финальное число, на последнем шаге.
"""

from __future__ import annotations

from dataclasses import dataclass

CLAMP_MIN, CLAMP_MAX = 0.0, 100.0
FINAL_SCORE_MAX = 25.0


def _clamp(x: float, lo: float = CLAMP_MIN, hi: float = CLAMP_MAX) -> float:
    return max(lo, min(hi, x))


@dataclass
class ScoreFactor:
    name: str
    value: float
    comment_ru: str


def _income_verification_k(cash_deposit_share: float) -> ScoreFactor:
    """Слой 1: насколько подтверждаем источник дохода — аналог пары
    «Источник дохода» + «НПД-статус» из анкеты. По выписке источник
    напрямую не спросишь, но доля поступлений в виде внесения
    наличных — рабочий прокси: чем она выше, тем меньше доход
    подтверждён документально."""
    if cash_deposit_share < 0.15:
        return ScoreFactor(
            "Подтверждаемость источника дохода (cash_deposit_share)", 1.00,
            "доход поступает преимущественно безналичным путём — источник прослеживается",
        )
    if cash_deposit_share < 0.40:
        return ScoreFactor(
            "Подтверждаемость источника дохода (cash_deposit_share)", 0.97,
            "часть дохода — внесение наличных",
        )
    if cash_deposit_share < 0.70:
        return ScoreFactor(
            "Подтверждаемость источника дохода (cash_deposit_share)", 0.90,
            "существенная доля дохода — внесение наличных, источник не подтверждается",
        )
    return ScoreFactor(
        "Подтверждаемость источника дохода (cash_deposit_share)", 0.80,
        "доход почти полностью в виде внесения наличных",
    )


def _income_regularity_k(income_cv: float) -> ScoreFactor:
    """Слой 3: аналог вопроса «Регулярность дохода» из анкеты — те же
    значения коэффициентов (1.10 / 1.08 / 0.90 / 0.80 / 0.50), но
    определяются коэффициентом вариации дохода по месяцам, а не
    выбором варианта ответа."""
    if income_cv < 0.12:
        return ScoreFactor("Регулярность дохода (income_cv)", 1.10, "доход стабилен от месяца к месяцу")
    if income_cv < 0.25:
        return ScoreFactor("Регулярность дохода (income_cv)", 1.08, "доход поступает регулярно")
    if income_cv < 0.45:
        return ScoreFactor("Регулярность дохода (income_cv)", 0.90, "доход умеренно колеблется по месяцам")
    if income_cv < 0.75:
        return ScoreFactor("Регулярность дохода (income_cv)", 0.80, "доход поступает нерегулярно")
    return ScoreFactor("Регулярность дохода (income_cv)", 0.50, "постоянного дохода по выписке не прослеживается")


def _credit_history_k(risk_tx_count: int, risk_amount_share: float, debt_series_count: int) -> ScoreFactor:
    """Слой 3: аналог пары «Кредитная история» + «Просрочки» из
    анкеты. Данных о просрочках по выписке нет, поэтому ближайший по
    силе наблюдаемый сигнал риска — операции с признаками МФО, ставок,
    казино или криптообмена."""
    if risk_tx_count > 0 and risk_amount_share > 0.15:
        return ScoreFactor(
            "Кредитная история и риск-операции", 0.65,
            f"найдено {risk_tx_count} операций с признаками МФО/ставок/казино/крипты, "
            f"на них приходится {risk_amount_share*100:.0f}% оборота",
        )
    if risk_tx_count > 0:
        return ScoreFactor(
            "Кредитная история и риск-операции", 0.80,
            f"найдено {risk_tx_count} операций с признаками МФО/ставок/казино/крипты",
        )
    if debt_series_count >= 1:
        return ScoreFactor(
            "Кредитная история и риск-операции", 1.05,
            "обнаружены регулярные платежи, похожие на плановое погашение кредита — обслуживается штатно",
        )
    return ScoreFactor(
        "Кредитная история и риск-операции", 0.95,
        "признаков действующих кредитов или займов не найдено",
    )


def _account_structure_k(large_expense_share: float, max_income_share: float, round_amount_share: float) -> ScoreFactor:
    """Слой 3: коэффициент без аналога в анкете — виден только по
    структуре движений на счёте. Если почти весь оборот формируют
    одна-две операции, а не повседневные траты, это больше похоже на
    транзитный счёт, чем на обычное потребительское поведение."""
    if large_expense_share > 0.7 or max_income_share > 0.6:
        return ScoreFactor(
            "Концентрация оборота (large_expense_share / max_income_share)", 0.75,
            "почти весь оборот формируют одна-две крупные операции, а не регулярные бытовые траты",
        )
    if round_amount_share > 0.5:
        return ScoreFactor(
            "Круглые суммы в операциях (round_amount_share)", 0.90,
            "больше половины операций — круглые суммы, что нетипично для бытовых трат",
        )
    return ScoreFactor("Структура оборота счёта", 1.00, "оборот распределён по операциям равномерно")


def _savings_rate_k(savings_rate: float) -> ScoreFactor:
    """Слой 3: коэффициент без аналога в анкете — норма сбережений
    видна только по факту движений по счёту."""
    if savings_rate >= 0.20:
        return ScoreFactor("Норма сбережений (savings_rate)", 1.10, f"после расходов остаётся ≈{savings_rate*100:.0f}% дохода")
    if savings_rate >= 0.0:
        return ScoreFactor("Норма сбережений (savings_rate)", 1.00, f"расходы близки к доходу, остаток ≈{savings_rate*100:.0f}%")
    if savings_rate >= -0.20:
        return ScoreFactor("Норма сбережений (savings_rate)", 0.90, f"расходы превышают доход на ≈{-savings_rate*100:.0f}%")
    return ScoreFactor("Норма сбережений (savings_rate)", 0.75, f"расходы существенно превышают доход (на ≈{-savings_rate*100:.0f}%)")


def _category_diversity_k(category_entropy: float) -> ScoreFactor:
    """Слой 3: аналог вопроса «Подписки» из анкеты — тот же диапазон
    коэффициентов (0.95–1.05), источник сигнала другой: разнообразие
    категорий бытовых трат вместо списка подписок."""
    if category_entropy > 1.3:
        return ScoreFactor("Разнообразие трат (category_entropy)", 1.05, "траты распределены по разным бытовым категориям")
    if category_entropy > 0.7:
        return ScoreFactor("Разнообразие трат (category_entropy)", 1.00, "траты умеренно разнообразны")
    return ScoreFactor("Разнообразие трат (category_entropy)", 0.95, "траты сконцентрированы в одной-двух категориях")


def score_from_features(f: dict) -> tuple[float, list[ScoreFactor], dict]:
    """Считает итоговый скор по признакам одной выписки.

    Возвращает (скор 0..25, список коэффициентов слоя 3 для отчёта,
    словарь с промежуточными величинами — скорректированный доход,
    ПДН, база 0..100, суммарный K).
    """
    income = max(f["avg_monthly_income"], 0.0)

    income_k = _income_verification_k(f["cash_deposit_share"])
    dch_corr = income * income_k.value

    if dch_corr > 0:
        pdn = _clamp(f["estimated_monthly_debt_payment"] / dch_corr * 100, 0, 500)
        base = _clamp(100 - pdn, 0, 100)
    else:
        pdn = None
        base = 60.0  # доход не определён — нейтральная база, как и в анкетной ветке

    factors = [
        income_k,
        _income_regularity_k(f["income_cv"]),
        _credit_history_k(f["risk_tx_count"], f["risk_amount_share"], f["debt_series_count"]),
        _account_structure_k(f["large_expense_share"], f["max_income_share"], f["round_amount_share"]),
        _savings_rate_k(f["savings_rate"]),
        _category_diversity_k(f["category_entropy"]),
    ]

    k_total = 1.0
    for factor in factors:
        k_total *= factor.value

    score_100 = _clamp(base * k_total)
    score = _clamp(score_100 * (FINAL_SCORE_MAX / 100.0), 0.0, FINAL_SCORE_MAX)
    debug = {"dch_corr": round(dch_corr, 2), "pdn": round(pdn, 2) if pdn is not None else None,
             "base": round(base, 2), "k_total": round(k_total, 4)}
    return score, factors, debug


def verdict(score: float) -> str:
    if score >= 0.70 * FINAL_SCORE_MAX:
        return "высокая платёжеспособность"
    if score >= 0.40 * FINAL_SCORE_MAX:
        return "средняя платёжеспособность"
    return "низкая платёжеспособность"
