from fastapi.testclient import TestClient

from apps.gateway.app import create_app
from runtime_core import RuntimeFacade


def test_ws_session_handles_turn_round_trip() -> None:
    client = TestClient(create_app(RuntimeFacade()))

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
                "text": "Fast reply: hello",
                "source": "fast",
            },
        }


def test_ws_session_accepts_media_messages_before_turn() -> None:
    client = TestClient(create_app(RuntimeFacade()))

    with client.websocket_connect("/sessions/s1") as websocket:
        websocket.send_json(
            {
                "type": "audio_chunk",
                "sessionId": "s1",
                "messageId": "m-a1",
                "payload": {
                    "mimeType": "audio/webm;codecs=opus",
                    "data": "Zm9v",
                    "sequence": 1,
                    "timestampMs": 1000,
                    "durationMs": 100,
                },
            }
        )
        websocket.send_json(
            {
                "type": "video_frame",
                "sessionId": "s1",
                "messageId": "m-v1",
                "payload": {
                    "mimeType": "image/jpeg",
                    "data": "YmFy",
                    "sequence": 1,
                    "timestampMs": 1010,
                    "width": 320,
                    "height": 180,
                },
            }
        )
        websocket.send_json(
            {
                "type": "turn",
                "sessionId": "s1",
                "messageId": "m1",
                "payload": {"text": "hello"},
            }
        )

        assert websocket.receive_json()["type"] == "assistant_text"


def test_ws_session_handles_handoff_resume_round_trip() -> None:
    client = TestClient(create_app(RuntimeFacade()))

    with client.websocket_connect("/sessions/s1") as websocket:
        websocket.send_json(
            {
                "type": "turn",
                "sessionId": "s1",
                "messageId": "m1",
                "payload": {"text": "Remind me to pay rent"},
            }
        )

        assert websocket.receive_json() == {
            "type": "assistant_text",
            "sessionId": "s1",
            "messageId": "m1:assistant",
            "payload": {
                "text": "When should I remind you?",
                "source": "fast",
            },
        }

        websocket.send_json(
            {
                "type": "handoff_resume",
                "sessionId": "s1",
                "messageId": "m2",
                "payload": {
                    "taskId": "task-1",
                    "text": "tomorrow at 9am",
                },
            }
        )

        assert websocket.receive_json() == {
            "type": "assistant_text",
            "sessionId": "s1",
            "messageId": "m2:assistant",
            "payload": {
                "text": "Okay, I’ll remind you tomorrow at 9am.",
                "source": "fast",
            },
        }


def test_ws_session_keeps_connection_open_after_invalid_handoff_resume() -> None:
    client = TestClient(create_app(RuntimeFacade()))

    with client.websocket_connect("/sessions/s1") as websocket:
        websocket.send_json(
            {
                "type": "turn",
                "sessionId": "s1",
                "messageId": "m1",
                "payload": {"text": "Remind me to pay rent"},
            }
        )
        assert websocket.receive_json()["payload"]["text"] == "When should I remind you?"

        websocket.send_json(
            {
                "type": "handoff_resume",
                "sessionId": "s1",
                "messageId": "m2",
                "payload": {
                    "taskId": "task-1",
                    "text": "tomorrow at 9am",
                },
            }
        )
        assert websocket.receive_json()["payload"]["text"] == "Okay, I’ll remind you tomorrow at 9am."

        websocket.send_json(
            {
                "type": "handoff_resume",
                "sessionId": "s1",
                "messageId": "m3",
                "payload": {
                    "taskId": "task-1",
                    "text": "next week",
                },
            }
        )
        assert websocket.receive_json() == {
            "type": "assistant_text",
            "sessionId": "s1",
            "messageId": "m3:assistant",
            "payload": {
                "text": "task task-1 is not waiting for user input",
                "source": "system",
            },
        }

        websocket.send_json(
            {
                "type": "turn",
                "sessionId": "s1",
                "messageId": "m4",
                "payload": {"text": "hello"},
            }
        )
        assert websocket.receive_json()["payload"]["text"] == "Fast reply: hello"
