from pathlib import Path

import sentry_sdk

from app.config import Settings
from app.observability import build_traces_sampler, init_sentry


def test_without_dsn_sentry_stays_off(tmp_path: Path) -> None:
    settings = Settings(cache_dir=tmp_path, sentry_dsn=None)

    assert init_sentry(settings) is False
    assert not sentry_sdk.get_client().is_active()


def test_sampler_drops_meta_routes() -> None:
    sampler = build_traces_sampler(0.05)

    assert sampler({"asgi_scope": {"path": "/health"}}) == 0.0
    assert sampler({"asgi_scope": {"path": "/voices"}}) == 0.0
    assert sampler({"asgi_scope": {"path": "/v1/synthesize"}}) == 0.05
