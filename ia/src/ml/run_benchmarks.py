"""
Benchmark ML ObRail
===================

Ce module NE remplace PAS le pipeline de production multi-horizon.

Il sert uniquement à :
- entraîner les modèles candidats historiques ;
- produire les artefacts de preuve ;
- produire les métriques ;
- produire les contrats modèle/preprocessor ;
- optimiser XGBoost et Ridge ;
- générer les rapports comparatifs ;
- fournir les artefacts nécessaires aux notebooks.

Production actuelle :
    forecast_classifier.joblib
    forecast_regressor.joblib
    forecast_manifest.json

Benchmark / preuves :
    logistic_clf.*
    random_forest_clf.*
    xgboost_clf.*
    mlp_clf.*
    xgboost_optimized_clf.*

    ridge_reg.*
    random_forest_reg.*
    xgboost_reg.*
    ridge_optimized_reg.*
    xgboost_optimized_reg.*

Les anciens modèles utilisent volontairement la vue de compatibilité
horizon == 1 définie dans train_utils.py.

Le modèle de production reste, lui, directement multi-horizon N+1/N+2/N+3.
"""

from __future__ import annotations

from pathlib import Path

from .config import (
    CLASSIF_DATASET_PATH,
    MODELS_DIR,
    PREPROCESSOR_CLF_PATH,
    PREPROCESSOR_REG_PATH,
    REGRESSION_DATASET_PATH,
    REPORTS_DIR,
)

from .evaluate_model import main as generate_comparison_reports

from .models.optimize_xgboost_ridge import (
    compare_results,
    optimize_ridge_reg,
    optimize_xgboost_clf,
    optimize_xgboost_reg,
)

from .models.train_logistic import train_logistic
from .models.train_mlp import train_mlp
from .models.train_random_forest import (
    train_random_forest,
    train_random_forest_regressor,
)
from .models.train_ridge import train_ridge
from .models.train_xgboost import (
    train_xgboost,
    train_xgboost_regressor,
)


# ---------------------------------------------------------------------------
# Modèles attendus
# ---------------------------------------------------------------------------

CLASSIFICATION_MODELS = [
    "logistic",
    "random_forest",
    "xgboost",
    "mlp",
    "xgboost_optimized",
]

REGRESSION_MODELS = [
    "ridge",
    "random_forest",
    "xgboost",
    "ridge_optimized",
    "xgboost_optimized",
]


# ---------------------------------------------------------------------------
# Vérification des prérequis
# ---------------------------------------------------------------------------

def check_prerequisites() -> None:
    """
    Vérifie que les datasets multi-horizon ont déjà été générés.

    Les trainers historiques utilisent ensuite automatiquement leur vue
    de compatibilité N+1 dans train_utils.py.
    """

    missing = []

    if not CLASSIF_DATASET_PATH.exists():
        missing.append(CLASSIF_DATASET_PATH)

    if not REGRESSION_DATASET_PATH.exists():
        missing.append(REGRESSION_DATASET_PATH)

    if missing:
        message = "\n".join(
            f"  - {path}"
            for path in missing
        )

        raise FileNotFoundError(
            "Datasets ML manquants.\n"
            f"{message}\n\n"
            "Lance d'abord :\n"
            "python -m ia.src.ml.run_pipeline"
        )


# ---------------------------------------------------------------------------
# Helpers validation
# ---------------------------------------------------------------------------

def expected_model_artifacts(
    model_name: str,
    axis: str,
) -> list[Path]:
    """
    Retourne les artefacts devant être produits pour un modèle de benchmark.
    """

    return [
        MODELS_DIR / f"{model_name}_{axis}.joblib",
        MODELS_DIR / f"{model_name}_{axis}_metrics.json",
        MODELS_DIR / f"{model_name}_{axis}_preprocessor.joblib",
        MODELS_DIR / f"{model_name}_{axis}_contract.json",
    ]


def validate_benchmark_artifacts() -> None:
    """
    Vérifie que tous les artefacts nécessaires aux preuves et notebooks
    ont réellement été produits.

    Important :
    contrairement à l'ancien run_training.py, une génération partielle
    n'est pas considérée comme un succès.
    """

    expected: list[Path] = []

    # Classification
    for model_name in CLASSIFICATION_MODELS:
        expected.extend(
            expected_model_artifacts(
                model_name=model_name,
                axis="clf",
            )
        )

    # Régression
    for model_name in REGRESSION_MODELS:
        expected.extend(
            expected_model_artifacts(
                model_name=model_name,
                axis="reg",
            )
        )

    # Preprocessors partagés de compatibilité historique.
    expected.extend(
        [
            PREPROCESSOR_CLF_PATH,
            PREPROCESSOR_REG_PATH,
        ]
    )

    # Rapports comparatifs.
    expected.extend(
        [
            REPORTS_DIR / "comparison_classification.csv",
            REPORTS_DIR / "comparison_regression.csv",
        ]
    )

    missing = [
        path
        for path in expected
        if not path.exists()
    ]

    if missing:
        print("\n" + "=" * 72)
        print("ERREUR — ARTEFACTS DE BENCHMARK MANQUANTS")
        print("=" * 72)

        for path in missing:
            print(f"  - {path}")

        raise RuntimeError(
            f"{len(missing)} artefact(s) de benchmark "
            "n'ont pas été généré(s)."
        )

    print("\n" + "=" * 72)
    print("VALIDATION DES ARTEFACTS DE BENCHMARK")
    print("=" * 72)

    print(
        f"Classification : "
        f"{len(CLASSIFICATION_MODELS)} modèles"
    )

    print(
        f"Régression     : "
        f"{len(REGRESSION_MODELS)} modèles"
    )

    print(
        f"Artefacts      : "
        f"{len(expected)} fichiers vérifiés"
    )

    print("Artefacts benchmark : OK")


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def run_classification_benchmarks() -> None:
    print("\n" + "=" * 72)
    print("BENCHMARK — CLASSIFICATION")
    print("=" * 72)

    print("\n[1/4] Logistic Regression")
    train_logistic()

    print("\n[2/4] Random Forest")
    train_random_forest()

    print("\n[3/4] XGBoost")
    train_xgboost()

    print("\n[4/4] MLP")
    train_mlp()


# ---------------------------------------------------------------------------
# Régression
# ---------------------------------------------------------------------------

def run_regression_benchmarks() -> None:
    print("\n" + "=" * 72)
    print("BENCHMARK — RÉGRESSION")
    print("=" * 72)

    print("\n[1/3] Ridge")
    train_ridge()

    print("\n[2/3] Random Forest")
    train_random_forest_regressor()

    print("\n[3/3] XGBoost")
    train_xgboost_regressor()


# ---------------------------------------------------------------------------
# Optimisations
# ---------------------------------------------------------------------------

def run_optimizations() -> None:
    print("\n" + "=" * 72)
    print("OPTIMISATION DES MODÈLES")
    print("=" * 72)

    print("\n[1/3] XGBoost classification")
    optimize_xgboost_clf()

    print("\n[2/3] XGBoost régression")
    optimize_xgboost_reg()

    print("\n[3/3] Ridge régression")
    optimize_ridge_reg()

    compare_results()


# ---------------------------------------------------------------------------
# Rapports
# ---------------------------------------------------------------------------

def run_reports() -> None:
    print("\n" + "=" * 72)
    print("GÉNÉRATION DES RAPPORTS COMPARATIFS")
    print("=" * 72)

    generate_comparison_reports()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n")
    print("=" * 72)
    print("OBRAIL — BENCHMARKS ET ARTEFACTS DE PREUVE")
    print("=" * 72)

    print(
        "\nCe run est indépendant des modèles de production "
        "multi-horizon."
    )

    print(
        "Les artefacts forecast_* ne seront pas remplacés."
    )

    # ----------------------------------------------------------
    # 0. Vérification
    # ----------------------------------------------------------

    print("\nSTEP B0 — Vérification des datasets")

    check_prerequisites()

    print(f"Classification : {CLASSIF_DATASET_PATH}")
    print(f"Régression     : {REGRESSION_DATASET_PATH}")

    # ----------------------------------------------------------
    # 1. Classification
    # ----------------------------------------------------------

    print("\nSTEP B1 — Modèles candidats classification")

    run_classification_benchmarks()

    # ----------------------------------------------------------
    # 2. Régression
    # ----------------------------------------------------------

    print("\nSTEP B2 — Modèles candidats régression")

    run_regression_benchmarks()

    # ----------------------------------------------------------
    # 3. Optimisation
    # ----------------------------------------------------------

    print("\nSTEP B3 — Optimisation")

    run_optimizations()

    # ----------------------------------------------------------
    # 4. Rapports
    # ----------------------------------------------------------

    print("\nSTEP B4 — Rapports comparatifs")

    run_reports()

    # ----------------------------------------------------------
    # 5. Validation stricte
    # ----------------------------------------------------------

    print("\nSTEP B5 — Validation des preuves")

    validate_benchmark_artifacts()

    # ----------------------------------------------------------
    # Résumé
    # ----------------------------------------------------------

    print("\n" + "=" * 72)
    print("BENCHMARK OBRAIL TERMINÉ")
    print("=" * 72)

    print(f"\nModèles / preuves : {MODELS_DIR}")
    print(f"Rapports           : {REPORTS_DIR}")

    print(
        "\nLes notebooks peuvent maintenant utiliser "
        "les modèles, métriques, contrats et rapports générés."
    )


if __name__ == "__main__":
    main()