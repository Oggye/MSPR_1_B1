"""
Transformation GTFS ObRail Europe.

Objectifs :
- conserver la quasi-totalité des données GTFS utiles ;
- traiter les gros stop_times par chunks pour éviter de saturer la RAM ;
- conserver les fichiers nettoyés complets dans data/processed ;
- produire un fichier train_services_processed.csv, une ligne par trip ferroviaire ;
- déterminer jour/nuit à partir des horaires réels lorsque c'est possible ;
- supporter FR, DE, CH, ES et LU sans modifier l'architecture générale.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GTFS_COUNTRIES = ("fr", "ch", "de", "es", "lu")
STOP_TIMES_CHUNK_SIZE = 500_000

# GTFS standard : 2 = rail. Les valeurs 100-117 correspondent aux sous-types
# ferroviaires de l'extension route_type communément utilisée.
RAIL_ROUTE_TYPES = {2, *range(100, 118)}
NIGHT_TEXT_PATTERN = r"night|nacht|nocturne|nightjet|nuit|sleeper|intercités de nuit"


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _normalise_id(series: pd.Series) -> pd.Series:
    """
    Normalise les identifiants GTFS sans les convertir en nombres.

    Certains flux (notamment DE) sont lus par pandas avec un agency_id entier
    dans agency.csv et flottant/texte dans routes.csv. Pandas refuse ensuite
    de fusionner int64 et string. On force donc tous les identifiants à une
    représentation texte stable. Les formes purement numériques comme 12.0
    deviennent 12, sans toucher aux identifiants alphanumériques.
    """
    text = series.astype("string").str.strip()
    numeric_float = text.str.fullmatch(r"[-+]?\d+\.0+", na=False)
    text.loc[numeric_float] = text.loc[numeric_float].str.replace(r"\.0+$", "", regex=True)
    return text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, **kwargs)


def _optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return _normalise_columns(_read_csv(path))


def _time_to_minutes(series: pd.Series) -> pd.Series:
    """Convertit HH:MM[:SS] GTFS en minutes. Accepte les heures > 24."""
    text = series.astype("string").str.strip()
    parts = text.str.extract(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?$")
    hours = pd.to_numeric(parts[0], errors="coerce")
    minutes = pd.to_numeric(parts[1], errors="coerce")
    seconds = pd.to_numeric(parts[2], errors="coerce").fillna(0)
    valid = hours.notna() & minutes.between(0, 59) & seconds.between(0, 59)
    result = hours * 60 + minutes + seconds / 60.0
    return result.where(valid)


def _haversine_vectorized(lat1, lon1, lat2, lon2) -> pd.Series:
    lat1 = pd.to_numeric(lat1, errors="coerce")
    lon1 = pd.to_numeric(lon1, errors="coerce")
    lat2 = pd.to_numeric(lat2, errors="coerce")
    lon2 = pd.to_numeric(lon2, errors="coerce")

    r = 6371.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return pd.Series(r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a)), index=lat1.index)


def _is_rail_route(routes_df: pd.DataFrame) -> pd.Series:
    if "route_type" not in routes_df.columns:
        logger.warning("route_type absent : toutes les routes sont conservées comme ferroviaires.")
        return pd.Series(True, index=routes_df.index)

    route_type = pd.to_numeric(routes_df["route_type"], errors="coerce")
    # Si le flux ne renseigne aucune valeur exploitable, ne pas jeter les données.
    if route_type.notna().sum() == 0:
        return pd.Series(True, index=routes_df.index)
    return route_type.isin(RAIL_ROUTE_TYPES)


def _clean_agency(df: pd.DataFrame, country: str) -> pd.DataFrame:
    df = _normalise_columns(df)
    if "agency_id" not in df.columns:
        df["agency_id"] = [f"{country.upper()}_AGENCY_{i+1}" for i in range(len(df))]
    if "agency_name" not in df.columns:
        df["agency_name"] = f"Opérateur {country.upper()}"
    df["agency_id"] = _normalise_id(df["agency_id"])
    df["agency_name"] = df["agency_name"].astype("string").fillna(f"Opérateur {country.upper()}").str.strip()
    df["country"] = country.upper()
    return df.drop_duplicates()


def _clean_routes(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalise_columns(df)
    if "route_id" not in df.columns:
        raise ValueError("routes.csv ne contient pas route_id")
    df = df[df["route_id"].notna()].copy()
    df["route_id"] = _normalise_id(df["route_id"])
    if "agency_id" in df.columns:
        df["agency_id"] = _normalise_id(df["agency_id"])
    for col in ("route_short_name", "route_long_name", "route_desc"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype("string").fillna("").str.strip()
    df["is_rail"] = _is_rail_route(df)
    route_text = (
        df["route_short_name"].fillna("") + " " +
        df["route_long_name"].fillna("") + " " +
        df["route_desc"].fillna("")
    )
    df["night_name_hint"] = route_text.str.contains(NIGHT_TEXT_PATTERN, case=False, regex=True, na=False)
    return df.drop_duplicates(subset=["route_id"], keep="first")


def _clean_stops(df: pd.DataFrame, country: str) -> pd.DataFrame:
    df = _normalise_columns(df)
    if "stop_id" not in df.columns:
        raise ValueError("stops.csv ne contient pas stop_id")
    df = df[df["stop_id"].notna()].copy()
    df["stop_id"] = _normalise_id(df["stop_id"])
    if "stop_name" not in df.columns:
        df["stop_name"] = ""
    df["stop_name"] = df["stop_name"].astype("string").fillna("").str.strip()
    missing_name = df["stop_name"].eq("")
    df.loc[missing_name, "stop_name"] = "Arrêt " + df.loc[missing_name, "stop_id"].astype(str)
    for col in ("stop_lat", "stop_lon"):
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["source_country"] = country.upper()
    # On ne remplace surtout pas les coordonnées manquantes par une moyenne artificielle.
    return df.drop_duplicates(subset=["stop_id"], keep="first")


def _clean_trips(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    df = _normalise_columns(df)
    if "trip_id" not in df.columns or "route_id" not in df.columns:
        raise ValueError("trips.csv doit contenir trip_id et route_id")
    initial = len(df)
    df = df[df["trip_id"].notna() & df["route_id"].notna()].copy()
    df["trip_id"] = _normalise_id(df["trip_id"])
    df["route_id"] = _normalise_id(df["route_id"])
    if "service_id" in df.columns:
        df["service_id"] = _normalise_id(df["service_id"])
    if "agency_id" in df.columns:
        df["agency_id"] = _normalise_id(df["agency_id"])
    if "trip_headsign" not in df.columns:
        df["trip_headsign"] = ""
    df["trip_headsign"] = df["trip_headsign"].astype("string").fillna("").str.strip()
    df = df.drop_duplicates(subset=["trip_id"], keep="first")
    return df, initial - len(df)


def _prepare_calendar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], int]:
    if df.empty:
        return df, {}, datetime.now().year
    df = _normalise_columns(df)
    if "date" not in df.columns:
        return df, {}, datetime.now().year

    date_text = df["date"].astype("string").str.replace(r"\.0$", "", regex=True).str.strip()
    parsed = pd.to_datetime(date_text, format="%Y%m%d", errors="coerce")
    df["service_year"] = parsed.dt.year
    years = df["service_year"].dropna().astype(int)
    default_year = int(years.max()) if not years.empty else datetime.now().year

    service_year_map: dict[str, int] = {}
    if "service_id" in df.columns:
        valid = df[df["service_id"].notna() & df["service_year"].notna()].copy()
        if not valid.empty:
            valid["service_id"] = valid["service_id"].astype(str)
            # Le max est retenu pour représenter le snapshot le plus récent du service.
            service_year_map = valid.groupby("service_id")["service_year"].max().astype(int).to_dict()
    return df, service_year_map, default_year


def _write_chunk(df: pd.DataFrame, path: Path, first_write: bool) -> bool:
    df.to_csv(path, index=False, mode="w" if first_write else "a", header=first_write)
    return False


def _first_last_candidates(chunk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = [c for c in ["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"] if c in chunk.columns]
    if chunk.empty:
        return pd.DataFrame(columns=cols), pd.DataFrame(columns=cols)
    first_idx = chunk.groupby("trip_id", sort=False)["stop_sequence"].idxmin()
    last_idx = chunk.groupby("trip_id", sort=False)["stop_sequence"].idxmax()
    return chunk.loc[first_idx, cols].copy(), chunk.loc[last_idx, cols].copy()


def _choose_time(df: pd.DataFrame, primary: str, secondary: str) -> pd.Series:
    p = df[primary].astype("string") if primary in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")
    s = df[secondary].astype("string") if secondary in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")
    return p.where(p.notna() & p.str.strip().ne(""), s)


def _make_train_label(df: pd.DataFrame) -> pd.Series:
    short = df.get("route_short_name", pd.Series("", index=df.index)).astype("string").fillna("").str.strip()
    long = df.get("route_long_name", pd.Series("", index=df.index)).astype("string").fillna("").str.strip()
    head = df.get("trip_headsign", pd.Series("", index=df.index)).astype("string").fillna("").str.strip()
    route_id = df["route_id"].astype(str)

    base = long.where(long.ne(""), short)
    base = base.where(base.ne(""), "Route " + route_id)
    add_head = head.ne("") & ~pd.Series(
        [h.lower() in b.lower() if h and b else False for h, b in zip(head, base)],
        index=df.index,
    )
    label = base.copy()
    label.loc[add_head] = base.loc[add_head] + " - " + head.loc[add_head]
    return label.str.slice(0, 300)


def _night_from_times(start_minutes: pd.Series, end_minutes: pd.Series, text_hint: pd.Series) -> pd.Series:
    start_clock = start_minutes % 1440
    end_clock = end_minutes % 1440
    crosses_day = (np.floor(end_minutes / 1440) > np.floor(start_minutes / 1440))
    time_night = (
        start_clock.ge(22 * 60) | start_clock.lt(5 * 60) |
        end_clock.ge(22 * 60) | end_clock.lt(5 * 60) |
        crosses_day.fillna(False)
    )
    return (time_night.fillna(False) | text_hint.fillna(False)).astype(bool)


def transform_gtfs_country(raw_dir: str, processed_dir: str, country: str) -> dict | None:
    country = country.lower()
    country_dir = Path(raw_dir) / f"gtfs_{country}"
    if not country_dir.exists():
        logger.warning("GTFS %s absent : %s", country.upper(), country_dir)
        return None

    required = ["agency.csv", "routes.csv", "stops.csv", "trips.csv", "stop_times.csv"]
    missing = [name for name in required if not (country_dir / name).exists()]
    if missing:
        logger.error("GTFS %s incomplet : %s", country.upper(), missing)
        return None

    logger.info("🚉 Transformation GTFS %s", country.upper())
    save_dir = Path(processed_dir) / "gtfs" / country
    save_dir.mkdir(parents=True, exist_ok=True)

    agency_df = _clean_agency(_read_csv(country_dir / "agency.csv"), country)
    routes_df = _clean_routes(_read_csv(country_dir / "routes.csv"))
    stops_df = _clean_stops(_read_csv(country_dir / "stops.csv"), country)
    trips_df, rejected_trips = _clean_trips(_read_csv(country_dir / "trips.csv"))

    calendar_df = _optional_csv(country_dir / "calendar_dates.csv")
    calendar_df, service_year_map, default_year = _prepare_calendar(calendar_df)

    agency_df.to_csv(save_dir / "agency_processed.csv", index=False)
    routes_df.to_csv(save_dir / "routes_processed.csv", index=False)
    stops_df.to_csv(save_dir / "stops_processed.csv", index=False)
    trips_df.to_csv(save_dir / "trips_processed.csv", index=False)
    if not calendar_df.empty:
        calendar_df.to_csv(save_dir / "calendar_dates_processed.csv", index=False)

    rail_route_ids = set(routes_df.loc[routes_df["is_rail"], "route_id"].astype(str))
    rail_trip_ids = set(trips_df.loc[trips_df["route_id"].isin(rail_route_ids), "trip_id"].astype(str))

    stop_times_out = save_dir / "stop_times_processed.csv"
    if stop_times_out.exists():
        stop_times_out.unlink()

    first_write = True
    stop_times_raw = 0
    stop_times_valid = 0
    stop_times_rejected = 0
    first_candidates: list[pd.DataFrame] = []
    last_candidates: list[pd.DataFrame] = []
    rail_stop_ids: set[str] = set()

    for chunk in pd.read_csv(
        country_dir / "stop_times.csv",
        chunksize=STOP_TIMES_CHUNK_SIZE,
        low_memory=False,
    ):
        stop_times_raw += len(chunk)
        chunk = _normalise_columns(chunk)
        if not {"trip_id", "stop_id"}.issubset(chunk.columns):
            raise ValueError(f"stop_times.csv {country.upper()} doit contenir trip_id et stop_id")
        if "stop_sequence" not in chunk.columns:
            chunk["stop_sequence"] = chunk.groupby("trip_id", sort=False).cumcount() + 1

        chunk["trip_id"] = _normalise_id(chunk["trip_id"])
        chunk["stop_id"] = _normalise_id(chunk["stop_id"])
        chunk["stop_sequence"] = pd.to_numeric(chunk["stop_sequence"], errors="coerce")

        valid_mask = (
            chunk["trip_id"].notna() & chunk["trip_id"].ne("") &
            chunk["stop_id"].notna() & chunk["stop_id"].ne("") &
            chunk["stop_sequence"].notna()
        )
        stop_times_rejected += int((~valid_mask).sum())
        valid = chunk.loc[valid_mask].drop_duplicates().copy()
        valid["stop_sequence"] = valid["stop_sequence"].astype(int)
        stop_times_valid += len(valid)
        first_write = _write_chunk(valid, stop_times_out, first_write)

        rail = valid[valid["trip_id"].isin(rail_trip_ids)]
        if not rail.empty:
            first, last = _first_last_candidates(rail)
            first_candidates.append(first)
            last_candidates.append(last)
            rail_stop_ids.update(rail["stop_id"].dropna().astype(str).tolist())

    pd.DataFrame({"stop_id": sorted(rail_stop_ids)}).to_csv(save_dir / "rail_stop_ids_processed.csv", index=False)

    # Une ligne par trip ferroviaire réel.
    rail_trips = trips_df[trips_df["trip_id"].isin(rail_trip_ids)].copy()
    route_cols = [
        c for c in [
            "route_id", "agency_id", "route_short_name", "route_long_name",
            "route_desc", "route_type", "night_name_hint"
        ] if c in routes_df.columns
    ]
    rail_trips = rail_trips.merge(routes_df[route_cols], on="route_id", how="left")

    if first_candidates:
        first_df = pd.concat(first_candidates, ignore_index=True)
        first_df = first_df.sort_values(["trip_id", "stop_sequence"]).drop_duplicates("trip_id", keep="first")
        first_df = first_df.rename(columns={
            "stop_id": "first_stop_id", "arrival_time": "first_arrival_time",
            "departure_time": "first_departure_time", "stop_sequence": "first_stop_sequence",
        })
        rail_trips = rail_trips.merge(first_df, on="trip_id", how="left")

    if last_candidates:
        last_df = pd.concat(last_candidates, ignore_index=True)
        last_df = last_df.sort_values(["trip_id", "stop_sequence"]).drop_duplicates("trip_id", keep="last")
        last_df = last_df.rename(columns={
            "stop_id": "last_stop_id", "arrival_time": "last_arrival_time",
            "departure_time": "last_departure_time", "stop_sequence": "last_stop_sequence",
        })
        rail_trips = rail_trips.merge(last_df, on="trip_id", how="left")

    # Noms et coordonnées des arrêts de début/fin.
    stop_lookup = stops_df[["stop_id", "stop_name", "stop_lat", "stop_lon"]].copy()
    first_lookup = stop_lookup.rename(columns={
        "stop_id": "first_stop_id", "stop_name": "first_stop_name",
        "stop_lat": "first_stop_lat", "stop_lon": "first_stop_lon",
    })
    last_lookup = stop_lookup.rename(columns={
        "stop_id": "last_stop_id", "stop_name": "last_stop_name",
        "stop_lat": "last_stop_lat", "stop_lon": "last_stop_lon",
    })
    if "first_stop_id" in rail_trips.columns:
        rail_trips = rail_trips.merge(first_lookup, on="first_stop_id", how="left")
    if "last_stop_id" in rail_trips.columns:
        rail_trips = rail_trips.merge(last_lookup, on="last_stop_id", how="left")

    # Opérateur. Toutes les clés sont normalisées en texte avant la fusion.
    # Cela évite notamment l'erreur pandas int64/string rencontrée sur le GTFS DE.
    if "agency_id" in rail_trips.columns and "agency_id" in agency_df.columns:
        rail_trips["agency_id"] = _normalise_id(rail_trips["agency_id"])
        operator_lookup = agency_df[["agency_id", "agency_name"]].drop_duplicates("agency_id").copy()
        operator_lookup["agency_id"] = _normalise_id(operator_lookup["agency_id"])
        rail_trips = rail_trips.merge(operator_lookup, on="agency_id", how="left", validate="m:1")
    elif len(agency_df) == 1:
        rail_trips["agency_name"] = agency_df.iloc[0]["agency_name"]
    else:
        rail_trips["agency_name"] = pd.NA
    rail_trips["operators"] = rail_trips.get("agency_name", pd.Series(index=rail_trips.index, dtype="object"))
    rail_trips["operators"] = rail_trips["operators"].astype("string").fillna(f"Opérateur {country.upper()}").str.strip()

    # Année de service : service_id -> calendar_dates, sinon année la plus récente du snapshot.
    if "service_id" in rail_trips.columns:
        rail_trips["year"] = rail_trips["service_id"].astype(str).map(service_year_map).fillna(default_year)
    else:
        rail_trips["year"] = default_year
    rail_trips["year"] = pd.to_numeric(rail_trips["year"], errors="coerce").fillna(default_year).astype(int)

    rail_trips["train"] = _make_train_label(rail_trips)
    rail_trips["country_code"] = country.upper()
    rail_trips["data_source"] = f"gtfs_{country}"
    rail_trips["is_synthetic"] = False

    first_name = rail_trips.get("first_stop_name", pd.Series("", index=rail_trips.index)).astype("string").fillna("").str.strip()
    last_name = rail_trips.get("last_stop_name", pd.Series("", index=rail_trips.index)).astype("string").fillna("").str.strip()
    rail_trips["itinerary"] = np.where(
        first_name.ne("") & last_name.ne(""),
        first_name + " - " + last_name,
        rail_trips["train"],
    )

    first_time = _choose_time(rail_trips, "first_departure_time", "first_arrival_time")
    last_time = _choose_time(rail_trips, "last_arrival_time", "last_departure_time")
    start_minutes = _time_to_minutes(first_time)
    end_minutes = _time_to_minutes(last_time)
    end_adjusted = end_minutes.copy()
    need_rollover = end_adjusted.notna() & start_minutes.notna() & end_adjusted.le(start_minutes)
    end_adjusted.loc[need_rollover] = end_adjusted.loc[need_rollover] + 1440
    rail_trips["duration_min"] = (end_adjusted - start_minutes).where((end_adjusted - start_minutes) > 0)

    text_hint = rail_trips.get("night_name_hint", pd.Series(False, index=rail_trips.index)).astype(bool)
    head_hint = rail_trips["train"].str.contains(NIGHT_TEXT_PATTERN, case=False, regex=True, na=False)
    rail_trips["is_night"] = _night_from_times(start_minutes, end_adjusted, text_hint | head_hint)

    required_coord_cols = {"first_stop_lat", "first_stop_lon", "last_stop_lat", "last_stop_lon"}
    if required_coord_cols.issubset(rail_trips.columns):
        straight = _haversine_vectorized(
            rail_trips["first_stop_lat"], rail_trips["first_stop_lon"],
            rail_trips["last_stop_lat"], rail_trips["last_stop_lon"],
        )
        # Un trajet ferroviaire est généralement plus long que la distance orthodromique.
        rail_trips["distance_km"] = (straight * 1.18).where(straight > 0)
    else:
        rail_trips["distance_km"] = np.nan

    service_cols = [
        "trip_id", "route_id", "service_id", "train", "country_code", "year",
        "operators", "is_night", "is_synthetic", "data_source", "itinerary",
        "first_stop_id", "last_stop_id", "first_departure_time", "last_arrival_time",
        "duration_min", "distance_km", "route_type",
    ]
    service_cols = [c for c in service_cols if c in rail_trips.columns]
    train_services = rail_trips[service_cols].copy()
    train_services.to_csv(save_dir / "train_services_processed.csv", index=False)

    missing_coords = int(stops_df[["stop_lat", "stop_lon"]].isna().any(axis=1).sum())
    report = {
        "source": f"gtfs_{country}",
        "agencies": int(len(agency_df)),
        "routes_total": int(len(routes_df)),
        "routes_rail": int(routes_df["is_rail"].sum()),
        "stops": int(len(stops_df)),
        "stops_missing_coordinates": missing_coords,
        "trips_total": int(len(trips_df)),
        "trips_rejected": int(rejected_trips),
        "train_services_rail": int(len(train_services)),
        "stop_times_raw": int(stop_times_raw),
        "stop_times_processed": int(stop_times_valid),
        "stop_times_rejected": int(stop_times_rejected),
        "retention_stop_times_pct": round((stop_times_valid / stop_times_raw * 100), 4) if stop_times_raw else 0.0,
        "night_services": int(train_services["is_night"].sum()) if not train_services.empty else 0,
        "day_services": int((~train_services["is_night"]).sum()) if not train_services.empty else 0,
        "service_year_min": int(train_services["year"].min()) if not train_services.empty else None,
        "service_year_max": int(train_services["year"].max()) if not train_services.empty else None,
    }
    logger.info(
        "✅ GTFS %s : %s trips ferroviaires | %s stop_times conservés (%.2f%%)",
        country.upper(), f"{len(train_services):,}", f"{stop_times_valid:,}", report["retention_stop_times_pct"],
    )
    return report


def transform_all_gtfs(raw_dir: str, processed_dir: str, countries: Iterable[str] = GTFS_COUNTRIES) -> list[dict]:
    reports: list[dict] = []
    for country in countries:
        report = transform_gtfs_country(raw_dir, processed_dir, country)
        if report:
            reports.append(report)
    return reports
