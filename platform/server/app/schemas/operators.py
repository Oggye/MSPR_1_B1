from typing import List, Optional

from .base import BaseSchema


class OperatorResponse(BaseSchema):
    operator_id: int
    operator_name: str


class OperatorRanking(BaseSchema):
    operator_id: int
    operator_name: str
    total_trains: int
    night_trains: int
    day_trains: int
    real_trains: int = 0
    synthetic_trains: int = 0
    distance_totale_km: float
    duree_moyenne_min: float
    avg_co2_per_passenger: Optional[float] = None
    countries_served: List[str]
    countries_count: int


class OperatorTimelineItem(BaseSchema):
    year: int
    total_trains: int
    night_trains: int
    day_trains: int
    real_trains: int
    synthetic_trains: int
