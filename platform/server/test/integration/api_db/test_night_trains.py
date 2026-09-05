"""
Tests pour les endpoints des trains de nuit
"""

import pytest


def get_first(data):
    """Retourne le premier élément d'une liste non vide"""
    assert len(data) > 0 # Vérifier que la liste n'est pas vide avant d'accéder au premier élément
    return data[0]


class TestNightTrainsEndpoints:
    """Tests pour tous les endpoints /api/night-trains/*"""

    def test_get_night_trains(self, client, sample_data):
        """Test récupération de tous les trains"""
        response = client.get("/api/night-trains")
        assert response.status_code == 200
        data = response.json()
        first = get_first(data) # Récupérer le premier train pour vérifier la structure de la réponse
        assert len(data) == 25  # 25 trains dans sample_data
        assert "night_train" in first
        assert "country_name" in first

    def test_get_night_trains_pagination_limit(self, client, sample_data):
        """La limite est appliquée par le contrat HTTP public."""
        response = client.get("/api/night-trains?skip=0&limit=5")

        assert response.status_code == 200
        assert len(response.json()) <= 5

    def test_get_night_trains_pagination_skip_changes_page(self, client, sample_data):
        """Deux pages successives ne commencent pas par le même train."""
        first_page = client.get("/api/night-trains?skip=0&limit=5")
        second_page = client.get("/api/night-trains?skip=5&limit=5")

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert len(first_page.json()) == 5
        assert len(second_page.json()) == 5
        assert first_page.json()[0]["fact_id"] != second_page.json()[0]["fact_id"]

    def test_get_night_trains_summary(self, client, sample_data):
        """Test récupération du résumé des trains"""
        response = client.get("/api/night-trains/summary")
        assert response.status_code == 200
        data = response.json()
        assert "total_trains" in data
        assert "total_night_trains" in data
        assert "total_day_trains" in data
        assert data["total_night_trains"] + data["total_day_trains"] == data["total_trains"] # Vérifier que le total correspond à la somme des trains de nuit et de jour
        assert data["total_night_trains"] == 12  # 12 trains de nuit dans sample_data
        assert data["total_day_trains"] == 13  # 13 trains de jour dans sample_data


    def test_get_night_trains_only(self, client, sample_data):
        """Test récupération des trains de nuit uniquement"""
        response = client.get("/api/night-trains/night")
        assert response.status_code == 200
        data = response.json()
        # Vérifier que tous les trains retournés sont des trains de nuit
        for train in data:
            assert train["is_night"] is True

    def test_get_day_trains_only(self, client, sample_data):
        """Test récupération des trains de jour uniquement"""
        response = client.get("/api/night-trains/day")
        assert response.status_code == 200
        data = response.json()
        # Vérifier que tous les trains retournés sont des trains de jour
        for train in data:
            assert train["is_night"] is False

    
    # Test pour vérifier le nombre total de trains par opérateur
    def test_get_night_trains_by_operator(self, client, sample_data):
        response = client.get("/api/night-trains/by-operator/1")
        assert response.status_code == 200

        data = response.json()

        # Vérifier que tous les trains retournés appartiennent à l'opérateur 1 (SNCF)
        assert all(t["operator_name"] == "SNCF" for t in data)



    # Test pour vérifier la structure de la réponse
    def test_response_structure(self, client, sample_data):
        response = client.get("/api/night-trains")
        data = response.json()
        
        first = get_first(data) # Récupérer le premier train pour vérifier la structure de la réponse

        # Vérifier que les champs attendus sont présents dans la réponse
        required_fields = {
            "night_train",
            "country_name",
            "distance_km",
            "duration_min",
            "is_night"
        }

        # Vérifier que tous les champs requis sont présents dans la réponse
        assert required_fields.issubset(first.keys())



    # Test pour vérifier le cas où l'opérateur n'existe pas
    def test_operator_not_found(self, client, sample_data):
        response = client.get("/api/night-trains/by-operator/999")

        # Vérifier que le code de statut est 404 Not Found
        assert response.status_code == 404



    # Test pour vérifier les types de données dans la réponse
    def test_types(self, client, sample_data):
        data = client.get("/api/night-trains").json()

        # Vérifier que la liste de trains n'est pas vide
        first = get_first(data)

        # Vérifier les types de données des champs
        assert isinstance(first["distance_km"], (int, float))
        assert isinstance(first["duration_min"], (int, float))
        assert isinstance(first["is_night"], bool)
        assert isinstance(first["night_train"], str)
        assert isinstance(first["country_name"], str)
