# =========================================================
# etl/extract/extract_eurostat.py
# =========================================================

import requests
import pandas as pd
import io
import gzip
from pathlib import Path

RAW_DIR = Path("data/raw/eurostat")
RAW_DIR.mkdir(parents=True, exist_ok=True)

EUROSTAT_FILES = {
    "rail_traffic": "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_tf_traveh?format=TSV&compressed=true",
    "rail_passengers": "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/rail_tf_passmov?format=TSV&compressed=true",
}

def extract_eurostat():
    for name, url in EUROSTAT_FILES.items():
        print(f"Téléchargement {name}…")
        response = requests.get(url)
        response.raise_for_status()

        # Décompression
        with gzip.open(io.BytesIO(response.content), 'rt', encoding='utf-8') as f:
            df = pd.read_csv(f, sep="\t")

        # Afficher les colonnes pour vérifier
        print(f"{name} colonnes disponibles :", df.columns.tolist())

        # Filtrage uniquement si la colonne existe
        if 'unit' in df.columns:
            df = df[df['unit'] == 'THS_TRKM']

        out_file = RAW_DIR / f"{name}.csv"
        df.to_csv(out_file, index=False)
        print(f"{name} extrait et sauvegardé → {out_file}")

if __name__ == "__main__":
    extract_eurostat()
