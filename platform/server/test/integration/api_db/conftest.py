"""
Configuration partagée pour les tests unitaires de l'API ObRail 
"""
# Note: Ce fichier est utilisé pour configurer les fixtures et les dépendances partagées entre les tests.
import sys
from types import SimpleNamespace
from pathlib import Path

# Ajouter le chemin pour accéder à app/ depuis test/
BASE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE_DIR))


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base
from app.models import (
    DimCountries, DimYears, DimOperators,
    FactsCountryStats, FactsNightTrains, DashboardMetrics, OperatorDashboard
)
from app.security import require_admin, require_user

# Configuration de la base de données de test
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    """Override de la dépendance get_db pour utiliser la DB de test"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
def test_engine():
    """Moteur de base de données de test"""
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """Session de base de données pour chaque test"""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client():
    """Client authentifié pour préserver les tests métier existants."""
    previous_user = app.dependency_overrides.get(require_user)
    previous_admin = app.dependency_overrides.get(require_admin)
    user = SimpleNamespace(id=1, email="admin@test.invalid", role="admin", is_active=True)
    app.dependency_overrides[require_user] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_user is None:
            app.dependency_overrides.pop(require_user, None)
        else:
            app.dependency_overrides[require_user] = previous_user
        if previous_admin is None:
            app.dependency_overrides.pop(require_admin, None)
        else:
            app.dependency_overrides[require_admin] = previous_admin

@pytest.fixture(scope="function")
def sample_data(db_session):
    """Données d'exemple pour les tests"""
    # Création des années
    years = []
    for year in range(2010, 2025):
        year_obj = DimYears(year_id=year-2009, year=year, is_after_2010=(year >= 2010))
        years.append(year_obj)
        db_session.add(year_obj)

    # Création des pays
    countries = [
        DimCountries(country_id=1, country_code="FR", country_name="France"),
        DimCountries(country_id=2, country_code="DE", country_name="Germany"),
        DimCountries(country_id=3, country_code="IT", country_name="Italy"),
        DimCountries(country_id=4, country_code="ES", country_name="Spain"),
        DimCountries(country_id=5, country_code="BE", country_name="Belgium"),
    ]
    for country in countries:
        db_session.add(country)

    # Création des opérateurs
    operators = [
        DimOperators(operator_id=1, operator_name="SNCF"),
        DimOperators(operator_id=2, operator_name="DB"),
        DimOperators(operator_id=3, operator_name="Trenitalia"),
        DimOperators(operator_id=4, operator_name="Renfe"),
        DimOperators(operator_id=5, operator_name="ÖBB"),
    ]
    for operator in operators:
        db_session.add(operator)

    # Création des statistiques pays
    stats = [
        FactsCountryStats(
            stat_id=1, country_id=1, year_id=1,
            passengers=100000.0, co2_emissions=5000.0, co2_per_passenger=0.05
        ),
        FactsCountryStats(
            stat_id=2, country_id=1, year_id=2,
            passengers=110000.0, co2_emissions=5200.0, co2_per_passenger=0.047
        ),
        FactsCountryStats(
            stat_id=3, country_id=2, year_id=1,
            passengers=200000.0, co2_emissions=8000.0, co2_per_passenger=0.04
        ),
    ]
    for stat in stats:
        db_session.add(stat)



    # Création automatique de 25 trains
    night_trains = []

    for i in range(1, 26):

        train = FactsNightTrains(
            fact_id=i,

            # Répartition entre les pays 1 à 5
            country_id=(i % 5) + 1,

             # Répartition entre les opérateurs 1 à 5
            operator_id=(i % 5) + 1,

            year_id=1,

            # Identifiant unique de route
            route_id=f"ROUTE-{i}",

            # Nom du train
            night_train=f"Train-{i}",

            # Un train sur deux = train de nuit
            is_night=(i % 2 == 0),

            # Distances différentes
            distance_km=500.0 + (i * 20),

            # Durées différentes
            duration_min=300.0 + (i * 10)
        
        )

        night_trains.append(train)
        db_session.add(train)



    # Création des données operator_dashboard (vue)
    operator_dashboards = [
        OperatorDashboard(
            operator_id=1, operator_name="SNCF",
            nb_trains=1, nb_trains_nuit=1, nb_trains_jour=0,
            distance_totale_km=1000.0, duree_moyenne_min=480.0
        ),
        OperatorDashboard(
            operator_id=2, operator_name="DB",
            nb_trains=1, nb_trains_nuit=1, nb_trains_jour=0,
            distance_totale_km=600.0, duree_moyenne_min=300.0
        ),
    ]
    for dashboard in operator_dashboards:
        db_session.add(dashboard)

    db_session.commit()

    return {
        "years": years,
        "countries": countries,
        "operators": operators,
        "stats": stats,
        "night_trains": night_trains,
        "operator_dashboards": operator_dashboards
    }
