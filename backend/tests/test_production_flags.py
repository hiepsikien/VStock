"""Sprint 13 production feature flags.

The helpers are plumbing only: the gated modules own their registrations and
render paths. These tests pin the parser contract, the default-off behaviour,
the ContextVar override and its cleanup, and the Barrios delegation to its
existing owner.
"""

from __future__ import annotations

import pytest

from app.sonify import guitar_barrios_period as barrios
from app.sonify import production_flags as flags

ENABLED_VALUES = ("1", "true", "TRUE", "yes", "on", " On ")
DISABLED_VALUES = ("", "0", "false", "no", "off", "rollback", "banana", "2")

# (environment name, reader, context-manager factory)
FLAGS = (
    (
        flags.VILLA_PRODUCTION_ENV,
        flags.villa_production_enabled,
        flags.use_villa_production,
    ),
    (
        flags.BROUWER_PRODUCTION_ENV,
        flags.brouwer_production_enabled,
        flags.use_brouwer_production,
    ),
    (
        flags.SUITE_MAZURKA_ENV,
        flags.suite_mazurka_enabled,
        flags.use_suite_mazurka,
    ),
    (
        flags.SUITE_VALSA_ENV,
        flags.suite_valsa_enabled,
        flags.use_suite_valsa,
    ),
    (
        flags.SUITE_GAVOTTA_ENV,
        flags.suite_gavotta_enabled,
        flags.use_suite_gavotta,
    ),
    (
        flags.SUITE_SCHOTTISH_ENV,
        flags.suite_schottish_enabled,
        flags.use_suite_schottish,
    ),
    (
        flags.SUITE_CHOROS1_ENV,
        flags.suite_choros1_enabled,
        flags.use_suite_choros1,
    ),
)
FLAG_IDS = (
    "villa",
    "brouwer",
    "suite_mazurka",
    "suite_valsa",
    "suite_gavotta",
    "suite_schottish",
    "suite_choros1",
)
FLAGS_WITH_IDS = tuple(
    pytest.param(*flag, id=flag_id)
    for flag, flag_id in zip(FLAGS, FLAG_IDS, strict=True)
)


def test_environment_names_are_the_public_contract() -> None:
    assert flags.VILLA_PRODUCTION_ENV == "VSTOCK_VILLA_PRODUCTION"
    assert flags.BROUWER_PRODUCTION_ENV == "VSTOCK_BROUWER_PRODUCTION"
    assert flags.SUITE_MAZURKA_ENV == "VSTOCK_SUITE_MAZURKA"
    assert flags.SUITE_VALSA_ENV == "VSTOCK_SUITE_VALSA"
    assert flags.SUITE_GAVOTTA_ENV == "VSTOCK_SUITE_GAVOTTA"
    assert flags.SUITE_SCHOTTISH_ENV == "VSTOCK_SUITE_SCHOTTISH"
    assert flags.SUITE_CHOROS1_ENV == "VSTOCK_SUITE_CHOROS1"


def test_suite_movement_map_is_the_four_remaining_flags() -> None:
    assert flags.SUITE_MOVEMENT_ENVS == {
        "suite_valsa": "VSTOCK_SUITE_VALSA",
        "suite_gavotta": "VSTOCK_SUITE_GAVOTTA",
        "suite_schottish": "VSTOCK_SUITE_SCHOTTISH",
        "suite_choros1": "VSTOCK_SUITE_CHOROS1",
    }
    assert flags.any_suite_movement_enabled() is False
    with flags.use_suite_schottish(True):
        assert flags.any_suite_movement_enabled() is True
    assert flags.any_suite_movement_enabled() is False


def test_unknown_suite_movement_is_a_loud_error() -> None:
    with pytest.raises(KeyError, match="unknown Suite movement"):
        flags.suite_movement_enabled("suite_nope")
    with pytest.raises(KeyError, match="unknown Suite movement"):
        flags.use_suite_movement("suite_nope")


@pytest.mark.parametrize(("env", "enabled", "_use"), FLAGS_WITH_IDS)
def test_missing_environment_is_off(monkeypatch, env, enabled, _use) -> None:
    monkeypatch.delenv(env, raising=False)
    assert enabled() is False


@pytest.mark.parametrize(("env", "enabled", "_use"), FLAGS_WITH_IDS)
@pytest.mark.parametrize("value", ENABLED_VALUES)
def test_truthy_tokens_turn_a_flag_on(monkeypatch, env, enabled, _use, value) -> None:
    monkeypatch.setenv(env, value)
    assert enabled() is True


@pytest.mark.parametrize(("env", "enabled", "_use"), FLAGS_WITH_IDS)
@pytest.mark.parametrize("value", DISABLED_VALUES)
def test_falsy_and_unknown_tokens_stay_off(
    monkeypatch, env, enabled, _use, value
) -> None:
    monkeypatch.setenv(env, value)
    assert enabled() is False


@pytest.mark.parametrize(("env", "enabled", "use"), FLAGS_WITH_IDS)
def test_override_wins_over_environment_and_restores(
    monkeypatch, env, enabled, use
) -> None:
    monkeypatch.delenv(env, raising=False)
    with use(True):
        assert enabled() is True
    assert enabled() is False

    monkeypatch.setenv(env, "on")
    assert enabled() is True
    with use(False):
        assert enabled() is False
    assert enabled() is True


@pytest.mark.parametrize(("env", "enabled", "use"), FLAGS_WITH_IDS)
def test_override_restores_after_an_exception(monkeypatch, env, enabled, use) -> None:
    monkeypatch.setenv(env, "on")
    with pytest.raises(RuntimeError):
        with use(False):
            assert enabled() is False
            raise RuntimeError("boom")
    assert enabled() is True


@pytest.mark.parametrize(("env", "enabled", "use"), FLAGS_WITH_IDS)
def test_nested_overrides_restore_each_level(monkeypatch, env, enabled, use) -> None:
    monkeypatch.delenv(env, raising=False)
    with use(True):
        assert enabled() is True
        with use(False):
            assert enabled() is False
        assert enabled() is True
    assert enabled() is False


def test_barrios_reads_the_existing_owner_flag(monkeypatch) -> None:
    monkeypatch.delenv(barrios.BARRIOS_PERIOD_ENV, raising=False)
    assert flags.barrios_period_enabled() is False

    monkeypatch.setenv(barrios.BARRIOS_PERIOD_ENV, "on")
    assert flags.barrios_period_enabled() is True
    with barrios.use_barrios_period(False):
        assert flags.barrios_period_enabled() is False
    assert flags.barrios_period_enabled() is True


def test_barrios_delegates_instead_of_reading_its_own_flag(monkeypatch) -> None:
    calls: list[bool] = []

    def spy() -> bool:
        calls.append(True)
        return True

    monkeypatch.setattr(barrios, "barrios_period_enabled", spy)
    assert flags.barrios_period_enabled() is True
    assert calls == [True]
