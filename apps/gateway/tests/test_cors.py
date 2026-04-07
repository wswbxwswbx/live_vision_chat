from fastapi.testclient import TestClient

from apps.gateway.app import create_app


def test_health_includes_cors_headers_for_demo_client_origin() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
