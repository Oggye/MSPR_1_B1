import numpy as np
import pandas as pd
import pytest

from ia.src.ml.build_dataset import (
    _safe_growth,
    _source_is_observed,
    add_historical_features,
    build_multihorizon_examples,
)
from ia.src.ml.train_forecasting import MODEL_FEATURES


@pytest.mark.parametrize(
    ("previous", "current", "expected"),
    [
        (100, 110, 0.10),
        (100, 90, -0.10),
        ("100", "110", 0.10),
        (0, 100, 0.0),
    ],
)
def test_safe_growth(previous, current, expected):
    result = float(_safe_growth(current, previous))

    assert result == pytest.approx(expected)
    assert np.isfinite(result)


def test_add_historical_features_keeps_country_boundaries():
    source = pd.DataFrame(
        [
            (1, 2020, 100, 50),
            (1, 2021, 110, 55),
            (1, 2022, 99, 44),
            (2, 2020, 200, 80),
            (2, 2021, 180, 88),
        ],
        columns=["country_id", "year", "passengers", "co2_emissions"],
    )
    source["passengers_source"] = "eurostat"
    source["co2_source"] = "eurostat"

    result = add_historical_features(source)
    france_2021 = result.query("country_id == 1 and year == 2021").iloc[0]
    france_2022 = result.query("country_id == 1 and year == 2022").iloc[0]
    country_2_first = result.query("country_id == 2 and year == 2020").iloc[0]

    assert france_2021["passengers_previous"] == 100
    assert france_2021["co2_previous"] == 50
    assert france_2021["passenger_growth_1y"] == pytest.approx(0.10)
    assert france_2021["co2_growth_1y"] == pytest.approx(0.10)
    assert france_2022["passengers_previous"] == 110
    assert france_2022["passenger_growth_1y"] == pytest.approx(-0.10)
    assert country_2_first[["passengers_previous", "co2_previous"]].isna().all()


def _history(years, passengers, country_id=1, sources="eurostat"):
    frame = pd.DataFrame(
        {
            "country_id": country_id,
            "country_name": "France",
            "year": years,
            "passengers": passengers,
            "co2_emissions": [value / 10 for value in passengers],
            "passengers_source": sources,
            "co2_source": sources,
        }
    )
    return add_historical_features(frame)


def test_multihorizon_target_is_direct():
    history = _history(
        [2020, 2021, 2022, 2023, 2024],
        [100, 110, 105, 120, 130],
    )

    result = build_multihorizon_examples(history)
    origin = result[result["year"] == 2021].sort_values("horizon")

    assert origin["horizon"].tolist() == [1, 2, 3]
    assert origin["target_year"].tolist() == [2022, 2023, 2024]
    assert origin["target_passengers"].tolist() == [105, 120, 130]
    assert origin["passengers"].tolist() == [110, 110, 110]
    assert set(result["horizon"]) <= {1, 2, 3}
    assert result["passengers_previous"].notna().all()


def test_forecast_does_not_treat_year_gaps_as_contiguous():
    history = _history([2020, 2021, 2023], [100, 110, 130])

    result = build_multihorizon_examples(history)

    assert result.empty


@pytest.mark.parametrize(
    ("future", "expected"),
    [(90, 1), (100, 0), (110, 0)],
)
def test_decline_target_is_strictly_lower(future, expected):
    history = _history([2020, 2021, 2022], [95, 100, future])

    result = build_multihorizon_examples(history)
    row = result.query("year == 2021 and horizon == 1").iloc[0]

    assert row["en_declin"] == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("eurostat", True),
        (" Observed ", True),
        ("REAL", True),
        ("unknown", False),
        ("synthetic_reference", False),
        (None, False),
    ],
)
def test_source_is_observed(source, expected):
    result = _source_is_observed(pd.Series([source]))

    assert bool(result.iloc[0]) is expected


def test_sample_quality_weights_are_stable():
    observed = _history([2020, 2021, 2022], [90, 100, 110], 1, "eurostat")
    mixed = _history([2020, 2021, 2022], [90, 100, 110], 2, "eurostat")
    mixed.loc[mixed["year"] == 2021, "co2_source"] = "unknown"
    synthetic = _history([2020, 2021, 2022], [90, 100, 110], 3, "unknown")

    result = build_multihorizon_examples(
        pd.concat([observed, mixed, synthetic], ignore_index=True)
    )
    weights = (
        result.query("year == 2021 and horizon == 1")
        .set_index("row_quality")["sample_weight"]
        .to_dict()
    )

    assert weights == {
        "observed": 1.0,
        "mixed": 0.70,
        "synthetic_or_unknown": 0.40,
    }


def test_target_columns_are_not_model_features():
    forbidden = {
        "target_passengers",
        "en_declin",
        "target_passengers_source",
        "co2_per_passenger",
    }

    assert forbidden.isdisjoint(MODEL_FEATURES)
    assert not any("target" in feature or "future" in feature for feature in MODEL_FEATURES)
    assert {"passengers", "passengers_previous"} <= set(MODEL_FEATURES)
