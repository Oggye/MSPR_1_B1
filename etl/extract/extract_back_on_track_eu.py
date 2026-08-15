# =========================================================
# etl/extract/extract_back_on_track_eu.py
# =========================================================

import requests
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw/back_on_track")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# URLs redirigées directement vers le JSON final
BACK_ON_TRACK_URLS = {
    "view_ontd_list": "https://raw.githubusercontent.com/Back-on-Track-eu/night-train-data/main/data/latest/view_ontd_list.json",
    "view_ontd_cities": "https://raw.githubusercontent.com/Back-on-Track-eu/night-train-data/main/data/latest/view_ontd_cities.json",
}

def extract_back_on_track():
    for table_name, url in BACK_ON_TRACK_URLS.items():
        print(f"Téléchargement {table_name}…")
        response = requests.get(url)
        response.raise_for_status()
        # On récupère le JSON final
        data = response.json()
        # Conversion en DataFrame
        df = pd.DataFrame.from_dict(data, orient='index')
        # Nettoyage éventuel des valeurs inutiles (#REF!)
        df = df[df.index != "#REF!"]
        # Sauvegarde
        out_file = RAW_DIR / f"{table_name}.csv"
        df.to_csv(out_file, index=False)
        print(f"{table_name} extrait et sauvegardé → {out_file}")
