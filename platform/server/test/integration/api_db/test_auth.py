import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import User
from app.routers import auth, internal
from app.security import SESSION_COOKIE, create_access_token, require_admin, require_user


TEST_JWT_SECRET = "test-jwt-secret-long-enough-for-authentication"
TEST_ADMIN_CODE = "654321"


@pytest.fixture
def auth_client(monkeypatch, db_session):
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("ADMIN_SIGNUP_CODE", TEST_ADMIN_CODE)
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120")
    auth.FAILED_ATTEMPTS.clear()
    previous_user = app.dependency_overrides.pop(require_user, None)
    previous_admin = app.dependency_overrides.pop(require_admin, None)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        auth.FAILED_ATTEMPTS.clear()
        if previous_user is not None:
            app.dependency_overrides[require_user] = previous_user
        if previous_admin is not None:
            app.dependency_overrides[require_admin] = previous_admin


def register_payload(email="user@example.com", password="Password1", **overrides):
    payload = {
        "email": email,
        "password": password,
        "password_confirm": password,
        "is_admin": False,
        "admin_code": None,
        "accept_terms": True,
    }
    payload.update(overrides)
    return payload


def register(auth_client, **overrides):
    return auth_client.post("/api/auth/register", json=register_payload(**overrides))


def login(auth_client, email="user@example.com", password="Password1"):
    return auth_client.post("/api/auth/login", json={"email": email, "password": password})


def test_register_user_hashes_password_and_normalizes_email(auth_client, db_session):
    response = register(auth_client, email="  Test@Example.com ")

    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "test@example.com", "role": "user"}
    db_session.expire_all()
    user = db_session.query(User).one()
    assert user.password_hash != "Password1"
    assert user.password_hash.startswith("$argon2")
    assert user.terms_accepted_at is not None
    assert user.legal_version == "1.0"


def test_register_rejects_duplicate_normalized_email(auth_client):
    assert register(auth_client, email="Test@example.com").status_code == 201
    assert register(auth_client, email="test@example.com").status_code == 409


@pytest.mark.parametrize(
    "password",
    ["Ab1", "bonjour1", "BONJOUR1", "Obrailxx"],
)
def test_register_rejects_weak_passwords(auth_client, password):
    response = register(auth_client, password=password)

    assert response.status_code == 400


def test_register_rejects_password_confirmation_mismatch(auth_client):
    response = register(auth_client, password_confirm="Different1")

    assert response.status_code == 400


def test_register_requires_terms_acceptance(auth_client):
    response = register(auth_client, accept_terms=False)

    assert response.status_code == 400


def test_register_admin_with_valid_code(auth_client):
    response = register(auth_client, is_admin=True, admin_code=TEST_ADMIN_CODE)

    assert response.status_code == 201
    assert response.json()["role"] == "admin"


def test_register_admin_with_invalid_code_creates_no_user(auth_client, db_session):
    response = register(auth_client, is_admin=True, admin_code="000000")

    assert response.status_code == 403
    assert db_session.query(User).count() == 0


def test_login_sets_httponly_session_cookie(auth_client):
    register(auth_client)
    response = login(auth_client)

    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie


def test_login_uses_generic_error_for_invalid_credentials(auth_client):
    register(auth_client)

    response = login(auth_client, password="WrongPass1")

    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou mot de passe incorrect."


def test_me_requires_cookie_and_returns_current_user(auth_client):
    register(auth_client)
    assert auth_client.get("/api/auth/me").status_code == 401
    login(auth_client)

    response = auth_client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_logout_deletes_session_cookie(auth_client):
    register(auth_client)
    login(auth_client)

    response = auth_client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Déconnexion réussie"}
    assert f"{SESSION_COOKIE}=\"\"" in response.headers["set-cookie"]


def test_expired_session_is_rejected(auth_client, db_session):
    register(auth_client)
    user = db_session.query(User).one()
    auth_client.cookies.set(SESSION_COOKIE, create_access_token(user.id, expires_minutes=-1))

    assert auth_client.get("/api/countries").status_code == 401


def test_user_and_admin_can_access_business_endpoint(auth_client):
    register(auth_client)
    login(auth_client)
    assert auth_client.get("/api/countries").status_code == 200

    auth_client.cookies.clear()
    register(auth_client, email="admin@example.com", is_admin=True, admin_code=TEST_ADMIN_CODE)
    login(auth_client, email="admin@example.com")
    assert auth_client.get("/api/countries").status_code == 200


def test_business_endpoint_rejects_anonymous_user(auth_client):
    assert auth_client.get("/api/countries").status_code == 401


def test_internal_endpoint_access_matrix(auth_client, monkeypatch):
    monkeypatch.setattr(internal, "_first_ok", lambda urls, path: ({"data": {"activeTargets": []}}, "http://test"))
    monkeypatch.setattr(internal, "_prometheus_query", lambda query: 0)
    monkeypatch.setattr(internal, "_prometheus_vector", lambda query: [])
    monkeypatch.setattr(internal, "_docker_status", lambda: {"available": False, "services": []})
    monkeypatch.setattr(internal, "_github_actions_status", lambda: {"available": False, "runs": []})
    monkeypatch.setattr(internal, "_db_totals", lambda: {})
    monkeypatch.setattr(internal, "_reports_summary", lambda: {})

    assert auth_client.get("/api/internal/overview").status_code == 401
    register(auth_client)
    login(auth_client)
    assert auth_client.get("/api/internal/overview").status_code == 403

    auth_client.cookies.clear()
    register(auth_client, email="admin@example.com", is_admin=True, admin_code=TEST_ADMIN_CODE)
    login(auth_client, email="admin@example.com")
    assert auth_client.get("/api/internal/overview").status_code == 200


def test_user_can_access_prediction_context(auth_client, sample_data):
    register(auth_client)
    login(auth_client)

    response = auth_client.get("/api/predict/context")

    assert response.status_code == 200


def test_health_and_metrics_remain_public(auth_client):
    assert auth_client.get("/health").status_code == 200
    assert auth_client.get("/metrics").status_code == 200


def test_login_rate_limit_blocks_fifth_failure(auth_client):
    register(auth_client)

    for _ in range(4):
        assert login(auth_client, password="WrongPass1").status_code == 401
    assert login(auth_client, password="WrongPass1").status_code == 429


def test_admin_registration_rate_limit_blocks_fifth_failure(auth_client, db_session):
    for index in range(4):
        response = register(
            auth_client,
            email=f"admin-{index}@example.com",
            is_admin=True,
            admin_code="000000",
        )
        assert response.status_code == 403

    response = register(
        auth_client,
        email="admin-blocked@example.com",
        is_admin=True,
        admin_code="000000",
    )
    assert response.status_code == 429
    assert db_session.query(User).count() == 0
