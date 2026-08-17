"""Métriques Prometheus runtime des prédictions IA ObRail."""

import logging

from prometheus_client import Counter, Histogram


logger = logging.getLogger("obrail.model_monitoring")

AI_PREDICTIONS_TOTAL = Counter(
    "obrail_ai_predictions_total",
    "Nombre de prédictions IA exécutées.",
    ("task", "status", "horizon"),
)

AI_INFERENCE_SECONDS = Histogram(
    "obrail_ai_inference_seconds",
    "Durée de l'appel au modèle IA en secondes.",
    ("task", "horizon"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

AI_CLASSIFICATION_RESULTS_TOTAL = Counter(
    "obrail_ai_classification_results_total",
    "Distribution des résultats du classifieur IA.",
    ("label", "horizon"),
)

AI_REGRESSION_RESULTS_TOTAL = Counter(
    "obrail_ai_regression_results_total",
    "Distribution des tendances produites par la régression IA.",
    ("trend", "horizon"),
)


def record_inference_success(task, horizon, inference_ms, result):
    """Enregistre une inférence réussie sans affecter la réponse métier."""
    try:
        horizon_label = str(horizon)
        AI_PREDICTIONS_TOTAL.labels(
            task=task,
            status="success",
            horizon=horizon_label,
        ).inc()
        AI_INFERENCE_SECONDS.labels(
            task=task,
            horizon=horizon_label,
        ).observe(inference_ms / 1000)

        if task == "classification":
            AI_CLASSIFICATION_RESULTS_TOTAL.labels(
                label=result,
                horizon=horizon_label,
            ).inc()
        elif task == "regression":
            AI_REGRESSION_RESULTS_TOTAL.labels(
                trend=result,
                horizon=horizon_label,
            ).inc()
    except Exception:
        logger.exception("Impossible d'enregistrer les métriques d'inférence")


def record_inference_error(task, horizon):
    """Enregistre un échec de l'appel au modèle sans masquer l'erreur initiale."""
    try:
        AI_PREDICTIONS_TOTAL.labels(
            task=task,
            status="error",
            horizon=str(horizon),
        ).inc()
    except Exception:
        logger.exception("Impossible d'enregistrer l'erreur d'inférence")
