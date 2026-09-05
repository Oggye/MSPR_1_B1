# Tests unitaires pour les fonctions d'analyse

# Importation de MagicMock pour simuler la base de données et SimpleNamespace pour créer des objets simples
from unittest.mock import MagicMock
from types import SimpleNamespace
from sqlalchemy import column, table
from app.routers.analysis import compare_train_types, get_policy_recommendations


# Vérification de la logique de comparaison jour/nuit
def test_compare_train_types():
    db = MagicMock()

    query_mock = MagicMock()
    query_mock.outerjoin.return_value.group_by.return_value.all.return_value = [
        SimpleNamespace(
            is_night=True,
            nb_trains=10,
            avg_distance=100.0,
            avg_duration=200.0,
            avg_co2=0.04,
            avg_passengers=500
        ),
        SimpleNamespace(
            is_night=False,
            nb_trains=20,
            avg_distance=200.0,
            avg_duration=400.0,
            avg_co2=0.08,
            avg_passengers=700
        ),
    ]
    db.query.return_value = query_mock

    result = compare_train_types(db)

    assert len(result) == 2

    assert result[0].train_type in ["night", "day"]
    assert hasattr(result[0], "efficiency_score")
    assert result[0].avg_co2_per_passenger != result[1].avg_co2_per_passenger




# Vérification de la logique de recommandations politiques
def test_get_policy_recommendations():
    db = MagicMock()

    top_mock = MagicMock()
    top_mock.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = [
        SimpleNamespace(country_name="France", avg_co2=0.08),
        SimpleNamespace(country_name="Germany", avg_co2=0.07),
    ]

    stats_mock = MagicMock()
    stats_mock.group_by.return_value.subquery.return_value = table(
        "stats_by_country",
        column("country_id"),
        column("avg_co2"),
    )

    trains_mock = MagicMock()
    trains_mock.group_by.return_value.subquery.return_value = table(
        "trains_by_country",
        column("country_id"),
        column("train_count"),
    )

    success_mock = MagicMock()
    success_mock.join.return_value.join.return_value.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(
        country_name="Switzerland",
        avg_co2=0.02,
        train_count=50,
    )

    db.query.side_effect = [top_mock, stats_mock, trains_mock, success_mock]

    result = get_policy_recommendations(db)

    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)
    assert len(result["recommendations"]) == 2




# Test pour vérifier le cas où il n'y a aucune recommandation à faire (tous les pays ont une bonne performance)
def test_policy_recommendations_empty():
    db = MagicMock()

    top_mock = MagicMock()
    top_mock.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []

    stats_mock = MagicMock()
    stats_mock.group_by.return_value.subquery.return_value = table(
        "stats_by_country",
        column("country_id"),
        column("avg_co2"),
    )

    trains_mock = MagicMock()
    trains_mock.group_by.return_value.subquery.return_value = table(
        "trains_by_country",
        column("country_id"),
        column("train_count"),
    )

    success_mock = MagicMock()
    success_mock.join.return_value.join.return_value.filter.return_value.order_by.return_value.first.return_value = None

    db.query.side_effect = [top_mock, stats_mock, trains_mock, success_mock]

    result = get_policy_recommendations(db)

    assert "recommendations" in result
    assert result["recommendations"] == []
