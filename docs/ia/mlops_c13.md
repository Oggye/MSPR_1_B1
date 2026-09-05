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
│ ML Pipeline Validation      │
└─────────────────────────────┘
        ↓
Docker Build
        ↓
GHCR (branche main uniquement)
        ↓
Container Smoke Test
```

Le job Docker Build dépend de la réussite des tests backend, IA, frontend,
qualité et du pipeline ML réel. Le push des images vers GHCR et le smoke test
des conteneurs sont réservés aux pushs sur `main`. La branche `fix-correctif`
et les pull requests vers `main` exécutent les contrôles et le build sans
publier d'image.

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

Le job GitHub Actions `ML Pipeline Validation` réutilise Docker Compose pour
démarrer PostgreSQL, exécuter l'ETL one-shot, construire les datasets,
entraîner les modèles puis valider les artefacts. Le code de sortie du service
IA et une seconde exécution explicite de `validate_artifacts` sont bloquants.
Le job Docker Build ne peut donc s'exécuter que si cette chaîne et les autres
contrôles obligatoires ont réussi.

L'ETL télécharge ses sources externes (GTFS, Eurostat et Back on Track) pendant
ce job. La CI exécute ainsi le pipeline existant sans fixture ni modèle factice,
mais sa disponibilité et sa durée dépendent de ces sources tierces.

Sur un push `main`, les images `front`, `api`, `etl` et `ia` sont publiées dans
GHCR avec `GITHUB_TOKEN`. Le smoke test local tire ces images publiées, démarre
PostgreSQL, l'API et le frontend, puis contrôle `pg_isready`, `/health`,
`/api/docs` et la page frontend. Les services ETL et IA restent des traitements
one-shot et ne sont pas transformés en démons pour ce smoke test.

## Matrice de preuves

| Besoin MLOps | Preuve ObRail |
| --- | --- |
| Versionnement | Git / GitHub |
| Automatisation | GitHub Actions |
| Tests IA | `ia/tests/` |
| Pipeline ML en CI | job `ML Pipeline Validation` |
| Validation | `ia/src/ml/validate_artifacts.py` |
| Packaging | `ia/Dockerfile` |
| Build | GitHub Actions |
| Registry | GHCR |
| Orchestration | Docker Compose |
| Smoke test local | Docker Compose et images GHCR |
| Monitoring | Prometheus / Grafana |

## Périmètre

Le projet n'utilise volontairement ni MLflow, ni Kubeflow, ni Kubernetes, ni
continuous training, ni registre de modèles spécialisé. Ces technologies ne
sont pas nécessaires au périmètre actuel : GitHub Actions, GHCR et Docker
Compose couvrent les besoins de contrôle, de packaging et d'exécution.
Aucun déploiement distant, VPS ou cloud n'est effectué ni revendiqué par ce
workflow.
