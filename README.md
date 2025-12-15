# Projet MSPR – ObRail Europe

## 🎯 Contexte du projet

Ce projet s’inscrit dans le cadre de la **MSPR – Bloc E6.1** du programme *Développeur en Intelligence Artificielle et Data Science (RNCP36581)*.

Le client fictif **ObRail Europe** est un observatoire indépendant spécialisé dans l’analyse des dessertes ferroviaires européennes (trains de jour et trains de nuit). L’objectif est de mettre en place **un processus ETL automatisé**, fiable et reproductible, permettant de centraliser des données ferroviaires hétérogènes afin de les exploiter via **une base de données, une API REST et un tableau de bord analytique**.

---

## 🧠 Objectifs principaux

* Centraliser des données issues de plusieurs sources open data européennes
* Nettoyer, harmoniser et fiabiliser les données
* Concevoir un **entrepôt de données relationnel**
* Exposer les données via une **API REST documentée**
* Proposer un **dashboard de suivi et d’analyse**
* Respecter les principes RGPD, de traçabilité et de documentation

---

## 🔗 Sources de données utilisées

* **transport.data.gouv.fr** – Données GTFS France
* **mobilitydatabase.org** – GTFS Europe
* **back-on-track.eu** – Données sur les trains de nuit européens
* **transit.land** – API internationale de transport
* **Eurostat** – Données environnementales et pays

---

## 🛠️ Technologies utilisées

* **Langage principal** : Python
* **ETL & Data processing** : pandas, requests
* **Base de données** : PostgreSQL / SQL
* **API REST** : FastAPI (ou Node.js possible)
* **Dashboard** : Streamlit
* **Conteneurisation** : Docker & Docker Compose

---

## 👥 Organisation de l’équipe

### Djamil

* Recherche et sélection des sources de données
* Scripts d’extraction automatisée
* Mise en place de l’architecture Docker

### Nafissa

* Nettoyage et préparation des données
* Construction de la base de données
* Chargement des données (Load du ETL)

### Mariam

* Transformation des données
* Conception du **Modèle Conceptuel de Données (MCD)**
* Création du **Modèle Physique de Données (MPD)**

### Travail collectif

* Développement de l’API REST
* Conception du dashboard
* Définition et suivi des KPI
* Documentation et soutenance

---

## 📂 Arborescence du projet

```
project-root/
│
├── docker-compose.yml        # Orchestration globale des services
├── .env                     # Variables d’environnement
├── README.md
│
├── data/
│   ├── raw/                 # Données brutes (non modifiées)
│   ├── processed/           # Données nettoyées et transformées
│   └── warehouse/           # Données finales prêtes pour la BDD
│
├── etl/
│   ├── extract/             # Scripts d’extraction des sources
│   ├── transform/           # Nettoyage & harmonisation
│   ├── load/                # Chargement PostgreSQL
│   └── main_etl.py          # Pipeline ETL complet
│
├── platform/
│   ├── server/              # API REST
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   └── routes/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── front/               # Dashboard Streamlit
│       ├── app.py
│       ├── Dockerfile
│       └── requirements.txt
│
├── sql/
│   └── 01_init.sql           # Création des tables PostgreSQL
│
└── docs/
    ├── architecture.png
    ├── mcd.png
    ├── mpd.png
    └── rapport_technique.md
```

---

## 🔄 Fonctionnement global du projet (Pipeline complet)

Le projet suit strictement la chaîne de traitement suivante :

### **Source → Extraction → Affichage brut → Nettoyage → Harmonisation → Stockage**

### 1️⃣ Choix des données

Les sources open data sont sélectionnées selon leur pertinence (couverture géographique, fiabilité, format).

### 2️⃣ Extraction

Les scripts du dossier `etl/extract/` récupèrent les données :

* Téléchargement de fichiers GTFS (ZIP → CSV)
* Appels API (Transit.land, Eurostat)
* Lecture de fichiers CSV / Excel

Les données sont stockées dans `data/raw/`.

### 3️⃣ Affichage brut

Chaque extraction affiche :

* aperçu des données (`head()`)
* schéma (`info()`)
* valeurs manquantes

Cette étape permet de comprendre la structure avant traitement.

### 4️⃣ Nettoyage

Dans `etl/transform/` :

* suppression des doublons
* gestion des valeurs manquantes
* correction des formats (dates, pays, codes gares)

Les données passent dans `data/processed/`.

### 5️⃣ Harmonisation

* Normalisation des référentiels (pays, gares, opérateurs)
* Fusion des sources hétérogènes
* Séparation trains de jour / trains de nuit

### 6️⃣ Stockage

Le script `etl/load/load_postgres.py` :

* se connecte à PostgreSQL
* crée les tables (via `01_init.sql`)
* charge les données finales depuis `data/warehouse/`

---

## 🗄️ Base de données

* SGBD : PostgreSQL
* Modélisation : MCD + MPD (dans `/docs`)
* Tables principales : trains, gares, opérateurs, pays, horaires

---

## 🌐 API REST

* Développée avec FastAPI
* Expose les données via des endpoints REST
* Filtres : type de train, pays, opérateur, villes
* Documentation automatique (Swagger)

---

## 📊 Dashboard

* Réalisé avec Streamlit
* Indicateurs clés :

  * Nombre de trajets jour / nuit
  * Répartition par pays
  * Taux de complétude des données
  * Volume de données par source

---

## 🚀 Lancer le projet

### Prérequis

* Docker
* Docker Compose

### Démarrage

```bash
docker-compose up --build
```

### Accès aux services

* PostgreSQL : `localhost:5432`
* API REST : `http://localhost:8000/docs`
* Dashboard : `http://localhost:8501`

---

## 📌 Tâches couvertes par le projet

1. Choix des données
2. Mise en place Docker
3. Conception MCD / MPD
4. ETL complet
5. Base de données
6. API REST
7. Dashboard
8. Documentation technique

---

## 🏁 Conclusion

Ce projet fournit à ObRail Europe un **entrepôt de données fiable, documenté et évolutif**, prêt à être exploité pour des analyses avancées, des modèles d’IA et des décisions stratégiques liées à la mobilité durable en Europe.
