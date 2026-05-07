from __future__ import annotations

from app.services.auth import create_user


def test_auth_flow(client):
    test_client, session_factory = client
    with session_factory() as session:
        create_user(session, full_name="Admin User", email="admin@example.com", password="ChangeMe123!")

    login_response = test_client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "ChangeMe123!"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    refresh_response = test_client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"] != ""

    logout_response = test_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_response.status_code == 200
