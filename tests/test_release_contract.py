"""Release-level checks for version identity and the stable public API surface."""

from fastapi.testclient import TestClient

from app.config import APP_NAME, APP_VERSION
from app.main import app


def test_release_identity_is_exposed_without_changing_health_contract() -> None:
    client = TestClient(app)

    health_response = client.get("/health")
    openapi_response = client.get("/openapi.json")

    assert APP_VERSION == "6.0.1"
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok", "app": APP_NAME}
    assert openapi_response.status_code == 200
    assert openapi_response.json()["info"]["version"] == APP_VERSION


def test_openapi_preserves_complete_stable_endpoint_surface() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]
    expected_methods = {
        "/health": {"get"},
        "/analysis": {"post"},
        "/journal": {"get", "post"},
        "/journal/summary": {"get"},
        "/backtest": {"post"},
        "/calibrate": {"post"},
        "/dashboard/overview": {"get"},
        "/dashboard/symbols": {"get"},
        "/dashboard/strategies": {"get"},
        "/dashboard/setups": {"get"},
        "/dashboard/readiness": {"get"},
        "/dashboard/risks": {"get"},
        "/dashboard/recommendations": {"get"},
    }

    for path, methods in expected_methods.items():
        assert path in paths
        assert methods <= set(paths[path])
