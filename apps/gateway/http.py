from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from runtime_core import RuntimeFacade


def register_http_routes(app: FastAPI, facade: RuntimeFacade) -> None:
    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/sessions/{session_id}/snapshot")
    async def get_session_snapshot(session_id: str) -> object:
        snapshot = facade.get_session_snapshot(session_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="session not found")
        return jsonable_encoder(snapshot)
