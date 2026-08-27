from __future__ import annotations
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import AsyncGenerator, Sequence
from app.api.routes import call, health, config
from app.config.config import get_settings
from contextlib import asynccontextmanager
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(
    cors_origins: Sequence[str] | None = None,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    origins = list(cors_origins) if cors_origins is not None else settings.cors_origins_raw
    if not origins:
        logger.warning(
            "No CORS origins configured; frontend browser requests will be blocked. "
            "Set FRONTEND_URL or CORS_ORIGINS."
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            "API started",
            extra={
                "cors_origins": origins,
                "environment": settings.environment,
                "agent_name": settings.livekit_agent_name,
            },
        )
        yield

    application = FastAPI(
        title="Lab Diagnostic Voice Agent API",
        description=(
            "HTTP API for the React frontend: start a voice call "
            "(dispatch agent + LiveKit token) and health checks."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(call.router)
    application.include_router(config.router)

    return application

app = create_app()