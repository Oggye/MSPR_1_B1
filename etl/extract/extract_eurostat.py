# MSPR_1_B1/etl/extract/extract_eurostat.py

import requests
import os

RAW_DIR = "MSPR_1_B1/data/raw/eurostat"
os.makedirs(RAW_DIR, exist_ok=True)

DATASETS = {
    "rail_tf_traveh": "rail_train_km.tsv",
    "rail_tf_passmov": "rail_passenger_km.tsv"
}

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data"

def extract_eurostat():
    for dataset, filename in DATASETS.items():
        url = f"{BASE_URL}/{dataset}?format=TSV&compressed=true"
        print(f"📥 Téléchargement Eurostat : {dataset}")

        response = requests.get(url)
        response.raise_for_status()

        path = os.path.join(RAW_DIR, filename)
        with open(path, "wb") as f:
            f.write(response.content)

        print(f"✅ Sauvegardé : {path}")

    print("📊 Extraction Eurostat terminée")

if __name__ == "__main__":
    extract_eurostat()
