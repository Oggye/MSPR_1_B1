from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
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
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import (
    CLASSIF_DATASET_PATH,
    DATASET_QUALITY_REPORT_PATH,
    MODELS_DIR,
    PREPROCESSOR_CLF_PATH,
    PREPROCESSOR_REG_PATH,
    REGRESSION_DATASET_PATH,
    TEMPORAL_TEST_START_YEAR,
)

# ------------------------------------------------------------------
# Features réellement utilisées par les modèles
# ------------------------------------------------------------------
# `year` reste dans le dataset pour la validation temporelle mais n'est PAS
# une feature. Cela évite que la classification apprenne simplement des années
# particulières (ex. choc COVID) au lieu de la dynamique ferroviaire.
COMMON_NUMERIC_FEATURES = [
    "passengers_lag1",
    "passengers_lag2",
    "passengers_growth_lag",
    "co2_emissions_lag1",
    "co2_emissions_lag2",
    "co2_growth_lag",
]
COMMON_CATEGORICAL_FEATURES = ["country_name"]

REG_NUMERIC_FEATURES = COMMON_NUMERIC_FEATURES.copy()
REG_CATEGORICAL_FEATURES = COMMON_CATEGORICAL_FEATURES.copy()
REG_TARGET = "passengers"

CLF_NUMERIC_FEATURES = COMMON_NUMERIC_FEATURES.copy()
CLF_CATEGORICAL_FEATURES = COMMON_CATEGORICAL_FEATURES.copy()
CLF_TARGET = "en_declin"


@dataclass
class PreparedData:
    X_train_raw: pd.DataFrame
    X_test_raw: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    preprocessor: ColumnTransformer
    X_train: np.ndarray
    X_test: np.ndarray
    train_years: list[int]
    test_years: list[int]


def build_preprocessor(numeric_features, categorical_features):
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            (
                "cat",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                categorical_features,
            ),
        ],
        remainder="drop",
    )


def _validate_dataset(
    df: pd.DataFrame,
    features: list[str],
    target: str,
    dataset_name: str,
):
    required = set(features + [target, "year"])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {dataset_name}: {missing}. "
            "Relancez d'abord `python -m ia.src.ml.run_pipeline`."
        )

    if df.duplicated(subset=["country_name", "year"]).any():
        raise ValueError(
            f"Doublons pays/année détectés dans {dataset_name}."
        )

    if df[features + [target]].isna().any().any():
        bad = (
            df[features + [target]]
            .isna()
            .sum()
        )
        raise ValueError(
            "Valeurs manquantes détectées : "
            f"{bad[bad > 0].to_dict()}"
        )


def _print_quality_summary(df: pd.DataFrame):
    if "row_quality" not in df.columns:
        print("   Qualité source : métadonnée non disponible")
        return

    counts = df["row_quality"].value_counts().to_dict()
    print(f"   Qualité source : {counts}")


def load_regression_data():
    df = pd.read_csv(REGRESSION_DATASET_PATH, low_memory=False)
    features = REG_NUMERIC_FEATURES + REG_CATEGORICAL_FEATURES

    _validate_dataset(
        df,
        features,
        REG_TARGET,
        "dataset régression",
    )

    df = df.sort_values(["year", "country_name"]).reset_index(drop=True)

    X = df[features + ["year"]].copy()
    y = pd.to_numeric(df[REG_TARGET], errors="raise")

    print(
        f"   [Régression] {len(X)} observations | "
        f"{df['country_name'].nunique()} pays | "
        f"{int(df['year'].min())}-{int(df['year'].max())}"
    )
    print(
        f"   Cible passengers (MIO_PKM) : "
        f"min={y.min():.2f} | médiane={y.median():.2f} | max={y.max():.2f}"
    )
    _print_quality_summary(df)

    return X, y


def load_classification_data():
    df = pd.read_csv(CLASSIF_DATASET_PATH, low_memory=False)
    features = CLF_NUMERIC_FEATURES + CLF_CATEGORICAL_FEATURES

    _validate_dataset(
        df,
        features,
        CLF_TARGET,
        "dataset classification",
    )

    df = df.sort_values(["year", "country_name"]).reset_index(drop=True)

    X = df[features + ["year"]].copy()
    y = pd.to_numeric(df[CLF_TARGET], errors="raise").astype(int)

    print(
        f"   [Classification] {len(X)} observations | "
        f"{df['country_name'].nunique()} pays | "
        f"{int(df['year'].min())}-{int(df['year'].max())}"
    )
    print(f"   Distribution cible : {y.value_counts().to_dict()}")
    _print_quality_summary(df)

    return X, y


def _prepare_temporal_data(
    X: pd.DataFrame,
    y: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
    test_start_year: int = TEMPORAL_TEST_START_YEAR,
) -> PreparedData:
    """
    Holdout temporel strict :
      train = années < test_start_year
      test  = années >= test_start_year

    Il n'y a aucun mélange aléatoire des années.
    """
    years = pd.to_numeric(X["year"], errors="raise").astype(int)

    train_mask = years < test_start_year
    test_mask = years >= test_start_year

    if train_mask.sum() == 0 or test_mask.sum() == 0:
        unique_years = sorted(years.unique())
        if len(unique_years) < 4:
            raise ValueError(
                "Pas assez d'années pour une validation temporelle."
            )
        fallback_start = unique_years[-2]
        train_mask = years < fallback_start
        test_mask = years >= fallback_start
        test_start_year = int(fallback_start)

    X_model = X[numeric_features + categorical_features].copy()

    X_train_raw = X_model.loc[train_mask].copy()
    X_test_raw = X_model.loc[test_mask].copy()
    y_train = y.loc[train_mask].copy()
    y_test = y.loc[test_mask].copy()

    preprocessor = build_preprocessor(
        numeric_features,
        categorical_features,
    )
    X_train = preprocessor.fit_transform(X_train_raw)
    X_test = preprocessor.transform(X_test_raw)

    train_years = sorted(years.loc[train_mask].unique().astype(int).tolist())
    test_years = sorted(years.loc[test_mask].unique().astype(int).tolist())

    print(
        f"   Split temporel : train {min(train_years)}-{max(train_years)} "
        f"({len(X_train_raw)} obs) | "
        f"test {min(test_years)}-{max(test_years)} "
        f"({len(X_test_raw)} obs)"
    )
    print(
        f"   Features transformées : {X_train.shape[1]}"
    )

    return PreparedData(
        X_train_raw=X_train_raw,
        X_test_raw=X_test_raw,
        y_train=y_train,
        y_test=y_test,
        preprocessor=preprocessor,
        X_train=X_train,
        X_test=X_test,
        train_years=train_years,
        test_years=test_years,
    )


def prepare_regression_data(
    X,
    y,
    test_start_year: int = TEMPORAL_TEST_START_YEAR,
):
    return _prepare_temporal_data(
        X,
        y,
        REG_NUMERIC_FEATURES,
        REG_CATEGORICAL_FEATURES,
        test_start_year,
    )


def prepare_classification_data(
    X,
    y,
    test_start_year: int = TEMPORAL_TEST_START_YEAR,
):
    return _prepare_temporal_data(
        X,
        y,
        CLF_NUMERIC_FEATURES,
        CLF_CATEGORICAL_FEATURES,
        test_start_year,
    )


def evaluate_regression(model, prepared: PreparedData):
    y_pred = model.predict(prepared.X_test)

    mae = mean_absolute_error(prepared.y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(prepared.y_test, y_pred))
    r2 = r2_score(prepared.y_test, y_pred)

    # Baseline "persistance" :
    # prédire N avec la valeur observée/synthétique de N-1.
    baseline_pred = prepared.X_test_raw["passengers_lag1"].to_numpy()
    baseline_mae = mean_absolute_error(prepared.y_test, baseline_pred)
    baseline_rmse = np.sqrt(
        mean_squared_error(prepared.y_test, baseline_pred)
    )
    baseline_r2 = r2_score(prepared.y_test, baseline_pred)

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "baseline_mae": float(baseline_mae),
        "baseline_rmse": float(baseline_rmse),
        "baseline_r2": float(baseline_r2),
        "beats_persistence_baseline_mae": bool(mae < baseline_mae),
        "temporal_test_start_year": int(min(prepared.test_years)),
        "train_year_min": int(min(prepared.train_years)),
        "train_year_max": int(max(prepared.train_years)),
        "test_year_min": int(min(prepared.test_years)),
        "test_year_max": int(max(prepared.test_years)),
        "n_train": int(len(prepared.y_train)),
        "n_test": int(len(prepared.y_test)),
    }


def evaluate_classification(model, prepared: PreparedData):
    y_pred = model.predict(prepared.X_test)

    metrics = {
        "accuracy": float(
            accuracy_score(prepared.y_test, y_pred)
        ),
        "precision": float(
            precision_score(
                prepared.y_test,
                y_pred,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                prepared.y_test,
                y_pred,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                prepared.y_test,
                y_pred,
                zero_division=0,
            )
        ),
    }

    if (
        hasattr(model, "predict_proba")
        and prepared.y_test.nunique() > 1
    ):
        y_proba = model.predict_proba(prepared.X_test)[:, 1]
        metrics["roc_auc"] = float(
            roc_auc_score(prepared.y_test, y_proba)
        )
    else:
        metrics["roc_auc"] = None

    # Baseline historique :
    # si N-1 < N-2, on prédit que la baisse continue en N.
    baseline_pred = (
        prepared.X_test_raw["passengers_lag1"]
        < prepared.X_test_raw["passengers_lag2"]
    ).astype(int)

    metrics["baseline_accuracy"] = float(
        accuracy_score(prepared.y_test, baseline_pred)
    )
    metrics["baseline_f1"] = float(
        f1_score(
            prepared.y_test,
            baseline_pred,
            zero_division=0,
        )
    )
    metrics["temporal_test_start_year"] = int(
        min(prepared.test_years)
    )
    metrics["train_year_min"] = int(min(prepared.train_years))
    metrics["train_year_max"] = int(max(prepared.train_years))
    metrics["test_year_min"] = int(min(prepared.test_years))
    metrics["test_year_max"] = int(max(prepared.test_years))
    metrics["n_train"] = int(len(prepared.y_train))
    metrics["n_test"] = int(len(prepared.y_test))

    return metrics


def fit_production_model(
    evaluated_model,
    X: pd.DataFrame,
    y: pd.Series,
    numeric_features: list[str],
    categorical_features: list[str],
):
    """
    Après l'évaluation temporelle, réentraîne un clone du modèle sur TOUTES
    les années 2012-2024 pour produire l'artefact utilisé en production.
    """
    X_all_raw = X[numeric_features + categorical_features].copy()

    preprocessor = build_preprocessor(
        numeric_features,
        categorical_features,
    )
    X_all = preprocessor.fit_transform(X_all_raw)

    production_model = clone(evaluated_model)
    production_model.fit(X_all, y)

    return production_model, preprocessor


def _model_feature_count(model) -> int | None:
    value = getattr(model, "n_features_in_", None)
    if value is not None:
        return int(value)

    if hasattr(model, "get_booster"):
        try:
            return int(model.get_booster().num_features())
        except Exception:
            return None

    return None


def _contract_payload(
    model,
    preprocessor,
    model_name: str,
    axis: str,
    metrics: dict,
):
    feature_names = [
        str(value)
        for value in preprocessor.get_feature_names_out()
    ]

    categories = {}
    try:
        encoder = preprocessor.named_transformers_["cat"]
        input_features = (
            CLF_CATEGORICAL_FEATURES
            if axis == "clf"
            else REG_CATEGORICAL_FEATURES
        )
        for feature, values in zip(
            input_features,
            encoder.categories_,
        ):
            categories[feature] = [
                str(value) for value in values
            ]
    except Exception:
        categories = {}

    return {
        "model_name": model_name,
        "axis": axis,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_feature_count": _model_feature_count(model),
        "preprocessor_feature_count": len(feature_names),
        "feature_names_out": feature_names,
        "numeric_features": (
            CLF_NUMERIC_FEATURES
            if axis == "clf"
            else REG_NUMERIC_FEATURES
        ),
        "categorical_features": (
            CLF_CATEGORICAL_FEATURES
            if axis == "clf"
            else REG_CATEGORICAL_FEATURES
        ),
        "categories": categories,
        "metrics": metrics,
        "dataset_quality_report": str(
            DATASET_QUALITY_REPORT_PATH
        ),
    }


def save_model_and_metrics(
    model,
    metrics,
    model_name,
    preprocessor,
    axis="clf",
):
    """
    Sauvegarde toujours le modèle ET le preprocessor qui a servi à son fit.

    Correction du bug historique :
    l'ancien code refusait d'écraser le preprocessor partagé, ce qui pouvait
    associer un modèle 36 features à un preprocessor 47 features.
    """
    model_path = MODELS_DIR / f"{model_name}_{axis}.joblib"
    metrics_path = MODELS_DIR / f"{model_name}_{axis}_metrics.json"
    specific_prep_path = (
        MODELS_DIR
        / f"{model_name}_{axis}_preprocessor.joblib"
    )
    contract_path = MODELS_DIR / f"{model_name}_{axis}_contract.json"

    joblib.dump(model, model_path)
    joblib.dump(preprocessor, specific_prep_path)

    # Compatibilité avec les anciens chemins du projet :
    shared_prep_path = (
        PREPROCESSOR_CLF_PATH
        if axis == "clf"
        else PREPROCESSOR_REG_PATH
    )
    joblib.dump(preprocessor, shared_prep_path)

    contract = _contract_payload(
        model,
        preprocessor,
        model_name,
        axis,
        metrics,
    )

    model_count = contract["model_feature_count"]
    prep_count = contract["preprocessor_feature_count"]

    if (
        model_count is not None
        and model_count != prep_count
    ):
        raise RuntimeError(
            "Incompatibilité avant sauvegarde : "
            f"modèle={model_count} features, "
            f"preprocessor={prep_count}."
        )

    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    contract_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"   Modèle       : {model_path}")
    print(f"   Preprocessor : {specific_prep_path}")
    print(f"   Contrat      : {contract_path}")
    print(
        f"   Compatibilité validée : "
        f"{prep_count} features transformées"
    )


def load_model_and_metrics(model_name, axis="clf"):
    model_path = MODELS_DIR / f"{model_name}_{axis}.joblib"
    metrics_path = MODELS_DIR / f"{model_name}_{axis}_metrics.json"

    if not model_path.exists() or not metrics_path.exists():
        raise FileNotFoundError(
            f"Modèle/métriques introuvables : {model_name}_{axis}"
        )

    model = joblib.load(model_path)
    metrics = json.loads(
        metrics_path.read_text(encoding="utf-8")
    )
    return model, metrics


def make_temporal_cv_splits(
    X: pd.DataFrame,
    test_start_year: int = TEMPORAL_TEST_START_YEAR,
):
    """
    Folds chronologiques sur la partie pré-holdout.
    Retourne des index positionnels compatibles avec GridSearchCV.
    """
    pre = X[X["year"] < test_start_year].copy()
    years = sorted(pre["year"].astype(int).unique().tolist())

    if len(years) < 5:
        raise ValueError(
            "Pas assez d'années pré-holdout pour la CV temporelle."
        )

    # 3 à 5 folds selon la profondeur historique.
    validation_years = years[max(3, len(years) // 2):]
    validation_years = validation_years[-5:]

    splits = []
    year_values = pre["year"].astype(int).to_numpy()

    for val_year in validation_years:
        train_idx = np.where(year_values < val_year)[0]
        val_idx = np.where(year_values == val_year)[0]

        if len(train_idx) and len(val_idx):
            splits.append((train_idx, val_idx))

    if len(splits) < 2:
        raise ValueError(
            "Impossible de construire au moins deux folds temporels."
        )

    return splits
