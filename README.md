# ObRail Europe — Pipeline ML de prédiction ferroviaire

**MSPR — Bloc E6.2 / E6.4 — RNCP36581**  
Programme : Développeur en Intelligence Artificielle et Data Science

ObRail Europe est un observatoire indépendant spécialisé dans l'analyse des flux ferroviaires européens. Ce projet développe un pipeline ML complet pour anticiper l'évolution de la fréquentation ferroviaire et détecter automatiquement les réseaux en fragilisation.

**Deux modèles en production :**
- **Classifieur XGBoost** — détection des pays en déclin ferroviaire (F1 = 0,667 / ROC-AUC = 0,826)
- **Régresseur Ridge** — prévision du volume de passagers (R² = 0,9962 / MAE = 4 339 k passagers)

---

## Documentation

| Document | Contenu |
|----------|---------|
| [`docs/ia/rapport_technique.md`](docs/ia/rapport_technique.md) | Rapport technique complet — architecture, modèles, incident data leakage, conformité |
| [`docs/ia/`](docs/ia/) | Mini-rapports par phase (EDA, preprocessing, entraînement, optimisation, explicabilité, API) |
| [`docs/ia/benchmark_cloud.md`](docs/ia/benchmark_cloud.md) | Comparaison SageMaker / Azure ML / Vertex AI / HuggingFace |
| [`docs/ia/veille.md`](docs/ia/veille.md) | Veille algorithmique, réglementaire et sécurité (sources 2026) |
| [`docs/ia/retraining.md`](docs/ia/phase/retraining.md) | Procédure de réentraînement des modèles |
| [`docs/ia/incident_data_leakage.md`](docs/ia/rapport%20de%20réorientation.md) | Chronologie et résolution de l'incident data leakage |

---

## Démarrage rapide

### Prérequis

- Docker et Docker Compose V2
- Git

```bash
git clone https://github.com/Oggye/MSPR_1_B3
cd MSPR_1_B3
docker compose up --build
```

La commande exécute automatiquement l'intégralité de la chaîne :

```
db (PostgreSQL) → etl (harmonisation données) → ia (entraînement ML) → api (FastAPI) → front (React)
```

Aucune intervention manuelle n'est nécessaire. L'API ne démarre jamais sans modèles disponibles.

---

## Services et URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend React | `http://localhost:3000` | Interface de prédiction |
| API FastAPI | `http://localhost:8000` | Endpoints de prédiction |
| Documentation Swagger | `http://localhost:8000/api/docs` | Tests interactifs des routes |
| Grafana | `http://localhost:3001` | Dashboards de monitoring |
| Prometheus | `http://localhost:9090` | Métriques |
| PostgreSQL | `localhost:5432` | Entrepôt de données |

---

## Routes API

```
POST /api/predict/classification   →  Détection déclin ferroviaire (XGBoost)
POST /api/predict/regression       →  Prévision volume passagers (Ridge)
GET  /health                       →  Health check
GET  /api/docs                     →  Swagger UI
```

Exemple de requête classification :

```json
{
  "country": "France",
  "year": 2024,
  "co2_emissions": 24800.0,
  "co2_per_passenger": 1.75,
  "co2_lag1": 25100.0,
  "passengers_lag1": 88000.0,
  "passengers_lag2": 86500.0
}
```

---

## Structure du projet

```
MSPR_1_B3/
├── docker-compose.yml
├── .env                          # Non versionné — credentials DB
│
├── etl/                          # Pipeline ETL Eurostat / ADEME
│
├── ia/                           # Chaîne ML complète
│   └── src/ml/
│       ├── build_dataset.py      # Construction datasets + feature engineering
│       ├── run_training.py       # Entraînement des 7 modèles candidats
│       ├── predict.py            # Inférence CLI + cache LRU
│       ├── models/               # Scripts d'entraînement par algorithme
│       │   └── optimize_xgboost_ridge.py
│       └── notebooks/            # EDA, évaluation, explicabilité SHAP
│
├── data/
│   ├── warehouse/                # CSV harmonisés par l'ETL
│   └── ml/                       # Datasets ML et preprocesseurs .joblib
│
├── platform/
│   ├── server/                   # API FastAPI (router enrichi)
│   └── front/                    # Frontend React / Nginx
│
├── monitoring/                   # Prometheus, Grafana, Loki, Promtail
├── sql/                          # Init PostgreSQL
├── docs/                         # Rapport technique et documentation
├── tests/
│   └── test_predict.py
└── .github/workflows/ci.yml
```

---

## Stack technique

### Intelligence Artificielle

| Bibliothèque | Rôle |
|-------------|------|
| XGBoost 2.x | Classifieur de détection de déclin ferroviaire |
| Scikit-learn 1.3+ | Ridge regression, preprocessing, pipelines, RandomizedSearchCV |
| SHAP | Explicabilité des prédictions (importance des variables) |
| Joblib | Sérialisation des modèles et preprocesseurs |
| Pandas / NumPy | Manipulation des données et feature engineering |

### Backend / API

| Technologie | Rôle |
|-------------|------|
| FastAPI | API REST asynchrone, Swagger automatique |
| Pydantic V2 | Validation des entrées, schémas typés |
| PostgreSQL 15 | Entrepôt de données (schéma en étoile) |
| SQLAlchemy | ORM |

### Frontend / Infrastructure

| Technologie | Rôle |
|-------------|------|
| React 18 / Nginx | Interface utilisateur |
| Docker / Compose V2 | Conteneurisation, orchestration, reproductibilité |
| Prometheus / Grafana | Métriques et dashboards |
| Loki / Promtail | Agrégation et requête des logs |
| GitHub Actions | CI/CD |

---

## Commandes utiles

```bash
# Démarrage complet (ETL + entraînement + API + frontend)
docker compose up --build

# Logs en temps réel
docker compose logs -f

# État des services
docker compose ps

# Arrêt
docker compose down

# Arrêt + suppression des volumes
docker compose down -v

# Tests unitaires
python -m pytest tests/ -v
```

---

## Données et modèles

Les modèles sont entraînés sur **546 observations** issues d'Eurostat (42 pays européens × 13 années, 2012–2024). Les artefacts produits sont :

```
ia/models/
├── xgboost_optimized_clf.joblib      # Classifieur final
├── ridge_reg.joblib                  # Régresseur final
data/ml/
├── preprocessor_classification.joblib
└── preprocessor_regression.joblib
ia/reports/
├── comparison_classification.csv
└── comparison_regression.csv
```

---

## Monitoring

La stack de supervision est provisionnée automatiquement au démarrage. Les dashboards Grafana sont disponibles dans :

```
monitoring/grafana/dashboards/
```

Métriques surveillées : trafic et latence HTTP, erreurs API, nombre et erreurs de prédictions IA, temps d'inférence et distribution des classifications/tendances de régression. La détection automatique du data drift et l'évaluation du model drift avec de nouvelles vérités terrain restent des perspectives d'évolution.

---

## Tests

```bash
# Tests unitaires Python
python -m pytest tests/ -v

# Tests frontend E2E
cd platform/front/app
npm ci
npm run e2e:install
npm run e2e
```

---

## Conformité

| Aspect | Statut |
|--------|--------|
| RGPD | ✅ Données agrégées par pays, aucune donnée personnelle, principes finalité/minimisation/sécurité/transparence respectés |
| AI Act (UE 2024/1689) | ✅ Catégorie à risque limité — notice de conformité art. 50 à rédiger avant août 2026 |
| Reproductibilité | ✅ `random_state=42` sur tous les modèles, pipelines joblib versionnés |
| Explicabilité | ✅ SHAP sur les deux modèles finaux, importance des variables documentée |

---

## Équipe

| Membre | Phases |
|--------|--------|
| NDIAYE Mansour Djamil | 0 · 1 · 5 · 12 · 13 · 15 · 17 |
| ABDILLAHI ABDI Mariam Marwo | 6 · 7 · 16 · 17 |
| SAMB Adja Nafissatou Lo | 8 · 9 · 14 · 17 |
| NKIBAN A ITCHIRI Orlane Emmanuelle Andrea | 10 · 11 · 17 |
| TOURE Zeinab Anne Marie | 2 · 3 · 4 · 17 |

Suivi projet : [Trello MSPR B3](https://trello.com/invite/b/69e74e583f650936f382ba17/ATTIaa05d72d0f16e3a2a3827bc407c678ffA9A7D7CE/mspr-b3)

---

*Certification RNCP36581 — Bloc E6.2 / E6.4*
