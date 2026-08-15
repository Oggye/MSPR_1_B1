# app/schemas/trains.py
from typing import Optional

from pydantic import BaseModel

from .base import BaseSchema


class NightTrainBase(BaseSchema):
    """
    Contrat commun d'un trajet.

    `train` est le champ canonique.
    `night_train` est conservé dans les réponses pendant la transition afin de
    ne pas casser le frontend existant.
    """

    route_id: str
    train: str
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
