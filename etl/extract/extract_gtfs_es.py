# =========================================================
# ETL/extract/extract_gtfs_es.py
# Extraction GTFS Espagne - Renfe
# =========================================================

import requests
import zipfile
import io
from pathlib import Path


# GTFS officiel Renfe :
# Alta Velocidad + Larga Distancia + Media Distancia
GTFS_ES_URL = (
    "https://ssl.renfe.com/gtransit/"
    "Fichero_AV_LD/google_transit.zip"
)

RAW_DIR = Path("data/raw/gtfs_es")

KEEP_FILES = {
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "stops.txt",
    "calendar_dates.txt",
}


def extract_gtfs_es():
    """
    Télécharge le GTFS ferroviaire Renfe et sauvegarde
    les fichiers nécessaires dans data/raw/gtfs_es/.
    """

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Téléchargement du GTFS Espagne (Renfe)...")

    response = requests.get(
        GTFS_ES_URL,
        timeout=120
    )

    response.raise_for_status()

    print(f"HTTP {response.status_code}")
    print(f"Taille archive : {len(response.content) / 1024 / 1024:.2f} Mo")

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:

            members = zip_file.namelist()

            extracted_files = []

            for member in members:

                # Permet aussi de supporter un éventuel dossier
                # interne dans le ZIP.
                filename = Path(member).name

                if filename not in KEEP_FILES:
                    continue

                output_name = Path(filename).with_suffix(".csv")
                output_path = RAW_DIR / output_name

                print(f"Extraction : {filename} -> {output_name}")

                with zip_file.open(member) as source:
                    with open(output_path, "wb") as destination:
                        destination.write(source.read())

                extracted_files.append(filename)

    except zipfile.BadZipFile as exc:
        raise RuntimeError(
            "Le fichier téléchargé depuis Renfe n'est pas un ZIP GTFS valide."
        ) from exc

    missing_files = KEEP_FILES - set(extracted_files)

    if missing_files:
        print(
            "Attention - fichiers GTFS non présents :",
            sorted(missing_files)
        )

    required_files = {
        "agency.txt",
        "routes.txt",
        "trips.txt",
        "stop_times.txt",
        "stops.txt",
    }

    missing_required = required_files - set(extracted_files)

    if missing_required:
        raise RuntimeError(
            f"GTFS Espagne incomplet. Fichiers obligatoires absents : "
            f"{sorted(missing_required)}"
        )

    print("\nGTFS Espagne extrait avec succès :")

    for file in sorted(RAW_DIR.glob("*.csv")):
        print(" -", file.name)


if __name__ == "__main__":
    extract_gtfs_es()