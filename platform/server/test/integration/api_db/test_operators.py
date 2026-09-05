"""
Tests pour les endpoints des opérateurs
"""

import pytest

class TestOperatorsEndpoints:
    """Tests pour /api/operators et /api/operators/{id}/stats"""

    def test_get_operators(self, client, sample_data):
        """Test récupération de la liste des opérateurs"""
        response = client.get("/api/operators")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5  # 5 opérateurs dans sample_data
        names = [operator["operator_name"] for operator in data]
        assert names == sorted(names)
        assert set(names) == {"SNCF", "DB", "Trenitalia", "Renfe", "ÖBB"}

    def test_get_operator_stats(self, client, sample_data):
        """Test récupération des stats d'un opérateur spécifique"""
        response = client.get("/api/operators/1/stats")  # SNCF
        assert response.status_code == 200
        data = response.json()
        assert "operator_name" in data
        assert "total_trains" in data
        assert "countries_served" in data

    def test_get_operator_stats_not_found(self, client, sample_data):
        """Test récupération des stats d'un opérateur inexistant"""
        response = client.get("/api/operators/999/stats")
        assert response.status_code == 404
