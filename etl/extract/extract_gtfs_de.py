# =========================================================
# etl/extract/extract_gtfs_de.py
# =========================================================

import requests
import zipfile
import io
from pathlib import Path
import csv
from datetime import datetime

GTFS_DE_URL = (
    "https://archiv.opendata-oepnv.de/DELFI/Soll-Fahrplandaten%20(GTFS)/"
    "2024/20241209_fahrplaene_gesamtdeutschland_gtfs.zip"
)
RAW_DIR = Path("data/raw/gtfs_de")
KEEP_FILES = [
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar_dates.txt",
    "agency.txt",
]

def extract_gtfs_de():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Telechargement du GTFS Allemagne DELFI 2024...")
    response = requests.get(GTFS_DE_URL, timeout=300)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for file_name in KEEP_FILES:
            if file_name in z.namelist():
                txt_path = Path(z.extract(file_name, RAW_DIR))
                
                # Transformation en CSV
                csv_path = txt_path.with_suffix(".csv")
                with open(txt_path, "r", encoding="utf-8") as txt_file, \
                     open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
                    reader = csv.reader(txt_file)
                    writer = csv.writer(csv_file)
                    for row in reader:
                        writer.writerow(row)
                
                # Suppression du fichier .txt
                txt_path.unlink()

    print("GTFS Allemagne extrait et converti en CSV :")
    for file in RAW_DIR.iterdir():
        if file.suffix == ".csv":
            print(" -", file.name)
    
    # Ajout d'un fichier de métadonnées
    metadata = {
        "source": "DELFI GTFS 2024 public archive",
        "url": GTFS_DE_URL,
        "date_extraction": datetime.now().isoformat(),
        "description": "Archive publique 2024 du feed national officiel DELFI, multimodale",
        "coverage": "Allemagne entière",
        "format": "GTFS standard"
    }
    
    import json
    with open(RAW_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

