from typing import List, Optional

from pydantic import BaseModel

from .base import BaseSchema


class NightTrainBase(BaseSchema):
    """Contrat commun d'un trajet ferroviaire."""

    route_id: str
    train: str
    # Alias legacy conservé pour le frontend historique.
    night_train: Optional[str] = None


class NightTrainCreate(NightTrainBase):
    country_id: int
    year_id: int
    operator_id: int
    is_night: bool = False
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    is_synthetic: bool = False
    data_source: str = "unknown"


class NightTrainResponse(NightTrainBase):
    fact_id: int
    country_name: str
    country_code: str
    operator_name: str
    year: int
    is_night: bool
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    is_synthetic: bool = False
    data_source: str = "unknown"
    train_type: str


class NightTrainFilter(BaseModel):
    country_code: Optional[str] = None
    operator_id: Optional[int] = None
    year: Optional[int] = None
    operator_name: Optional[str] = None
    is_night: Optional[bool] = None
    is_synthetic: Optional[bool] = None
    data_source: Optional[str] = None


class NightTrainSummary(BaseModel):
    total_trains: int
    total_night_trains: int
    total_day_trains: int
    total_real_trains: int
    total_synthetic_trains: int


class CountrySliceSummary(BaseModel):
    country_name: str
    country_code: str
    total_filtered: int
    slice_trains: int
    slice_percent: float
    night_trains: int
    day_trains: int
    real_trains: int
    synthetic_trains: int
    avg_distance_km: Optional[float] = None
    avg_duration_min: Optional[float] = None


class StratifiedTrainPage(BaseModel):
    """
    Une tranche analytique stable.

    Les agrégats sont calculés sur toutes les lignes de la tranche.
    `items` ne contient qu'un petit aperçu représentatif par pays afin
    d'éviter d'envoyer plusieurs dizaines de milliers de lignes au navigateur.
    """

    slice_page: int
    page_count: int = 10
    target_slice_percent: float = 10.0

    total_filtered: int
    slice_total: int
    actual_slice_percent: float

    countries_filtered: int
    countries_covered: int

    total_night_trains: int
    total_day_trains: int
    total_real_trains: int
    total_synthetic_trains: int

    avg_distance_km: Optional[float] = None
    avg_duration_min: Optional[float] = None

    sample_per_country: int
    items_returned: int

    by_country: List[CountrySliceSummary]
    items: List[NightTrainResponse]


class TrainFacets(BaseModel):
    years: List[int]
    data_sources: List[str]
    page_count: int = 10
