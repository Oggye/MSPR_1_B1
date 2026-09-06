"""Extraction d'une archive publique 2024 du feed officiel SNCB/NMBS."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import requests

GTFS_BE_URL = "https://gtfs.flatturtle.cloud/sncb-nmbs/sncb-nmbs-gtfs_2024-11-12.zip"
RAW_DIR = Path("data/raw/gtfs_be")
KEEP_FILES = {"agency.txt", "routes.txt", "trips.txt", "stop_times.txt", "stops.txt", "calendar_dates.txt"}


def _write_new_or_identical(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"Fichier local different a sauvegarder avant remplacement : {path}")
        return
    path.write_bytes(content)


def extract_gtfs_be(raw_dir: str | Path = RAW_DIR) -> dict:
    output_dir = Path(raw_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(GTFS_BE_URL, timeout=180)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        members = {Path(name).name: name for name in archive.namelist()}
        missing = KEEP_FILES - set(members)
        if missing:
            raise RuntimeError(f"Archive GTFS BE incomplete : {sorted(missing)}")
        for filename in KEEP_FILES:
            with archive.open(members[filename]) as source:
                _write_new_or_identical(
                    output_dir / Path(filename).with_suffix(".csv"), source.read()
                )

    metadata = {
        "data_source": "gtfs_be", "producer": "SNCB/NMBS",
        "url": GTFS_BE_URL, "archive_kind": "public_archive_of_official_feed_2024",
        "service_year": 2024, "downloaded_at": datetime.now().isoformat(),
    }
    metadata_path = output_dir / "metadata.json"
    if not metadata_path.exists():
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    print(extract_gtfs_be())
