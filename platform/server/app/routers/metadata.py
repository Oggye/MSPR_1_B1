# app/routers/metadata.py
"""
Métadonnées et qualité des données.

Le rapport prioritaire est celui généré par l'ETL dans data/warehouse.
Aucune métrique de qualité n'est inventée si ce rapport n'est pas disponible.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _quality_report_candidates() -> list[Path]:
    candidates: list[Path] = []

    explicit = os.getenv("QUALITY_REPORT_PATH")
    if explicit:
        candidates.append(Path(explicit))

    # Chemin Docker : ./data est monté dans /app/data.
    candidates.append(Path("/app/data/warehouse/quality_reports.json"))

    # Exécution locale : cherche un dossier data/warehouse en remontant
    # l'arborescence à partir de ce fichier.
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidates.append(
            parent / "data" / "warehouse" / "quality_reports.json"
        )

    # Dernier recours : ancien rapport empaqueté avec l'API.
    candidates.append(
        Path(__file__).resolve().parents[1]
        / "reports"
        / "quality_reports.json"
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _load_quality_report() -> tuple[dict[str, Any] | None, Path | None]:
    for path in _quality_report_candidates():
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Rapport de qualité illisible: {path.name}: {exc}",
            ) from exc

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=500,
                detail="Le rapport de qualité doit être un objet JSON.",
            )
        return data, path

    return None, None


@router.get("/api/metadata/quality")
def get_quality_report():
    report, path = _load_quality_report()

    if report is not None:
        # Champs additionnels non destructifs : les anciens clients gardent le
        # contenu original, les nouveaux savent quelle source a été utilisée.
        result = dict(report)
        result.setdefault("project", "ObRail Europe")
        result.setdefault("execution_date", None)
        result.setdefault("reports", [])
        result.setdefault("summary", {})
        result["metadata_report_source"] = str(path)
        result["metadata_report_available"] = True
        return result

    # Fallback transparent, sans faux pourcentages ni faux volumes.
    return {
        "execution_date": datetime.now(timezone.utc).isoformat(),
        "project": "ObRail Europe - MSPR",
        "reports": [],
        "traceability": {
            "warning": (
                "Aucun quality_reports.json généré par l'ETL n'a été trouvé."
            )
        },
        "summary": {
            "success": False,
            "reason": "quality_report_missing",
        },
        "metadata_report_source": None,
        "metadata_report_available": False,
    }


SOURCE_CATALOG = [
    {
        "id": 1,
        "source_id": "eurostat_rail",
        "name": "Eurostat - Rail",
        "url": "https://ec.europa.eu/eurostat",
        "description": (
            "Statistiques européennes de trafic ferroviaire et de "
            "voyageurs-km."
        ),
        "datasets": ["rail_traffic.csv", "rail_passengers.csv"],
        "role": "statistiques officielles et calibration",
    },
    {
        "id": 2,
        "source_id": "eurostat_co2",
        "name": "Eurostat - Émissions CO2",
        "url": "https://ec.europa.eu/eurostat",
        "description": "Inventaires nationaux d'émissions ENV_AIR_GGE.",
        "datasets": [
            "eurostat_env_air_gge_sdmx.csv",
            "eurostat_env_air_gge_full.tsv",
        ],
        "role": "indicateurs environnementaux",
    },
    {
        "id": 3,
        "source_id": "back_on_track",
        "name": "Back on Track EU",
        "url": "https://back-on-track.eu",
        "description": "Référence européenne dédiée aux trains de nuit.",
        "datasets": ["view_ontd_list.csv", "view_ontd_cities.csv"],
        "role": "trains de nuit réels",
    },
    {
        "id": 4,
        "source_id": "gtfs_fr",
        "name": "GTFS France",
        "url": "https://ressources.data.sncf.com",
        "description": "Horaires ferroviaires GTFS France.",
        "datasets": [
            "agency",
            "routes",
            "trips",
            "stops",
            "stop_times",
            "calendar_dates",
        ],
        "role": "services ferroviaires réels",
    },
    {
        "id": 5,
        "source_id": "gtfs_ch",
        "name": "GTFS Suisse",
        "url": "https://data.opentransportdata.swiss",
        "description": "Horaires GTFS du réseau suisse.",
        "datasets": [
            "agency",
            "routes",
            "trips",
            "stops",
            "stop_times",
            "calendar_dates",
        ],
        "role": "services ferroviaires réels",
    },
    {
        "id": 6,
        "source_id": "gtfs_de",
        "name": "GTFS Allemagne",
        "url": "https://www.bahn.de",
        "description": "Horaires ferroviaires GTFS Allemagne.",
        "datasets": [
            "agency",
            "routes",
            "trips",
            "stops",
            "stop_times",
            "calendar_dates",
        ],
        "role": "services ferroviaires réels",
    },
    {
        "id": 7,
        "source_id": "gtfs_es",
        "name": "GTFS Espagne - Renfe",
        "url": "https://data.renfe.com",
        "description": (
            "Horaires Renfe haute vitesse, longue distance et moyenne distance."
        ),
        "datasets": [
            "agency",
            "routes",
            "trips",
            "stops",
            "stop_times",
            "calendar_dates",
        ],
        "role": "services ferroviaires réels",
    },
    {
        "id": 8,
        "source_id": "gtfs_lu",
        "name": "GTFS Luxembourg",
        "url": "https://data.public.lu",
        "description": "GTFS national luxembourgeois, filtré rail en transformation.",
        "datasets": [
            "agency",
            "routes",
            "trips",
            "stops",
            "stop_times",
            "calendar_dates",
        ],
        "role": "services ferroviaires réels",
    },
]


def _quality_by_source() -> dict[str, Any]:
    report, _ = _load_quality_report()
    if not report:
        return {}

    by_source: dict[str, Any] = {}
    for item in report.get("reports", []):
        if isinstance(item, dict) and item.get("source"):
            by_source[str(item["source"])] = item
    return by_source


@router.get("/api/metadata/sources")
def get_data_sources():
    """
    Catalogue stable des sources.

    Les volumes ne sont jamais codés en dur. Si le rapport ETL contient une
    section pour la source, elle est jointe dans `quality_report`.
    """
    quality = _quality_by_source()
    sources = []

    aliases = {
        "eurostat_rail": ["eurostat"],
        "eurostat_co2": ["emissions"],
        "back_on_track": ["back_on_track"],
        "gtfs_fr": ["gtfs_fr"],
        "gtfs_ch": ["gtfs_ch"],
        "gtfs_de": ["gtfs_de"],
        "gtfs_es": ["gtfs_es"],
        "gtfs_lu": ["gtfs_lu"],
    }

    for source in SOURCE_CATALOG:
        item = dict(source)
        report_item = None
        for alias in aliases.get(source["source_id"], []):
            if alias in quality:
                report_item = quality[alias]
                break
        item["quality_report"] = report_item
        sources.append(item)

    return {
        "sources": sources,
        "count": len(sources),
        "quality_report_available": bool(quality),
    }
