from fastapi.testclient import TestClient

from apps.gateway.app import create_app
from runtime_core import RuntimeFacade


def test_snapshot_api_returns_none_for_unknown_session() -> None:
    client = TestClient(create_app(RuntimeFacade()))

    response = client.get("/sessions/missing/snapshot")

    assert response.status_code == 404
    assert response.json() == {"detail": "session not found"}


def test_snapshot_api_returns_session_snapshot_after_turn() -> None:
    facade = RuntimeFacade()
    client = TestClient(create_app(facade))

    with client.websocket_connect("/sessions/s1") as websocket:
        websocket.send_json(
            {
                "type": "turn",
                "sessionId": "s1",
                "messageId": "m1",
                "payload": {"text": "hello"},
            }
        )
        assert websocket.receive_json() == {
            "type": "assistant_text",
            "sessionId": "s1",
            "messageId": "m1:assistant",
            "payload": {
                "text": "stub",
                "source": "fast",
            },
        }

    response = client.get("/sessions/s1/snapshot")

    assert response.status_code == 200
    assert response.json()["session_id"] == "s1"
    assert response.json()["dialog_id"] == "s1"
