import json

from sklearn.base import clone
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
import xgboost as xgb

from .train_utils import (
    CLF_CATEGORICAL_FEATURES,
    CLF_NUMERIC_FEATURES,
    REG_CATEGORICAL_FEATURES,
    REG_NUMERIC_FEATURES,
    evaluate_classification,
    evaluate_regression,
    fit_production_model,
    load_classification_data,
    load_regression_data,
    make_temporal_cv_splits,
    prepare_classification_data,
    prepare_regression_data,
    save_model_and_metrics,
)
from ..config import MODELS_DIR, TEMPORAL_TEST_START_YEAR


def optimize_xgboost_clf():
    print("\n--- Optimisation Classification : XGBoost ---")

    X, y = load_classification_data()
    prepared = prepare_classification_data(X, y)

    cv_splits = make_temporal_cv_splits(
        X,
        TEMPORAL_TEST_START_YEAR,
    )

    n_neg = int((prepared.y_train == 0).sum())
    n_pos = int((prepared.y_train == 1).sum())
    default_scale = float(n_neg / n_pos) if n_pos else 1.0

    param_dist = {
        "n_estimators": [100, 150, 200, 300],
        "max_depth": [2, 3, 4, 5],
        "learning_rate": [0.02, 0.05, 0.1, 0.2],
        "subsample": [0.75, 0.9, 1.0],
        "colsample_bytree": [0.8, 0.9, 1.0],
        "scale_pos_weight": [
            1.0,
            default_scale,
            max(1.0, default_scale * 0.75),
        ],
    }

    base_model = xgb.XGBClassifier(
        random_state=42,
        eval_metric="logloss",
        n_jobs=-1,
    )

    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_dist,
        n_iter=24,
        scoring="f1",
        cv=cv_splits,
        random_state=42,
        n_jobs=-1,
        verbose=1,
        refit=True,
    )
    search.fit(prepared.X_train, prepared.y_train)

    evaluation_model = search.best_estimator_
    metrics = evaluate_classification(
        evaluation_model,
        prepared,
    )
    metrics["cv_best_f1"] = float(search.best_score_)
    metrics["best_params"] = search.best_params_

    print("Meilleurs paramètres :", search.best_params_)
    print(f"Meilleur F1 CV temporelle : {search.best_score_:.4f}")

    production_model, production_preprocessor = fit_production_model(
        evaluation_model,
        X,
        y,
        CLF_NUMERIC_FEATURES,
        CLF_CATEGORICAL_FEATURES,
    )

    save_model_and_metrics(
        production_model,
        metrics,
        "xgboost_optimized",
        preprocessor=production_preprocessor,
        axis="clf",
    )


def optimize_xgboost_reg():
    print("\n--- Optimisation Régression : XGBoost ---")

    X, y = load_regression_data()
    prepared = prepare_regression_data(X, y)

    cv_splits = make_temporal_cv_splits(
        X,
        TEMPORAL_TEST_START_YEAR,
    )

    param_dist = {
        "n_estimators": [100, 150, 200, 300],
        "max_depth": [2, 3, 4, 5],
        "learning_rate": [0.02, 0.05, 0.1, 0.2],
        "subsample": [0.75, 0.9, 1.0],
        "colsample_bytree": [0.8, 0.9, 1.0],
    }

    base_model = xgb.XGBRegressor(
        random_state=42,
        eval_metric="rmse",
        n_jobs=-1,
    )

    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_dist,
        n_iter=20,
        scoring="r2",
        cv=cv_splits,
        random_state=42,
        n_jobs=-1,
        verbose=1,
        refit=True,
    )
    search.fit(prepared.X_train, prepared.y_train)

    evaluation_model = search.best_estimator_
    metrics = evaluate_regression(
        evaluation_model,
        prepared,
    )
    metrics["cv_best_r2"] = float(search.best_score_)
    metrics["best_params"] = search.best_params_

    print("Meilleurs paramètres :", search.best_params_)
    print(f"Meilleur R² CV temporelle : {search.best_score_:.4f}")

    production_model, production_preprocessor = fit_production_model(
        evaluation_model,
        X,
        y,
        REG_NUMERIC_FEATURES,
        REG_CATEGORICAL_FEATURES,
    )

    save_model_and_metrics(
        production_model,
        metrics,
        "xgboost_optimized",
        preprocessor=production_preprocessor,
        axis="reg",
    )


def optimize_ridge_reg():
    print("\n--- Optimisation Régression : Ridge ---")

    X, y = load_regression_data()
    prepared = prepare_regression_data(X, y)

    cv_splits = make_temporal_cv_splits(
        X,
        TEMPORAL_TEST_START_YEAR,
    )

    search = GridSearchCV(
        Ridge(),
        param_grid={
            "alpha": [
                0.001,
                0.01,
                0.05,
                0.1,
                0.5,
                1.0,
                2.0,
                5.0,
                10.0,
                50.0,
                100.0,
            ]
        },
        scoring="r2",
        cv=cv_splits,
        n_jobs=-1,
        refit=True,
    )
    search.fit(prepared.X_train, prepared.y_train)

    evaluation_model = search.best_estimator_
    metrics = evaluate_regression(
        evaluation_model,
        prepared,
    )
    metrics["cv_best_r2"] = float(search.best_score_)
    metrics["best_params"] = search.best_params_

    print("Meilleur alpha :", search.best_params_["alpha"])
    print(f"Meilleur R² CV temporelle : {search.best_score_:.4f}")

    production_model, production_preprocessor = fit_production_model(
        evaluation_model,
        X,
        y,
        REG_NUMERIC_FEATURES,
        REG_CATEGORICAL_FEATURES,
    )

    save_model_and_metrics(
        production_model,
        metrics,
        "ridge_optimized",
        preprocessor=production_preprocessor,
        axis="reg",
    )


def _read_metric(model_name: str, metric: str) -> str:
    path = MODELS_DIR / f"{model_name}_metrics.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return "N/A"

    value = data.get(metric, "N/A")
    return f"{value:.4f}" if isinstance(value, (int, float)) else str(value)


def compare_results():
    print("\n--- Comparaison Avant / Après optimisation ---")

    pairs = [
        (
            "Classification XGBoost",
            "xgboost_clf",
            "xgboost_optimized_clf",
            "f1",
        ),
        (
            "Régression XGBoost",
            "xgboost_reg",
            "xgboost_optimized_reg",
            "r2",
        ),
        (
            "Régression Ridge",
            "ridge_reg",
            "ridge_optimized_reg",
            "r2",
        ),
    ]

    for label, before_name, after_name, metric in pairs:
        before = _read_metric(before_name, metric)
        after = _read_metric(after_name, metric)
        print(
            f"{label} — avant {metric.upper()}={before} | "
            f"après {metric.upper()}={after}"
        )


if __name__ == "__main__":
    optimize_xgboost_clf()
    optimize_xgboost_reg()
    optimize_ridge_reg()
    compare_results()
