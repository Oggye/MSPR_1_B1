# Rapport de comparaison — `main` → `fix-correctif`

## 1. Périmètre de la comparaison

Ce rapport compare :

- **ancienne version :** branche `main`
- **nouvelle version :** branche `fix-correctif`

La branche `fix-correctif` est une évolution directe de `main` : elle est **13 commits en avance** et **0 commit en retard**. Elle reprend donc la base existante puis ajoute plusieurs briques fonctionnelles, des correctifs de données et une meilleure industrialisation.

L’objectif général des modifications est de renforcer le projet sans changer son architecture principale : PostgreSQL reste le stockage opérationnel, FastAPI l’API, React le frontend, Docker Compose l’orchestration, Prometheus/Grafana le monitoring et GitHub Actions la CI/CD.

---

## 2. Résumé des principaux ajouts

| Domaine | Ajout principal | Objectif |
|---|---|---|
| Sécurité | Authentification utilisateur/admin | Contrôler l’accès aux espaces externe, IA et administration |
| ETL | Nouvelles sources GTFS Espagne et Luxembourg + corrections | Étendre et fiabiliser la couverture européenne |
| IA | Nouveau pipeline de prévision multi-horizon | Produire des prédictions plus cohérentes et évaluables |
| Monitoring IA | Métriques Prometheus + dashboard Grafana + affichage admin | Superviser réellement le modèle déployé |
| Big Data | Démonstration PySpark / Spark SQL indépendante | Valider la compétence C2 sans perturber l’application |
| MLOps | Tests IA, validation d’artefacts et CI/CD renforcée | Automatiser contrôle, packaging et livraison |
| Frontend/API | Pagination, corrections UX et requêtes plus robustes | Rendre les volumes de données plus lisibles et éviter certaines requêtes coûteuses |
| Configuration | `.env.example`, secrets sortis du dépôt | Réduire le risque de versionner des identifiants sensibles |

---

# 3. Authentification et sécurisation des accès

### Ce qui a été ajouté

Une véritable couche d’authentification a été intégrée au backend et au frontend.

Principaux fichiers :

- `platform/server/app/routers/auth.py`
- `platform/server/app/security.py`
- `platform/front/app/src/auth/AuthContext.js`
- `platform/front/app/src/auth/ProtectedRoute.js`
- `platform/front/app/src/pages/auth/LoginPage.js`
- `platform/front/app/src/pages/auth/RegisterPage.js`
- `platform/front/app/src/pages/legal/LegalPage.js`
- `platform/front/app/src/services/auth.js`

Deux rôles sont gérés :

- `user`
- `admin`

### Pourquoi cet ajout

L’ancienne version exposait les interfaces sans véritable gestion de session. La nouvelle version permet de séparer :

- les pages publiques ;
- l’espace utilisateur ;
- l’espace d’administration.

### Fonctionnement

Lors de l’inscription, le mot de passe est contrôlé puis hashé. Une inscription administrateur nécessite également un code défini par `ADMIN_SIGNUP_CODE`.

Lors de la connexion, l’API génère un JWT et le place dans un cookie `HttpOnly` nommé `obrail_session`.

Le frontend utilise ensuite `ProtectedRoute` :

- `/externe` et `/ia` nécessitent un utilisateur connecté ;
- `/interne` nécessite le rôle administrateur.

Une limitation simple des tentatives de connexion est également présente : plusieurs échecs successifs sur une période courte provoquent une réponse HTTP `429`.

### Mise en place

Les secrets ne sont plus destinés à être stockés directement dans le dépôt. Le fichier `.env` a été retiré et remplacé par `.env.example` contenant uniquement les variables attendues :

`DB_*`, `JWT_SECRET`, `ADMIN_SIGNUP_CODE`, `COOKIE_SECURE`, `ACCESS_TOKEN_EXPIRE_MINUTES`.

---

# 4. Extension et fiabilisation du pipeline ETL

### Ce qui a été ajouté

Le pipeline prend maintenant en compte deux nouvelles sources GTFS :

- **Espagne** : `etl/extract/extract_gtfs_es.py`
- **Luxembourg** : `etl/extract/extract_gtfs_lu.py`

La version `main` utilisait principalement France, Allemagne et Suisse pour les GTFS. `fix-correctif` ajoute explicitement Espagne et Luxembourg dans `etl/main_etl.py`.

De nombreux fichiers de transformation ont également été corrigés :

- `transform/gtfs.py`
- `transform/eurostat.py`
- `transform/back_on_track.py`
- `transform/emissions.py`
- `transform/enrichment.py`
- `transform/dim_stops.py`
- `transform/duration.py`
- `transform/main_transform.py`

Le chargement PostgreSQL a lui aussi été simplifié/corrigé dans `etl/load/database.py` et `load_night_trains.py`.

### Pourquoi

L’objectif est double :

1. améliorer la couverture européenne ;
2. réduire les incohérences provoquées par les données hétérogènes provenant de GTFS, Eurostat et Back-on-Track.

### Fonctionnement

Le pipeline reste organisé en trois phases :

```text
Extraction
   ↓
Transformation
   ↓
Chargement PostgreSQL
```

Les nouvelles sources sont ajoutées à la phase d’extraction existante : elles ne créent donc pas un second ETL.

Les corrections de transformation harmonisent ensuite davantage les pays, arrêts, trajets, durées, statistiques, émissions et enrichissements avant le chargement dans le warehouse.

---

# 5. Refonte du pipeline IA et prévision multi-horizon

### Ce qui a été ajouté

Le changement IA le plus important est l’ajout de :

- `ia/src/ml/train_forecasting.py`
- `ia/src/ml/validate_artifacts.py`

ainsi qu’une refonte importante de :

- `build_dataset.py`
- `predict.py`
- `train_utils.py`
- les scripts d’entraînement Logistic, Ridge, Random Forest, MLP et XGBoost.

Les anciens artefacts tels que certains preprocessors et modèles optimisés versionnés ont été supprimés afin que les nouveaux artefacts soient reconstruits par le pipeline.

### Pourquoi

L’objectif est d’éviter une IA qui se contente de produire une valeur sans protocole temporel suffisamment clair.

Le nouveau pipeline structure explicitement la prévision selon plusieurs **horizons**, avec sélection et évaluation des modèles.

### Fonctionnement

Les variables numériques et le pays sont intégrés dans un pipeline Scikit-learn comprenant :

```text
Données
  ↓
ColumnTransformer
  ├─ StandardScaler
  └─ OneHotEncoder(country)
  ↓
Modèle
```

Pour la **classification**, le pipeline compare notamment Logistic Regression et XGBoost.

Pour la **régression**, il compare Ridge et XGBoost.

La validation est temporelle : les observations antérieures servent à entraîner le modèle et une année future sert à la validation. Cela évite de mélanger aléatoirement passé et futur.

La régression est également comparée à des baselines simples :

- persistance ;
- tendance linéaire.

Le système peut ensuite combiner la prédiction ML avec la meilleure baseline lorsque cela améliore la MAE.

Les artefacts finaux sont notamment :

- `forecast_classifier.joblib`
- `forecast_regressor.joblib`
- `forecast_manifest.json`

Le manifest centralise la version, les horizons, les modèles sélectionnés et les métriques d’évaluation.

### Validation des artefacts

`validate_artifacts.py` recharge réellement les deux modèles et le manifest, exécute une prédiction puis vérifie que les artefacts et datasets nécessaires existent.

Cela évite qu’un conteneur IA termine avec succès alors que les fichiers produits sont inutilisables.

---

# 6. Monitoring opérationnel de l’IA

### Ce qui a été ajouté

Une couche de supervision spécifique au modèle IA a été ajoutée.

Principaux fichiers :

- `platform/server/app/model_monitoring.py`
- `monitoring/grafana/dashboards/obrail-ia-monitoring.json`
- `monitoring/grafana/provisioning/alerting/alerting.yml`
- `docs/ia/monitoring_c11.md`
- évolution de `MonitoringTab.jsx`
- évolution de `/api/internal/overview`

### Pourquoi

Avant cela, Prometheus/Grafana supervisaient essentiellement l’application et l’API.

La nouvelle version distingue maintenant :

- les **performances offline** enregistrées lors de l’entraînement ;
- les **métriques online** produites pendant les vraies prédictions.

### Fonctionnement

Quatre familles de métriques Prometheus ont été ajoutées :

- `obrail_ai_predictions_total`
- `obrail_ai_inference_seconds`
- `obrail_ai_classification_results_total`
- `obrail_ai_regression_results_total`

Elles permettent de connaître :

- le nombre de prédictions réussies ;
- le nombre d’erreurs ;
- la latence d’inférence ;
- la distribution des résultats de classification ;
- la distribution des tendances de régression.

L’API interne interroge Prometheus puis synthétise l’état du runtime en :

- `healthy`
- `warning`
- `incident`
- `no_data`
- `unavailable`

### Administration

L’onglet **Monitoring** de l’espace interne affiche maintenant :

- état des targets Prometheus ;
- trafic et erreurs API ;
- latence moyenne/P95 ;
- version du modèle ;
- horizons disponibles ;
- F1, ROC-AUC et Accuracy de classification ;
- MAE, RMSE et R² de régression ;
- présence des artefacts IA ;
- nombre de prédictions réelles ;
- erreurs d’inférence ;
- distributions des résultats ;
- lien vers le dashboard Grafana IA.

Deux alertes Grafana ont également été ajoutées :

- erreur d’inférence sur les 5 dernières minutes ;
- latence P95 supérieure à 1 seconde.

Le choix est volontairement simple : aucune plateforme MLOps supplémentaire n’a été introduite.

---

# 7. Ajout d’une démonstration Big Data avec Spark

### Ce qui a été ajouté

Une brique totalement indépendante a été créée :

- `bigdata/spark_gtfs.py`
- `bigdata/postgres_queries.sql`
- `bigdata/README.md`
- `docker-compose.bigdata.yml`

### Pourquoi

Cette partie permet de démontrer l’utilisation d’un système Big Data pour la compétence C2 sans transformer toute l’architecture du projet.

Le PostgreSQL, l’ETL, l’IA, l’API et le frontend existants ne dépendent pas de Spark.

### Fonctionnement

Spark lit directement les fichiers GTFS bruts disponibles pour :

- France ;
- Allemagne ;
- Suisse ;
- Espagne ;
- Luxembourg.

Les jeux utilisés sont principalement :

- `stop_times.csv`
- `trips.csv`
- `routes.csv`
- `stops.csv`

Les données sont enrichies avec un champ `country`.

Spark SQL réalise ensuite plusieurs traitements réels :

- `SELECT`
- `JOIN`
- `GROUP BY`
- `COUNT`
- `COUNT DISTINCT`
- `ORDER BY`

Les jointures utilisent des clés composées avec le pays afin d’éviter les collisions d’identifiants GTFS entre deux réseaux.

Le résultat est écrit en **Parquet partitionné par pays** dans :

`data/bigdata/gtfs_metrics/`

### Lancement

La plateforme normale reste :

```bash
docker compose up --build
```

Spark se lance séparément :

```bash
docker compose -f docker-compose.bigdata.yml run --rm spark-bigdata
```

C’est une intégration volontairement minimale : aucun Kafka, Hadoop, HDFS, Spark Streaming ou cluster artificiel n’a été ajouté.

---

# 8. Renforcement MLOps et CI/CD

### Ce qui a été ajouté

Le workflow `.github/workflows/ci-cd.yml` a été largement renforcé.

La CI distingue désormais plusieurs contrôles :

```text
Backend Tests
IA Tests
Frontend E2E
Code Quality
      ↓
Docker Build
      ↓
GHCR sur main
      ↓
Smoke Test
```

### Tests IA

Un dossier `ia/tests/` a été ajouté pour tester notamment :

- construction des datasets ;
- prédiction ;
- API de prédiction ;
- entraînement forecasting ;
- validation des artefacts.

Le workflow exécute également une couverture de code sur les briques IA principales.

### Orchestration Docker

L’ordre de démarrage est maintenant clairement matérialisé :

```text
db
 ↓
etl
 ↓
ia
 ↓
api
 ↓
front
```

Le service IA est un traitement ponctuel : il attend la fin correcte de l’ETL, construit les datasets, entraîne les modèles et valide les artefacts.

L’API ne démarre qu’après la réussite du service IA.

### Pourquoi

Cette organisation transforme l’entraînement en étape reproductible du déploiement local au lieu de dépendre de modèles préparés manuellement.

La documentation `docs/ia/mlops_c13.md` formalise cette chaîne sans introduire MLflow, Kubeflow ou Kubernetes, qui seraient disproportionnés pour le projet.

---

# 9. Frontend, pagination et corrections de requêtes

### Ce qui a été ajouté

Un composant de pagination générique a été créé :

- `DataPagination.js`
- `DataPagination.css`

Deux modes sont disponibles :

1. pagination classique page par page ;
2. pagination par **tranches d’analyse**, représentant environ une fraction constante des données de chaque pays.

Cette logique est réutilisée dans plusieurs pages externes.

Les pages Home, Carte, Trajets, Statistiques, Opérateurs et IA ont également été retravaillées pour intégrer les nouvelles données et améliorer leur affichage.

### Pourquoi

Avec davantage de données GTFS, charger ou afficher la totalité des enregistrements devient peu pratique.

La pagination limite les volumes affichés sans supprimer les données.

### Corrections backend associées

Des requêtes analytiques ont été revues, notamment dans `routers/analysis.py`.

Exemple important : les statistiques pays/année sont maintenant jointes avec les trains sur **le pays et l’année**, afin d’éviter les multiplications de lignes.

D’autres agrégations sont calculées avant certaines jointures afin d’éviter des produits cartésiens coûteux.

Ces changements améliorent donc à la fois la cohérence des statistiques et les performances.

---

# 10. Tests et documentation ajoutés

La nouvelle branche ajoute également plusieurs tests de non-régression :

### Backend

- authentification ;
- endpoints internes ;
- pagination stratifiée ;
- timeline opérateurs ;
- monitoring IA.

### Frontend

- routes protégées ;
- inscription ;
- authentification E2E ;
- adaptation des tests des pages publiques et internes.

### IA

- datasets ;
- forecasting ;
- prédiction ;
- API de prédiction ;
- validation d’artefacts.

### Documentation

Deux documents importants formalisent les nouvelles compétences :

- `docs/ia/monitoring_c11.md`
- `docs/ia/mlops_c13.md`

et le dossier `bigdata/` contient sa propre documentation C2.

---

# 11. Conclusion

`fix-correctif` ne remplace pas l’architecture de `main`. Elle la complète principalement autour de quatre axes :

1. **fiabilisation des données et extension européenne** ;
2. **industrialisation et amélioration de l’IA** ;
3. **sécurité et supervision de l’application** ;
4. **ajout de preuves techniques pour Big Data, monitoring IA et MLOps**.

Le point positif de l’évolution est que les nouvelles briques ont été intégrées en réutilisant au maximum l’existant :

- Spark reste optionnel et isolé ;
- le monitoring IA utilise Prometheus/Grafana déjà présents ;
- le MLOps utilise GitHub Actions, Docker et GHCR déjà cohérents avec le projet ;
- l’authentification s’intègre directement à FastAPI et React ;
- les nouveaux pays passent par le pipeline ETL existant.

La branche est donc nettement plus complète que `main`, tout en restant proche de l’architecture initiale et sans ajouter inutilement une infrastructure complexe.
