from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_db
from app.routers import predict as predict_router


@pytest.fixture(autouse=True)
def clear_router_caches():
    predict_router._manifest.cache_clear()
    predict_router._quality_map.cache_clear()
    yield
    predict_router._manifest.cache_clear()
    predict_router._quality_map.cache_clear()


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(predict_router.router)
    state = {"db": MagicMock()}

    def override_db():
        yield state["db"]

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, state


def _country():
    return SimpleNamespace(country_id=1, country_code="FR", country_name="France")


def _context(target_year):
    return predict_router.ForecastContext(
        origin_year=2024,
        target_year=target_year,
        horizon=target_year - 2024,
        passengers_current=100,
        passengers_previous=90,
        passenger_growth_1y_pct=11.11,
        co2_current=50,
        co2_previous=45,
        co2_growth_1y_pct=11.11,
        train_count_current=12,
        night_share_current=0.25,
        real_share_current=0.75,
        avg_distance_current=300,
        avg_duration_current=180,
        operator_count_current=4,
        network_data_available=True,
    )


def _metadata(axis):
    return predict_router.ModelMetadata(
        model_name=f"fake-{axis}",
        model_type="direct_multi_horizon",
        training_date="2026-01-01",
        axis=axis,
        metrics={"mae": 1.0},
    )


def _prepare_success(monkeypatch):
    monkeypatch.setattr(predict_router, "_resolve_country", lambda _db, _name: _country())
    monkeypatch.setattr(
        predict_router,
        "_load_forecast_context",
        lambda _db, _country_value, target_year: _context(target_year),
    )
    monkeypatch.setattr(predict_router, "_quality_warnings", lambda *_args: [])
    monkeypatch.setattr(predict_router, "_metadata", _metadata)


def test_get_prediction_context_uses_latest_warehouse_year(api_client, monkeypatch):
    client, state = api_client
    monkeypatch.setattr(predict_router, "_year_bounds", lambda _db: (2010, 2024))
    query = MagicMock()
    query.join.return_value.group_by.return_value.having.return_value.order_by.return_value.all.return_value = [
        ("Belgium",),
        ("France",),
    ]
    state["db"].query.return_value = query

    response = client.get("/api/predict/context")

    assert response.status_code == 200
    assert response.json() == {
        "countries": ["Belgium", "France"],
        "data_min_year": 2010,
        "data_max_year": 2024,
        "forecast_origin_year": 2024,
        "target_min_year": 2025,
        "target_max_year": 2027,
        "max_horizon": 3,
        "passenger_unit": "MIO_PKM",
        "co2_unit": "MIO_T",
    }


@pytest.mark.parametrize(("target_year", "horizon"), [(2025, 1), (2027, 3)])
def test_classification_endpoint_supports_n_plus_1_and_n_plus_3(
    api_client, monkeypatch, target_year, horizon
):
    client, _ = api_client
    _prepare_success(monkeypatch)
    monkeypatch.setattr(
        predict_router,
        "ml_predict",
        lambda **_kwargs: {
            "classification": {
                "prediction": 1,
                "label": "Baisse probable",
                "probability_decline": 0.8,
            }
        },
    )

    response = client.post(
        "/api/predict/classification", json={"country": "France", "year": target_year}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "France"
    assert body["origin_year"] == 2024
    assert body["year"] == target_year
    assert body["horizon"] == horizon
    assert body["prediction"] == 1
    assert body["probability_decline"] == pytest.approx(0.8)
    assert body["decision_margin"] == pytest.approx(30)
    assert body["risk_level"] == "Critique"
    assert isinstance(body["forecast_context"], dict)
    assert body["metadata"]["axis"] == "classification"


def test_regression_endpoint_respects_response_contract(api_client, monkeypatch):
    client, _ = api_client
    _prepare_success(monkeypatch)
    monkeypatch.setattr(
        predict_router,
        "ml_predict",
        lambda **_kwargs: {
            "regression": {
                "prediction": 120.0,
                "interval_low": 110.0,
                "interval_high": 130.0,
                "interval_level": 0.9,
            }
        },
    )
    monkeypatch.setattr(
        predict_router,
        "_manifest",
        lambda: {
            "regression": {
                "selected_baseline": "linear_trend",
                "blend_weight_ml": 0.25,
            }
        },
    )

    response = client.post(
        "/api/predict/regression", json={"country": "France", "year": 2027}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "France"
    assert body["origin_year"] == 2024
    assert body["year"] == 2027
    assert body["horizon"] == 3
    assert body["prediction_raw"] == pytest.approx(120)
    assert body["prediction_low"] == pytest.approx(110)
    assert body["prediction_high"] == pytest.approx(130)
    assert body["trend_vs_origin"] == pytest.approx(20)
    assert body["trend_label"] == "Croissance"
    assert isinstance(body["forecast_context"], dict)
    assert body["metadata"]["axis"] == "regression"


def test_endpoint_rejects_horizon_above_n_plus_3(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setattr(predict_router, "_resolve_country", lambda *_args: _country())
    monkeypatch.setattr(predict_router, "_year_bounds", lambda _db: (2010, 2024))

    response = client.post(
        "/api/predict/classification", json={"country": "France", "year": 2028}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "Horizon non supporté"


def test_endpoint_rejects_unknown_country(api_client):
    client, state = api_client
    query = MagicMock()
    query.filter.return_value.first.return_value = None
    state["db"].query.return_value = query

    response = client.post(
        "/api/predict/classification", json={"country": "Atlantis", "year": 2025}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "Pays non disponible"


def test_endpoint_rejects_insufficient_history(api_client, monkeypatch):
    client, _ = api_client
    monkeypatch.setattr(predict_router, "_resolve_country", lambda *_args: _country())
    monkeypatch.setattr(predict_router, "_year_bounds", lambda _db: (2010, 2024))
    monkeypatch.setattr(predict_router, "_country_stat", lambda *_args: None)

    response = client.post(
        "/api/predict/regression", json={"country": "France", "year": 2025}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "Historique insuffisant"


@pytest.mark.parametrize("endpoint", ["classification", "regression"])
def test_missing_model_files_return_503(api_client, monkeypatch, endpoint):
    client, _ = api_client
    _prepare_success(monkeypatch)

    def missing_artifacts(**_kwargs):
        raise FileNotFoundError("forecast_manifest.json")

    monkeypatch.setattr(predict_router, "ml_predict", missing_artifacts)

    response = client.post(
        f"/api/predict/{endpoint}", json={"country": "France", "year": 2025}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "Modèle IA non disponible"


def test_forecast_does_not_use_future_passenger_values(monkeypatch):
    requested_stat_years = []
    requested_network_years = []

    monkeypatch.setattr(predict_router, "_year_bounds", lambda _db: (2010, 2024))

    def country_stat(_db, _country_id, year):
        requested_stat_years.append(year)
        return SimpleNamespace(passengers=100 if year == 2024 else 90, co2_emissions=50)

    def network_context(_db, _country_id, year):
        requested_network_years.append(year)
        return {
            "train_count_current": 0,
            "night_share_current": 0,
            "real_share_current": 0,
            "avg_distance_current": 0,
            "avg_duration_current": 0,
            "operator_count_current": 0,
            "network_data_available": False,
        }

    monkeypatch.setattr(predict_router, "_country_stat", country_stat)
    monkeypatch.setattr(predict_router, "_network_context", network_context)

    context = predict_router._load_forecast_context(MagicMock(), _country(), 2027)

    assert context.origin_year == 2024
    assert context.target_year == 2027
    assert context.horizon == 3
    assert requested_stat_years == [2024, 2023]
    assert requested_network_years == [2024]
    assert all(year <= context.origin_year for year in requested_stat_years)
