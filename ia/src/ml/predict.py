from __future__ import annotations

import json
import logging
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from .config import (
    FORECAST_CLASSIFIER_PATH,
    FORECAST_MANIFEST_PATH,
    FORECAST_REGRESSOR_PATH,
    MAX_FORECAST_HORIZON,
)

logger = logging.getLogger("obrail.ml.predict")


@lru_cache(maxsize=1)
def load_artifacts():
    required = [
        FORECAST_CLASSIFIER_PATH,
        FORECAST_REGRESSOR_PATH,
        FORECAST_MANIFEST_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Artefacts multi-horizon manquants : "
            + ", ".join(missing)
        )

    classifier = joblib.load(FORECAST_CLASSIFIER_PATH)
    regressor = joblib.load(FORECAST_REGRESSOR_PATH)
    manifest = json.loads(
        FORECAST_MANIFEST_PATH.read_text(encoding="utf-8")
    )

    return classifier, regressor, manifest


def _growth(current: float, previous: float) -> float:
    if abs(previous) <= 1e-12:
        return 0.0
    return (current - previous) / abs(previous)


def _build_row(
    *,
    country: str,
    horizon: int,
    passengers_current: float,
    passengers_previous: float,
    co2_current: float,
    co2_previous: float,
    train_count_current: float,
    night_share_current: float,
    real_share_current: float,
    avg_distance_current: float,
    avg_duration_current: float,
    operator_count_current: float,
    network_data_available: int,
):
    return pd.DataFrame(
        [
            {
                "country_name": country,
                "horizon": int(horizon),
                "passengers": float(passengers_current),
                "passengers_previous": float(passengers_previous),
                "passenger_growth_1y": _growth(
                    passengers_current,
                    passengers_previous,
                ),
                "co2_emissions": float(co2_current),
                "co2_previous": float(co2_previous),
                "co2_growth_1y": _growth(
                    co2_current,
                    co2_previous,
                ),
                "train_count_current": float(train_count_current),
                "night_share_current": float(night_share_current),
                "real_share_current": float(real_share_current),
                "avg_distance_current": float(avg_distance_current),
                "avg_duration_current": float(avg_duration_current),
                "operator_count_current": float(operator_count_current),
                "network_data_available": int(network_data_available),
            }
        ]
    )


def _baseline_prediction(
    mode: str,
    horizon: int,
    passengers_current: float,
    passengers_previous: float,
):
    if mode == "linear_trend":
        value = (
            passengers_current
            + horizon * (
                passengers_current - passengers_previous
            )
        )
        return max(0.0, float(value))

    return max(0.0, float(passengers_current))


def predict(
    *,
    country: str,
    horizon: int,
    passengers_current: float,
    passengers_previous: float,
    co2_current: float,
    co2_previous: float,
    train_count_current: float = 0.0,
    night_share_current: float = 0.0,
    real_share_current: float = 0.0,
    avg_distance_current: float = 0.0,
    avg_duration_current: float = 0.0,
    operator_count_current: float = 0.0,
    network_data_available: int = 0,
):
    if horizon < 1 or horizon > MAX_FORECAST_HORIZON:
        raise ValueError(
            f"Horizon invalide : {horizon}. "
            f"Valeurs autorisées : 1 à {MAX_FORECAST_HORIZON}."
        )

    classifier, regressor, manifest = load_artifacts()

    X = _build_row(
        country=country,
        horizon=horizon,
        passengers_current=passengers_current,
        passengers_previous=passengers_previous,
        co2_current=co2_current,
        co2_previous=co2_previous,
        train_count_current=train_count_current,
        night_share_current=night_share_current,
        real_share_current=real_share_current,
        avg_distance_current=avg_distance_current,
        avg_duration_current=avg_duration_current,
        operator_count_current=operator_count_current,
        network_data_available=network_data_available,
    )

    class_pred = int(classifier.predict(X)[0])

    if hasattr(classifier, "predict_proba"):
        decline_probability = float(
            classifier.predict_proba(X)[0][1]
        )
    else:
        decline_probability = float(class_pred)

    ml_regression = max(
        0.0,
        float(regressor.predict(X)[0]),
    )

    regression_cfg = manifest["regression"]
    baseline = _baseline_prediction(
        regression_cfg["selected_baseline"],
        horizon,
        passengers_current,
        passengers_previous,
    )

    ml_weight = float(
        regression_cfg["blend_weight_ml"]
    )
    final_prediction = (
        ml_weight * ml_regression
        + (1.0 - ml_weight) * baseline
    )
    final_prediction = max(0.0, float(final_prediction))

    q90 = float(
        regression_cfg[
            "final_holdout"
        ][
            "interval_q90_by_horizon"
        ].get(str(horizon), 0.0)
    )

    interval_low = max(0.0, final_prediction - q90)
    interval_high = final_prediction + q90

    logger.info(
        "[FORECAST] %s horizon=%s | clf=%s proba=%.3f | "
        "reg=%.2f [%0.2f, %.2f]",
        country,
        horizon,
        class_pred,
        decline_probability,
        final_prediction,
        interval_low,
        interval_high,
    )

    return {
        "classification": {
            "prediction": class_pred,
            "label": (
                "Baisse probable"
                if class_pred == 1
                else "Croissance / stabilité probable"
            ),
            "probability_decline": decline_probability,
            "model": manifest["classification"]["selected_model"],
        },
        "regression": {
            "prediction": final_prediction,
            "interval_low": interval_low,
            "interval_high": interval_high,
            "interval_level": 0.90,
            "ml_prediction": ml_regression,
            "baseline_prediction": baseline,
            "blend_weight_ml": ml_weight,
            "model": regression_cfg["selected_model"],
            "baseline": regression_cfg["selected_baseline"],
        },
        "horizon": int(horizon),
        "manifest_version": manifest.get("version", 3),
    }
