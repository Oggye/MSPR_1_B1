# app/schemas/statistics.py
from typing import Optional

from .base import BaseSchema


PASSENGER_METRIC = "MIO_PKM"
PASSENGER_UNIT = "million passenger-km"


class DashboardMetricsResponse(BaseSchema):
    country_id: int
    country_name: str
    country_code: str
    avg_passengers: float
    avg_co2_emissions: float
    avg_co2_per_passenger: float


class KPIsResponse(BaseSchema):
    total_countries: int
    total_trains: int
    total_night_trains: int
    total_day_trains: int
    total_operators: int
    years_covered: str
    avg_co2_per_passenger: float
    total_passengers: float
    total_co2_emissions: float

    # Information sémantique : la colonne historique `passengers` transporte
    # désormais la métrique canonique Eurostat MIO_PKM.
    passenger_metric: str = PASSENGER_METRIC
    passenger_unit: str = PASSENGER_UNIT


class TimelineData(BaseSchema):
    year: int
    passengers: Optional[float] = None
    co2_emissions: Optional[float] = None
    co2_per_passenger: Optional[float] = None
    total_trains_count: int = 0
    night_trains_count: int = 0
    day_trains_count: int = 0
    passenger_metric: str = PASSENGER_METRIC
    passenger_unit: str = PASSENGER_UNIT


class CO2RankingItem(BaseSchema):
    country_name: str
    country_code: str
    avg_co2_per_passenger: float
    ranking: int
    performance: str


class TrainTypeComparison(BaseSchema):
    train_type: str
    avg_passengers: float
    avg_distance: float
    avg_co2_per_passenger: float
    efficiency_score: float
