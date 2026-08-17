# C13 — Chaîne MLOps ObRail

## Objectif

La chaîne MLOps automatise les contrôles, le packaging et la livraison de
l'application ObRail et de son composant IA. Elle s'appuie sur l'architecture
existante du projet, sans plateforme MLOps supplémentaire.

## Chaîne CI/CD

```text
Git push / Pull Request
        ↓
GitHub Actions
        ↓
┌─────────────────────────────┐
│ Backend Tests               │
│ IA Tests                    │
│ Frontend E2E                │
│ Code Quality                │
└─────────────────────────────┘
        ↓
Docker Build
        ↓
GHCR (branche main uniquement)
        ↓
Container Smoke Test
```

Le job Docker Build dépend de la réussite des tests backend, IA, frontend et
qualité. Le push des images vers GHCR et le smoke test des conteneurs sont
réservés aux pushs sur `main`. La branche `fix-correctif` exécute les tests et
le build sans publier d'image.

## Pipeline IA dans Docker Compose

```text
Données préparées par l'ETL
        ↓
run_pipeline
        ↓
run_training
        ↓
forecast_classifier
forecast_regressor
forecast_manifest
        ↓
validate_artifacts
        ↓
API autorisée à démarrer
```

Le service IA produit les jeux de données, entraîne les modèles puis valide
la présence et le chargement des artefacts. Docker Compose impose l'ordre
`db → etl → ia → api → front` : l'API attend la réussite du service IA.

## Distinction entre CI et exécution IA

La CI automatise les tests, la validation du code et des imports, le build
Docker, puis sur `main` le push GHCR et le smoke test.

L'environnement Docker Compose automatise séparément l'ETL, l'entraînement
IA, la validation des artefacts et le démarrage de l'API. GitHub Actions ne
prétend donc pas réaliser un entraînement complet à chaque contrôle de branche.

## Matrice de preuves

| Besoin MLOps | Preuve ObRail |
| --- | --- |
| Versionnement | Git / GitHub |
| Automatisation | GitHub Actions |
| Tests IA | `ia/tests/` |
| Validation | `ia/src/ml/validate_artifacts.py` |
| Packaging | `ia/Dockerfile` |
| Build | GitHub Actions |
| Registry | GHCR |
| Orchestration | Docker Compose |
| Déploiement local | Docker Compose |
| Monitoring | Prometheus / Grafana |

## Périmètre

Le projet n'utilise volontairement ni MLflow, ni Kubeflow, ni Kubernetes, ni
continuous training, ni registre de modèles spécialisé. Ces technologies ne
sont pas nécessaires au périmètre actuel : GitHub Actions, GHCR et Docker
Compose couvrent les besoins de contrôle, de packaging et d'exécution.
