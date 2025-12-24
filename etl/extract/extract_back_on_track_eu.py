# MSPR_1_B1/etl/extract/extract_back-on-track_eu.py

import requests
import os
import pandas as pd

RAW_DIR = "MSPR_1_B1/data/raw/back_on_track"
os.makedirs(RAW_DIR, exist_ok=True)

BASE_URL = "https://script.google.com/macros/s/AKfycbwY9zNQFq0urCHsTstWRKxLe0SstWrwyY04tSuDIVb_yRCtTs_HDlRARS-5fqltgEZr/exec"

TABLES = {
    "view_ontd_list": "night_trains_list.csv",
    "view_ontd_cities": "cities.csv"
}

def extract_back_on_track():
    for table, filename in TABLES.items():
        url = f"{BASE_URL}?table={table}"
        print(f"🌙 Téléchargement Back-on-Track : {table}")

        response = requests.get(url)
        response.raise_for_status()

        df = pd.read_json(response.text)
        output_path = os.path.join(RAW_DIR, filename)
        df.to_csv(output_path, index=False)

        print(f"✅ Sauvegardé : {output_path}")

    print("🌍 Extraction Back-on-Track terminée")

if __name__ == "__main__":
    extract_back_on_track()
