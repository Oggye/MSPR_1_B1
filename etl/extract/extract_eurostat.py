# =========================================================
# ETL/extract/extract_eurostat.py
# Sources Eurostat ferroviaires officielles
# =========================================================

import gzip
import io
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path("data/raw/eurostat")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# rail_tf_traveh : mouvements de trains/véhicules (trafic, train-km)
# rail_pa_typepas : voyageurs transportés par type de transport
#                   (passagers / passenger-km selon l'unité)
EUROSTAT_FILES = {
    "rail_traffic": (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        "rail_tf_traveh?format=TSV&compressed=true"
    ),
    "rail_passengers": (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        "rail_pa_typepas?format=TSV&compressed=true"
    ),
}


def _download_tsv_gzip(name: str, url: str) -> pd.DataFrame:
    print(f"Téléchargement {name}…")
    response = requests.get(url, timeout=180)
    response.raise_for_status()

    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("content-type"))
    print(f"Taille reçue : {len(response.content) / 1024 / 1024:.2f} Mo")

    try:
        with gzip.open(io.BytesIO(response.content), "rt", encoding="utf-8") as f:
            df = pd.read_csv(f, sep="\t", low_memory=False)
    except (OSError, EOFError) as exc:
        raise ValueError(f"Eurostat n'a pas renvoyé un gzip TSV valide pour {name}") from exc

    print("Colonnes détectées :", df.columns.tolist())
    print(df.head(4).to_string())
    return df


def extract_eurostat():
    for name, url in EUROSTAT_FILES.items():
        df = _download_tsv_gzip(name, url)
        out_file = RAW_DIR / f"{name}.csv"
        df.to_csv(out_file, index=False)
        print(f"{name} extrait et sauvegardé → {out_file}")


if __name__ == "__main__":
    extract_eurostat()
