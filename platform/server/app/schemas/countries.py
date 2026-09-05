# app/schemas/countries.py
from pydantic import BaseModel
from typing import Optional
from .base import BaseSchema


class CountryBase(BaseSchema):
    """Schéma de base pour un pays."""
    country_code: str
    country_name: str


class CountryCreate(CountryBase):
    """Schéma pour la création d'un nouveau pays."""
    pass


class CountryResponse(CountryBase):
    """Schéma de réponse pour un pays."""
    country_id: int


class CountryStatsBase(BaseSchema):
    """Schéma de base pour les statistiques par pays."""
    passengers: float
    co2_emissions: float
    co2_per_passenger: float
    year: Optional[int] = None


class CountryStatsResponse(CountryStatsBase):
    """Schéma de réponse pour les statistiques par pays."""
    stats_id: int
    country_name: str
    country_code: str
    country_id: int
    year_id: int


class CountryStatsFilter(BaseModel):
    """Schéma pour filtrer les requêtes de statistiques pays."""
    country_code: Optional[str] = None
    year: Optional[int] = None
    min_passengers: Optional[float] = None
    max_passengers: Optional[float] = None
    min_co2_per_passenger: Optional[float] = None
    max_co2_per_passenger: Optional[float] = None
