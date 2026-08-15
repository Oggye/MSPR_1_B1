# app/routers/night_trains.py
"""
Endpoints des trajets ferroviaires.

Le chemin historique `/api/night-trains` est conservé pour compatibilité, mais
les endpoints retournent bien les trains de jour ET de nuit.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import DimCountries, DimOperators, DimYears, FactsNightTrains
from app.schemas.trains import NightTrainResponse, NightTrainSummary

router = APIRouter()

DEFAULT_LIMIT = 100
MAX_LIMIT = 5000


def _build_night_trains_query(db: Session, is_night: Optional[bool] = None):
    query = (
        db.query(
            FactsNightTrains,
            DimCountries.country_name,
            DimCountries.country_code,
            DimOperators.operator_name,
            DimYears.year,
        )
        .join(
            DimCountries,
            FactsNightTrains.country_id == DimCountries.country_id,
        )
        .join(
            DimOperators,
            FactsNightTrains.operator_id == DimOperators.operator_id,
        )
        .join(
            DimYears,
            FactsNightTrains.year_id == DimYears.year_id,
        )
    )

    if is_night is not None:
        query = query.filter(FactsNightTrains.is_night.is_(is_night))

    # Pagination stable même si les données sont rechargées en gros volume.
    return query.order_by(FactsNightTrains.fact_id)


def _apply_common_filters(
    query,
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
):
    if country_code:
        query = query.filter(
            DimCountries.country_code == country_code.strip().upper()
        )
    if operator_name:
        query = query.filter(
            DimOperators.operator_name.ilike(f"%{operator_name.strip()}%")
        )
    if year is not None:
        query = query.filter(DimYears.year == year)
    if is_synthetic is not None:
        query = query.filter(
            FactsNightTrains.is_synthetic.is_(is_synthetic)
        )
    if data_source:
        query = query.filter(
            FactsNightTrains.data_source == data_source.strip()
        )
    return query


def _apply_pagination(query, skip: int, limit: Optional[int]):
    query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)
    return query


def _to_response(
    train,
    country_name,
    country_code,
    operator_name,
    year,
) -> NightTrainResponse:
    canonical_name = getattr(train, "train", None) or getattr(
        train, "night_train", "Train"
    )

    return NightTrainResponse(
        fact_id=train.fact_id,
        route_id=train.route_id,
        train=canonical_name,
        # Alias temporaire pour ne pas casser l'ancien frontend.
        night_train=canonical_name,
        country_name=country_name,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=bool(train.is_night),
        distance_km=(
            float(train.distance_km)
            if train.distance_km is not None
            else None
        ),
        duration_min=(
            float(train.duration_min)
            if train.duration_min is not None
            else None
        ),
        is_synthetic=bool(getattr(train, "is_synthetic", False)),
        data_source=getattr(train, "data_source", None) or "unknown",
        train_type="night" if train.is_night else "day",
    )


@router.get("/api/night-trains/summary", response_model=NightTrainSummary)
def get_night_trains_summary(db: Session = Depends(get_db)):
    """
    Résumé global en une seule requête SQL.

    Adapté aux centaines de milliers / millions de faits.
    """
    row = db.query(
        func.count(FactsNightTrains.fact_id).label("total"),
        func.sum(
            case((FactsNightTrains.is_night.is_(True), 1), else_=0)
        ).label("night"),
        func.sum(
            case((FactsNightTrains.is_night.is_(False), 1), else_=0)
        ).label("day"),
        func.sum(
            case((FactsNightTrains.is_synthetic.is_(True), 1), else_=0)
        ).label("synthetic"),
        func.sum(
            case((FactsNightTrains.is_synthetic.is_(False), 1), else_=0)
        ).label("real"),
    ).one()

    return NightTrainSummary(
        total_trains=int(row.total or 0),
        total_night_trains=int(row.night or 0),
        total_day_trains=int(row.day or 0),
        total_real_trains=int(row.real or 0),
        total_synthetic_trains=int(row.synthetic or 0),
    )


@router.get("/api/night-trains", response_model=List[NightTrainResponse])
def get_all_night_trains(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
):
    """
    Retourne les trajets jour+nuit.

    Une limite est obligatoire côté serveur pour éviter de sérialiser plusieurs
    centaines de milliers de lignes en une seule réponse.
    """
    query = _build_night_trains_query(db)
    query = _apply_common_filters(
        query,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    results = _apply_pagination(query, skip, limit).all()
    return [_to_response(*row) for row in results]


@router.get("/api/night-trains/night", response_model=List[NightTrainResponse])
def get_night_trains_only(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
):
    query = _build_night_trains_query(db, is_night=True)
    query = _apply_common_filters(
        query,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    results = _apply_pagination(query, skip, limit).all()
    return [_to_response(*row) for row in results]


@router.get("/api/night-trains/day", response_model=List[NightTrainResponse])
def get_day_trains_only(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
):
    query = _build_night_trains_query(db, is_night=False)
    query = _apply_common_filters(
        query,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    results = _apply_pagination(query, skip, limit).all()
    return [_to_response(*row) for row in results]


@router.get(
    "/api/night-trains/by-operator/{operator_id}",
    response_model=List[NightTrainResponse],
)
def get_night_trains_by_operator(
    operator_id: int,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    is_synthetic: Optional[bool] = None,
):
    operator = (
        db.query(DimOperators)
        .filter(DimOperators.operator_id == operator_id)
        .first()
    )
    if not operator:
        raise HTTPException(status_code=404, detail="Opérateur non trouvé")

    query = _build_night_trains_query(db).filter(
        FactsNightTrains.operator_id == operator_id
    )
    if is_synthetic is not None:
        query = query.filter(
            FactsNightTrains.is_synthetic.is_(is_synthetic)
        )

    results = _apply_pagination(query, skip, limit).all()
    return [_to_response(*row) for row in results]


@router.get("/api/geographic/coverage")
def get_geographic_coverage(db: Session = Depends(get_db)):
    coverage = (
        db.query(
            DimCountries.country_name,
            DimCountries.country_code,
            func.count(FactsNightTrains.fact_id).label("train_count"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(False), 1),
                    else_=0,
                )
            ).label("real_count"),
            func.sum(
                case(
                    (FactsNightTrains.is_synthetic.is_(True), 1),
                    else_=0,
                )
            ).label("synthetic_count"),
        )
        .join(
            FactsNightTrains,
            DimCountries.country_id == FactsNightTrains.country_id,
        )
        .group_by(
            DimCountries.country_id,
            DimCountries.country_name,
            DimCountries.country_code,
        )
        .order_by(func.count(FactsNightTrains.fact_id).desc())
        .all()
    )

    return {
        "total_countries_covered": len(coverage),
        "coverage_by_country": [
            {
                "country_name": row.country_name,
                "country_code": row.country_code,
                "train_count": int(row.train_count or 0),
                "real_count": int(row.real_count or 0),
                "synthetic_count": int(row.synthetic_count or 0),
            }
            for row in coverage
        ],
    }
