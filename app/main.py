"""FastAPI application factory for Aurora Speech."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.engine import KokoroEngine, build_engine
from app.observability import init_sentry


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare the cache directory and optionally warm the engine."""
    settings = get_settings()
    # In non-container environments the configured path may not be writable.
    # The cache dependency recreates it per request anyway.
    with contextlib.suppress(OSError):
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

    if settings.eager_engine_init:
        engine = build_engine(settings)
        if isinstance(engine, KokoroEngine):
            engine.warm_up()

    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        summary="Internal pt-BR speech synthesis for the Aurora platform.",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


init_sentry(get_settings())
app = create_app()
