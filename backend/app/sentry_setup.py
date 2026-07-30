from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """Initialize Sentry if SENTRY_DSN is set. Returns True when enabled."""
    dsn = (os.getenv("SENTRY_DSN") or "").strip()
    if not dsn:
        return False

    import sentry_sdk

    environment = os.getenv("SENTRY_ENVIRONMENT") or os.getenv("ENV") or "production"
    try:
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    except ValueError:
        traces_sample_rate = 0.1

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
    )
    logger.info("Sentry enabled (environment=%s)", environment)
    return True
