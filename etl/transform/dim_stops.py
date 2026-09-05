"""Construction de dim_stops à partir de tous les GTFS transformés."""
from pathlib import Path
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_dim_stops(processed_dir: str, warehouse_dir: str) -> pd.DataFrame:
    logger.info("🚏 Construction de dim_stops...")
    gtfs_root = Path(processed_dir) / "gtfs"
    frames = []

    if not gtfs_root.exists():
        logger.warning("Aucun répertoire GTFS transformé : %s", gtfs_root)
        return pd.DataFrame()

    for country_dir in sorted(p for p in gtfs_root.iterdir() if p.is_dir()):
        stops_path = country_dir / "stops_processed.csv"
        if not stops_path.exists():
            continue
        country = country_dir.name.upper()
        stops = pd.read_csv(stops_path, low_memory=False)
        stops.columns = [str(c).strip().lower() for c in stops.columns]
        if "stop_id" not in stops.columns:
            logger.warning("stop_id absent pour %s", country)
            continue

        # Si gtfs.py a calculé les arrêts réellement utilisés par les trains,
        # on élimine ici les arrêts bus/tram d'un flux multimodal (ex. Luxembourg).
        rail_ids_path = country_dir / "rail_stop_ids_processed.csv"
        if rail_ids_path.exists():
            rail_ids = set(pd.read_csv(rail_ids_path, dtype=str)["stop_id"].dropna().astype(str))
            stops["stop_id"] = stops["stop_id"].astype(str)
            stops = stops[stops["stop_id"].isin(rail_ids)]

        for col in ("stop_name", "stop_lat", "stop_lon"):
            if col not in stops.columns:
                stops[col] = pd.NA
        stops["stop_name"] = stops["stop_name"].astype("string").fillna("").str.strip()
        missing_name = stops["stop_name"].eq("")
        stops.loc[missing_name, "stop_name"] = "Arrêt " + stops.loc[missing_name, "stop_id"].astype(str)
        stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
        stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
        stops["source_country"] = country
        frames.append(stops[["stop_name", "stop_lat", "stop_lon", "stop_id", "source_country"]])

    if not frames:
        logger.warning("Aucun arrêt ferroviaire transformé.")
        return pd.DataFrame()

    all_stops = pd.concat(frames, ignore_index=True)
    # Le stop_id n'est unique qu'à l'intérieur d'un flux/pays.
    all_stops = all_stops.drop_duplicates(subset=["source_country", "stop_id"], keep="first")
    all_stops.insert(0, "stop_id_dim", range(1, len(all_stops) + 1))

    warehouse_path = Path(warehouse_dir)
    warehouse_path.mkdir(parents=True, exist_ok=True)
    all_stops.to_csv(warehouse_path / "dim_stops.csv", index=False)
    logger.info("✅ dim_stops : %s arrêts ferroviaires", f"{len(all_stops):,}")
    return all_stops
