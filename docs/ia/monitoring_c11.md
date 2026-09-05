# Monitoring du modèle IA — C11

## Objectif

Cette mise en œuvre apporte la preuve C11 manquante sans remplacer la supervision existante. Les métriques d'évaluation sauvegardées à l'entraînement restent séparées des métriques produites pendant l'utilisation réelle des modèles.

## Architecture

```text
Prediction API
      ↓
prometheus_client (mémoire locale)
      ↓
/metrics existant
      ↓
Prometheus (job fastapi)
      ↓
Grafana
      ↓
Alerting Grafana
```

Aucun appel réseau n'est effectué par une route de prédiction pour enregistrer une métrique. Le job Prometheus existant collecte le même endpoint `/metrics` que les métriques HTTP FastAPI.

## Métriques offline

`_ia_summary()` lit le manifest et contrôle la présence du classifier et du regressor. L'espace administrateur continue ainsi d'afficher l'état `healthy`, `degraded`, `unavailable` ou `error`, la version, l'architecture, les horizons, la date des artefacts et les résultats de holdout (F1, ROC-AUC, Accuracy, MAE, RMSE, R² et baseline).

Ces informations décrivent le modèle entraîné et déployé ; elles ne sont pas dupliquées dans Prometheus.

## Métriques online

| Nom | Type | Labels | Utilité |
|---|---|---|---|
| `obrail_ai_predictions_total` | Counter | `task`, `status`, `horizon` | Compter les succès et les erreurs réelles d'appel au modèle. |
| `obrail_ai_inference_seconds` | Histogram | `task`, `horizon` | Mesurer uniquement la durée de `ml_predict()` et calculer des quantiles. |
| `obrail_ai_classification_results_total` | Counter | `label`, `horizon` | Suivre la distribution des libellés réellement retournés par le classifieur. |
| `obrail_ai_regression_results_total` | Counter | `trend`, `horizon` | Suivre la distribution de `Croissance`, `Stable` et `Déclin` calculée par `_trend_label()`. |

Les labels sont bornés et ne contiennent ni pays, ni utilisateur, ni adresse IP, ni autre donnée personnelle.

## Alertes

Les deux règles sont évaluées chaque minute par Grafana :

- `IAInferenceErrors` : `sum(increase(obrail_ai_predictions_total{status="error"}[5m])) > 0` ; elle détecte au moins un échec de `ml_predict()` sur cinq minutes.
- `IAInferenceSlow` : `histogram_quantile(0.95, sum(rate(obrail_ai_inference_seconds_bucket[5m])) by (le)) > 1` ; le seuil initial d'une seconde doit être ajusté après observation des latences réelles.

L'absence de séries est traitée comme `OK`. Aucun Alertmanager ni canal de notification externe n'est ajouté.

## Test en environnement dédié

Le Docker Compose local constitue l'environnement dédié de validation C11 :

```bash
docker compose up --build
```

Depuis l'interface `http://localhost:3000`, se connecter puis lancer au moins une classification et une régression pour plusieurs horizons. La même démonstration peut être faite en HTTP avec un compte existant :

```bash
curl -c cookies.txt -H "Content-Type: application/json" \
  -d '{"email":"UTILISATEUR","password":"MOT_DE_PASSE"}' \
  http://localhost:8000/api/auth/login

curl -b cookies.txt http://localhost:8000/api/predict/context

curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"country":"France","year":2025}' \
  http://localhost:8000/api/predict/classification

curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"country":"France","year":2025}' \
  http://localhost:8000/api/predict/regression
```

Adapter l'année à `target_min_year` retournée par `/api/predict/context`.

## Vérification

1. Ouvrir `http://localhost:8000/metrics` et rechercher les quatre préfixes `obrail_ai_`.
2. Ouvrir `http://localhost:9090`, vérifier la target `fastapi`, puis exécuter `obrail_ai_predictions_total`.
3. Ouvrir `http://localhost:3001/d/obrail-ia-monitoring/obrail-ia-monitoring` et contrôler les cinq panneaux.
4. Dans Grafana, ouvrir **Alerting > Alert rules** et vérifier `IAInferenceErrors` et `IAInferenceSlow`.

Avant la première prédiction, certains panneaux affichent normalement `No data`.

## Limites volontaires

Le monitoring opérationnel du modèle est implémenté. Restent volontairement hors périmètre :

- la détection automatique du data drift ;
- le model drift, qui nécessitera de futures vérités terrain pour comparer prédictions et observations ;
- le réentraînement automatique ou continu ;
- les notifications externes et une plateforme MLOps supplémentaire.

Une alerte signale donc une dégradation opérationnelle et déclenche une investigation humaine. Elle ne déclenche pas automatiquement un réentraînement.
