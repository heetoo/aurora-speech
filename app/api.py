"""HTTP routes for Aurora Speech."""

from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, Depends, Response
from fastapi.concurrency import run_in_threadpool

from app.cache import Cache, get_cache
from app.config import Settings, get_settings
from app.engine import SpeechEngine, get_engine
from app.modes import get_mode_config
from app.schemas import HealthResponse, SynthesizeRequest, VoiceInfo, VoicesResponse
from app.utils import elapsed_ms
from app.voices import public_voices, resolve_engine_voice

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Report service liveness and the active engine."""
    return HealthResponse(
        status="healthy",
        engine=settings.engine_name,
        version=settings.app_version,
    )


@router.get("/voices", response_model=VoicesResponse, tags=["meta"])
async def voices() -> VoicesResponse:
    """Return the public Aurora voice catalogue.

    Internal engine voice names are never exposed here.
    """
    return VoicesResponse(voices=[VoiceInfo(**entry) for entry in public_voices()])


@router.post(
    "/v1/synthesize",
    tags=["synthesis"],
    responses={200: {"content": {"audio/ogg": {}}, "description": "Synthesized audio"}},
)
async def synthesize(
    request: SynthesizeRequest,
    settings: Settings = Depends(get_settings),
    cache: Cache = Depends(get_cache),
    engine: SpeechEngine = Depends(get_engine),
) -> Response:
    """Synthesize pt-BR speech, serving from the on-disk cache when possible."""
    started = perf_counter()

    key = cache.compute_key(
        engine=settings.engine_name,
        voice=request.voice,
        mode=request.mode.value,
        text=request.text,
    )

    audio = cache.get(key)
    if audio is None:
        cache_status = "MISS"
        mode_config = get_mode_config(request.mode)
        engine_voice = resolve_engine_voice(request.voice)
        audio = await run_in_threadpool(
            engine.synthesize,
            text=request.text,
            voice=engine_voice,
            speed=mode_config.speed,
        )
        cache.put(key, audio)
    else:
        cache_status = "HIT"

    return Response(
        content=audio,
        media_type="audio/ogg",
        headers={
            "X-Cache": cache_status,
            "X-Cache-Key": key,
            "X-Duration-Ms": str(elapsed_ms(started)),
        },
    )
