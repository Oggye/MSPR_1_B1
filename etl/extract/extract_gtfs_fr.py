# =========================================================
# etl/extract/extract_gtfs_fr.py
# =========================================================

import requests
import zipfile
import io
from pathlib import Path

GTFS_FR_URL = "https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip"
RAW_DIR = Path("data/raw/gtfs_fr")
KEEP_FILES = [
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar_dates.txt",
    "agency.txt",
]

def extract_gtfs_fr():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Téléchargement du GTFS SNCF…")
    response = requests.get(GTFS_FR_URL)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for file_name in KEEP_FILES:
            if file_name in z.namelist():
                z.extract(file_name, RAW_DIR)

    print("GTFS France extrait :")
    for file in RAW_DIR.iterdir():
        print(" -", file.name)
