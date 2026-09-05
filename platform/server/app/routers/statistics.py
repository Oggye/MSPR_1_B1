# app/routers/statistics.py
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import DashboardMetrics, DimYears, FactsCountryStats, FactsNightTrains
from app.schemas.statistics import CO2RankingItem, TimelineData

router = APIRouter()


@router.get("/api/statistics/timeline", response_model=List[TimelineData])
def get_timeline_data(db: Session = Depends(get_db)):
    """
    Série temporelle complète.

    Les comptages jour/nuit sont calculés séparément. Les années GTFS récentes
    peuvent exister même lorsqu'Eurostat ne possède pas encore de statistique
    pays correspondante ; elles sont alors conservées avec métriques `None`.
    """
    stats_rows = (
        db.query(
            DimYears.year,
            func.sum(FactsCountryStats.passengers).label("passengers"),
            func.sum(FactsCountryStats.co2_emissions).label("co2_emissions"),
            func.avg(FactsCountryStats.co2_per_passenger).label(
                "co2_per_passenger"
            ),
        )
        .join(
            DimYears,
            FactsCountryStats.year_id == DimYears.year_id,
        )
        .group_by(DimYears.year_id, DimYears.year)
        .order_by(DimYears.year)
        .all()
    )

    train_rows = (
        db.query(
            DimYears.year,
            func.count(FactsNightTrains.fact_id).label("total_trains"),
            func.sum(
                case((FactsNightTrains.is_night.is_(True), 1), else_=0)
            ).label("night_trains"),
            func.sum(
                case((FactsNightTrains.is_night.is_(False), 1), else_=0)
            ).label("day_trains"),
        )
        .join(
            DimYears,
            FactsNightTrains.year_id == DimYears.year_id,
        )
        .group_by(DimYears.year_id, DimYears.year)
        .order_by(DimYears.year)
        .all()
    )

    stats_by_year = {
        int(year): {
            "passengers": passengers,
            "co2_emissions": co2,
            "co2_per_passenger": co2_pp,
        }
        for year, passengers, co2, co2_pp in stats_rows
    }
    trains_by_year = {
        int(year): {
            "total": int(total or 0),
            "night": int(night or 0),
            "day": int(day or 0),
        }
        for year, total, night, day in train_rows
    }

    years = sorted(set(stats_by_year) | set(trains_by_year))
    timeline = []

    for year in years:
        stats = stats_by_year.get(year, {})
        trains = trains_by_year.get(
            year,
            {"total": 0, "night": 0, "day": 0},
        )

        passengers = stats.get("passengers")
        co2 = stats.get("co2_emissions")
        co2_pp = stats.get("co2_per_passenger")

        timeline.append(
            TimelineData(
                year=year,
                passengers=(
                    float(passengers)
                    if passengers is not None
                    else None
                ),
                co2_emissions=(
                    float(co2)
                    if co2 is not None
                    else None
                ),
                co2_per_passenger=(
                    float(co2_pp)
                    if co2_pp is not None
                    else None
                ),
                total_trains_count=trains["total"],
                night_trains_count=trains["night"],
                day_trains_count=trains["day"],
            )
        )

    return timeline


@router.get(
    "/api/statistics/co2-ranking",
    response_model=List[CO2RankingItem],
)
def get_co2_ranking(
    db: Session = Depends(get_db),
    limit: Optional[int] = Query(None, ge=1, le=200),
):
    query = db.query(
        DashboardMetrics.country_name,
        DashboardMetrics.country_code,
        DashboardMetrics.avg_co2_per_passenger,
    ).filter(
        DashboardMetrics.avg_co2_per_passenger.isnot(None)
    ).order_by(
        DashboardMetrics.avg_co2_per_passenger.asc()
    )

    if limit is not None:
        query = query.limit(limit)

    ranking_data = query.all()
    ranking_items = []

    for ranking, (country_name, country_code, avg_co2) in enumerate(
        ranking_data,
        start=1,
    ):
        value = float(avg_co2)
        if value < 0.05:
            performance = "good"
        elif value < 0.1:
            performance = "medium"
        else:
            performance = "bad"

        ranking_items.append(
            CO2RankingItem(
                country_name=country_name,
                country_code=country_code,
                avg_co2_per_passenger=value,
                ranking=ranking,
                performance=performance,
            )
        )

    return ranking_items
