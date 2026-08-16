import numpy as np
import pandas as pd
import pytest

from ia.src.ml import train_forecasting
from ia.src.ml.train_forecasting import (
    _baseline_regression,
    _best_blend_weight,
    _classification_metrics,
    _regression_metrics,
    _rolling_splits,
    _weighted_mae,
)


def test_temporal_split_never_trains_on_future(monkeypatch):
    monkeypatch.setattr(
        train_forecasting,
        "CV_VALIDATION_YEARS",
        [2019, 2020, 2021, 2022, 2025],
    )
    frame = pd.DataFrame(
        {"target_year": [2018, 2019, 2020, 2021, 2022, 2022]},
        index=[10, 11, 20, 21, 30, 31],
    )

    splits = _rolling_splits(frame)

    assert [year for year, _, _ in splits] == [2019, 2020, 2021, 2022]
    for validation_year, train_idx, validation_idx in splits:
        train = frame.loc[train_idx]
        validation = frame.loc[validation_idx]
        assert (train["target_year"] < validation_year).all()
        assert (validation["target_year"] == validation_year).all()
        assert set(train_idx).isdisjoint(validation_idx)
        assert train["target_year"].max() < validation["target_year"].min()


def test_rolling_splits_requires_at_least_two_folds(monkeypatch):
    monkeypatch.setattr(train_forecasting, "CV_VALIDATION_YEARS", [2020, 2021])
    frame = pd.DataFrame({"target_year": [2019, 2020]})

    with pytest.raises(ValueError, match="folds temporels"):
        _rolling_splits(frame)


@pytest.mark.parametrize("horizon", [1, 2, 3])
def test_regression_baselines_for_each_horizon(horizon):
    frame = pd.DataFrame(
        {"passengers_previous": [100], "passengers": [110], "horizon": [horizon]}
    )

    result = _baseline_regression(frame)

    assert result["persistence"][0] == 110
    assert result["linear_trend"][0] == 110 + 10 * horizon


def test_linear_trend_baseline_is_clipped_at_zero():
    frame = pd.DataFrame(
        {"passengers_previous": [100], "passengers": [20], "horizon": [3]}
    )

    result = _baseline_regression(frame)

    assert result["linear_trend"][0] == 0


def test_best_blend_selects_perfect_baseline():
    result = _best_blend_weight(
        y_true=[10, 20],
        ml_pred=[30, 40],
        baseline_pred=[10, 20],
        weights=[1, 1],
    )

    assert 0 <= result["weight"] <= 1
    assert result == {"weight": 0.0, "mae": 0.0}


def test_best_blend_selects_perfect_ml_prediction():
    result = _best_blend_weight(
        y_true=[10, 20],
        ml_pred=[10, 20],
        baseline_pred=[30, 40],
        weights=[1, 1],
    )

    assert result == {"weight": 1.0, "mae": 0.0}


def test_weighted_mae_uses_sample_weights():
    assert _weighted_mae([0, 10], [2, 14], [1, 3]) == pytest.approx(3.5)


def test_regression_metrics_are_deterministic():
    result = _regression_metrics([1, 2, 3], [1, 3, 2], weights=[1, 1, 2])

    assert result["mae"] == pytest.approx(2 / 3)
    assert result["rmse"] == pytest.approx(np.sqrt(2 / 3))
    assert result["r2"] == pytest.approx(0.0)
    assert result["weighted_mae"] == pytest.approx(0.75)


def test_classification_metrics_include_roc_auc():
    result = _classification_metrics(
        y_true=[0, 0, 1, 1],
        y_pred=[0, 1, 1, 1],
        y_proba=[0.1, 0.7, 0.8, 0.9],
    )

    assert result["accuracy"] == pytest.approx(0.75)
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(1.0)
    assert result["f1"] == pytest.approx(0.8)
    assert result["roc_auc"] == pytest.approx(1.0)


def test_classification_metrics_single_class_does_not_compute_auc():
    result = _classification_metrics([0, 0], [0, 0], [0.1, 0.2])

    assert result["roc_auc"] is None
