"""
Run ML complet ObRail
=====================

Ce script orchestre :

1. Construction des datasets multi-horizon
2. Entraînement du système de production N+1 / N+2 / N+3
3. Génération des benchmarks / preuves historiques
4. Validation finale des artefacts de production

Commande :

    python -m ia.src.ml.run_full_ml


IMPORTANT
---------

Le pipeline de production reste celui défini dans :

    run_training.py
        -> train_forecasting.py

Les benchmarks n'interviennent PAS dans les prédictions utilisées par l'API.

Ils sont générés uniquement pour :
- comparaison de modèles ;
- preuves de démarche ML ;
- mémoire / soutenance ;
- notebooks EDA / évaluation / explicabilité.
"""

from __future__ import annotations

from .run_benchmarks import main as run_benchmarks
from .run_pipeline import run as run_pipeline
from .run_training import main as run_production_training
from .validate_artifacts import main as validate_production_artifacts


def separator(title: str) -> None:
    print("\n")
    print("#" * 80)
    print(title)
    print("#" * 80)


def main() -> None:
    separator(
        "OBRAIL — PIPELINE ML COMPLET"
    )

    print(
        "\nCe run génère à la fois :\n"
        "  - les modèles multi-horizon réellement utilisés en production ;\n"
        "  - les modèles candidats servant aux benchmarks et aux preuves."
    )

    # ------------------------------------------------------------------
    # STEP 1
    # ------------------------------------------------------------------

    separator(
        "STEP 1/5 — CONSTRUCTION DES DATASETS MULTI-HORIZON"
    )

    run_pipeline()

    # ------------------------------------------------------------------
    # STEP 2
    # ------------------------------------------------------------------

    separator(
        "STEP 2/5 — ENTRAÎNEMENT PRODUCTION MULTI-HORIZON"
    )

    run_production_training()

    # ------------------------------------------------------------------
    # STEP 3
    # ------------------------------------------------------------------

    separator(
        "STEP 3/5 — VALIDATION PRODUCTION AVANT BENCHMARK"
    )

    validate_production_artifacts()

    # ------------------------------------------------------------------
    # STEP 4
    # ------------------------------------------------------------------

    separator(
        "STEP 4/5 — BENCHMARKS ET ARTEFACTS DE PREUVE"
    )

    run_benchmarks()

    # ------------------------------------------------------------------
    # STEP 5
    # ------------------------------------------------------------------

    separator(
        "STEP 5/5 — VALIDATION FINALE DE LA PRODUCTION"
    )

    # Les benchmarks ne doivent en aucun cas casser ou remplacer
    # les artefacts forecast_* utilisés par la production.
    validate_production_artifacts()

    # ------------------------------------------------------------------
    # FIN
    # ------------------------------------------------------------------

    separator(
        "PIPELINE ML COMPLET TERMINÉ"
    )

    print(
        "\nRésultat attendu :\n"
        "\n"
        "Production :\n"
        "  ia/models/forecast_classifier.joblib\n"
        "  ia/models/forecast_regressor.joblib\n"
        "  ia/models/forecast_manifest.json\n"
        "\n"
        "Benchmarks classification :\n"
        "  logistic_clf.*\n"
        "  random_forest_clf.*\n"
        "  xgboost_clf.*\n"
        "  mlp_clf.*\n"
        "  xgboost_optimized_clf.*\n"
        "\n"
        "Benchmarks régression :\n"
        "  ridge_reg.*\n"
        "  random_forest_reg.*\n"
        "  xgboost_reg.*\n"
        "  ridge_optimized_reg.*\n"
        "  xgboost_optimized_reg.*\n"
        "\n"
        "Rapports :\n"
        "  ia/reports/comparison_classification.csv\n"
        "  ia/reports/comparison_regression.csv\n"
        "\n"
        "Les notebooks peuvent maintenant être exécutés."
    )


if __name__ == "__main__":
    main()