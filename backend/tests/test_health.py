import os

import pytest

from app.api import health


def test_liveness_responds_without_database(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_readiness_returns_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(health, "database_is_ready", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_readiness_ok_when_database_answers(client, monkeypatch):
    monkeypatch.setattr(health, "database_is_ready", lambda: True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="sem Postgres (roda no CI e no Docker)")
def test_readiness_against_real_database(client):
    assert client.get("/health/ready").status_code == 200
