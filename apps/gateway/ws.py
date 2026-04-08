from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from protocol.messages import parse_client_message
from runtime_core import RuntimeFacade


def register_ws_routes(app: FastAPI, facade: RuntimeFacade) -> None:
    @app.websocket("/sessions/{session_id}")
    async def session_socket(websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()

        try:
            while True:
                payload = await websocket.receive_json()
                message = parse_client_message(payload)
                if message.sessionId != session_id:
                    await websocket.send_json({"error": "session mismatch"})
                    continue

                if message.type in {"audio_chunk", "video_frame"}:
                    continue

                try:
                    result = await facade.handle_client_message(message)
                except ValueError as exc:
                    await websocket.send_json(
                        {
                            "type": "assistant_text",
                            "sessionId": session_id,
                            "messageId": f"{message.messageId}:assistant",
                            "payload": {
                                "text": str(exc),
                                "source": "system",
                            },
                        }
                    )
                    continue

                if result.reply_text is not None:
                    await websocket.send_json(
                        {
                            "type": "assistant_text",
                            "sessionId": session_id,
                            "messageId": f"{message.messageId}:assistant",
                            "payload": {
                                "text": result.reply_text,
                                "source": "fast",
                            },
                        }
                    )
        except WebSocketDisconnect:
            return
