import numpy as np
import pytest

from ia.src.ml import predict as predict_module
from ia.src.ml.train_forecasting import MODEL_FEATURES


class FakeClassifier:
    def __init__(self, prediction=1, probability=0.8):
        self.prediction = prediction
        self.probability = probability
        self.rows = []

    def predict(self, frame):
        self.rows.append(frame.copy())
        return np.array([self.prediction])

    def predict_proba(self, frame):
        self.rows.append(frame.copy())
        return np.array([[1.0 - self.probability, self.probability]])


class FakeRegressor:
    def __init__(self, prediction=150.0):
        self.prediction = prediction
        self.rows = []

    def predict(self, frame):
        self.rows.append(frame.copy())
        return np.array([self.prediction])


def _manifest(*, baseline="linear_trend", ml_weight=0.25, q90=10.0):
    return {
        "version": 7,
        "classification": {"selected_model": "fake-classifier"},
        "regression": {
            "selected_model": "fake-regressor",
            "selected_baseline": baseline,
            "blend_weight_ml": ml_weight,
            "final_holdout": {
                "interval_q90_by_horizon": {"1": q90, "2": q90, "3": q90}
            },
        },
    }


def _arguments(horizon=2, **overrides):
    values = {
        "country": "France",
        "horizon": horizon,
        "passengers_current": 100,
        "passengers_previous": 90,
        "co2_current": 50,
        "co2_previous": 40,
        "train_count_current": 12,
        "night_share_current": 0.25,
        "real_share_current": 0.75,
        "avg_distance_current": 300,
        "avg_duration_current": 180,
        "operator_count_current": 4,
        "network_data_available": 1,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize("horizon", [0, 4])
def test_prediction_horizon_is_limited_to_three_years(monkeypatch, horizon):
    def unexpected_load():
        raise AssertionError("Artifacts must not be loaded for an invalid horizon")

    monkeypatch.setattr(predict_module, "load_artifacts", unexpected_load)

    with pytest.raises(ValueError, match="Horizon invalide"):
        predict_module.predict(**_arguments(horizon))


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_prediction_accepts_supported_horizons(monkeypatch, horizon):
    artifacts = (FakeClassifier(), FakeRegressor(), _manifest())
    monkeypatch.setattr(predict_module, "load_artifacts", lambda: artifacts)

    result = predict_module.predict(**_arguments(horizon))

    assert result["horizon"] == horizon


def test_prediction_builds_origin_only_model_features(monkeypatch):
    classifier = FakeClassifier()
    regressor = FakeRegressor()
    monkeypatch.setattr(
        predict_module,
        "load_artifacts",
        lambda: (classifier, regressor, _manifest()),
    )

    predict_module.predict(**_arguments())
    row = regressor.rows[0].iloc[0]

    assert set(regressor.rows[0].columns) == set(MODEL_FEATURES)
    assert len(regressor.rows[0].columns) == len(MODEL_FEATURES)
    assert row["country_name"] == "France"
    assert row["horizon"] == 2
    assert row["passengers"] == 100
    assert row["passengers_previous"] == 90
    assert row["passenger_growth_1y"] == pytest.approx(1 / 9)
    assert row["co2_growth_1y"] == pytest.approx(0.25)
    assert row["network_data_available"] == 1


def test_prediction_returns_probability_blend_interval_and_contract(monkeypatch):
    monkeypatch.setattr(
        predict_module,
        "load_artifacts",
        lambda: (FakeClassifier(), FakeRegressor(150), _manifest()),
    )

    result = predict_module.predict(**_arguments(horizon=2))

    # Linear trend baseline: 100 + 2 * (100 - 90) = 120.
    # Blend: 25% * 150 + 75% * 120 = 127.5.
    assert result["classification"]["prediction"] == 1
    assert result["classification"]["probability_decline"] == pytest.approx(0.8)
    assert result["regression"]["baseline_prediction"] == pytest.approx(120)
    assert result["regression"]["ml_prediction"] == pytest.approx(150)
    assert result["regression"]["prediction"] == pytest.approx(127.5)
    assert result["regression"]["interval_low"] == pytest.approx(117.5)
    assert result["regression"]["interval_high"] == pytest.approx(137.5)
    assert result["regression"]["blend_weight_ml"] == pytest.approx(0.25)
    assert result["manifest_version"] == 7
    assert {"classification", "regression", "horizon", "manifest_version"} <= result.keys()


def test_prediction_uses_persistence_baseline(monkeypatch):
    monkeypatch.setattr(
        predict_module,
        "load_artifacts",
        lambda: (
            FakeClassifier(),
            FakeRegressor(200),
            _manifest(baseline="persistence", ml_weight=0.5),
        ),
    )

    result = predict_module.predict(**_arguments(horizon=3))

    assert result["regression"]["baseline_prediction"] == pytest.approx(100)
    assert result["regression"]["prediction"] == pytest.approx(150)


def test_prediction_interval_lower_bound_is_never_negative(monkeypatch):
    monkeypatch.setattr(
        predict_module,
        "load_artifacts",
        lambda: (
            FakeClassifier(),
            FakeRegressor(2),
            _manifest(baseline="persistence", ml_weight=1.0, q90=10),
        ),
    )

    result = predict_module.predict(**_arguments(horizon=1))

    assert result["regression"]["prediction"] == pytest.approx(2)
    assert result["regression"]["interval_low"] == 0
    assert result["regression"]["interval_high"] == pytest.approx(12)
