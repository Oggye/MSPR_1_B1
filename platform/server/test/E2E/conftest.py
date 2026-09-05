import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# parents[0] = E2E/, parents[1] = test/, parents[2] = server/
SERVER_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SERVER_DIR))

from app.dependencies import get_db
from app.main import app
from app.models import (
    Base,
    DimCountries,
    DimOperators,
    DimYears,
    FactsCountryStats,
    FactsNightTrains,
)
from app.security import require_admin, require_user


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    previous_override = app.dependency_overrides.get(get_db)
    previous_user = app.dependency_overrides.get(require_user)
    previous_admin = app.dependency_overrides.get(require_admin)
    app.dependency_overrides[get_db] = override_get_db
    user = SimpleNamespace(id=1, email="admin@test.invalid", role="admin", is_active=True)
    app.dependency_overrides[require_user] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
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
    years = []
    for year in range(2010, 2025):
        year_obj = DimYears(year_id=year - 2009, year=year, is_after_2010=True)
        years.append(year_obj)
        db_session.add(year_obj)

    countries = [
        DimCountries(country_id=1, country_code="FR", country_name="France"),
        DimCountries(country_id=2, country_code="DE", country_name="Germany"),
        DimCountries(country_id=3, country_code="IT", country_name="Italy"),
        DimCountries(country_id=4, country_code="ES", country_name="Spain"),
        DimCountries(country_id=5, country_code="BE", country_name="Belgium"),
    ]
    db_session.add_all(countries)

    operators = [
        DimOperators(operator_id=1, operator_name="SNCF"),
        DimOperators(operator_id=2, operator_name="DB"),
        DimOperators(operator_id=3, operator_name="Trenitalia"),
        DimOperators(operator_id=4, operator_name="Renfe"),
        DimOperators(operator_id=5, operator_name="OBB"),
    ]
    db_session.add_all(operators)

    stats = [
        FactsCountryStats(
            stat_id=1,
            country_id=1,
            year_id=1,
            passengers=100000.0,
            co2_emissions=5000.0,
            co2_per_passenger=0.05,
        ),
        FactsCountryStats(
            stat_id=2,
            country_id=1,
            year_id=2,
            passengers=110000.0,
            co2_emissions=5200.0,
            co2_per_passenger=0.047,
        ),
        FactsCountryStats(
            stat_id=3,
            country_id=2,
            year_id=1,
            passengers=200000.0,
            co2_emissions=8000.0,
            co2_per_passenger=0.04,
        ),
    ]
    db_session.add_all(stats)

    night_trains = []
    for train_id in range(1, 26):
        train = FactsNightTrains(
            fact_id=train_id,
            country_id=(train_id % 5) + 1,
            operator_id=(train_id % 5) + 1,
            year_id=1,  # 2010
            route_id=f"ROUTE-{train_id}",
            night_train=f"Train-{train_id}",
            is_night=(train_id % 2 == 0),
            distance_km=500.0 + train_id * 20,
            duration_min=300.0 + train_id * 10,
        )
        night_trains.append(train)
        db_session.add(train)

    db_session.commit()

    return {
        "years": years,
        "countries": countries,
        "operators": operators,
        "stats": stats,
        "night_trains": night_trains,
    }
