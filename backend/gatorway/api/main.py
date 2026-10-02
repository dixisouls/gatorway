"""uvicorn gatorway.api.main:create_app --factory --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gatorway.db.session import init_db

from .errors import install_error_handlers
from .routes import auth, health, pathways, programs, transcripts
from .state import AppState, build_state


def create_app(state: AppState | None = None, init_db_on_startup: bool = True) -> FastAPI:
    logging.basicConfig(level=logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if init_db_on_startup:
            init_db(app.state.gw.engine)
        yield

    app = FastAPI(title="GatorWay API", version="0.1.0", lifespan=lifespan)
    app.state.gw = state or build_state()
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
    install_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(transcripts.router)
    app.include_router(programs.router)
    app.include_router(pathways.router)
    app.include_router(health.router)
    return app
