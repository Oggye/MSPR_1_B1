"""Normalisation des passenger-km ferroviaires OECD/ITF."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COUNTRY_CODES = {"BEL": "BE", "HUN": "HU"}


def transform_oecd_itf(raw_dir: str, processed_dir: str) -> dict:
    source = Path(raw_dir) / "oecd_itf" / "rail_passenger_km.csv"
    if not source.exists():
        raise FileNotFoundError(source)
    frame = pd.read_csv(source, low_memory=False)
    required = {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Colonnes OECD/ITF inattendues : {frame.columns.tolist()}")

    mask = pd.Series(True, index=frame.index)
    exact_filters = {
        "FREQ": "A", "MEASURE": "PASSENGER", "UNIT_MEASURE": "PASKM",
        "TRANSPORT_MODE": "RAIL", "TRANSPORT_TYPE": "RAIL",
    }
    for column, value in exact_filters.items():
        if column in frame.columns:
            mask &= frame[column].astype("string").str.upper().eq(value)
    frame = frame[mask].copy()
    frame["country_code"] = frame["REF_AREA"].map(COUNTRY_CODES)
    frame["year"] = pd.to_numeric(frame["TIME_PERIOD"], errors="coerce")
    values = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    if "UNIT_MULT" in frame.columns:
        multiplier = pd.to_numeric(frame["UNIT_MULT"], errors="coerce").fillna(6)
    else:
        multiplier = pd.Series(6, index=frame.index, dtype=float)
    frame["passengers"] = values * (10.0 ** multiplier) / 1_000_000.0
    frame = frame[
        frame["country_code"].notna()
        & frame["year"].between(2010, 2024)
        & frame["passengers"].notna()
    ].copy()
    frame["year"] = frame["year"].astype(int)
    canonical = frame.groupby(["country_code", "year"], as_index=False)["passengers"].median()
    canonical["passenger_metric"] = "MIO_PKM"
    canonical["data_quality"] = "observed"
    canonical["data_source"] = "oecd_itf"

    output = Path(processed_dir) / "oecd_itf"
    output.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(output / "passengers_processed.csv", index=False)
    return {
        "source": "oecd_itf", "records": int(len(canonical)),
        "countries": int(canonical["country_code"].nunique()) if not canonical.empty else 0,
        "year_min": int(canonical["year"].min()) if not canonical.empty else None,
        "year_max": int(canonical["year"].max()) if not canonical.empty else None,
    }
