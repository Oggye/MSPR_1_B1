"""Tests unitaires des conversions de réponses des trains."""

from types import SimpleNamespace

from app.routers.night_trains import _to_response


def test_to_response_returns_valid_object():
    train = SimpleNamespace(
        fact_id=1,
        route_id="FR001",
        night_train="Paris → Nice",
        is_night=True,
        distance_km=1200,
        duration_min=720,
    )

    response = _to_response(
        train,
        country_name="France",
        country_code="FR",
        operator_name="SNCF",
        year=2024,
    )

    assert response.fact_id == 1
    assert response.route_id == "FR001"
    assert response.night_train == "Paris → Nice"
    assert response.country_name == "France"
    assert response.country_code == "FR"
    assert response.operator_name == "SNCF"
    assert response.year == 2024
    assert response.train_type == "night"


def test_to_response_day_train():
    train = SimpleNamespace(
        fact_id=2,
        route_id="FR002",
        night_train="Paris → Lyon",
        is_night=False,
        distance_km=500,
        duration_min=120,
    )

    response = _to_response(
        train,
        country_name="France",
        country_code="FR",
        operator_name="SNCF",
        year=2024,
    )

    assert response.train_type == "day"


def test_to_response_handles_none_values():
    train = SimpleNamespace(
        fact_id=3,
        route_id="FR003",
        night_train="Test Train",
        is_night=True,
        distance_km=None,
        duration_min=None,
    )

    response = _to_response(
        train,
        country_name="France",
        country_code="FR",
        operator_name="SNCF",
        year=2024,
    )

    assert response.distance_km is None
    assert response.duration_min is None
