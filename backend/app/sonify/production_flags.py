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

The helpers here only read or pin a flag. The call sites own every registration
and render gate, so importing this module changes no runtime behaviour and
registers nothing.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from types import MappingProxyType

VILLA_PRODUCTION_ENV = "VSTOCK_VILLA_PRODUCTION"
BROUWER_PRODUCTION_ENV = "VSTOCK_BROUWER_PRODUCTION"
SUITE_MAZURKA_ENV = "VSTOCK_SUITE_MAZURKA"

# The four remaining Suite movements. `suite_mazurka` keeps its own constant
# and reader above so its historical flag contract does not move.
SUITE_VALSA_ENV = "VSTOCK_SUITE_VALSA"
SUITE_GAVOTTA_ENV = "VSTOCK_SUITE_GAVOTTA"
SUITE_SCHOTTISH_ENV = "VSTOCK_SUITE_SCHOTTISH"
SUITE_CHOROS1_ENV = "VSTOCK_SUITE_CHOROS1"

# Movement id -> environment name, in selection precedence order.
SUITE_MOVEMENT_ENVS: Mapping[str, str] = MappingProxyType(
    {
        "suite_valsa": SUITE_VALSA_ENV,
        "suite_gavotta": SUITE_GAVOTTA_ENV,
        "suite_schottish": SUITE_SCHOTTISH_ENV,
        "suite_choros1": SUITE_CHOROS1_ENV,
    }
)

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
_SUITE_MOVEMENT_OVERRIDES: Mapping[str, ContextVar[bool | None]] = MappingProxyType(
    {
        movement: ContextVar(f"{movement}_enabled", default=None)
        for movement in SUITE_MOVEMENT_ENVS
    }
)

__all__ = [
    "BROUWER_PRODUCTION_ENV",
    "SUITE_CHOROS1_ENV",
    "SUITE_GAVOTTA_ENV",
    "SUITE_MAZURKA_ENV",
    "SUITE_MOVEMENT_ENVS",
    "SUITE_SCHOTTISH_ENV",
    "SUITE_VALSA_ENV",
    "VILLA_PRODUCTION_ENV",
    "any_suite_movement_enabled",
    "barrios_period_enabled",
    "brouwer_production_enabled",
    "suite_choros1_enabled",
    "suite_gavotta_enabled",
    "suite_mazurka_enabled",
    "suite_movement_enabled",
    "suite_schottish_enabled",
    "suite_valsa_enabled",
    "use_brouwer_production",
    "use_suite_choros1",
    "use_suite_gavotta",
    "use_suite_mazurka",
    "use_suite_movement",
    "use_suite_schottish",
    "use_suite_valsa",
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


def suite_movement_enabled(movement: str) -> bool:
    """True when one remaining Suite movement's gate is enabled.

    ``movement`` is the production id, e.g. ``suite_valsa``. An unknown id is a
    programming error, not a silent off: a call site must name a real gate.
    """
    try:
        override = _SUITE_MOVEMENT_OVERRIDES[movement]
        env = SUITE_MOVEMENT_ENVS[movement]
    except KeyError:
        raise KeyError(f"unknown Suite movement flag {movement!r}") from None
    pinned = override.get()
    if pinned is not None:
        return pinned
    return _env_enabled(env)


def suite_valsa_enabled() -> bool:
    """True when the gated Suite Valsa-Choro path is selected."""
    return suite_movement_enabled("suite_valsa")


def suite_gavotta_enabled() -> bool:
    """True when the gated Suite Gavotta-Choro path is selected."""
    return suite_movement_enabled("suite_gavotta")


def suite_schottish_enabled() -> bool:
    """True when the gated Suite Schottish-Choro path is selected."""
    return suite_movement_enabled("suite_schottish")


def suite_choros1_enabled() -> bool:
    """True when the gated Suite Choros No. 1 path is selected."""
    return suite_movement_enabled("suite_choros1")


def any_suite_movement_enabled() -> bool:
    """True when any remaining Suite gate is on.

    The renderer uses this to avoid importing the movement modules on the
    default-off path, which keeps the historical render free of extra work.
    """
    return any(suite_movement_enabled(movement) for movement in SUITE_MOVEMENT_ENVS)


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


def use_suite_movement(
    movement: str, enabled: bool = True
) -> AbstractContextManager[None]:
    """Test/audition override for one remaining Suite movement's flag."""
    try:
        override = _SUITE_MOVEMENT_OVERRIDES[movement]
    except KeyError:
        raise KeyError(f"unknown Suite movement flag {movement!r}") from None
    return _use_override(override, enabled)


def use_suite_valsa(enabled: bool = True) -> AbstractContextManager[None]:
    """Test/audition override for :func:`suite_valsa_enabled`."""
    return use_suite_movement("suite_valsa", enabled)


def use_suite_gavotta(enabled: bool = True) -> AbstractContextManager[None]:
    """Test/audition override for :func:`suite_gavotta_enabled`."""
    return use_suite_movement("suite_gavotta", enabled)


def use_suite_schottish(enabled: bool = True) -> AbstractContextManager[None]:
    """Test/audition override for :func:`suite_schottish_enabled`."""
    return use_suite_movement("suite_schottish", enabled)


def use_suite_choros1(enabled: bool = True) -> AbstractContextManager[None]:
    """Test/audition override for :func:`suite_choros1_enabled`."""
    return use_suite_movement("suite_choros1", enabled)
