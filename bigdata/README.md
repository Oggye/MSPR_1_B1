# Démonstration C2 Big Data — ObRail Europe

## Objectif

Cette brique démontre un traitement Big Data complémentaire sur les fichiers GTFS bruts déjà produits par ObRail. PostgreSQL reste la base opérationnelle et l'ETL, l'IA, l'API, le frontend et le monitoring restent inchangés.

Le dataset final destiné au machine learning étant plus compact, Spark est volontairement appliqué aux fichiers GTFS bruts, notamment `stop_times.csv`, qui représentent le volume le plus important. Le job détecte les sources disponibles parmi FR, DE, CH, ES et LU, ajoute la colonne `country`, crée quatre vues temporaires et exécute les analyses avec Spark SQL.

Les sources `data/raw/` sont montées en lecture seule. Seul le répertoire ignoré `data/bigdata/` reçoit des fichiers générés.

## Architecture

```text
                    ┌── ETL → PostgreSQL → IA → API → Front
Sources GTFS ───────┤
                    └── PySpark → Spark SQL → Parquet
```

Spark est un traitement local, ponctuel et totalement optionnel. Il ne dépend d'aucun service du Compose principal et aucun service existant ne dépend de lui.
Le Compose dédié utilise l'image Apache Software Foundation épinglée `apache/spark:3.5.9-python3`.

## Données utilisées

Chaque pays n'est chargé que si les quatre fichiers suivants sont présents et possèdent les colonnes nécessaires :

- `stop_times.csv`
- `trips.csv`
- `routes.csv`
- `stops.csv`

Un pays incomplet produit un avertissement puis est ignoré. L'absence de toute source exploitable termine le job avec un code non nul.

## Lancement

Le pipeline principal conserve sa commande habituelle :

```bash
docker compose up --build
```

La démonstration Big Data se lance séparément :

```bash
docker compose -f docker-compose.bigdata.yml run --rm spark-bigdata
```

Pour un test rapide limité à plusieurs pays, sans changer le comportement par défaut :

```bash
docker compose -f docker-compose.bigdata.yml run --rm -e GTFS_COUNTRIES=DE,ES spark-bigdata
```

Les résultats sont écrits en Parquet dans `data/bigdata/gtfs_metrics/`, partitionnés sous la forme `country=XX/`. Le mode `overwrite` ne concerne que ce répertoire de sortie.

## Requêtes Spark SQL

Le script exécute trois appels réels à `spark.sql()` :

1. volume d'événements d'arrêt et nombre de trajets distincts par pays ;
2. nombre d'arrêts par trajet, avec affichage des vingt trajets les plus longs ;
3. activité par route avec jointure `trips + stop_times + routes`, agrégation et comptage distinct.

Les jointures utilisent toujours les clés composées `country + trip_id` et `country + route_id` afin d'éviter les collisions d'identifiants entre pays.

## Validation de la compétence C2

La démonstration couvre les deux familles demandées :

```text
SGBD relationnel → PostgreSQL → SQL
Système Big Data → Apache Spark → PySpark → Spark SQL
```

Spark SQL met concrètement en œuvre `SELECT`, `JOIN`, `GROUP BY`, `COUNT`, `COUNT DISTINCT` et `ORDER BY` sur des données ferroviaires GTFS multi-pays. Le résultat agrégé est stocké dans un format colonne Parquet partitionné par pays.

Le fichier `postgres_queries.sql` contient trois requêtes de lecture sur les tables et vues existantes, sans JDBC et sans modification du schéma.

## Limites volontaires

- exécution Spark locale, sans cluster artificiel ;
- aucun Spark Streaming, Hadoop, HDFS, Kafka ou orchestrateur supplémentaire ;
- aucune connexion JDBC entre Spark et PostgreSQL ;
- aucune intégration Spark MLlib, API, interface React ou supervision Spark ;
- aucune modification ou suppression des données GTFS sources.
