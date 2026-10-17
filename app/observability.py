"""Optional Sentry error tracking."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import sentry_sdk

from app.config import Settings

# Routes with no tracing value; they would only burn the Sentry quota.
IGNORED_PATHS = ("/health", "/voices", "/docs", "/openapi.json")


def build_traces_sampler(rate: float) -> Callable[[dict[str, Any]], float]:
    """Return a sampler that drops meta routes and samples the rest at ``rate``."""

    def sampler(context: dict[str, Any]) -> float:
        path = (context.get("asgi_scope") or {}).get("path", "")
        if path.startswith(IGNORED_PATHS):
            return 0.0
        return rate

    return sampler


def init_sentry(settings: Settings) -> bool:
    """Initialise Sentry when ``SENTRY_DSN`` is configured.

    Neither request bodies nor stack-frame local variables are attached: the
    synthesized text may come from children using Aurora and would otherwise
    leak through ``text`` arguments in the traceback. PII collection stays off.

    Returns:
        Whether Sentry was initialised.
    """
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        release=f"aurora-speech@{settings.app_git_sha}",
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sampler=build_traces_sampler(settings.sentry_traces_sample_rate),
    )
    return True
