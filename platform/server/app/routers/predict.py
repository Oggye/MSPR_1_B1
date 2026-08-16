from __future__ import annotations

import csv
from datetime import datetime
from functools import lru_cache
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import (
    DimCountries,
    DimYears,
    FactsCountryStats,
    FactsNightTrains,
)
from ia.src.ml.config import (
    FORECAST_MANIFEST_PATH,
    MAX_FORECAST_HORIZON,
    QUALITY_FILE,
)
from ia.src.ml.predict import predict as ml_predict

logger = logging.getLogger("obrail.predict")

router = APIRouter(
    prefix="/api/predict",
    tags=["Prédictions IA"],
)


class PredictionInput(BaseModel):
    country: str = Field(..., min_length=2, max_length=100)
    year: int = Field(..., ge=2012, le=2035)

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le pays ne peut pas être vide.")
        return value


class ForecastContext(BaseModel):
    origin_year: int
    target_year: int
    horizon: int

    passengers_current: float
    passengers_previous: float
    passenger_growth_1y_pct: float

    co2_current: float
    co2_previous: float
    co2_growth_1y_pct: float

    train_count_current: int
    night_share_current: float
    real_share_current: float
    avg_distance_current: float
    avg_duration_current: float
    operator_count_current: int
    network_data_available: bool

    passenger_unit: str = "MIO_PKM"
    co2_unit: str = "MIO_T"


class ModelMetadata(BaseModel):
    model_name: str
    model_type: str
    training_date: str
    axis: str
    metrics: dict = Field(default_factory=dict)


class ClassificationResponse(BaseModel):
    country: str
    origin_year: int
    year: int
    horizon: int

    prediction: int
    label: str
    probability_decline: float
    decision_margin: float
    risk_level: str
    risk_description: str

    business_message: str
    recommendations: list[str]
    key_drivers: list[dict]
    forecast_context: ForecastContext
    warnings: list[str] = Field(default_factory=list)
    metadata: ModelMetadata
    inference_ms: float


class RegressionResponse(BaseModel):
    country: str
    origin_year: int
    year: int
    horizon: int

    prediction_raw: float
    prediction_display: str
    prediction_low: float
    prediction_high: float
    interval_level: float

    trend_vs_origin: Optional[float] = None
    trend_label: str

    business_message: str
    reliability_note: str
    key_drivers: list[dict]
    forecast_context: ForecastContext
    warnings: list[str] = Field(default_factory=list)
    metadata: ModelMetadata
    inference_ms: float


class PredictionContextResponse(BaseModel):
    countries: list[str]
    data_min_year: int
    data_max_year: int
    forecast_origin_year: int
    target_min_year: int
    target_max_year: int
    max_horizon: int
    passenger_unit: str = "MIO_PKM"
    co2_unit: str = "MIO_T"


@lru_cache(maxsize=1)
def _manifest():
    if not FORECAST_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest IA absent : {FORECAST_MANIFEST_PATH}"
        )

    return json.loads(
        FORECAST_MANIFEST_PATH.read_text(encoding="utf-8")
    )


def _model_date() -> str:
    try:
        return datetime.fromtimestamp(
            FORECAST_MANIFEST_PATH.stat().st_mtime
        ).strftime("%Y-%m-%d")
    except Exception:
        return "inconnue"


def _growth_pct(current: float, previous: float) -> float:
    if abs(previous) <= 1e-12:
        return 0.0
    return round(
        ((current - previous) / abs(previous)) * 100,
        2,
    )


def _resolve_country(db: Session, country_name: str):
    country = (
        db.query(DimCountries)
        .filter(
            func.lower(DimCountries.country_name)
            == country_name.lower()
        )
        .first()
    )

    if not country:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Pays non disponible",
                "message": (
                    f"Le pays '{country_name}' n'existe pas "
                    "dans le warehouse."
                ),
            },
        )

    return country


def _year_bounds(db: Session):
    row = (
        db.query(
            func.min(DimYears.year),
            func.max(DimYears.year),
        )
        .join(
            FactsCountryStats,
            FactsCountryStats.year_id == DimYears.year_id,
        )
        .one()
    )

    if row[0] is None or row[1] is None:
        raise HTTPException(
            status_code=503,
            detail="Aucune statistique pays/année disponible.",
        )

    return int(row[0]), int(row[1])


def _country_stat(
    db: Session,
    country_id: int,
    year: int,
):
    return (
        db.query(
            FactsCountryStats.passengers,
            FactsCountryStats.co2_emissions,
        )
        .join(
            DimYears,
            FactsCountryStats.year_id == DimYears.year_id,
        )
        .filter(
            FactsCountryStats.country_id == country_id,
            DimYears.year == year,
        )
        .first()
    )


def _network_context(
    db: Session,
    country_id: int,
    year: int,
):
    row = (
        db.query(
            func.count(FactsNightTrains.fact_id).label("total"),
            func.sum(
                case(
                    (FactsNightTrains.is_night.is_(True), 1),
                    else_=0,
                )
            ).label("night"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(False), 1),
                    else_=0,
                )
            ).label("real"),
            func.avg(FactsNightTrains.distance_km).label("avg_distance"),
            func.avg(FactsNightTrains.duration_min).label("avg_duration"),
            func.count(
                func.distinct(FactsNightTrains.operator_id)
            ).label("operators"),
        )
        .join(
            DimYears,
            FactsNightTrains.year_id == DimYears.year_id,
        )
        .filter(
            FactsNightTrains.country_id == country_id,
            DimYears.year == year,
        )
        .one()
    )

    total = int(row.total or 0)

    if total <= 0:
        return {
            "train_count_current": 0,
            "night_share_current": 0.0,
            "real_share_current": 0.0,
            "avg_distance_current": 0.0,
            "avg_duration_current": 0.0,
            "operator_count_current": 0,
            "network_data_available": False,
        }

    return {
        "train_count_current": total,
        "night_share_current": float(row.night or 0) / total,
        "real_share_current": float(row.real or 0) / total,
        "avg_distance_current": float(row.avg_distance or 0),
        "avg_duration_current": float(row.avg_duration or 0),
        "operator_count_current": int(row.operators or 0),
        "network_data_available": True,
    }


def _load_forecast_context(
    db: Session,
    country,
    target_year: int,
):
    data_min_year, data_max_year = _year_bounds(db)

    horizon = target_year - data_max_year

    if horizon < 1 or horizon > MAX_FORECAST_HORIZON:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Horizon non supporté",
                "message": (
                    f"Le warehouse s'arrête en {data_max_year}. "
                    f"Les prévisions directes disponibles vont de "
                    f"{data_max_year + 1} à "
                    f"{data_max_year + MAX_FORECAST_HORIZON}."
                ),
            },
        )

    current = _country_stat(
        db,
        country.country_id,
        data_max_year,
    )
    previous = _country_stat(
        db,
        country.country_id,
        data_max_year - 1,
    )

    if current is None or previous is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Historique insuffisant",
                "message": (
                    f"Les années {data_max_year - 1} et "
                    f"{data_max_year} sont nécessaires pour "
                    f"{country.country_name}."
                ),
            },
        )

    network = _network_context(
        db,
        country.country_id,
        data_max_year,
    )

    passengers_current = float(current.passengers)
    passengers_previous = float(previous.passengers)
    co2_current = float(current.co2_emissions)
    co2_previous = float(previous.co2_emissions)

    return ForecastContext(
        origin_year=data_max_year,
        target_year=target_year,
        horizon=horizon,
        passengers_current=passengers_current,
        passengers_previous=passengers_previous,
        passenger_growth_1y_pct=_growth_pct(
            passengers_current,
            passengers_previous,
        ),
        co2_current=co2_current,
        co2_previous=co2_previous,
        co2_growth_1y_pct=_growth_pct(
            co2_current,
            co2_previous,
        ),
        **network,
    )


@lru_cache(maxsize=1)
def _quality_map():
    if not QUALITY_FILE.exists():
        return {}

    result = {}

    try:
        with QUALITY_FILE.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)

            for row in reader:
                code = str(
                    row.get("country_code", "")
                ).upper().strip()

                try:
                    year = int(float(row.get("year", "")))
                except (TypeError, ValueError):
                    continue

                result[(code, year)] = {
                    "passengers_source": row.get(
                        "passengers_source",
                        "unknown",
                    ),
                    "co2_source": row.get(
                        "co2_source",
                        "unknown",
                    ),
                }
    except Exception as exc:
        logger.warning(
            "Lecture quality report impossible : %s",
            exc,
        )

    return result


def _quality_warnings(
    country_code: str,
    origin_year: int,
):
    quality = _quality_map()

    if not quality:
        return [
            "Provenance observée/synthétique indisponible pour ce calcul."
        ]

    warnings = []

    for year in [origin_year - 1, origin_year]:
        sources = quality.get(
            (country_code.upper(), year)
        )

        if not sources:
            warnings.append(
                f"Provenance non renseignée pour {year}."
            )
            continue

        if str(sources["passengers_source"]).lower() != "eurostat":
            warnings.append(
                f"Activité voyageurs {year} : "
                f"source {sources['passengers_source']}."
            )

        if str(sources["co2_source"]).lower() != "eurostat":
            warnings.append(
                f"CO₂ {year} : source {sources['co2_source']}."
            )

    return warnings


def _risk_level(probability: float):
    if probability < 0.25:
        return (
            "Faible",
            "La probabilité estimée de baisse reste faible.",
        )
    if probability < 0.50:
        return (
            "Modéré",
            "Le modèle identifie un risque intermédiaire.",
        )
    if probability < 0.75:
        return (
            "Élevé",
            "Le modèle estime que la baisse devient plus probable.",
        )
    return (
        "Critique",
        "Le modèle estime une forte probabilité de baisse.",
    )


def _trend_label(change_pct: float):
    if change_pct > 2:
        return "Croissance"
    if change_pct < -2:
        return "Déclin"
    return "Stable"


def _key_drivers(context: ForecastContext):
    return [
        {
            "variable": (
                f"Activité voyageurs {context.origin_year - 1}"
                f" → {context.origin_year}"
            ),
            "value": (
                f"{context.passenger_growth_1y_pct:+.2f} %"
            ),
            "explanation": (
                "Dynamique voyageurs connue au point de départ de la prévision."
            ),
        },
        {
            "variable": (
                f"CO₂ {context.origin_year - 1}"
                f" → {context.origin_year}"
            ),
            "value": (
                f"{context.co2_growth_1y_pct:+.2f} %"
            ),
            "explanation": (
                "Signal environnemental historique, sans utiliser "
                "de donnée future."
            ),
        },
        {
            "variable": "Offre ferroviaire à l'année d'origine",
            "value": (
                f"{context.train_count_current:,} trajets | "
                f"{context.operator_count_current} opérateurs"
            ),
            "explanation": (
                "Agrégat construit depuis facts_night_trains "
                "pour relier le modèle au réseau ObRail."
            ),
        },
    ]


def _metadata(axis: str):
    manifest = _manifest()
    section = manifest[axis]

    if axis == "classification":
        model_name = section["selected_model"]
        metrics = section["final_holdout"]
        model_type = "Classification directe multi-horizon"
    else:
        model_name = section["selected_model"]
        metrics = section["final_holdout"]
        model_type = "Régression directe multi-horizon hybride"

    return ModelMetadata(
        model_name=model_name,
        model_type=model_type,
        training_date=_model_date(),
        axis=axis,
        metrics=metrics,
    )


@router.get(
    "/context",
    response_model=PredictionContextResponse,
)
def get_prediction_context(
    db: Session = Depends(get_db),
):
    data_min_year, data_max_year = _year_bounds(db)

    countries = (
        db.query(DimCountries.country_name)
        .join(
            FactsCountryStats,
            FactsCountryStats.country_id
            == DimCountries.country_id,
        )
        .group_by(
            DimCountries.country_id,
            DimCountries.country_name,
        )
        .having(
            func.count(FactsCountryStats.stat_id) >= 2
        )
        .order_by(DimCountries.country_name)
        .all()
    )

    return PredictionContextResponse(
        countries=[row[0] for row in countries],
        data_min_year=data_min_year,
        data_max_year=data_max_year,
        forecast_origin_year=data_max_year,
        target_min_year=data_max_year + 1,
        target_max_year=data_max_year + MAX_FORECAST_HORIZON,
        max_horizon=MAX_FORECAST_HORIZON,
    )


@router.post(
    "/classification",
    response_model=ClassificationResponse,
)
def predict_classification(
    data: PredictionInput,
    db: Session = Depends(get_db),
):
    country = _resolve_country(db, data.country)
    context = _load_forecast_context(
        db,
        country,
        data.year,
    )

    warnings = _quality_warnings(
        country.country_code,
        context.origin_year,
    )

    try:
        start = time.perf_counter()
        raw = ml_predict(
            country=country.country_name,
            horizon=context.horizon,
            passengers_current=context.passengers_current,
            passengers_previous=context.passengers_previous,
            co2_current=context.co2_current,
            co2_previous=context.co2_previous,
            train_count_current=context.train_count_current,
            night_share_current=context.night_share_current,
            real_share_current=context.real_share_current,
            avg_distance_current=context.avg_distance_current,
            avg_duration_current=context.avg_duration_current,
            operator_count_current=context.operator_count_current,
            network_data_available=int(
                context.network_data_available
            ),
        )
        inference_ms = round(
            (time.perf_counter() - start) * 1000,
            1,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Modèle IA non disponible",
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:
        logger.exception("Erreur classification multi-horizon")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Erreur de prédiction",
                "message": str(exc),
            },
        ) from exc

    clf = raw["classification"]
    probability = float(clf["probability_decline"])
    prediction = int(clf["prediction"])

    risk_level, risk_description = _risk_level(
        probability
    )
    decision_margin = round(
        abs(probability - 0.5) * 100,
        1,
    )

    return ClassificationResponse(
        country=country.country_name,
        origin_year=context.origin_year,
        year=data.year,
        horizon=context.horizon,
        prediction=prediction,
        label=clf["label"],
        probability_decline=round(probability, 4),
        decision_margin=decision_margin,
        risk_level=risk_level,
        risk_description=risk_description,
        business_message=(
            f"À horizon N+{context.horizon}, le modèle estime "
            f"une probabilité de baisse de l'activité voyageurs de "
            f"{probability:.1%} entre {context.origin_year} et "
            f"{data.year} pour {country.country_name}."
        ),
        recommendations=[
            (
                "Comparer la prévision aux prochaines publications "
                "Eurostat dès leur disponibilité."
            ),
            (
                "Interpréter ce résultat avec la trajectoire de l'offre "
                "ferroviaire et la provenance réelle/synthétique des données."
            ),
        ],
        key_drivers=_key_drivers(context),
        forecast_context=context,
        warnings=warnings,
        metadata=_metadata("classification"),
        inference_ms=inference_ms,
    )


@router.post(
    "/regression",
    response_model=RegressionResponse,
)
def predict_regression(
    data: PredictionInput,
    db: Session = Depends(get_db),
):
    country = _resolve_country(db, data.country)
    context = _load_forecast_context(
        db,
        country,
        data.year,
    )

    warnings = _quality_warnings(
        country.country_code,
        context.origin_year,
    )

    try:
        start = time.perf_counter()
        raw = ml_predict(
            country=country.country_name,
            horizon=context.horizon,
            passengers_current=context.passengers_current,
            passengers_previous=context.passengers_previous,
            co2_current=context.co2_current,
            co2_previous=context.co2_previous,
            train_count_current=context.train_count_current,
            night_share_current=context.night_share_current,
            real_share_current=context.real_share_current,
            avg_distance_current=context.avg_distance_current,
            avg_duration_current=context.avg_duration_current,
            operator_count_current=context.operator_count_current,
            network_data_available=int(
                context.network_data_available
            ),
        )
        inference_ms = round(
            (time.perf_counter() - start) * 1000,
            1,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Modèle IA non disponible",
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:
        logger.exception("Erreur régression multi-horizon")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Erreur de prédiction",
                "message": str(exc),
            },
        ) from exc

    reg = raw["regression"]

    prediction = float(reg["prediction"])
    low = float(reg["interval_low"])
    high = float(reg["interval_high"])

    trend_vs_origin = _growth_pct(
        prediction,
        context.passengers_current,
    )
    label = _trend_label(trend_vs_origin)

    manifest = _manifest()
    regression_manifest = manifest["regression"]

    reliability = (
        "Prévision directe multi-horizon : aucun résultat 2025/2026 "
        "n'est réinjecté pour produire 2027. "
        f"Le modèle est combiné à une baseline "
        f"{regression_manifest['selected_baseline']} "
        f"(poids ML {regression_manifest['blend_weight_ml']:.0%}). "
        "L'intervalle affiché utilise le 90e percentile des erreurs "
        "du holdout temporel pour cet horizon."
    )

    return RegressionResponse(
        country=country.country_name,
        origin_year=context.origin_year,
        year=data.year,
        horizon=context.horizon,
        prediction_raw=round(prediction, 4),
        prediction_display=(
            f"{prediction:,.2f} MIO_PKM prévus"
        ),
        prediction_low=round(low, 4),
        prediction_high=round(high, 4),
        interval_level=float(reg["interval_level"]),
        trend_vs_origin=trend_vs_origin,
        trend_label=label,
        business_message=(
            f"Pour {country.country_name}, le modèle prévoit "
            f"{prediction:,.2f} MIO_PKM en {data.year}, soit "
            f"{trend_vs_origin:+.2f} % par rapport à "
            f"l'année d'origine {context.origin_year}."
        ),
        reliability_note=reliability,
        key_drivers=_key_drivers(context),
        forecast_context=context,
        warnings=warnings,
        metadata=_metadata("regression"),
        inference_ms=inference_ms,
    )
