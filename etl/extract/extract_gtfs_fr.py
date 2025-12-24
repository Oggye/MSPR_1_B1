# MSPR_1_B1/etl/extract/extract_gtfs_fr.py

import requests
import zipfile
import io
import os

GTFS_URL = "https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip"

RAW_DIR = "MSPR_1_B1/data/raw/gtfs_fr"
REQUIRED_FILES = {
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar_dates.txt"
}

def extract_gtfs():
    os.makedirs(RAW_DIR, exist_ok=True)

    print("📥 Téléchargement du GTFS SNCF...")
    response = requests.get(GTFS_URL)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for file_name in z.namelist():
            base_name = os.path.basename(file_name)

            if base_name in REQUIRED_FILES:
                print(f"✅ Extraction : {base_name}")
                with z.open(file_name) as source, open(
                    os.path.join(RAW_DIR, base_name), "wb"
                ) as target:
                    target.write(source.read())

    print("🚆 Extraction GTFS terminée")

if __name__ == "__main__":
    extract_gtfs()
