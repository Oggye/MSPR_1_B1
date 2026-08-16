from __future__ import annotations

import json
from copy import deepcopy

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    CLASSIF_DATASET_PATH,
    CV_VALIDATION_YEARS,
    FINAL_TEST_TARGET_START_YEAR,
    FORECAST_CLASSIFIER_PATH,
    FORECAST_MANIFEST_PATH,
    FORECAST_REGRESSOR_PATH,
    REGRESSION_DATASET_PATH,
)


NUMERIC_FEATURES = [
    "horizon",
    "passengers",
    "passengers_previous",
    "passenger_growth_1y",
    "co2_emissions",
    "co2_previous",
    "co2_growth_1y",
    "train_count_current",
    "night_share_current",
    "real_share_current",
    "avg_distance_current",
    "avg_duration_current",
    "operator_count_current",
    "network_data_available",
]
CATEGORICAL_FEATURES = ["country_name"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_preprocessor():
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def build_pipeline(model):
    return Pipeline(
        steps=[
            ("preprocess", build_preprocessor()),
            ("model", model),
        ]
    )


def _weighted_mae(y_true, y_pred, weights):
    return float(
        np.average(
            np.abs(
                np.asarray(y_true, dtype=float)
                - np.asarray(y_pred, dtype=float)
            ),
            weights=np.asarray(weights, dtype=float),
        )
    )


def _regression_metrics(y_true, y_pred, weights=None):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    result = {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(
            np.sqrt(mean_squared_error(y_true, y_pred))
        ),
        "r2": float(r2_score(y_true, y_pred)),
    }

    if weights is not None:
        result["weighted_mae"] = _weighted_mae(
            y_true,
            y_pred,
            weights,
        )

    return result


def _classification_metrics(y_true, y_pred, y_proba=None):
    result = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(y_true, y_pred, zero_division=0)
        ),
        "recall": float(
            recall_score(y_true, y_pred, zero_division=0)
        ),
        "f1": float(
            f1_score(y_true, y_pred, zero_division=0)
        ),
    }

    if y_proba is not None and len(np.unique(y_true)) > 1:
        result["roc_auc"] = float(
            roc_auc_score(y_true, y_proba)
        )
    else:
        result["roc_auc"] = None

    return result


def _fit_pipeline(pipeline, X, y, weights=None):
    kwargs = {}
    if weights is not None:
        kwargs["model__sample_weight"] = np.asarray(weights, dtype=float)

    pipeline.fit(X, y, **kwargs)
    return pipeline


def _classification_candidates():
    return {
        "logistic": build_pipeline(
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                C=1.0,
                random_state=42,
            )
        ),
        "xgboost": build_pipeline(
            xgb.XGBClassifier(
                n_estimators=220,
                learning_rate=0.05,
                max_depth=3,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="logloss",
                random_state=42,
                n_jobs=-1,
            )
        ),
    }


def _regression_candidates():
    return {
        "ridge": build_pipeline(
            Ridge(alpha=0.1)
        ),
        "xgboost": build_pipeline(
            xgb.XGBRegressor(
                n_estimators=260,
                learning_rate=0.05,
                max_depth=3,
                subsample=0.9,
                colsample_bytree=0.9,
                eval_metric="rmse",
                random_state=42,
                n_jobs=-1,
            )
        ),
    }


def _rolling_splits(df):
    """
    Validation par année cible :
    entraînement = toutes les targets antérieures à l'année de validation.
    """
    splits = []

    for validation_year in CV_VALIDATION_YEARS:
        train_idx = df.index[df["target_year"] < validation_year].to_numpy()
        val_idx = df.index[df["target_year"] == validation_year].to_numpy()

        if len(train_idx) > 0 and len(val_idx) > 0:
            splits.append(
                (
                    int(validation_year),
                    train_idx,
                    val_idx,
                )
            )

    if len(splits) < 2:
        raise ValueError(
            "Pas assez de folds temporels pour la sélection du modèle."
        )

    return splits


def _baseline_regression(df):
    current = df["passengers"].to_numpy(dtype=float)
    previous = df["passengers_previous"].to_numpy(dtype=float)
    horizon = df["horizon"].to_numpy(dtype=float)

    persistence = np.clip(current, 0.0, None)
    trend = np.clip(
        current + horizon * (current - previous),
        0.0,
        None,
    )

    return {
        "persistence": persistence,
        "linear_trend": trend,
    }


def _best_blend_weight(
    y_true,
    ml_pred,
    baseline_pred,
    weights,
):
    best = {
        "weight": 1.0,
        "mae": float("inf"),
    }

    for weight in np.linspace(0.0, 1.0, 21):
        blended = (
            weight * np.asarray(ml_pred)
            + (1.0 - weight) * np.asarray(baseline_pred)
        )
        mae = _weighted_mae(
            y_true,
            blended,
            weights,
        )

        if mae < best["mae"]:
            best = {
                "weight": float(round(weight, 2)),
                "mae": float(mae),
            }

    return best


def select_classifier(df_train):
    candidates = _classification_candidates()
    splits = _rolling_splits(df_train)

    candidate_scores = {}

    for name, template in candidates.items():
        fold_metrics = []

        for validation_year, train_idx, val_idx in splits:
            train = df_train.loc[train_idx]
            val = df_train.loc[val_idx]

            model = deepcopy(template)
            model = _fit_pipeline(
                model,
                train[MODEL_FEATURES],
                train["en_declin"],
                train["sample_weight"],
            )

            pred = model.predict(val[MODEL_FEATURES])
            proba = (
                model.predict_proba(val[MODEL_FEATURES])[:, 1]
                if hasattr(model, "predict_proba")
                else None
            )

            metrics = _classification_metrics(
                val["en_declin"],
                pred,
                proba,
            )
            metrics["validation_year"] = validation_year
            fold_metrics.append(metrics)

        mean_f1 = float(
            np.mean([item["f1"] for item in fold_metrics])
        )
        mean_auc_values = [
            item["roc_auc"]
            for item in fold_metrics
            if item["roc_auc"] is not None
        ]
        mean_auc = (
            float(np.mean(mean_auc_values))
            if mean_auc_values
            else None
        )

        candidate_scores[name] = {
            "cv_mean_f1": mean_f1,
            "cv_mean_roc_auc": mean_auc,
            "folds": fold_metrics,
        }

    selected_name = max(
        candidate_scores,
        key=lambda name: candidate_scores[name]["cv_mean_f1"],
    )

    return (
        selected_name,
        candidates[selected_name],
        candidate_scores,
    )


def select_regressor(df_train):
    candidates = _regression_candidates()
    splits = _rolling_splits(df_train)

    candidate_scores = {}

    for name, template in candidates.items():
        all_y = []
        all_weights = []
        all_ml_pred = []
        all_baselines = {
            "persistence": [],
            "linear_trend": [],
        }

        fold_metrics = []

        for validation_year, train_idx, val_idx in splits:
            train = df_train.loc[train_idx]
            val = df_train.loc[val_idx]

            model = deepcopy(template)
            model = _fit_pipeline(
                model,
                train[MODEL_FEATURES],
                train["target_passengers"],
                train["sample_weight"],
            )

            ml_pred = np.clip(
                model.predict(val[MODEL_FEATURES]),
                0.0,
                None,
            )
            baselines = _baseline_regression(val)

            fold_metrics.append(
                {
                    "validation_year": validation_year,
                    **_regression_metrics(
                        val["target_passengers"],
                        ml_pred,
                        val["sample_weight"],
                    ),
                }
            )

            all_y.extend(val["target_passengers"].tolist())
            all_weights.extend(val["sample_weight"].tolist())
            all_ml_pred.extend(ml_pred.tolist())

            for baseline_name, baseline_pred in baselines.items():
                all_baselines[baseline_name].extend(
                    baseline_pred.tolist()
                )

        baseline_scores = {
            baseline_name: _weighted_mae(
                all_y,
                pred,
                all_weights,
            )
            for baseline_name, pred in all_baselines.items()
        }

        best_baseline_name = min(
            baseline_scores,
            key=baseline_scores.get,
        )

        blend = _best_blend_weight(
            all_y,
            all_ml_pred,
            all_baselines[best_baseline_name],
            all_weights,
        )

        candidate_scores[name] = {
            "cv_ml_weighted_mae": _weighted_mae(
                all_y,
                all_ml_pred,
                all_weights,
            ),
            "baseline_scores": baseline_scores,
            "selected_baseline": best_baseline_name,
            "blend_weight_ml": blend["weight"],
            "cv_blended_weighted_mae": blend["mae"],
            "folds": fold_metrics,
        }

    selected_name = min(
        candidate_scores,
        key=lambda name: candidate_scores[name][
            "cv_blended_weighted_mae"
        ],
    )

    return (
        selected_name,
        candidates[selected_name],
        candidate_scores,
    )


def evaluate_classifier(
    model_template,
    df_train,
    df_test,
):
    model = deepcopy(model_template)
    model = _fit_pipeline(
        model,
        df_train[MODEL_FEATURES],
        df_train["en_declin"],
        df_train["sample_weight"],
    )

    pred = model.predict(df_test[MODEL_FEATURES])
    proba = (
        model.predict_proba(df_test[MODEL_FEATURES])[:, 1]
        if hasattr(model, "predict_proba")
        else None
    )

    overall = _classification_metrics(
        df_test["en_declin"],
        pred,
        proba,
    )

    baseline_pred = (
        df_test["passengers"]
        < df_test["passengers_previous"]
    ).astype(int).to_numpy()

    baseline = _classification_metrics(
        df_test["en_declin"],
        baseline_pred,
        None,
    )

    observed_mask = df_test["row_quality"] == "observed"
    observed = None
    if observed_mask.sum() >= 10:
        observed_proba = (
            proba[observed_mask.to_numpy()]
            if proba is not None
            else None
        )
        observed = _classification_metrics(
            df_test.loc[observed_mask, "en_declin"],
            pred[observed_mask.to_numpy()],
            observed_proba,
        )

    by_horizon = {}
    for horizon, group in df_test.groupby("horizon"):
        idx = group.index
        positions = df_test.index.get_indexer(idx)
        horizon_proba = (
            proba[positions]
            if proba is not None
            else None
        )
        by_horizon[str(int(horizon))] = _classification_metrics(
            group["en_declin"],
            pred[positions],
            horizon_proba,
        )

    return model, {
        "overall": overall,
        "baseline_only": baseline,
        "observed_only": observed,
        "by_horizon": by_horizon,
    }


def evaluate_regressor(
    model_template,
    df_train,
    df_test,
    baseline_name,
    blend_weight_ml,
):
    model = deepcopy(model_template)
    model = _fit_pipeline(
        model,
        df_train[MODEL_FEATURES],
        df_train["target_passengers"],
        df_train["sample_weight"],
    )

    ml_pred = np.clip(
        model.predict(df_test[MODEL_FEATURES]),
        0.0,
        None,
    )
    baselines = _baseline_regression(df_test)
    baseline_pred = baselines[baseline_name]

    final_pred = (
        blend_weight_ml * ml_pred
        + (1.0 - blend_weight_ml) * baseline_pred
    )
    final_pred = np.clip(final_pred, 0.0, None)

    overall = _regression_metrics(
        df_test["target_passengers"],
        final_pred,
        df_test["sample_weight"],
    )

    baseline_metrics = _regression_metrics(
        df_test["target_passengers"],
        baseline_pred,
        df_test["sample_weight"],
    )

    ml_only_metrics = _regression_metrics(
        df_test["target_passengers"],
        ml_pred,
        df_test["sample_weight"],
    )

    observed_mask = df_test["row_quality"] == "observed"
    observed = None
    if observed_mask.sum() >= 10:
        positions = np.where(observed_mask.to_numpy())[0]
        observed = _regression_metrics(
            df_test.loc[observed_mask, "target_passengers"],
            final_pred[positions],
            df_test.loc[observed_mask, "sample_weight"],
        )

    by_horizon = {}
    interval_q90 = {}

    for horizon, group in df_test.groupby("horizon"):
        positions = df_test.index.get_indexer(group.index)
        y_true = group["target_passengers"].to_numpy(dtype=float)
        y_pred = final_pred[positions]

        by_horizon[str(int(horizon))] = _regression_metrics(
            y_true,
            y_pred,
            group["sample_weight"],
        )

        absolute_residuals = np.abs(y_true - y_pred)
        interval_q90[str(int(horizon))] = float(
            np.quantile(absolute_residuals, 0.90)
        )

    return model, {
        "overall": overall,
        "observed_only": observed,
        "ml_only": ml_only_metrics,
        "baseline_only": baseline_metrics,
        "by_horizon": by_horizon,
        "interval_q90_by_horizon": interval_q90,
    }


def fit_production_pipeline(
    template,
    df,
    target_column,
):
    model = deepcopy(template)
    return _fit_pipeline(
        model,
        df[MODEL_FEATURES],
        df[target_column],
        df["sample_weight"],
    )


def main():
    print("=" * 72)
    print("ENTRAÎNEMENT IA DIRECT MULTI-HORIZON — N+1 / N+2 / N+3")
    print("=" * 72)

    clf = pd.read_csv(CLASSIF_DATASET_PATH, low_memory=False)
    reg = pd.read_csv(REGRESSION_DATASET_PATH, low_memory=False)

    train_clf = clf[
        clf["target_year"] < FINAL_TEST_TARGET_START_YEAR
    ].copy()
    test_clf = clf[
        clf["target_year"] >= FINAL_TEST_TARGET_START_YEAR
    ].copy()

    train_reg = reg[
        reg["target_year"] < FINAL_TEST_TARGET_START_YEAR
    ].copy()
    test_reg = reg[
        reg["target_year"] >= FINAL_TEST_TARGET_START_YEAR
    ].copy()

    print(
        f"Classification : train={len(train_clf)} | "
        f"holdout final={len(test_clf)}"
    )
    print(
        f"Régression     : train={len(train_reg)} | "
        f"holdout final={len(test_reg)}"
    )

    # Classification : sélection uniquement sur CV pré-holdout.
    clf_name, clf_template, clf_selection = select_classifier(
        train_clf
    )
    print(
        f"\nClassif sélectionnée : {clf_name} | "
        f"F1 CV={clf_selection[clf_name]['cv_mean_f1']:.4f}"
    )

    _, clf_test_metrics = evaluate_classifier(
        clf_template,
        train_clf,
        test_clf,
    )

    clf_production = fit_production_pipeline(
        clf_template,
        clf,
        "en_declin",
    )
    joblib.dump(
        clf_production,
        FORECAST_CLASSIFIER_PATH,
    )

    # Régression : sélection + blend déterminés uniquement sur CV pré-holdout.
    reg_name, reg_template, reg_selection = select_regressor(
        train_reg
    )
    reg_choice = reg_selection[reg_name]
    baseline_name = reg_choice["selected_baseline"]
    blend_weight_ml = reg_choice["blend_weight_ml"]

    print(
        f"\nRégression sélectionnée : {reg_name} | "
        f"baseline={baseline_name} | "
        f"poids ML={blend_weight_ml:.2f} | "
        f"MAE CV blend={reg_choice['cv_blended_weighted_mae']:.2f}"
    )

    _, reg_test_metrics = evaluate_regressor(
        reg_template,
        train_reg,
        test_reg,
        baseline_name,
        blend_weight_ml,
    )

    reg_production = fit_production_pipeline(
        reg_template,
        reg,
        "target_passengers",
    )
    joblib.dump(
        reg_production,
        FORECAST_REGRESSOR_PATH,
    )

    manifest = {
        "version": 3,
        "architecture": "direct_multi_horizon",
        "forecast_horizons": [1, 2, 3],
        "features": MODEL_FEATURES,
        "units": {
            "passengers": "MIO_PKM",
            "co2": "MIO_T",
        },
        "classification": {
            "selected_model": clf_name,
            "selection": clf_selection,
            "final_holdout": clf_test_metrics,
            "target_definition": (
                "1 si target_passengers(horizon) < "
                "passengers de l'année d'origine"
            ),
        },
        "regression": {
            "selected_model": reg_name,
            "selected_baseline": baseline_name,
            "blend_weight_ml": blend_weight_ml,
            "blend_weight_baseline": round(
                1.0 - blend_weight_ml,
                2,
            ),
            "selection": reg_selection,
            "final_holdout": reg_test_metrics,
        },
        "final_test_target_start_year": (
            FINAL_TEST_TARGET_START_YEAR
        ),
    }

    FORECAST_MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nHoldout final classification :")
    print(
        json.dumps(
            clf_test_metrics["overall"],
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nHoldout final régression :")
    print(
        json.dumps(
            reg_test_metrics["overall"],
            indent=2,
            ensure_ascii=False,
        )
    )
    print(
        "Baseline holdout :",
        json.dumps(
            reg_test_metrics["baseline_only"],
            ensure_ascii=False,
        ),
    )
    print(
        "Intervalle q90 par horizon :",
        reg_test_metrics["interval_q90_by_horizon"],
    )

    print(f"\nClassifier -> {FORECAST_CLASSIFIER_PATH}")
    print(f"Regressor  -> {FORECAST_REGRESSOR_PATH}")
    print(f"Manifest   -> {FORECAST_MANIFEST_PATH}")


if __name__ == "__main__":
    main()
