from app.routers import internal


class TestInternalEndpoints:
    def test_internal_overview_returns_monitoring_payload(self, client, monkeypatch):
        monkeypatch.setattr(internal, "_first_ok", lambda urls, path: ({"data": {"activeTargets": []}}, "http://test"))
        monkeypatch.setattr(internal, "_prometheus_query", lambda query: 0)
        monkeypatch.setattr(internal, "_prometheus_vector", lambda query: [])
        monkeypatch.setattr(internal, "_docker_status", lambda: {"available": False, "success": False, "services": []})
        monkeypatch.setattr(internal, "_reports_summary", lambda: {"quality": {}, "diagnostic": None})
        monkeypatch.setattr(internal, "_ia_summary", lambda: {"available": False, "status": "unavailable"})

        response = client.get("/api/internal/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["health"]["status"] == "ok"
        assert "metrics" in data
        assert "prometheus" in data
        assert "grafana" in data
        assert "docker" in data
        assert data["ia"] == {"available": False, "status": "unavailable"}

    def test_internal_diagnostic_reports_missing_script(self, client, monkeypatch):
        monkeypatch.setattr(internal.Path, "exists", lambda self: False)

        response = client.post("/api/internal/diagnostic/run")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["available"] is False

    def test_internal_tests_reports_missing_directory(self, client, monkeypatch):
        monkeypatch.setattr(internal.Path, "exists", lambda self: False)

        response = client.post("/api/internal/tests/run")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["available"] is False
