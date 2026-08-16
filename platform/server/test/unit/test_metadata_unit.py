import json

import pytest
from fastapi import HTTPException

from app.routers import metadata


def test_quality_report_uses_file_when_available(tmp_path, monkeypatch):
    report_path = tmp_path / "quality_reports.json"
    report = {"execution_date": "2026-01-01", "project": "test", "summary": {"success": True}}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(metadata, "_quality_report_candidates", lambda: [report_path])

    result = metadata.get_quality_report()

    assert result["execution_date"] == report["execution_date"]
    assert result["project"] == report["project"]
    assert result["summary"] == report["summary"]
    assert result["metadata_report_source"] == str(report_path)
    assert result["metadata_report_available"] is True


def test_quality_report_returns_default_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        metadata,
        "_quality_report_candidates",
        lambda: [tmp_path / "missing.json"],
    )

    result = metadata.get_quality_report()

    assert result["project"].startswith("ObRail")
    assert result["summary"]["success"] is False
    assert result["summary"]["reason"] == "quality_report_missing"
    assert result["metadata_report_available"] is False


def test_quality_report_wraps_unreadable_json(tmp_path, monkeypatch):
    report_path = tmp_path / "quality_reports.json"
    report_path.write_text("not valid JSON", encoding="utf-8")
    monkeypatch.setattr(metadata, "_quality_report_candidates", lambda: [report_path])

    with pytest.raises(HTTPException) as exc:
        metadata.get_quality_report()

    assert exc.value.status_code == 500


def test_data_sources_catalog_has_expected_shape():
    result = metadata.get_data_sources()

    assert "sources" in result
    assert len(result["sources"]) >= 6
    assert {"id", "name", "url", "datasets"}.issubset(result["sources"][0])
