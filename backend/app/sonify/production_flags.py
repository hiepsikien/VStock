"""Feature flags for the Sprint 13 production wiring.

Each flag is read at call time from the environment and defaults off. Only the
usual truthy tokens -- ``1``, ``true``, ``yes``, and ``on``, case-insensitive
and ignoring surrounding whitespace -- turn a path on. Missing, empty, falsy,
unknown, and rollback values all keep the historical renderer. The helpers also
accept a :class:`contextvars.ContextVar` override so a test or an audition can
pin a value without touching the process environment.

The Barrios Cathedral period already owns its flag in
``app.sonify.guitar_barrios_period``; :func:`barrios_period_enabled` delegates
there instead of copying that flag or its override.

Nothing here is wired into render or selection yet. Sprint 13 calls these
helpers at the documented seams; importing this module changes no runtime
behaviour and registers nothing.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar

VILLA_PRODUCTION_ENV = "VSTOCK_VILLA_PRODUCTION"
BROUWER_PRODUCTION_ENV = "VSTOCK_BROUWER_PRODUCTION"
SUITE_MAZURKA_ENV = "VSTOCK_SUITE_MAZURKA"

_TRUE = frozenset({"1", "true", "yes", "on"})

_VILLA_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "villa_production_enabled", default=None
)
_BROUWER_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "brouwer_production_enabled", default=None
)
_SUITE_MAZURKA_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "suite_mazurka_enabled", default=None
)

__all__ = [
    "BROUWER_PRODUCTION_ENV",
    "SUITE_MAZURKA_ENV",
    "VILLA_PRODUCTION_ENV",
    "barrios_period_enabled",
    "brouwer_production_enabled",
    "suite_mazurka_enabled",
    "use_brouwer_production",
    "use_suite_mazurka",
    "use_villa_production",
    "villa_production_enabled",
]


def _env_enabled(name: str) -> bool:
    """Read one flag without caching it, so an env change takes effect at once."""
    raw = os.environ.get(name)
    return raw is not None and raw.strip().lower() in _TRUE


def villa_production_enabled() -> bool:
    """True when the gated Villa production sentence path is selected."""
    override = _VILLA_OVERRIDE.get()
    if override is not None:
        return override
    return _env_enabled(VILLA_PRODUCTION_ENV)


def brouwer_production_enabled() -> bool:
    """True when the gated Brouwer production sentence path is selected."""
    override = _BROUWER_OVERRIDE.get()
    if override is not None:
        return override
    return _env_enabled(BROUWER_PRODUCTION_ENV)


def suite_mazurka_enabled() -> bool:
    """True when the gated Villa-Lobos Suite Mazurka-Choro path is selected."""
    override = _SUITE_MAZURKA_OVERRIDE.get()
    if override is not None:
        return override
    return _env_enabled(SUITE_MAZURKA_ENV)


def barrios_period_enabled() -> bool:
    """Delegate to the owner module; this module never duplicates the flag.

    ``app.sonify.guitar_barrios_period`` keeps both the ``VSTOCK_BARRIOS_PERIOD``
    environment variable and its own ContextVar override.
    """
    from app.sonify.guitar_barrios_period import (
        barrios_period_enabled as _barrios_enabled,
    )

    return _barrios_enabled()


@contextmanager
def _use_override(
    override: ContextVar[bool | None], enabled: bool
) -> Iterator[None]:
    """Pin one flag for the context and restore the previous value on exit."""
    token = override.set(bool(enabled))
    try:
        yield
    finally:
        override.reset(token)


def use_villa_production(
    enabled: bool = True,
) -> AbstractContextManager[None]:
    """Test/audition override for :func:`villa_production_enabled`."""
    return _use_override(_VILLA_OVERRIDE, enabled)


def use_brouwer_production(
    enabled: bool = True,
) -> AbstractContextManager[None]:
    """Test/audition override for :func:`brouwer_production_enabled`."""
    return _use_override(_BROUWER_OVERRIDE, enabled)


def use_suite_mazurka(enabled: bool = True) -> AbstractContextManager[None]:
    """Test/audition override for :func:`suite_mazurka_enabled`."""
    return _use_override(_SUITE_MAZURKA_OVERRIDE, enabled)
