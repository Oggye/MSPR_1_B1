import json

from audit import diagnostic


def test_lister_sources_raw_uses_directories_present_on_disk(tmp_path, monkeypatch):
    (tmp_path / "gtfs_es").mkdir()
    (tmp_path / "gtfs_lu").mkdir()
    (tmp_path / "README.txt").write_text("not a source", encoding="utf-8")
    monkeypatch.setattr(diagnostic, "RAW_DIR", tmp_path)

    assert list(diagnostic.lister_sources_raw()) == ["gtfs_es", "gtfs_lu"]


def test_compter_lignes_csv_handles_file_without_final_newline(tmp_path):
    csv_path = tmp_path / "data.csv"
    csv_path.write_bytes(b"header\nfirst\nsecond")

    assert diagnostic.compter_lignes_csv(csv_path) == 2


def test_report_status_reflects_coherence_result(tmp_path):
    report_path = tmp_path / "diagnostic.json"

    diagnostic.generer_rapport_json({}, {}, {}, False, report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["statut"] == "A_VERIFIER"
