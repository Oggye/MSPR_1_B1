from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from prometheus_client import generate_latest

from app import model_monitoring
from app.routers import predict


def _sample_value(collector, sample_name, labels):
    for metric in collector.collect():
        for sample in metric.samples:
            if sample.name == sample_name and sample.labels == labels:
                return sample.value
    return 0.0


@pytest.fixture
def prediction_dependencies(monkeypatch):
    country = SimpleNamespace(
        country_id=1,
        country_code="FR",
        country_name="France",
    )
    context = predict.ForecastContext(
        origin_year=2024,
        target_year=2025,
        horizon=1,
        passengers_current=100.0,
        passengers_previous=95.0,
        passenger_growth_1y_pct=5.26,
        co2_current=10.0,
        co2_previous=11.0,
        co2_growth_1y_pct=-9.09,
        train_count_current=20,
        night_share_current=0.5,
        real_share_current=1.0,
        avg_distance_current=450.0,
        avg_duration_current=300.0,
        operator_count_current=3,
        network_data_available=True,
    )

    monkeypatch.setattr(predict, "_resolve_country", lambda db, name: country)
    monkeypatch.setattr(
        predict,
        "_load_forecast_context",
        lambda db, resolved_country, year: context.model_copy(
            update={"target_year": year, "horizon": year - 2024}
        ),
    )
    monkeypatch.setattr(predict, "_quality_warnings", lambda code, year: [])
    monkeypatch.setattr(
        predict,
        "_metadata",
        lambda axis: predict.ModelMetadata(
            model_name="test-model",
            model_type=axis,
            training_date="2026-01-01",
            axis=axis,
            metrics={},
        ),
    )
    monkeypatch.setattr(
        predict,
        "_manifest",
        lambda: {
            "regression": {
                "selected_baseline": "persistence",
                "blend_weight_ml": 0.7,
            }
        },
    )


def test_successful_classification_records_runtime_metrics(
    monkeypatch,
    prediction_dependencies,
):
    labels = {"task": "classification", "status": "success", "horizon": "1"}
    result_labels = {"label": "Baisse probable", "horizon": "1"}
    histogram_labels = {"task": "classification", "horizon": "1"}
    before_predictions = _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    )
    before_results = _sample_value(
        model_monitoring.AI_CLASSIFICATION_RESULTS_TOTAL,
        "obrail_ai_classification_results_total",
        result_labels,
    )
    before_latency = _sample_value(
        model_monitoring.AI_INFERENCE_SECONDS,
        "obrail_ai_inference_seconds_count",
        histogram_labels,
    )
    monkeypatch.setattr(
        predict,
        "ml_predict",
        lambda **kwargs: {
            "classification": {
                "prediction": 1,
                "label": "Baisse probable",
                "probability_decline": 0.8,
            }
        },
    )

    response = predict.predict_classification(
        predict.PredictionInput(country="France", year=2025),
        db=object(),
    )

    assert response.label == "Baisse probable"
    assert response.inference_ms >= 0
    assert _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    ) == before_predictions + 1
    assert _sample_value(
        model_monitoring.AI_CLASSIFICATION_RESULTS_TOTAL,
        "obrail_ai_classification_results_total",
        result_labels,
    ) == before_results + 1
    assert _sample_value(
        model_monitoring.AI_INFERENCE_SECONDS,
        "obrail_ai_inference_seconds_count",
        histogram_labels,
    ) == before_latency + 1


def test_successful_regression_records_runtime_metrics(
    monkeypatch,
    prediction_dependencies,
):
    labels = {"task": "regression", "status": "success", "horizon": "2"}
    result_labels = {"trend": "Croissance", "horizon": "2"}
    before_predictions = _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    )
    before_results = _sample_value(
        model_monitoring.AI_REGRESSION_RESULTS_TOTAL,
        "obrail_ai_regression_results_total",
        result_labels,
    )
    monkeypatch.setattr(
        predict,
        "ml_predict",
        lambda **kwargs: {
            "regression": {
                "prediction": 110.0,
                "interval_low": 100.0,
                "interval_high": 120.0,
                "interval_level": 0.9,
            }
        },
    )

    response = predict.predict_regression(
        predict.PredictionInput(country="France", year=2026),
        db=object(),
    )

    assert response.trend_label == "Croissance"
    assert _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    ) == before_predictions + 1
    assert _sample_value(
        model_monitoring.AI_REGRESSION_RESULTS_TOTAL,
        "obrail_ai_regression_results_total",
        result_labels,
    ) == before_results + 1


def test_ml_predict_error_is_counted(monkeypatch, prediction_dependencies):
    labels = {"task": "classification", "status": "error", "horizon": "1"}
    before_errors = _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    )

    def fail_prediction(**kwargs):
        raise RuntimeError("model failure")

    monkeypatch.setattr(predict, "ml_predict", fail_prediction)

    with pytest.raises(HTTPException) as error:
        predict.predict_classification(
            predict.PredictionInput(country="France", year=2025),
            db=object(),
        )

    assert error.value.status_code == 500
    assert _sample_value(
        model_monitoring.AI_PREDICTIONS_TOTAL,
        "obrail_ai_predictions_total",
        labels,
    ) == before_errors + 1


def test_custom_metrics_are_exposed_by_prometheus_registry():
    model_monitoring.record_inference_success(
        "classification",
        3,
        12.5,
        "Croissance / stabilité probable",
    )
    model_monitoring.record_inference_success(
        "regression",
        3,
        10.0,
        "Stable",
    )

    metrics = generate_latest()

    assert b"obrail_ai_predictions_total" in metrics
    assert b"obrail_ai_inference_seconds_bucket" in metrics
    assert b"obrail_ai_classification_results_total" in metrics
    assert b"obrail_ai_regression_results_total" in metrics
