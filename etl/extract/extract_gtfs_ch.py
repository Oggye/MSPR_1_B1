# =========================================================
# ETL / extract / extract_gtfs_ch.py
# Extraction du GTFS Suisse (sans conversion inutile)
# =========================================================

import requests
import zipfile
import io
from pathlib import Path

GTFS_CH_URL = (
    "https://archive.opentransportdata.swiss/timetable_gtfs/"
    "timetable-2024-gtfs2020/GTFS_FP2024_2024-12-12.zip"
)

RAW_DIR = Path("data/raw/gtfs_ch")

KEEP_FILES = {
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar_dates.txt",
    "agency.txt",
}

def extract_gtfs_ch():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Telechargement du GTFS Suisse...")
    response = requests.get(GTFS_CH_URL, stream=True, timeout=300)
    print(response.status_code)
    response.raise_for_status()

    print("Ouverture de l'archive ZIP...")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        for file_name in zip_file.namelist():
            if file_name in KEEP_FILES:
                print(f"Extraction de {file_name}")
                zip_file.extract(file_name, RAW_DIR)

    print("\nGTFS Suisse extrait avec succes :")
    for file in RAW_DIR.iterdir():
        print(" -", file.name)

    for file in RAW_DIR.glob("*.txt"):
        csv_file = file.with_suffix(".csv")

        if csv_file.exists():
            csv_file.unlink()

        file.rename(csv_file)

    print("\nFichiers .txt convertis en .csv")
