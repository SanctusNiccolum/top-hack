# -*- coding: utf-8 -*-
"""
synth_data.py — генерация обучающего набора для первой версии модели.

Пока нет исторических пар «признаки по выписке -> фактический исход по
кредиту», обучающая выборка строится так:

  1. Задаются архетипы держателя счёта (стабильный наёмный работник,
     нерегулярный фрилансер, студент, закредитованный клиент,
     подозрительный/транзитный счёт и т.д.) с правдоподобными
     диапазонами признаков для каждого.
  2. Признаки сэмплируются из этих диапазонов.
  3. Целевая переменная размечается формулой из scoring_rules.py с
     добавлением шума — модель учится обобщать эту формулу на новые
     комбинации признаков, которых не было в явном виде ни в одном
     архетипе.

Когда появятся реальные размеченные данные (наблюдаемый исход по
выданным кредитам), в train_model.py достаточно подменить источник
таргета на них — пайплайн парсинга и признаков не меняется.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features import FEATURE_NAMES
from scoring_rules import FINAL_SCORE_MAX, score_from_features

RNG = np.random.default_rng(42)


def _sample_archetype(name: str, n: int) -> pd.DataFrame:
    """Возвращает n сэмплов признаков для заданного архетипа."""

    def clip01(x):
        return np.clip(x, 0.0, 1.0)

    if name == "stable_salaried":
        income = RNG.normal(90000, 25000, n).clip(20000)
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(2, 5, n),
            "income_cv": clip01(RNG.normal(0.12, 0.08, n)),
            "income_gap_std_days": RNG.normal(3, 2, n).clip(0),
            "cash_deposit_share": clip01(RNG.normal(0.05, 0.05, n)),
            "max_income_share": clip01(RNG.normal(0.4, 0.1, n)),
            "avg_monthly_expense": income * RNG.normal(0.75, 0.15, n).clip(0.3, 1.3),
            "expense_tx_count": RNG.integers(30, 90, n),
            "category_entropy": RNG.normal(1.6, 0.3, n).clip(0.3, 2.5),
            "essential_share": clip01(RNG.normal(0.5, 0.12, n)),
            "discretionary_share": clip01(RNG.normal(0.25, 0.1, n)),
            "large_expense_share": clip01(RNG.normal(0.15, 0.1, n)),
            "balance_volatility": income * RNG.normal(0.08, 0.05, n).clip(0.01),
            "estimated_monthly_debt_payment": income * clip01(RNG.normal(0.12, 0.1, n)),
            "debt_series_count": RNG.integers(0, 2, n),
            "risk_tx_count": np.zeros(n),
            "risk_amount_share": np.zeros(n),
            "round_amount_share": clip01(RNG.normal(0.1, 0.08, n)),
            "tx_per_month": RNG.normal(35, 10, n).clip(5),
            "period_days": np.full(n, 90),
        })

    elif name == "irregular_freelancer":
        income = RNG.normal(70000, 30000, n).clip(10000)
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(3, 12, n),
            "income_cv": clip01(RNG.normal(0.55, 0.15, n)),
            "income_gap_std_days": RNG.normal(15, 8, n).clip(1),
            "cash_deposit_share": clip01(RNG.normal(0.15, 0.1, n)),
            "max_income_share": clip01(RNG.normal(0.35, 0.15, n)),
            "avg_monthly_expense": income * RNG.normal(0.85, 0.2, n).clip(0.3, 1.5),
            "expense_tx_count": RNG.integers(20, 70, n),
            "category_entropy": RNG.normal(1.4, 0.35, n).clip(0.2, 2.5),
            "essential_share": clip01(RNG.normal(0.45, 0.15, n)),
            "discretionary_share": clip01(RNG.normal(0.3, 0.12, n)),
            "large_expense_share": clip01(RNG.normal(0.25, 0.15, n)),
            "balance_volatility": income * RNG.normal(0.18, 0.1, n).clip(0.02),
            "estimated_monthly_debt_payment": income * clip01(RNG.normal(0.15, 0.12, n)),
            "debt_series_count": RNG.integers(0, 3, n),
            "risk_tx_count": np.zeros(n),
            "risk_amount_share": np.zeros(n),
            "round_amount_share": clip01(RNG.normal(0.15, 0.1, n)),
            "tx_per_month": RNG.normal(20, 8, n).clip(3),
            "period_days": np.full(n, 90),
        })

    elif name == "student_low_income":
        income = RNG.normal(20000, 10000, n).clip(0)
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(1, 4, n),
            "income_cv": clip01(RNG.normal(0.3, 0.15, n)),
            "income_gap_std_days": RNG.normal(10, 6, n).clip(0),
            "cash_deposit_share": clip01(RNG.normal(0.2, 0.15, n)),
            "max_income_share": clip01(RNG.normal(0.6, 0.2, n)),
            "avg_monthly_expense": income * RNG.normal(0.95, 0.2, n).clip(0.3, 1.6),
            "expense_tx_count": RNG.integers(15, 50, n),
            "category_entropy": RNG.normal(1.2, 0.3, n).clip(0.2, 2.2),
            "essential_share": clip01(RNG.normal(0.5, 0.15, n)),
            "discretionary_share": clip01(RNG.normal(0.3, 0.15, n)),
            "large_expense_share": clip01(RNG.normal(0.2, 0.12, n)),
            "balance_volatility": (income.clip(1000)) * RNG.normal(0.15, 0.1, n).clip(0.02),
            "estimated_monthly_debt_payment": np.zeros(n),
            "debt_series_count": np.zeros(n),
            "risk_tx_count": np.zeros(n),
            "risk_amount_share": np.zeros(n),
            "round_amount_share": clip01(RNG.normal(0.1, 0.08, n)),
            "tx_per_month": RNG.normal(15, 6, n).clip(2),
            "period_days": np.full(n, 90),
        })

    elif name == "overindebted":
        income = RNG.normal(65000, 20000, n).clip(15000)
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(2, 6, n),
            "income_cv": clip01(RNG.normal(0.25, 0.15, n)),
            "income_gap_std_days": RNG.normal(6, 4, n).clip(0),
            "cash_deposit_share": clip01(RNG.normal(0.1, 0.1, n)),
            "max_income_share": clip01(RNG.normal(0.4, 0.15, n)),
            "avg_monthly_expense": income * RNG.normal(1.05, 0.2, n).clip(0.5, 1.8),
            "expense_tx_count": RNG.integers(25, 70, n),
            "category_entropy": RNG.normal(1.3, 0.3, n).clip(0.2, 2.2),
            "essential_share": clip01(RNG.normal(0.55, 0.15, n)),
            "discretionary_share": clip01(RNG.normal(0.15, 0.1, n)),
            "large_expense_share": clip01(RNG.normal(0.2, 0.1, n)),
            "balance_volatility": income * RNG.normal(0.2, 0.1, n).clip(0.02),
            "estimated_monthly_debt_payment": income * clip01(RNG.normal(0.55, 0.18, n)),
            "debt_series_count": RNG.integers(2, 6, n),
            "risk_tx_count": np.zeros(n),
            "risk_amount_share": np.zeros(n),
            "round_amount_share": clip01(RNG.normal(0.25, 0.12, n)),
            "tx_per_month": RNG.normal(30, 8, n).clip(5),
            "period_days": np.full(n, 90),
        })

    elif name == "risk_flags":
        income = RNG.normal(60000, 25000, n).clip(10000)
        risk_share = clip01(RNG.normal(0.25, 0.15, n))
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(2, 6, n),
            "income_cv": clip01(RNG.normal(0.35, 0.2, n)),
            "income_gap_std_days": RNG.normal(12, 8, n).clip(0),
            "cash_deposit_share": clip01(RNG.normal(0.2, 0.15, n)),
            "max_income_share": clip01(RNG.normal(0.45, 0.15, n)),
            "avg_monthly_expense": income * RNG.normal(1.0, 0.25, n).clip(0.4, 1.8),
            "expense_tx_count": RNG.integers(20, 60, n),
            "category_entropy": RNG.normal(1.1, 0.3, n).clip(0.1, 2.0),
            "essential_share": clip01(RNG.normal(0.35, 0.15, n)),
            "discretionary_share": clip01(RNG.normal(0.2, 0.12, n)),
            "large_expense_share": clip01(RNG.normal(0.3, 0.15, n)),
            "balance_volatility": income * RNG.normal(0.3, 0.15, n).clip(0.03),
            "estimated_monthly_debt_payment": income * clip01(RNG.normal(0.2, 0.15, n)),
            "debt_series_count": RNG.integers(0, 3, n),
            "risk_tx_count": RNG.integers(1, 8, n),
            "risk_amount_share": risk_share,
            "round_amount_share": clip01(RNG.normal(0.3, 0.15, n)),
            "tx_per_month": RNG.normal(25, 10, n).clip(3),
            "period_days": np.full(n, 90),
        })

    elif name == "passthrough_suspicious":
        # Похоже на пример из реальной загруженной выписки: крупные
        # наличные поступления и единичный крупный исходящий перевод,
        # почти без бытовых трат.
        income = RNG.normal(300000, 150000, n).clip(50000)
        df = pd.DataFrame({
            "avg_monthly_income": income,
            "income_tx_count": RNG.integers(2, 6, n),
            "income_cv": clip01(RNG.normal(0.8, 0.15, n)),
            "income_gap_std_days": RNG.normal(20, 10, n).clip(1),
            "cash_deposit_share": clip01(RNG.normal(0.85, 0.1, n)),
            "max_income_share": clip01(RNG.normal(0.65, 0.15, n)),
            "avg_monthly_expense": income * RNG.normal(0.98, 0.05, n).clip(0.7, 1.2),
            "expense_tx_count": RNG.integers(10, 30, n),
            "category_entropy": RNG.normal(0.3, 0.2, n).clip(0.0, 1.0),
            "essential_share": clip01(RNG.normal(0.03, 0.03, n)),
            "discretionary_share": clip01(RNG.normal(0.02, 0.02, n)),
            "large_expense_share": clip01(RNG.normal(0.9, 0.08, n)),
            "balance_volatility": income * RNG.normal(0.5, 0.2, n).clip(0.05),
            "estimated_monthly_debt_payment": income * clip01(RNG.normal(0.05, 0.05, n)),
            "debt_series_count": RNG.integers(0, 2, n),
            "risk_tx_count": np.zeros(n),
            "risk_amount_share": np.zeros(n),
            "round_amount_share": clip01(RNG.normal(0.6, 0.2, n)),
            "tx_per_month": RNG.normal(12, 5, n).clip(2),
            "period_days": np.full(n, 90),
        })

    else:
        raise ValueError(name)

    df["estimated_dti"] = (df["estimated_monthly_debt_payment"] / df["avg_monthly_income"].clip(lower=1)).clip(0, 5)
    income_safe = df["avg_monthly_income"].clip(lower=1)
    df["savings_rate"] = ((df["avg_monthly_income"] - df["avg_monthly_expense"]) / income_safe).clip(-3, 1)
    df["expense_income_ratio"] = (df["avg_monthly_expense"] / income_safe).clip(0, 10)
    return df[FEATURE_NAMES]


ARCHETYPES = {
    "stable_salaried": 0.32,
    "irregular_freelancer": 0.18,
    "student_low_income": 0.15,
    "overindebted": 0.15,
    "risk_flags": 0.10,
    "passthrough_suspicious": 0.10,
}


def generate_dataset(n_total: int = 6000, noise_std: float = 1.5, seed: int = 42) -> pd.DataFrame:
    global RNG
    RNG = np.random.default_rng(seed)

    frames = []
    for name, frac in ARCHETYPES.items():
        n = int(round(n_total * frac))
        frames.append(_sample_archetype(name, n).assign(archetype=name))
    data = pd.concat(frames, ignore_index=True)
    data = data.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    scores = []
    for _, row in data[FEATURE_NAMES].iterrows():
        s, _, _ = score_from_features(row.to_dict())
        scores.append(s)
    scores = np.array(scores) + RNG.normal(0, noise_std, len(scores))
    data["score"] = np.clip(scores, 0, FINAL_SCORE_MAX)

    return data


if __name__ == "__main__":
    import sys
    from pathlib import Path

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "synthetic_train.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_dataset()
    df.to_csv(out_path, index=False)
    print(f"Сохранено {len(df)} синтетических записей в {out_path}")
    print(df.groupby("archetype")["score"].agg(["mean", "std", "count"]))
