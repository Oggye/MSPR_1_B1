"""
Endpoints des trajets ferroviaires.

Le chemin historique `/api/night-trains` est conservé pour compatibilité.
En plus de la pagination classique, `/api/night-trains/stratified` découpe
le jeu filtré en dix tranches stables.

Tranche 1 : fact_id % 10 == 0
...
Tranche 10 : fact_id % 10 == 9

Les dix tranches sont disjointes et couvrent 100 % des faits. Comme fact_id
est séquentiel dans le warehouse, chaque pays suffisamment volumineux est
réparti quasi uniformément entre les dix tranches.

Important : les agrégats portent sur TOUTE la tranche, mais seuls quelques
exemples par pays sont renvoyés dans `items` pour ne pas surcharger React.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import DimCountries, DimOperators, DimYears, FactsNightTrains
from app.schemas.trains import (
    CountrySliceSummary,
    NightTrainResponse,
    NightTrainSummary,
    StratifiedTrainPage,
    TrainFacets,
)

router = APIRouter()

DEFAULT_LIMIT = 100
MAX_LIMIT = 5000
STRATIFIED_PAGE_COUNT = 10
DEFAULT_SAMPLE_PER_COUNTRY = 2
MAX_SAMPLE_PER_COUNTRY = 50


def _base_query(db: Session, *entities):
    return (
        db.query(*entities)
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


def _apply_common_filters(
    query,
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
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
    if is_night is not None:
        query = query.filter(FactsNightTrains.is_night.is_(is_night))
    if is_synthetic is not None:
        query = query.filter(
            FactsNightTrains.is_synthetic.is_(is_synthetic)
        )
    if data_source:
        query = query.filter(
            FactsNightTrains.data_source == data_source.strip()
        )
    return query


def _apply_slice_filter(query, slice_page: Optional[int]):
    if slice_page is None:
        return query

    bucket = slice_page - 1
    return query.filter(
        (FactsNightTrains.fact_id % STRATIFIED_PAGE_COUNT) == bucket
    )


def _build_train_query(
    db: Session,
    *,
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
    slice_page: Optional[int] = None,
):
    query = _base_query(
        db,
        FactsNightTrains,
        DimCountries.country_name,
        DimCountries.country_code,
        DimOperators.operator_name,
        DimYears.year,
    )
    query = _apply_common_filters(
        query,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    query = _apply_slice_filter(query, slice_page)
    return query.order_by(FactsNightTrains.fact_id)


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
        fact_id=int(train.fact_id),
        route_id=train.route_id,
        train=canonical_name,
        night_train=canonical_name,
        country_name=country_name,
        country_code=country_code,
        operator_name=operator_name,
        year=int(year),
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


def _country_aggregate_query(
    db: Session,
    *,
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
    slice_page: Optional[int] = None,
):
    query = _base_query(
        db,
        DimCountries.country_name,
        DimCountries.country_code,
        func.count(FactsNightTrains.fact_id).label("total"),
        func.sum(
            case((FactsNightTrains.is_night.is_(True), 1), else_=0)
        ).label("night"),
        func.sum(
            case((FactsNightTrains.is_night.is_(False), 1), else_=0)
        ).label("day"),
        func.sum(
            case((FactsNightTrains.is_synthetic.is_(False), 1), else_=0)
        ).label("real"),
        func.sum(
            case((FactsNightTrains.is_synthetic.is_(True), 1), else_=0)
        ).label("synthetic"),
        func.avg(FactsNightTrains.distance_km).label("avg_distance"),
        func.avg(FactsNightTrains.duration_min).label("avg_duration"),
        func.sum(FactsNightTrains.distance_km).label("sum_distance"),
        func.count(FactsNightTrains.distance_km).label("count_distance"),
        func.sum(FactsNightTrains.duration_min).label("sum_duration"),
        func.count(FactsNightTrains.duration_min).label("count_duration"),
    )
    query = _apply_common_filters(
        query,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    query = _apply_slice_filter(query, slice_page)

    return (
        query.group_by(
            DimCountries.country_id,
            DimCountries.country_name,
            DimCountries.country_code,
        )
        .order_by(
            func.count(FactsNightTrains.fact_id).desc(),
            DimCountries.country_code,
        )
    )


def _sample_items(
    db: Session,
    *,
    slice_page: int,
    sample_per_country: int,
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
) -> List[NightTrainResponse]:
    if sample_per_country <= 0:
        return []

    # Ordre pseudo-aléatoire mais déterministe : meilleure diversité d'aperçu
    # qu'une simple sélection des premiers fact_id.
    stable_order = (
        (FactsNightTrains.fact_id * 1103515245 + 12345)
        % 2147483647
    )

    ranked = _base_query(
        db,
        FactsNightTrains.fact_id.label("fact_id"),
        FactsNightTrains.route_id.label("route_id"),
        FactsNightTrains.train.label("train"),
        FactsNightTrains.is_night.label("is_night"),
        FactsNightTrains.distance_km.label("distance_km"),
        FactsNightTrains.duration_min.label("duration_min"),
        FactsNightTrains.is_synthetic.label("is_synthetic"),
        FactsNightTrains.data_source.label("data_source"),
        DimCountries.country_name.label("country_name"),
        DimCountries.country_code.label("country_code"),
        DimOperators.operator_name.label("operator_name"),
        DimYears.year.label("year"),
        func.row_number()
        .over(
            partition_by=FactsNightTrains.country_id,
            order_by=(stable_order, FactsNightTrains.fact_id),
        )
        .label("country_rank"),
    )
    ranked = _apply_common_filters(
        ranked,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )
    ranked = _apply_slice_filter(ranked, slice_page)
    ranked = ranked.subquery("ranked_stratified_trains")

    statement = (
        select(ranked)
        .where(ranked.c.country_rank <= sample_per_country)
        .order_by(
            ranked.c.country_rank,
            ranked.c.country_code,
            ranked.c.fact_id,
        )
    )

    rows = db.execute(statement).mappings().all()

    items = []
    for row in rows:
        is_night_value = bool(row["is_night"])
        canonical_name = row["train"] or "Train"

        items.append(
            NightTrainResponse(
                fact_id=int(row["fact_id"]),
                route_id=row["route_id"],
                train=canonical_name,
                night_train=canonical_name,
                country_name=row["country_name"],
                country_code=row["country_code"],
                operator_name=row["operator_name"],
                year=int(row["year"]),
                is_night=is_night_value,
                distance_km=(
                    float(row["distance_km"])
                    if row["distance_km"] is not None
                    else None
                ),
                duration_min=(
                    float(row["duration_min"])
                    if row["duration_min"] is not None
                    else None
                ),
                is_synthetic=bool(row["is_synthetic"]),
                data_source=row["data_source"] or "unknown",
                train_type="night" if is_night_value else "day",
            )
        )

    return items


@router.get("/api/night-trains/summary", response_model=NightTrainSummary)
def get_night_trains_summary(db: Session = Depends(get_db)):
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


@router.get("/api/night-trains/facets", response_model=TrainFacets)
def get_train_facets(db: Session = Depends(get_db)):
    years = (
        db.query(DimYears.year)
        .join(
            FactsNightTrains,
            FactsNightTrains.year_id == DimYears.year_id,
        )
        .distinct()
        .order_by(DimYears.year)
        .all()
    )

    sources = (
        db.query(FactsNightTrains.data_source)
        .filter(FactsNightTrains.data_source.isnot(None))
        .distinct()
        .order_by(FactsNightTrains.data_source)
        .all()
    )

    return TrainFacets(
        years=[int(row[0]) for row in years],
        data_sources=[
            str(row[0])
            for row in sources
            if row[0] and str(row[0]).strip()
        ],
        page_count=STRATIFIED_PAGE_COUNT,
    )


@router.get(
    "/api/night-trains/stratified",
    response_model=StratifiedTrainPage,
)
def get_stratified_trains(
    db: Session = Depends(get_db),
    slice_page: int = Query(1, ge=1, le=STRATIFIED_PAGE_COUNT),
    sample_per_country: int = Query(
        DEFAULT_SAMPLE_PER_COUNTRY,
        ge=0,
        le=MAX_SAMPLE_PER_COUNTRY,
    ),
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
):
    """Retourne une tranche stable d'environ 10 % de chaque pays."""

    full_rows = _country_aggregate_query(
        db,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
        slice_page=None,
    ).all()

    slice_rows = _country_aggregate_query(
        db,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
        slice_page=slice_page,
    ).all()

    full_by_country = {row.country_code: row for row in full_rows}
    slice_by_country = {row.country_code: row for row in slice_rows}

    total_filtered = sum(int(row.total or 0) for row in full_rows)
    slice_total = sum(int(row.total or 0) for row in slice_rows)

    total_night = 0
    total_day = 0
    total_real = 0
    total_synthetic = 0
    sum_distance = 0.0
    count_distance = 0
    sum_duration = 0.0
    count_duration = 0

    by_country = []

    for country_code_key, full_row in full_by_country.items():
        slice_row = slice_by_country.get(country_code_key)

        country_total = int(full_row.total or 0)
        country_slice_total = int(slice_row.total or 0) if slice_row else 0

        night = int(slice_row.night or 0) if slice_row else 0
        day = int(slice_row.day or 0) if slice_row else 0
        real = int(slice_row.real or 0) if slice_row else 0
        synthetic = int(slice_row.synthetic or 0) if slice_row else 0

        total_night += night
        total_day += day
        total_real += real
        total_synthetic += synthetic

        if slice_row:
            if slice_row.sum_distance is not None:
                sum_distance += float(slice_row.sum_distance)
            count_distance += int(slice_row.count_distance or 0)

            if slice_row.sum_duration is not None:
                sum_duration += float(slice_row.sum_duration)
            count_duration += int(slice_row.count_duration or 0)

        by_country.append(
            CountrySliceSummary(
                country_name=full_row.country_name,
                country_code=country_code_key,
                total_filtered=country_total,
                slice_trains=country_slice_total,
                slice_percent=(
                    round((country_slice_total / country_total) * 100, 3)
                    if country_total > 0
                    else 0.0
                ),
                night_trains=night,
                day_trains=day,
                real_trains=real,
                synthetic_trains=synthetic,
                avg_distance_km=(
                    float(slice_row.avg_distance)
                    if slice_row
                    and slice_row.avg_distance is not None
                    else None
                ),
                avg_duration_min=(
                    float(slice_row.avg_duration)
                    if slice_row
                    and slice_row.avg_duration is not None
                    else None
                ),
            )
        )

    by_country.sort(key=lambda item: (-item.slice_trains, item.country_code))

    items = _sample_items(
        db,
        slice_page=slice_page,
        sample_per_country=sample_per_country,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
    )

    return StratifiedTrainPage(
        slice_page=slice_page,
        page_count=STRATIFIED_PAGE_COUNT,
        target_slice_percent=100 / STRATIFIED_PAGE_COUNT,
        total_filtered=total_filtered,
        slice_total=slice_total,
        actual_slice_percent=(
            round((slice_total / total_filtered) * 100, 3)
            if total_filtered > 0
            else 0.0
        ),
        countries_filtered=len(full_rows),
        countries_covered=sum(
            1 for item in by_country if item.slice_trains > 0
        ),
        total_night_trains=total_night,
        total_day_trains=total_day,
        total_real_trains=total_real,
        total_synthetic_trains=total_synthetic,
        avg_distance_km=(
            sum_distance / count_distance if count_distance > 0 else None
        ),
        avg_duration_min=(
            sum_duration / count_duration if count_duration > 0 else None
        ),
        sample_per_country=sample_per_country,
        items_returned=len(items),
        by_country=by_country,
        items=items,
    )


@router.get("/api/night-trains", response_model=List[NightTrainResponse])
def get_all_night_trains(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    country_code: Optional[str] = None,
    operator_name: Optional[str] = None,
    year: Optional[int] = None,
    is_night: Optional[bool] = None,
    is_synthetic: Optional[bool] = None,
    data_source: Optional[str] = None,
    slice_page: Optional[int] = Query(
        None, ge=1, le=STRATIFIED_PAGE_COUNT
    ),
):
    query = _build_train_query(
        db,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=is_night,
        is_synthetic=is_synthetic,
        data_source=data_source,
        slice_page=slice_page,
    )
    results = query.offset(skip).limit(limit).all()
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
    slice_page: Optional[int] = Query(
        None, ge=1, le=STRATIFIED_PAGE_COUNT
    ),
):
    query = _build_train_query(
        db,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=True,
        is_synthetic=is_synthetic,
        data_source=data_source,
        slice_page=slice_page,
    )
    results = query.offset(skip).limit(limit).all()
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
    slice_page: Optional[int] = Query(
        None, ge=1, le=STRATIFIED_PAGE_COUNT
    ),
):
    query = _build_train_query(
        db,
        country_code=country_code,
        operator_name=operator_name,
        year=year,
        is_night=False,
        is_synthetic=is_synthetic,
        data_source=data_source,
        slice_page=slice_page,
    )
    results = query.offset(skip).limit(limit).all()
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
    slice_page: Optional[int] = Query(
        None, ge=1, le=STRATIFIED_PAGE_COUNT
    ),
):
    operator = (
        db.query(DimOperators)
        .filter(DimOperators.operator_id == operator_id)
        .first()
    )
    if not operator:
        raise HTTPException(status_code=404, detail="Opérateur non trouvé")

    query = _build_train_query(
        db,
        is_synthetic=is_synthetic,
        slice_page=slice_page,
    ).filter(FactsNightTrains.operator_id == operator_id)

    results = query.offset(skip).limit(limit).all()
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
