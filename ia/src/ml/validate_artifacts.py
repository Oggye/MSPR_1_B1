from __future__ import annotations

import json

import pandas as pd

from .config import (
    CLASSIF_DATASET_PATH,
    FORECAST_CLASSIFIER_PATH,
    FORECAST_MANIFEST_PATH,
    FORECAST_REGRESSOR_PATH,
    REGRESSION_DATASET_PATH,
)
from .predict import load_artifacts, predict


def main():
    classifier, regressor, manifest = load_artifacts()

    print("Classifier :", type(classifier).__name__)
    print("Regressor  :", type(regressor).__name__)
    print(
        "Horizons   :",
        manifest.get("forecast_horizons"),
    )

    clf = pd.read_csv(CLASSIF_DATASET_PATH)
    reg = pd.read_csv(REGRESSION_DATASET_PATH)

    row = reg.sort_values(
        ["target_year", "horizon"]
    ).iloc[-1]

    result = predict(
        country=str(row["country_name"]),
        horizon=int(row["horizon"]),
        passengers_current=float(row["passengers"]),
        passengers_previous=float(row["passengers_previous"]),
        co2_current=float(row["co2_emissions"]),
        co2_previous=float(row["co2_previous"]),
        train_count_current=float(row["train_count_current"]),
        night_share_current=float(row["night_share_current"]),
        real_share_current=float(row["real_share_current"]),
        avg_distance_current=float(row["avg_distance_current"]),
        avg_duration_current=float(row["avg_duration_current"]),
        operator_count_current=float(row["operator_count_current"]),
        network_data_available=int(row["network_data_available"]),
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    assert FORECAST_CLASSIFIER_PATH.exists()
    assert FORECAST_REGRESSOR_PATH.exists()
    assert FORECAST_MANIFEST_PATH.exists()
    assert len(clf) > 0
    assert len(reg) > 0

    print("Artefacts multi-horizon : OK")


if __name__ == "__main__":
    main()
