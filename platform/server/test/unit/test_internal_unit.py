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


def test_report_metadata_marks_report_older_than_data_as_stale(tmp_path):
    report = tmp_path / "diagnostic.json"
    report.write_text("{}", encoding="utf-8")

    result = internal._report_metadata(report, report.stat().st_mtime_ns + 1)

    assert result["available"] is True
    assert result["stale"] is True


def test_reports_summary_uses_generated_warehouse_quality(tmp_path, monkeypatch):
    quality_path = tmp_path / "data" / "warehouse" / "quality_reports.json"
    quality_path.parent.mkdir(parents=True)
    quality_path.write_text(json.dumps({"summary": {"total_sources_processed": 8}}), encoding="utf-8")
    monkeypatch.setattr(internal, "PROJECT_ROOT", tmp_path)

    result = internal._reports_summary()

    assert result["quality"]["summary"]["total_sources_processed"] == 8
    assert result["quality_meta"]["path"] == str(quality_path)


def test_run_diagnostic_ignores_previous_report_on_failure(tmp_path, monkeypatch):
    script = tmp_path / "etl" / "audit" / "diagnostic.py"
    script.parent.mkdir(parents=True)
    script.write_text("raise SystemExit(1)", encoding="utf-8")
    report = tmp_path / "data" / "audit" / "diagnostic_report.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"date_diagnostic": "old"}), encoding="utf-8")
    monkeypatch.setattr(internal, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        internal,
        "_run_command",
        lambda *args, **kwargs: {
            "available": True,
            "success": False,
            "returncode": 1,
            "stderr": "failure",
            "ran_at": "now",
        },
    )

    result = internal.run_diagnostic()

    assert result["success"] is False
    assert result["report"] is None
    assert result["stale_report_ignored"] is True


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


def test_ia_runtime_summary_returns_prometheus_metrics(monkeypatch):
    query_values = {
        'sum(obrail_ai_predictions_total{status="success"})': 12.0,
        'sum(obrail_ai_predictions_total{status="error"})': 2.0,
        (
            "histogram_quantile(0.95, "
            "sum(rate(obrail_ai_inference_seconds_bucket[5m])) by (le))"
        ): 0.084,
        'sum(increase(obrail_ai_predictions_total{status="error"}[5m]))': 0.0,
    }
    monkeypatch.setattr(
        internal,
        "_prometheus_query",
        lambda query: query_values[query],
    )

    def vector(query):
        if "classification" in query:
            return [
                {"metric": {"label": "Croissance / stabilité probable"}, "value": 4.0},
                {"metric": {"label": "Baisse probable"}, "value": 3.0},
            ]
        return [
            {"metric": {"trend": "Croissance"}, "value": 3.0},
            {"metric": {"trend": "Stable"}, "value": 1.0},
            {"metric": {"trend": "Déclin"}, "value": 1.0},
        ]

    monkeypatch.setattr(internal, "_prometheus_vector", vector)

    result = internal._ia_runtime_summary()

    assert result["available"] is True
    assert result["status"] == "healthy"
    assert result["predictions_success"] == 12.0
    assert result["predictions_error"] == 2.0
    assert result["latency_p95_seconds"] == 0.084
    assert result["classification"]["total"] == 7.0
    assert result["classification"]["distribution"]["Baisse probable"] == 3.0
    assert result["regression"]["total"] == 5.0
    assert result["regression"]["distribution"]["Stable"] == 1.0


def test_ia_runtime_summary_handles_no_predictions(monkeypatch):
    monkeypatch.setattr(
        internal,
        "_prometheus_query",
        lambda query: float("nan") if "histogram_quantile" in query else 0.0,
    )
    monkeypatch.setattr(internal, "_prometheus_vector", lambda query: [])

    result = internal._ia_runtime_summary()

    assert result["available"] is True
    assert result["status"] == "no_data"
    assert result["latency_p95_seconds"] is None
    assert result["classification"] == {"total": 0, "distribution": {}}
    assert result["regression"] == {"total": 0, "distribution": {}}


def test_overview_keeps_offline_ia_when_prometheus_is_unavailable(monkeypatch):
    offline = {
        "available": True,
        "status": "healthy",
        "artifacts": {"manifest": True, "classifier": True, "regressor": True},
        "classification": {"overall": {"f1": 0.82}},
        "regression": {"overall": {"mae": 123.4}},
    }
    monkeypatch.setattr(internal, "_first_ok", lambda urls, path: ({"error": "offline"}, None))
    monkeypatch.setattr(internal, "_prometheus_query", lambda query: None)
    monkeypatch.setattr(internal, "_prometheus_vector", lambda query: [])
    monkeypatch.setattr(internal, "_ia_summary", lambda: offline.copy())
    monkeypatch.setattr(internal, "_reports_summary", lambda: {})
    monkeypatch.setattr(internal, "_docker_status", lambda: {})
    monkeypatch.setattr(internal, "_github_actions_status", lambda: {})
    monkeypatch.setattr(internal, "_db_totals", lambda: {})

    result = internal.get_internal_overview()

    assert result["ia"]["available"] is True
    assert result["ia"]["status"] == "healthy"
    assert result["ia"]["artifacts"]["manifest"] is True
    assert result["ia"]["classification"]["overall"]["f1"] == 0.82
    assert result["ia"]["runtime"]["available"] is False
