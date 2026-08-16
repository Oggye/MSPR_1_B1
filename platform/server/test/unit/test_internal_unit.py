import json
from pathlib import Path

from app.routers import internal


def _set_ia_paths(monkeypatch, models_dir):
    monkeypatch.setattr(internal, "IA_MODELS_DIR", models_dir)
    monkeypatch.setattr(internal, "IA_MANIFEST", models_dir / "forecast_manifest.json")
    monkeypatch.setattr(internal, "IA_CLASSIFIER", models_dir / "forecast_classifier.joblib")
    monkeypatch.setattr(internal, "IA_REGRESSOR", models_dir / "forecast_regressor.joblib")


def test_read_json_returns_data_for_valid_file(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    assert internal._read_json(report) == {"status": "ok"}


def test_read_json_returns_none_for_missing_file(tmp_path):
    assert internal._read_json(tmp_path / "missing.json") is None


def test_scan_csv_dir_counts_files_and_lines(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("header\none\ntwo\n", encoding="utf-8")

    result = internal._scan_csv_dir(tmp_path, with_lines=True)

    assert result["exists"] is True
    assert result["files"] == 1
    assert result["details"][0]["name"] == "data.csv"
    assert result["details"][0]["lines"] == 2


def test_scan_csv_dir_handles_missing_directory(tmp_path):
    result = internal._scan_csv_dir(tmp_path / "missing")

    assert result == {
        "exists": False,
        "files": 0,
        "total_size_kb": 0,
        "details": [],
    }


def test_run_command_reports_success():
    result = internal._run_command(["python", "--version"], timeout=10)

    assert result["available"] is True
    assert result["success"] is True
    assert result["returncode"] == 0


def test_first_ok_returns_first_success(monkeypatch):
    calls = []

    def fake_http_json(url, timeout=2):
        calls.append(url)
        if "bad" in url:
            return {"error": "unavailable"}
        return {"status": "ok"}

    monkeypatch.setattr(internal, "_http_json", fake_http_json)

    result, base_url = internal._first_ok(["http://bad", "http://good"], "/health")

    assert result == {"status": "ok"}
    assert base_url == "http://good"
    assert calls == ["http://bad/health", "http://good/health"]


def test_ia_summary_returns_healthy_for_complete_artifacts(tmp_path, monkeypatch):
    _set_ia_paths(monkeypatch, tmp_path)
    manifest = {
        "version": 3,
        "architecture": "direct_multi_horizon",
        "forecast_horizons": [1, 2, 3],
        "units": {"passengers": "MIO_PKM"},
        "classification": {
            "selected_model": "xgboost",
            "final_holdout": {"overall": {"f1": 0.82, "roc_auc": 0.87}, "by_horizon": {}},
        },
        "regression": {
            "selected_model": "xgboost",
            "selected_baseline": "persistence",
            "final_holdout": {
                "overall": {"mae": 123.4, "r2": 0.75},
                "baseline_only": {"mae": 130.0},
                "by_horizon": {},
            },
        },
    }
    internal.IA_MANIFEST.write_text(json.dumps(manifest), encoding="utf-8")
    internal.IA_CLASSIFIER.write_bytes(b"classifier")
    internal.IA_REGRESSOR.write_bytes(b"regressor")

    result = internal._ia_summary()

    assert result["available"] is True
    assert result["status"] == "healthy"
    assert result["classification"]["overall"]["f1"] == 0.82
    assert result["regression"]["overall"]["mae"] == 123.4
    assert result["regression"]["baseline_metrics"]["mae"] == 130.0


def test_ia_summary_handles_missing_manifest(tmp_path, monkeypatch):
    _set_ia_paths(monkeypatch, tmp_path)

    result = internal._ia_summary()

    assert result["available"] is False
    assert result["status"] == "unavailable"
    assert result["artifacts"] == {"manifest": False, "classifier": False, "regressor": False}


def test_ia_summary_handles_invalid_manifest(tmp_path, monkeypatch):
    _set_ia_paths(monkeypatch, tmp_path)
    internal.IA_MANIFEST.write_text("not valid JSON", encoding="utf-8")

    result = internal._ia_summary()

    assert result["available"] is False
    assert result["status"] == "error"
    assert result["error"] == "Impossible de lire le manifest IA"


def test_ia_summary_returns_degraded_when_classifier_is_missing(tmp_path, monkeypatch):
    _set_ia_paths(monkeypatch, tmp_path)
    internal.IA_MANIFEST.write_text(json.dumps({"version": 3}), encoding="utf-8")
    internal.IA_REGRESSOR.write_bytes(b"regressor")

    result = internal._ia_summary()

    assert result["available"] is True
    assert result["status"] == "degraded"
    assert result["artifacts"]["classifier"] is False
