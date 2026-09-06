# -*- coding: utf-8 -*-
"""
train_model.py — обучает регрессионную модель «признаки по выписке ->
скор 0..100» на обучающем наборе (synth_data.py) и сохраняет артефакт в
model/.

Основной бэкенд — CatBoost. Если пакет catboost не установлен в
окружении, скрипт откатывается на sklearn.HistGradientBoostingRegressor
и явно сообщает об этом в логе. Для честного per-sample SHAP в score.py
нужен именно CatBoost (см. requirements.txt).

Использование:
    python train_model.py                  # обучить и сохранить модель
    python train_model.py --n 10000        # увеличить обучающую выборку
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from features import FEATURE_NAMES
from synth_data import generate_dataset

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
MODEL_DIR.mkdir(exist_ok=True)


def _try_import_catboost():
    try:
        from catboost import CatBoostRegressor
        return CatBoostRegressor
    except ImportError:
        return None


def train(n_samples: int = 6000, seed: int = 42) -> dict:
    data = generate_dataset(n_total=n_samples, seed=seed)
    X = data[FEATURE_NAMES]
    y = data["score"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed
    )

    CatBoostRegressor = _try_import_catboost()
    backend = "catboost" if CatBoostRegressor is not None else "sklearn_hgb"

    if backend == "catboost":
        model = CatBoostRegressor(
            iterations=400,
            depth=6,
            learning_rate=0.05,
            loss_function="RMSE",
            random_seed=seed,
            verbose=False,
        )
        model.fit(X_train, y_train, eval_set=(X_test, y_test))
        model.save_model(str(MODEL_DIR / "statement_model.cbm"))
        pred = model.predict(X_test)
    else:
        from sklearn.ensemble import HistGradientBoostingRegressor

        print(
            "[train_model] catboost не установлен — обучаю "
            "sklearn.HistGradientBoostingRegressor. Для основного "
            "бэкенда: pip install catboost"
        )
        model = HistGradientBoostingRegressor(
            max_depth=6, learning_rate=0.05, max_iter=400, random_state=seed
        )
        model.fit(X_train, y_train)
        with open(MODEL_DIR / "statement_model.pkl", "wb") as fh:
            pickle.dump(model, fh)
        pred = model.predict(X_test)

    metrics = {
        "backend": backend,
        "mae": round(float(mean_absolute_error(y_test, pred)), 3),
        "r2": round(float(r2_score(y_test, pred)), 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }

    meta = {
        "feature_names": FEATURE_NAMES,
        "backend": backend,
        "metrics": metrics,
    }
    with open(MODEL_DIR / "meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=6000, help="Размер синтетической выборки")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(n_samples=args.n, seed=args.seed)
