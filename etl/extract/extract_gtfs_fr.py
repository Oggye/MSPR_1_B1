# =========================================================
# etl/extract/extract_gtfs_fr.py
# =========================================================

import requests
import zipfile
import io
from pathlib import Path
import csv

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
                txt_path = Path(z.extract(file_name, RAW_DIR))
                
                # Transformation en CSV
                csv_path = txt_path.with_suffix(".csv")
                with open(txt_path, "r", encoding="utf-8") as txt_file, open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
                    reader = csv.reader(txt_file)
                    writer = csv.writer(csv_file)
                    for row in reader:
                        writer.writerow(row)
                
                # Suppression du fichier .txt
                txt_path.unlink()

    print("GTFS France extrait et converti en CSV :")
    for file in RAW_DIR.iterdir():
        if file.suffix == ".csv":
            print(" -", file.name)
