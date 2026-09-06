"""Extraction SDMX publique OECD/ITF des passenger-km ferroviaires."""
from __future__ import annotations

from pathlib import Path

import requests

RAW_DIR = Path("data/raw/oecd_itf")
SDMX_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.ITF,DSD_TRENDS@DF_TRENDS,1.0/"
    "BEL+HUN.A.PASSENGER.PASKM.RAIL.RAIL._T"
    "?startPeriod=2010&endPeriod=2024&dimensionAtObservation=AllDimensions"
)


def extract_oecd_itf(raw_dir: str | Path = RAW_DIR) -> dict:
    output_dir = Path(raw_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(SDMX_URL, headers={"Accept": "text/csv"}, timeout=120)
    response.raise_for_status()
    if "TIME_PERIOD" not in response.text or "OBS_VALUE" not in response.text:
        raise ValueError("OECD/ITF n'a pas renvoye le CSV SDMX attendu")

    data_path = output_dir / "rail_passenger_km.csv"
    data_path.write_text(response.text, encoding="utf-8")
    return {
        "source": "oecd_itf",
        "url": SDMX_URL,
        "countries_requested": ["BEL", "HUN"],
        "period": [2010, 2024],
        "output": str(data_path),
    }


if __name__ == "__main__":
    print(extract_oecd_itf())
