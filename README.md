# ObRail Europe

Projet MSPR de Bachelor 3 consacré à la collecte, l'analyse et la valorisation de données ferroviaires européennes.

ObRail Europe met en œuvre une chaîne complète allant de l'acquisition des données jusqu'à leur exploitation dans une application web :

```text
Sources ferroviaires
        ↓
       ETL
        ↓
   PostgreSQL
        ↓
        IA
        ↓
 FastAPI / API REST
        ↓
      React
```

La plateforme intègre également une chaîne CI/CD, des tests automatisés, une supervision Prometheus/Grafana et une démonstration Big Data avec Apache Spark.

---

## Fonctionnalités principales

* collecte et transformation de données ferroviaires européennes ;
* entrepôt PostgreSQL ;
* analyse des trains de jour et de nuit ;
* statistiques par pays et opérateur ;
* modèles IA de classification et de prévision ;
* interface web React ;
* authentification utilisateur et administrateur ;
* monitoring de l'API et des modèles IA ;
* tests automatisés et CI/CD GitHub Actions ;
* traitement Big Data avec PySpark et Spark SQL.

---

## Architecture du projet

```text
MSPR_1_B3/
├── etl/                 # Extraction, transformation et chargement
├── data/                # Données brutes, transformées et warehouse
├── ia/                  # Pipeline Machine Learning
├── platform/
│   ├── server/          # API FastAPI
│   └── front/           # Application React
├── monitoring/          # Prometheus, Grafana, Loki et Promtail
├── bigdata/             # Démonstration Apache Spark / Spark SQL
├── sql/                 # Initialisation PostgreSQL
├── docs/                # Documentation technique
├── .github/workflows/   # CI/CD GitHub Actions
└── docker-compose.yml   # Orchestration de la plateforme
```

---

# Installation

## Prérequis

* Git
* Docker
* Docker Compose V2

### 1. Récupérer le projet

Pour récupérer la version utilisée dans le cadre du mémoire :

```bash
git clone -b fix-correctif https://github.com/Oggye/MSPR_1_B3.git
cd MSPR_1_B3
```

### 2. Configurer l'environnement

Copier :

```text
.env.example
```

vers :

```text
.env
```

puis renseigner les variables nécessaires :

```env
DB_NAME=obrail
DB_USER=obrail_user
DB_PASSWORD=...
JWT_SECRET=...
ADMIN_SIGNUP_CODE=...
COOKIE_SECURE=false
ACCESS_TOKEN_EXPIRE_MINUTES=120
```

### 3. Démarrer la plateforme

```bash
docker compose up --build
```

Docker Compose exécute automatiquement la chaîne principale :

```text
PostgreSQL
    ↓
   ETL
    ↓
    IA
    ↓
FastAPI
    ↓
  React
```

L'API démarre après la préparation des données et la génération des artefacts IA nécessaires.

---

# Accès aux services

| Service                     | Adresse                        |
| --------------------------- | ------------------------------ |
| Application ObRail          | http://localhost:3000          |
| API FastAPI                 | http://localhost:8000          |
| Swagger / documentation API | http://localhost:8000/api/docs |
| Grafana                     | http://localhost:3001          |
| Prometheus                  | http://localhost:9090          |
| PostgreSQL                  | localhost:5432                 |

L'interface web donne accès aux fonctionnalités publiques, aux prédictions IA ainsi qu'à un espace interne réservé aux administrateurs.

---

# Big Data

Une démonstration Apache Spark complémentaire permet d'effectuer des traitements distribués sur les fichiers GTFS avec PySpark et Spark SQL.

Elle est volontairement indépendante de l'application principale.

```bash
docker compose -f docker-compose.bigdata.yml run --rm spark-bigdata
```

Les traitements et leur fonctionnement sont documentés dans :

  [`bigdata/README.md`](bigdata/README.md)

---

# Documentation du projet

La documentation détaillée n'est volontairement pas dupliquée dans ce README.

## ETL, API, Frontend et infrastructure

  [`docs/etl-front/`](docs/etl-front/)

Documents principaux :

* [`Rapport technique`](docs/etl-front/rapport_technique.md)
* [`Tests Backend`](docs/etl-front/tests_backend.md)
* [`Tests E2E`](docs/etl-front/E2E_tests.md)
* [`CI/CD`](docs/etl-front/ci-cd.md)
* [`Sujet MSPR`](docs/etl-front/2025-2026%20DIA-DIADS%20-%20Sujet%20MSPR%20TPRE532.pdf)

## Intelligence Artificielle

  [`docs/ia/`](docs/ia/)

Documents principaux :

* [`Rapport technique IA`](docs/ia/rapport_technique.md)
* [`Guide IA`](docs/ia/Guide.md)
* [`Monitoring IA`](docs/ia/monitoring_c11.md)
* [`MLOps`](docs/ia/mlops_c13.md)
* [`Benchmark Cloud`](docs/ia/benchmark_cloud.md)
* [`Veille technologique`](docs/ia/veille.md)
* [`Rapport de réorientation`](docs/ia/rapport%20de%20réorientation.md)

## Big Data

  [`bigdata/README.md`](bigdata/README.md)

Ce document présente l'utilisation de PySpark, Spark SQL, les requêtes réalisées et la génération de fichiers Parquet.

---

# Tests et CI/CD

Les tests couvrent plusieurs niveaux :

```text
Tests unitaires
Tests d'intégration
Tests API
Tests IA
Tests frontend E2E
```

La CI/CD est définie dans :

```text
.github/workflows/ci-cd.yml
```

GitHub Actions contrôle notamment les tests backend, les tests IA, les tests frontend, la qualité du code et la construction des images Docker.

  [GitHub Actions](https://github.com/Oggye/MSPR_1_B3/actions)

---

# Monitoring

La supervision repose sur :

* **Prometheus** pour la collecte des métriques ;
* **Grafana** pour leur visualisation et les alertes ;
* **Loki / Promtail** pour les logs.

La supervision couvre l'API ainsi que l'activité des modèles IA : prédictions, erreurs et temps d'inférence.

Documentation :

  [`docs/ia/monitoring_c11.md`](docs/ia/monitoring_c11.md)

---

# Technologies principales

`Python` · `FastAPI` · `PostgreSQL` · `React` · `Docker` · `Scikit-learn` · `XGBoost` · `PySpark` · `Prometheus` · `Grafana` · `GitHub Actions`

---

# Équipe

* Mansour Djamil NDIAYE
* Mariam Marwo ABDILLAHI ABDI
* Adja Nafissatou Lo SAMB
* Orlane Emmanuelle Andrea NKIBAN A ITCHIRI
* Zeinab Anne Marie TOURE

Suivi du projet : [Trello MSPR B3](https://trello.com/invite/b/69e74e583f650936f382ba17/ATTIaa05d72d0f16e3a2a3827bc407c678ffA9A7D7CE/mspr-b3)

---

> Ce README constitue le point d'entrée du projet. Les choix techniques, méthodes de développement, résultats, tests et justifications sont détaillés dans les rapports disponibles dans le dossier [`docs/`](docs/).
