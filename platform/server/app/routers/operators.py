from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import (
    DimCountries,
    DimOperators,
    DimYears,
    FactsCountryStats,
    FactsNightTrains,
    OperatorDashboard,
)
from app.schemas.operators import (
    OperatorRanking,
    OperatorResponse,
    OperatorTimelineItem,
)

router = APIRouter()


@router.get("/api/operators", response_model=List[OperatorResponse])
def get_operators(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    operators = (
        db.query(DimOperators)
        .order_by(DimOperators.operator_name)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        OperatorResponse(
            operator_id=op.operator_id,
            operator_name=op.operator_name,
        )
        for op in operators
    ]


@router.get(
    "/api/operators/{operator_id}/stats",
    response_model=OperatorRanking,
)
def get_operator_stats(
    operator_id: int,
    db: Session = Depends(get_db),
):
    dashboard = (
        db.query(OperatorDashboard)
        .filter(OperatorDashboard.operator_id == operator_id)
        .first()
    )

    if not dashboard:
        raise HTTPException(status_code=404, detail="Opérateur non trouvé")

    countries = (
        db.query(DimCountries)
        .join(
            FactsNightTrains,
            DimCountries.country_id == FactsNightTrains.country_id,
        )
        .filter(FactsNightTrains.operator_id == operator_id)
        .distinct()
        .order_by(DimCountries.country_name)
        .all()
    )

    # Distinct country/year prevents one macro statistic from being repeated
    # once per train in the CO2 average.
    served_pairs = (
        db.query(
            FactsNightTrains.country_id.label("country_id"),
            FactsNightTrains.year_id.label("year_id"),
        )
        .filter(FactsNightTrains.operator_id == operator_id)
        .distinct()
        .subquery()
    )

    avg_co2 = (
        db.query(func.avg(FactsCountryStats.co2_per_passenger))
        .join(
            served_pairs,
            (
                FactsCountryStats.country_id
                == served_pairs.c.country_id
            )
            & (
                FactsCountryStats.year_id
                == served_pairs.c.year_id
            ),
        )
        .scalar()
    )

    source_counts = (
        db.query(
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(False), 1),
                    else_=0,
                )
            ).label("real"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(True), 1),
                    else_=0,
                )
            ).label("synthetic"),
        )
        .filter(FactsNightTrains.operator_id == operator_id)
        .one()
    )

    return OperatorRanking(
        operator_id=dashboard.operator_id,
        operator_name=dashboard.operator_name,
        total_trains=int(dashboard.nb_trains or 0),
        night_trains=int(dashboard.nb_trains_nuit or 0),
        day_trains=int(dashboard.nb_trains_jour or 0),
        real_trains=int(source_counts.real or 0),
        synthetic_trains=int(source_counts.synthetic or 0),
        distance_totale_km=float(dashboard.distance_totale_km or 0),
        duree_moyenne_min=float(dashboard.duree_moyenne_min or 0),
        avg_co2_per_passenger=(
            float(avg_co2)
            if avg_co2 is not None
            else None
        ),
        countries_served=[c.country_name for c in countries],
        countries_count=len(countries),
    )


@router.get(
    "/api/operators/{operator_id}/timeline",
    response_model=List[OperatorTimelineItem],
)
def get_operator_timeline(
    operator_id: int,
    db: Session = Depends(get_db),
):
    operator_exists = (
        db.query(DimOperators.operator_id)
        .filter(DimOperators.operator_id == operator_id)
        .first()
    )

    if not operator_exists:
        raise HTTPException(status_code=404, detail="Opérateur non trouvé")

    rows = (
        db.query(
            DimYears.year,
            func.count(FactsNightTrains.fact_id).label("total"),
            func.sum(
                case(
                    (FactsNightTrains.is_night.is_(True), 1),
                    else_=0,
                )
            ).label("night"),
            func.sum(
                case(
                    (FactsNightTrains.is_night.is_(False), 1),
                    else_=0,
                )
            ).label("day"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(False), 1),
                    else_=0,
                )
            ).label("real"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(True), 1),
                    else_=0,
                )
            ).label("synthetic"),
        )
        .join(
            FactsNightTrains,
            FactsNightTrains.year_id == DimYears.year_id,
        )
        .filter(FactsNightTrains.operator_id == operator_id)
        .group_by(DimYears.year_id, DimYears.year)
        .order_by(DimYears.year)
        .all()
    )

    return [
        OperatorTimelineItem(
            year=int(row.year),
            total_trains=int(row.total or 0),
            night_trains=int(row.night or 0),
            day_trains=int(row.day or 0),
            real_trains=int(row.real or 0),
            synthetic_trains=int(row.synthetic or 0),
        )
        for row in rows
    ]
