"""Normalisation des passenger-km ferroviaires UNECE."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COUNTRY_CODES = {
    "Albania": "AL", "Austria": "AT", "Belgium": "BE", "Bosnia and Herzegovina": "BA",
    "Bulgaria": "BG", "Croatia": "HR", "Cyprus": "CY", "Czechia": "CZ",
    "Czech Republic": "CZ", "Denmark": "DK", "Estonia": "EE", "Finland": "FI",
    "France": "FR", "Germany": "DE", "Greece": "GR", "Hungary": "HU",
    "Ireland": "IE", "Italy": "IT", "Latvia": "LV", "Lithuania": "LT",
    "Luxembourg": "LU", "Malta": "MT", "Montenegro": "ME", "Netherlands": "NL",
    "North Macedonia": "MK", "Norway": "NO", "Poland": "PL", "Portugal": "PT",
    "Romania": "RO", "Serbia": "RS", "Slovakia": "SK", "Slovenia": "SI",
    "Spain": "ES", "Sweden": "SE", "Switzerland": "CH", "United Kingdom": "GB",
}


def transform_unece(raw_dir: str, processed_dir: str) -> dict:
    source = Path(raw_dir) / "unece" / "rail_passenger_km.csv"
    if not source.exists():
        raise FileNotFoundError(source)
    frame = pd.read_csv(source, sep=None, engine="python")
    frame.columns = [str(column).strip() for column in frame.columns]
    if "Country" not in frame.columns:
        raise ValueError(f"Colonnes UNECE inattendues : {frame.columns.tolist()}")

    if {"Year", "Value"}.issubset(frame.columns):
        long = frame.copy()
    else:
        year_columns = [column for column in frame.columns if str(column).isdigit()]
        if not year_columns:
            raise ValueError(f"Annees UNECE absentes : {frame.columns.tolist()}")
        id_columns = [column for column in frame.columns if column not in year_columns]
        long = frame.melt(
            id_vars=id_columns, value_vars=year_columns,
            var_name="Year", value_name="Value",
        )

    long["country_code"] = long["Country"].astype(str).str.strip().map(COUNTRY_CODES)
    long["year"] = pd.to_numeric(long["Year"], errors="coerce")
    long["passengers"] = pd.to_numeric(
        long["Value"].astype("string").str.replace(" ", "", regex=False), errors="coerce"
    )
    long = long[
        long["country_code"].notna()
        & long["year"].between(2010, 2024)
        & long["passengers"].notna()
    ].copy()
    long["year"] = long["year"].astype(int)
    canonical = long.groupby(["country_code", "year"], as_index=False)["passengers"].median()
    canonical["passenger_metric"] = "MIO_PKM"
    canonical["data_quality"] = "observed"
    canonical["data_source"] = "unece"

    output = Path(processed_dir) / "unece"
    output.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(output / "passengers_processed.csv", index=False)
    return {
        "source": "unece", "records": int(len(canonical)),
        "countries": int(canonical["country_code"].nunique()) if not canonical.empty else 0,
        "year_min": int(canonical["year"].min()) if not canonical.empty else None,
        "year_max": int(canonical["year"].max()) if not canonical.empty else None,
    }
