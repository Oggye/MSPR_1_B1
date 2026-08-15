# app/routers/analysis.py
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import DimCountries, FactsCountryStats, FactsNightTrains
from app.schemas.statistics import TrainTypeComparison

router = APIRouter()


@router.get("/api/analysis/train-types-comparison")
def compare_train_types(db: Session = Depends(get_db)):
    """
    Compare les trains de jour et de nuit.

    Les statistiques pays/année sont jointes sur le même pays ET la même année
    pour éviter les multiplications de lignes.
    """
    reference_co2 = 0.05

    results = (
        db.query(
            FactsNightTrains.is_night,
            func.count(FactsNightTrains.fact_id).label("nb_trains"),
            func.avg(FactsNightTrains.distance_km).label("avg_distance"),
            func.avg(FactsNightTrains.duration_min).label("avg_duration"),
            func.avg(FactsCountryStats.co2_per_passenger).label("avg_co2"),
            func.avg(FactsCountryStats.passengers).label("avg_passengers"),
        )
        .outerjoin(
            FactsCountryStats,
            and_(
                FactsCountryStats.country_id
                == FactsNightTrains.country_id,
                FactsCountryStats.year_id == FactsNightTrains.year_id,
            ),
        )
        .group_by(FactsNightTrains.is_night)
        .all()
    )

    comparisons: List[TrainTypeComparison] = []
    for row in results:
        avg_co2 = float(row.avg_co2 or 0)
        avg_passengers = float(row.avg_passengers or 0)
        avg_distance = float(row.avg_distance or 0)
        efficiency = (
            min(100, (reference_co2 / avg_co2) * 100)
            if avg_co2 > 0
            else 0
        )

        comparisons.append(
            TrainTypeComparison(
                train_type="night" if row.is_night else "day",
                avg_passengers=avg_passengers,
                avg_distance=avg_distance,
                avg_co2_per_passenger=avg_co2,
                efficiency_score=efficiency,
            )
        )

    if not comparisons:
        return [
            TrainTypeComparison(
                train_type="night",
                avg_passengers=0,
                avg_distance=0,
                avg_co2_per_passenger=0,
                efficiency_score=0,
            ),
            TrainTypeComparison(
                train_type="day",
                avg_passengers=0,
                avg_distance=0,
                avg_co2_per_passenger=0,
                efficiency_score=0,
            ),
        ]

    return comparisons


@router.get("/api/analysis/policy-recommendations")
def get_policy_recommendations(db: Session = Depends(get_db)):
    """
    Recommandations simples basées sur les agrégats disponibles.

    Le comptage des trains est pré-agrégé par pays avant jointure avec le CO2.
    Cela évite le produit cartésien historique entre plusieurs années de stats
    et plusieurs centaines de milliers de trains.
    """
    recommendations = []

    top_emitters = (
        db.query(
            DimCountries.country_name,
            func.avg(FactsCountryStats.co2_per_passenger).label("avg_co2"),
        )
        .join(
            FactsCountryStats,
            DimCountries.country_id == FactsCountryStats.country_id,
        )
        .group_by(DimCountries.country_id, DimCountries.country_name)
        .order_by(
            func.avg(FactsCountryStats.co2_per_passenger).desc()
        )
        .limit(5)
        .all()
    )

    if top_emitters:
        recommendations.append(
            {
                "title": "Pays prioritaires pour la modernisation",
                "description": (
                    "Ces pays ont les émissions moyennes les plus élevées: "
                    + ", ".join(row.country_name for row in top_emitters)
                ),
                "suggestion": (
                    "Prioriser l'analyse des causes et les investissements "
                    "dans l'efficacité énergétique du rail."
                ),
                "avg_co2_per_passenger": [
                    float(row.avg_co2) for row in top_emitters
                ],
            }
        )

    stats_by_country = (
        db.query(
            FactsCountryStats.country_id.label("country_id"),
            func.avg(FactsCountryStats.co2_per_passenger).label("avg_co2"),
        )
        .group_by(FactsCountryStats.country_id)
        .subquery()
    )

    trains_by_country = (
        db.query(
            FactsNightTrains.country_id.label("country_id"),
            func.count(FactsNightTrains.fact_id).label("train_count"),
        )
        .group_by(FactsNightTrains.country_id)
        .subquery()
    )

    success = (
        db.query(
            DimCountries.country_name,
            stats_by_country.c.avg_co2,
            trains_by_country.c.train_count,
        )
        .join(
            stats_by_country,
            DimCountries.country_id == stats_by_country.c.country_id,
        )
        .join(
            trains_by_country,
            DimCountries.country_id == trains_by_country.c.country_id,
        )
        .filter(stats_by_country.c.avg_co2 < 0.03)
        .order_by(trains_by_country.c.train_count.desc())
        .first()
    )

    if success:
        recommendations.append(
            {
                "title": "Bonnes pratiques",
                "description": (
                    f"{success.country_name} combine un indicateur CO2 faible "
                    f"({float(success.avg_co2):.3f}) et "
                    f"{int(success.train_count):,} services."
                ),
                "suggestion": (
                    "Étudier les facteurs expliquant cette performance avant "
                    "de transposer les bonnes pratiques."
                ),
            }
        )

    return {"recommendations": recommendations}
