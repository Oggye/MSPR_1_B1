# Tests unitaires pour les fonctions de statistiques

# Importer les modules nécessaires
from unittest.mock import MagicMock
from app.routers.statistics import get_timeline_data, get_co2_ranking


# Vérification de la logique de l'évolution temporelle des indicateurs
def test_timeline_logic():
    db = MagicMock()

    #  Mock de la 1ère requête (stats)
    stats_query_mock = MagicMock()
    stats_query_mock.join.return_value.group_by.return_value.order_by.return_value.all.return_value = [
        (2024, 1000, 500, 0.05)
    ]

    #  Mock de la 2ème requête (night trains)
    night_query_mock = MagicMock()
    night_query_mock.join.return_value.group_by.return_value.order_by.return_value.all.return_value = [
        (2024, 10, 6, 4)
    ]

    #  IMPORTANT : 2 appels à db.query()
    db.query.side_effect = [stats_query_mock, night_query_mock]

    result = get_timeline_data(db)

    assert len(result) == 1
    assert result[0].year == 2024
    assert result[0].passengers == 1000
    assert result[0].co2_emissions == 500
    assert result[0].co2_per_passenger == 0.05




# Vérification de la logique du classement par impact CO2
def test_co2_ranking_logic():
    db = MagicMock()

    ranking_mock = MagicMock()
    ranking_mock.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        ("France", "FR", 0.03)
    ]

    db.query.return_value = ranking_mock

    result = get_co2_ranking(db, limit=5)

    assert len(result) == 1
    assert result[0].country_name == "France"
    assert result[0].country_code == "FR"
    assert result[0].avg_co2_per_passenger == 0.03
    assert result[0].performance in ["good", "medium", "bad"]




# Test pour vérifier le cas où il n'y a aucune donnée dans la base (timeline vide)
def test_co2_ranking_empty():
    db = MagicMock()

    ranking_mock = MagicMock()
    ranking_mock.filter.return_value.order_by.return_value.all.return_value = []

    db.query.return_value = ranking_mock

    result = get_co2_ranking(db)

    assert isinstance(result, list)
    assert result == []
