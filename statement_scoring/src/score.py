# -*- coding: utf-8 -*-
"""
score.py — точка входа ветки «Выписка карты → Feature Engineering →
CatBoost Model → скор + объяснение».

    PDF-выписка -> parser.py -> features.py -> scoring_rules.py (База × K_итог)
                                            -> модель (CatBoost/фолбэк)
                                            -> итоговый отчёт

Использование:
    python score.py /путь/к/выписке.pdf
    python score.py /путь/к/выписке.pdf --json   # машиночитаемый вывод

Программно:
    from score import score_statement
    result = score_statement("выписка.pdf")
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from features import FEATURE_NAMES, extract_features
from parser import parse_statement, validate_against_declared_totals
from scoring_rules import FINAL_SCORE_MAX, score_from_features, verdict

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"


def _load_model():
    """Возвращает (backend, predict_fn, shap_fn_or_None)."""
    cbm_path = MODEL_DIR / "statement_model.cbm"
    pkl_path = MODEL_DIR / "statement_model.pkl"

    if cbm_path.exists():
        from catboost import CatBoostRegressor, Pool

        model = CatBoostRegressor()
        model.load_model(str(cbm_path))

        def predict(X: pd.DataFrame) -> np.ndarray:
            return model.predict(X)

        def shap_values(X: pd.DataFrame) -> np.ndarray:
            pool = Pool(X)
            raw = model.get_feature_importance(pool, type="ShapValues")
            return raw[:, :-1]  # последний столбец — base_value, отбрасываем

        return "catboost", predict, shap_values

    if pkl_path.exists():
        import pickle

        with open(pkl_path, "rb") as fh:
            model = pickle.load(fh)

        def predict(X: pd.DataFrame) -> np.ndarray:
            return model.predict(X)

        importances = getattr(model, "feature_importances_", None)
        return "sklearn_hgb", predict, importances

    return None, None, None


def _model_explanation_shap(shap_row: np.ndarray, feature_names: list[str], top_k: int = 5) -> list[dict]:
    order = np.argsort(-np.abs(shap_row))[:top_k]
    return [
        {"feature": feature_names[i], "shap_contribution": round(float(shap_row[i]), 2)}
        for i in order
    ]


def _model_explanation_importance(importances: np.ndarray, feature_names: list[str], top_k: int = 5) -> list[dict]:
    order = np.argsort(-importances)[:top_k]
    return [
        {"feature": feature_names[i], "global_importance": round(float(importances[i]), 4)}
        for i in order
    ]


def score_statement(pdf_path: str | Path, top_k: int = 5) -> dict:
    df_tx = parse_statement(pdf_path)
    totals_check = validate_against_declared_totals(df_tx)

    feats = extract_features(df_tx).values
    X = pd.DataFrame([feats])[FEATURE_NAMES]

    rule_score, rule_factors, rule_debug = score_from_features(feats)

    result = {
        "input_file": str(pdf_path),
        "period": {
            "start": str(df_tx.attrs.get("period_start")),
            "end": str(df_tx.attrs.get("period_end")),
        },
        "n_transactions": int(len(df_tx)),
        "totals_sanity_check": totals_check,
        "features": feats,
        "rule_based_score": round(rule_score, 1),
        "rule_based_verdict": verdict(rule_score),
        "rule_based_breakdown": {
            "adjusted_monthly_income": rule_debug["dch_corr"],
            "estimated_pdn_percent": rule_debug["pdn"],
            "base_before_coefficients": rule_debug["base"],
            "combined_coefficient": rule_debug["k_total"],
        },
        "rule_based_factors": [
            {"factor": f.name, "coefficient": f.value, "comment": f.comment_ru}
            for f in sorted(rule_factors, key=lambda f: -abs(f.value - 1.0))
        ],
    }

    backend, predict_fn, extra = _load_model()

    if backend is None:
        result["model_score"] = None
        result["model_backend"] = None
        result["final_score"] = round(rule_score, 1)
        result["final_verdict"] = verdict(rule_score)
        return result

    model_score = float(predict_fn(X)[0])
    model_score = max(0.0, min(FINAL_SCORE_MAX, model_score))
    result["model_score"] = round(model_score, 1)
    result["model_backend"] = backend
    result["model_verdict"] = verdict(model_score)

    if backend == "catboost":
        shap_row = extra(X)[0]
        result["model_explanation"] = _model_explanation_shap(shap_row, FEATURE_NAMES, top_k)
        result["model_explanation_method"] = "catboost_shap"
    elif extra is not None:
        result["model_explanation"] = _model_explanation_importance(extra, FEATURE_NAMES, top_k)
        result["model_explanation_method"] = "global_feature_importance"
    else:
        result["model_explanation"] = []
        result["model_explanation_method"] = "недоступно для данного бэкенда"

    final_score = 0.6 * model_score + 0.4 * rule_score
    result["final_score"] = round(final_score, 1)
    result["final_verdict"] = verdict(final_score)

    if abs(model_score - rule_score) > 0.2 * FINAL_SCORE_MAX:
        result["disagreement_warning"] = (
            f"Модель ({model_score:.1f}) и формула ({rule_score:.1f}) расходятся "
            f"более чем на {0.2 * FINAL_SCORE_MAX:.1f} из {FINAL_SCORE_MAX:.0f} — рекомендуется ручная проверка."
        )

    return result


def build_server_payload(result: dict) -> dict:
    """Сворачивает полный результат score_statement() в компактный вид
    для отправки на сервер: итоговый скор + готовый текст объяснения.

    Формат:
        {
            "final_score": 33.5,
            "ai_comment": "Коэффициенты слоя 3:\n×0.5 Регулярность дохода ..."
        }
    """
    lines = ["Коэффициенты слоя 3:"]
    for f in result["rule_based_factors"]:
        lines.append(f"×{f['coefficient']} {f['factor']} — {f['comment']}")
    ai_comment = "\n".join(lines)

    return {
        "final_score": result["final_score"],
        "ai_comment": ai_comment,
    }


def score_statement_for_server(pdf_path: str | Path) -> dict:
    """Удобный шорткат: сразу возвращает компактный пейлоад для сервера,
    без полного результата score_statement()."""
    return build_server_payload(score_statement(pdf_path))


def _print_report(res: dict) -> None:
    print("=" * 70)
    print(f"Файл:            {res['input_file']}")
    print(f"Период выписки:  {res['period']['start']} — {res['period']['end']}")
    print(f"Операций:        {res['n_transactions']}")
    tc = res["totals_sanity_check"]
    ok = tc.get("income_match") and tc.get("expense_match")
    print(f"Контроль сумм:   {'OK' if ok else 'РАСХОЖДЕНИЕ — проверьте парсинг'}")
    print("-" * 70)
    if res.get("model_score") is not None:
        print(f"Скор модели ({res['model_backend']}):   {res['model_score']} / {FINAL_SCORE_MAX:.0f}  [{res['model_verdict']}]")
    print(f"Скор по формуле:              {res['rule_based_score']} / {FINAL_SCORE_MAX:.0f}  [{res['rule_based_verdict']}]")
    print(f"ИТОГОВЫЙ СКОР:                 {res['final_score']} / {FINAL_SCORE_MAX:.0f}  [{res['final_verdict']}]")
    if res.get("disagreement_warning"):
        print(f"! {res['disagreement_warning']}")
    print("-" * 70)
    b = res["rule_based_breakdown"]
    print(f"Скорректированный доход: {b['adjusted_monthly_income']} ₽/мес")
    print(f"Оценочный ПДН:           {b['estimated_pdn_percent']}%")
    print(f"База (100 − ПДН):        {b['base_before_coefficients']}")
    print(f"Итоговый K:              {b['combined_coefficient']}")
    print("-" * 70)
    print("Коэффициенты слоя 3:")
    for f in res["rule_based_factors"]:
        print(f"  ×{f['coefficient']:<6}  {f['factor']}")
        print(f"           {f['comment']}")
    if res.get("model_explanation"):
        print(f"\nКлючевые факторы модели ({res['model_explanation_method']}):")
        for item in res["model_explanation"]:
            if "shap_contribution" in item:
                print(f"  {item['shap_contribution']:>7.2f}   {item['feature']}")
            else:
                print(f"  {item.get('global_importance'):>7.4f}   {item['feature']}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf_path")
    parser.add_argument("--json", action="store_true", help="Вывести полный результат как JSON")
    parser.add_argument("--server", action="store_true", help="Вывести компактный пейлоад {final_score, final_verdict, ai_comment}")
    args = parser.parse_args()

    result = score_statement(args.pdf_path)
    if args.server:
        print(json.dumps(build_server_payload(result), ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        _print_report(result)
