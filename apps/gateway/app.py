from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from runtime_core import RuntimeFacade

from .http import register_http_routes
from .ws import register_ws_routes


def create_app(facade: RuntimeFacade | None = None) -> FastAPI:
    app = FastAPI()
    runtime_facade = facade or RuntimeFacade()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_http_routes(app, runtime_facade)
    register_ws_routes(app, runtime_facade)

    return app
