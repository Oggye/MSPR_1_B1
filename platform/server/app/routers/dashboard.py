# server/app/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.dependencies import get_db
from app.models import DashboardMetrics, FactsCountryStats, FactsNightTrains, DimCountries, DimOperators, DimYears
from app.schemas.statistics import DashboardMetricsResponse, KPIsResponse

router = APIRouter()


@router.get("/api/dashboard/metrics", response_model=List[DashboardMetricsResponse])
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Métriques agrégées par pays. Vue: dashboard_metrics"""
    return db.query(DashboardMetrics).all()


@router.get("/api/dashboard/kpis", response_model=KPIsResponse)
def get_dashboard_kpis(db: Session = Depends(get_db)):
    """Indicateurs clés de performance."""

    # Comptages corrects et séparés
    total_countries = db.query(DimCountries).count()
    total_trains = db.query(FactsNightTrains).count()
    total_night_trains = db.query(FactsNightTrains).filter(FactsNightTrains.is_night.is_(True)).count()
    total_day_trains = db.query(FactsNightTrains).filter(FactsNightTrains.is_night.is_(False)).count()
    total_operators = db.query(DimOperators).count()

    # Période couverte
    years = db.query(DimYears.year).order_by(DimYears.year).all()
    if years:
        years_covered = f"{years[0][0]}-{years[-1][0]}"
    else:
        years_covered = "Pas de données"

    # Agrégations en une seule requête
    stats = db.query(
        func.avg(FactsCountryStats.co2_per_passenger),
        func.sum(FactsCountryStats.passengers),
        func.sum(FactsCountryStats.co2_emissions)
    ).first()

    avg_co2_per_passenger = float(stats[0] or 0)
    total_passengers = float(stats[1] or 0)
    total_co2_emissions = float(stats[2] or 0)

    return KPIsResponse(
        total_countries=total_countries,
        total_trains=total_trains,
        total_night_trains=total_night_trains,
        total_day_trains=total_day_trains,
        total_operators=total_operators,
        years_covered=years_covered,
        avg_co2_per_passenger=avg_co2_per_passenger,
        total_passengers=total_passengers,
        total_co2_emissions=total_co2_emissions
    )
