# -*- coding: utf-8 -*-
"""
features.py — превращает DataFrame операций (см. parser.py) в вектор
признаков для модели скоринга.

Признаки сгруппированы в пять смысловых блоков — это соответствует
ветке «Выписка карты (3 мес) → Feature Engineering» на схеме пайплайна:

  1. Доход        — сколько, как часто, насколько предсказуемо.
  2. Расходы       — структура трат, доля обязательных/дискреционных категорий.
  3. Денежный поток — баланс приход/расход, норма сбережений, волатильность.
  4. Долговая нагрузка (прокси) — обнаружение периодических платежей похожих
     на погашение кредита/займа, без явного поля «текущие платежи» —
     именно то, чего анкете не хватало (см. предыдущий калькулятор ПДН).
  5. Риск-флаги    — ключевые слова МФО/ставки/казино, аномально крупные и
     круглые движения средств, высокая доля наличных.

Все признаки — числа, без утечки целевой переменной; функция
`extract_features` не знает и не должна знать, как трактуется скор.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

# --- справочники категорий -------------------------------------------------

ESSENTIAL_CATEGORIES = {
    "Супермаркеты", "Транспорт", "Здоровье и красота", "Аптеки",
    "ЖКХ и связь", "Связь", "Топливо", "Автозаправки",
}
DISCRETIONARY_CATEGORIES = {
    "Рестораны и кафе", "Развлечения", "Одежда и обувь", "Электроника",
    "Путешествия", "Хобби",
}
CASH_CATEGORIES = {"Внесение наличных", "Снятие наличных"}

RISK_KEYWORDS = re.compile(
    r"мфо|займ|zaym|money\s?man|webbankir|migcredit|kazino|казино|"
    r"ставк|букмекер|1xbet|fonbet|winline|покер|poker|"
    r"crypto|криптовалют|bitcoin|бинанс|binance|"
    r"ломбард",
    re.IGNORECASE,
)

# Ключевые слова в имени контрагента, по которым правдоподобно, что
# регулярный исходящий платёж — это погашение кредита/займа, а не просто
# повторяющийся перевод другу.
DEBT_PAYEE_KEYWORDS = re.compile(
    r"банк|bank|мфо|займ|zaym|credit|кредит|финанс",
    re.IGNORECASE,
)


@dataclass
class FeatureSet:
    values: dict

    def to_series(self) -> pd.Series:
        return pd.Series(self.values)


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b not in (0, 0.0) else default


def _shannon_entropy(shares: pd.Series) -> float:
    p = shares[shares > 0]
    if p.empty:
        return 0.0
    return float(-(p * np.log(p)).sum())


def _detect_recurring_debt_payments(df: pd.DataFrame) -> tuple[float, int]:
    """
    Ищет среди исходящих операций серии похожих по сумме платежей одному и
    тому же контрагенту с более-менее регулярным интервалом — это рабочий
    прокси для «текущих ежемесячных платежей по кредитам», которые в
    выписке никак отдельно не помечены.

    Возвращает: (оценка суммы ежемесячных платежей по долгам, число серий).
    """
    out = df[df.direction == "out"].copy()
    if out.empty:
        return 0.0, 0

    total_days = max((df.date.max() - df.date.min()).days, 1)
    months = max(total_days / 30.0, 1e-6)

    monthly_estimate = 0.0
    n_series = 0

    for payee, grp in out.groupby("counterparty"):
        if len(grp) < 2:
            continue
        amounts = grp["amount"].abs()
        cv = amounts.std(ddof=0) / amounts.mean() if amounts.mean() else np.inf
        looks_like_bank = bool(DEBT_PAYEE_KEYWORDS.search(str(payee)))
        # Похоже на регулярный платёж: сумма стабильна (низкий разброс)
        # И (контрагент похож на банк/МФО ИЛИ платежей достаточно много,
        # чтобы это не было совпадением).
        if cv <= 0.05 and (looks_like_bank or len(grp) >= 3):
            n_series += 1
            monthly_estimate += amounts.sum() / months

    return round(monthly_estimate, 2), n_series


def _round_amount_share(df: pd.DataFrame) -> float:
    """Доля операций с «круглыми» суммами (кратны 1000) — слабый сигнал
    неорганических/ненативных для повседневных трат движений денег."""
    amounts = df["amount"].abs()
    if amounts.empty:
        return 0.0
    is_round = (amounts % 1000 == 0) & (amounts >= 1000)
    return float(is_round.mean())


def extract_features(df: pd.DataFrame) -> FeatureSet:
    if df.empty:
        raise ValueError("Пустой набор операций — нечего анализировать.")

    period_days = max((df.date.max() - df.date.min()).days, 1)
    months = max(period_days / 30.0, 1e-6)

    income = df[df.direction == "in"]
    expense = df[df.direction == "out"]

    total_income = income["amount"].sum()
    total_expense = -expense["amount"].sum()
    avg_monthly_income = total_income / months
    avg_monthly_expense = total_expense / months

    # --- 1. Доход ------------------------------------------------------
    income_tx_count = len(income)
    income_per_month = income.groupby(income["date"].dt.to_period("M"))["amount"].sum()
    income_cv = _safe_div(income_per_month.std(ddof=0), income_per_month.mean(), default=1.0)

    if income_tx_count >= 2:
        gaps = income.sort_values("date")["date"].diff().dt.days.dropna()
        income_gap_std = float(gaps.std(ddof=0)) if len(gaps) > 1 else 0.0
    else:
        income_gap_std = 999.0  # одна операция дохода — регулярность неизвестна/плохая

    cash_deposit_amount = income[income.category.isin(CASH_CATEGORIES)]["amount"].sum()
    cash_deposit_share = _safe_div(cash_deposit_amount, total_income)

    max_income_share = _safe_div(income["amount"].max() if income_tx_count else 0, total_income)

    # --- 2. Расходы ------------------------------------------------------
    expense_tx_count = len(expense)
    cat_spend = expense.groupby("category")["amount"].sum().abs()
    cat_shares = cat_spend / cat_spend.sum() if cat_spend.sum() else cat_spend
    category_entropy = _shannon_entropy(cat_shares)

    essential_spend = cat_spend[cat_spend.index.isin(ESSENTIAL_CATEGORIES)].sum()
    discretionary_spend = cat_spend[cat_spend.index.isin(DISCRETIONARY_CATEGORIES)].sum()
    essential_share = _safe_div(essential_spend, total_expense)
    discretionary_share = _safe_div(discretionary_spend, total_expense)

    avg_expense_amount = expense["amount"].abs().mean() if expense_tx_count else 0.0
    large_expense_share = _safe_div(
        expense.loc[expense["amount"].abs() > 3 * avg_expense_amount, "amount"].abs().sum()
        if avg_expense_amount else 0.0,
        total_expense,
    )

    # --- 3. Денежный поток -------------------------------------------------
    net_cashflow = total_income - total_expense
    savings_rate = _safe_div(net_cashflow, total_income)
    expense_income_ratio = _safe_div(total_expense, total_income, default=99.0)

    daily_net = df.set_index("date").resample("D")["amount"].sum()
    balance_path = daily_net.cumsum()
    balance_volatility = float(balance_path.diff().std(ddof=0)) if len(balance_path) > 1 else 0.0

    # --- 4. Долговая нагрузка (прокси) -------------------------------------
    est_debt_payment, debt_series_count = _detect_recurring_debt_payments(df)
    est_dti = _safe_div(est_debt_payment, avg_monthly_income, default=1.0)

    # --- 5. Риск-флаги -------------------------------------------------
    risky_mask = df["description"].str.contains(RISK_KEYWORDS) | df["category"].str.contains(
        RISK_KEYWORDS
    )
    risk_tx_count = int(risky_mask.sum())
    risk_amount_share = _safe_div(df.loc[risky_mask, "amount"].abs().sum(), total_expense + total_income)

    round_amount_share = _round_amount_share(df)

    tx_per_month = (income_tx_count + expense_tx_count) / months

    values = {
        # доход
        "avg_monthly_income": round(avg_monthly_income, 2),
        "income_tx_count": income_tx_count,
        "income_cv": round(float(income_cv), 4),
        "income_gap_std_days": round(income_gap_std, 2),
        "cash_deposit_share": round(float(cash_deposit_share), 4),
        "max_income_share": round(float(max_income_share), 4),
        # расходы
        "avg_monthly_expense": round(avg_monthly_expense, 2),
        "expense_tx_count": expense_tx_count,
        "category_entropy": round(category_entropy, 4),
        "essential_share": round(float(essential_share), 4),
        "discretionary_share": round(float(discretionary_share), 4),
        "large_expense_share": round(float(large_expense_share), 4),
        # денежный поток
        "savings_rate": round(float(savings_rate), 4),
        "expense_income_ratio": round(float(expense_income_ratio), 4),
        "balance_volatility": round(balance_volatility, 2),
        # долговая нагрузка (прокси)
        "estimated_monthly_debt_payment": est_debt_payment,
        "estimated_dti": round(float(min(est_dti, 5.0)), 4),
        "debt_series_count": debt_series_count,
        # риск
        "risk_tx_count": risk_tx_count,
        "risk_amount_share": round(float(risk_amount_share), 4),
        "round_amount_share": round(round_amount_share, 4),
        # общий контекст
        "tx_per_month": round(tx_per_month, 2),
        "period_days": period_days,
    }
    return FeatureSet(values)


FEATURE_NAMES = [
    "avg_monthly_income", "income_tx_count", "income_cv", "income_gap_std_days",
    "cash_deposit_share", "max_income_share",
    "avg_monthly_expense", "expense_tx_count", "category_entropy",
    "essential_share", "discretionary_share", "large_expense_share",
    "savings_rate", "expense_income_ratio", "balance_volatility",
    "estimated_monthly_debt_payment", "estimated_dti", "debt_series_count",
    "risk_tx_count", "risk_amount_share", "round_amount_share",
    "tx_per_month", "period_days",
]


if __name__ == "__main__":
    import sys
    from parser import parse_statement

    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("Использование: python features.py <путь_к_выписке.pdf>")
        raise SystemExit(1)

    df = parse_statement(path)
    fs = extract_features(df)
    for k, v in fs.values.items():
        print(f"{k:35s} {v}")
