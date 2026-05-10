"""CORS must allow the configured frontend origin (demo: http://localhost:3000)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_localhost_3000():
    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/markets/today",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    # FastAPI's CORS middleware returns 200 for valid preflight
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in resp.headers["access-control-allow-methods"]


def test_cors_simple_get_includes_origin_header():
    with TestClient(app) as client:
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
