"""Extraction publique UNECE PXWeb des passenger-km ferroviaires."""
from __future__ import annotations

import json
from pathlib import Path

import requests

RAW_DIR = Path("data/raw/unece")
API_URL = (
    "https://w3.unece.org/PXWeb2015/api/v1/en/STAT/40-TRTRANS/"
    "05-TRRAIL/01_en_TRrailpassengers_r.px"
)
EUROPE_NUMERIC_CODES = {
    "008", "040", "056", "070", "100", "191", "196", "203", "208", "233",
    "246", "250", "276", "300", "348", "372", "380", "428", "440", "442",
    "470", "499", "528", "578", "616", "620", "642", "688", "703", "705",
    "724", "752", "756", "807", "826",
}


def _values_for_texts(variable: dict, accepted: set[str]) -> list[str]:
    return [
        value for value, label in zip(variable.get("values", []), variable.get("valueTexts", []))
        if str(label) in accepted
    ]


def extract_unece(raw_dir: str | Path = RAW_DIR) -> dict:
    output_dir = Path(raw_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata_response = requests.get(API_URL, timeout=60)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    variables = {item["code"]: item for item in metadata["variables"]}

    countries = [
        value for value in variables["Country"].get("values", [])
        if value in EUROPE_NUMERIC_CODES
    ]
    years = _values_for_texts(variables["Year"], {str(year) for year in range(2010, 2025)})
    if not countries or not years:
        raise ValueError("Metadonnees UNECE incompatibles : pays ou annees introuvables")

    query = {
        "query": [
            {"code": "Passengers", "selection": {"filter": "item", "values": ["TR.119"]}},
            {"code": "Topic", "selection": {"filter": "item", "values": ["TR.8"]}},
            {"code": "Country", "selection": {"filter": "item", "values": countries}},
            {"code": "Year", "selection": {"filter": "item", "values": years}},
        ],
        "response": {"format": "csv"},
    }
    response = requests.post(API_URL, json=query, timeout=120)
    response.raise_for_status()
    if "Country" not in response.text or '"2010"' not in response.text:
        raise ValueError("UNECE n'a pas renvoye le CSV PXWeb attendu")

    data_path = output_dir / "rail_passenger_km.csv"
    metadata_path = output_dir / "metadata.json"
    data_path.write_text(response.text, encoding="utf-8-sig")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "source": "unece",
        "url": API_URL,
        "countries_requested": len(countries),
        "years_requested": len(years),
        "output": str(data_path),
    }


if __name__ == "__main__":
    print(extract_unece())
