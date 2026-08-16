import pandas as pd
import pytest

from ia.src.ml import predict as predict_module
from ia.src.ml import validate_artifacts


def test_load_artifacts_detects_missing_required_file(monkeypatch, tmp_path):
    classifier_path = tmp_path / "forecast_classifier.joblib"
    regressor_path = tmp_path / "forecast_regressor.joblib"
    manifest_path = tmp_path / "forecast_manifest.json"
    classifier_path.touch()
    regressor_path.touch()

    monkeypatch.setattr(predict_module, "FORECAST_CLASSIFIER_PATH", classifier_path)
    monkeypatch.setattr(predict_module, "FORECAST_REGRESSOR_PATH", regressor_path)
    monkeypatch.setattr(predict_module, "FORECAST_MANIFEST_PATH", manifest_path)
    predict_module.load_artifacts.cache_clear()

    with pytest.raises(FileNotFoundError, match="forecast_manifest.json"):
        predict_module.load_artifacts()

    predict_module.load_artifacts.cache_clear()


def test_validate_artifacts_nominal_path_uses_fake_artifacts(
    monkeypatch, tmp_path, capsys
):
    classifier_path = tmp_path / "forecast_classifier.joblib"
    regressor_path = tmp_path / "forecast_regressor.joblib"
    manifest_path = tmp_path / "forecast_manifest.json"
    for path in (classifier_path, regressor_path, manifest_path):
        path.touch()

    monkeypatch.setattr(validate_artifacts, "FORECAST_CLASSIFIER_PATH", classifier_path)
    monkeypatch.setattr(validate_artifacts, "FORECAST_REGRESSOR_PATH", regressor_path)
    monkeypatch.setattr(validate_artifacts, "FORECAST_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        validate_artifacts,
        "load_artifacts",
        lambda: (object(), object(), {"forecast_horizons": [1, 2, 3]}),
    )
    row = pd.DataFrame(
        [
            {
                "target_year": 2025,
                "horizon": 1,
                "country_name": "France",
                "passengers": 100,
                "passengers_previous": 90,
                "co2_emissions": 50,
                "co2_previous": 45,
                "train_count_current": 1,
                "night_share_current": 1,
                "real_share_current": 1,
                "avg_distance_current": 100,
                "avg_duration_current": 60,
                "operator_count_current": 1,
                "network_data_available": 1,
            }
        ]
    )
    monkeypatch.setattr(validate_artifacts.pd, "read_csv", lambda _path: row.copy())
    monkeypatch.setattr(
        validate_artifacts,
        "predict",
        lambda **_kwargs: {"classification": {}, "regression": {}},
    )

    validate_artifacts.main()

    assert "Artefacts multi-horizon : OK" in capsys.readouterr().out
