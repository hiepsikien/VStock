"""Final local-Studio stabilization gate.

This module is the release regression that sits on top of the feature tests. It
does not change production behaviour: every case pins the current contract and
fails loudly when a future change moves an off path, drops the shared tail, or
lets an authored micro-velocity override reach a render with the writer flag
off.

Covered here
------------
* flag off / on for the full production tail of Villa, Suite Mazurka, Brouwer,
  and the Barrios Cathedral period, with pinned deterministic digests;
* the shared tail really runs wave, scale, hairpin restamp, and the post-wave
  pinned check for all four gated families;
* a slot micro-velocity override changes production output only when
  ``VSTOCK_MICRO_VELOCITY_WRITERS`` is on, for all four gated families;
* a pattern/texture micro-velocity override reaches the production tail with
  only velocity changed, and is byte-identical when the writer flag is off;
* the texture interpreter dispatches 4/4 and 3/4 to different specs and falls
  back to code for every non-matching context or a failing registry;
* the release checklist paths/commands are still present.

Local release checklist
-----------------------
Run from ``backend`` unless a line says otherwise.

Backend focused gate
  [ ] ``python -m pytest tests/test_studio_stabilization_gate.py -q``
  [ ] ``python -m pytest tests/test_studio_e2e.py -q``
  [ ] ``python -m pytest tests/test_studio_*.py -q``
  [ ] ``python -m pytest -q`` (full backend)

Frontend gate (only when ``node_modules`` is installed; no network fetch)
  [ ] ``npm run test:studio`` from the repository root
  [ ] ``npm run test:unit`` for the complete unit gate
  [ ] ``npm run web`` and open the Studio pill/room as a manual smoke test

Expected invariants
  [ ] No flag defaults to on; every off path is byte-identical.
  [ ] No test leaves a sentence in ``SENTENCE_SPECS``.
  [ ] No Studio call registers a candidate; candidates stay preview-only.
  [ ] No external network access; ``test_studio_e2e`` enforces the socket guard.
  [ ] No frontend command is run when ``node_modules`` is absent, so the gate
      never falls through to an implicit ``npx`` download.

Hand-off
  [ ] Record exact pytest counts and any skipped frontend step with its reason.
  [ ] Report a real bug plus the smallest safe fix; do not self-commit.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import app.sonify.guitar_barrios_period as barrios
import app.sonify.guitar_brouwer_production as brouwer
import app.sonify.guitar_scale_passages as scale_passages
import app.sonify.guitar_suite_choros1 as suite_choros1
import app.sonify.guitar_suite_gavotta as suite_gavotta
import app.sonify.guitar_suite_gate as suite_gate
import app.sonify.guitar_suite_mazurka as suite
import app.sonify.guitar_suite_schottish as suite_schottish
import app.sonify.guitar_suite_valsa as suite_valsa
import app.sonify.guitar_villa_production as villa
import app.sonify.guitar_wave as guitar_wave
import app.sonify.micro_velocity_writer as micro_writer
import app.sonify.texture_interpreter as texture_interpreter
import app.sonify.texture_registry as texture_registry
from app.sonify import production_flags as flags
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34, METER_44, METER_68, FormSection, FormSpec
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.texture_interpreter import (
    INTERPRETER_PATTERN,
    dispatch_key,
    dispatch_spec,
    reset_spec_cache,
    use_texture_interpreter,
)
from app.studio.micro_velocity import MicroVelocity, VelocityOffset
from tests import texture_interpreter_fixture as fixture

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

# The flag-off digests are the historical renders. They match
# ``test_production_wiring`` and ``test_barrios_period_production``.
VILLA_OFF_DIGEST = (
    "45c4f172e990c2c3fb204c9c01e7c2df33d62e4becd1c71b555390e692c6b51f"
)
SUITE_OFF_DIGEST = (
    "a958682cf3dc16f5922ac415d3e541d1fee0ffd384bc8cb896993fd67b69e1b1"
)
BROUWER_OFF_DIGEST = (
    "702224c05a8d0da6a4aaa4f0a73b0210fb1894eed00c699e409659e3725346de"
)
BARRIOS_OFF_DIGEST = (
    "84aa7a873175dc7f6912a4bd256c97ff2f4d1919ccaf7a7a9a86703b3cd5e090"
)

# Flag-on renders with the micro-velocity writer flag at its default (off).
# These are determinism anchors, not an expectation about future authoring.
VILLA_ON_DIGEST = (
    "769bd78e6e7e86cda2d8cdcaaa5b9ba5fbf32f9f8970a0bc84852a67315750bc"
)
SUITE_ON_DIGEST = (
    "e0ba430c328d47a7849e45e421287d7597284cd0b294f595cdd46d529ae586c5"
)
BROUWER_ON_DIGEST = (
    "e8d192965de3de370f411bed3c1f53936033c7bd84d4d9e20b445ee36b418f9e"
)
BARRIOS_ON_DIGEST = (
    "fc86d04b572f1921492a7fe19d32f527174e6df7e6ec6ff46ff860f7686d5473"
)

VALSA_ON_DIGEST = "251257f146c1e01e1278c49331e834f957ee6717e88c76c272c475153c05fef9"
GAVOTTA_OFF_DIGEST = "597bc984befaf22568a2f9050d74fdf64f5151c00ebd33a6f7e49fa3989571b5"
GAVOTTA_ON_DIGEST = "4566225cf0c8ca043f8df99668b7deb62e8a54b1e7c312333f76a193457b52b0"
SCHOTTISH_ON_DIGEST = "2dfa8721e53a15a65fac6614fe3a48d1beb88981fb4017666447a1d3736459f4"
CHOROS1_ON_DIGEST = "698953a982e382253a7d6a342aa0248e705197494f7ff6adc2666ef23ca76046"

@dataclasses.dataclass(frozen=True)
class _GateCase:
    """One feature-gated production family."""

    context: Any
    ensemble: str
    meter: Any
    bars: int
    off_digest: str
    on_digest: str
    key: Any
    spec: Any
    slot_index: int
    pattern: str
    pattern_meter: str


GATED_CASES = (
    pytest.param(
        _GateCase(
            villa.use_villa_aba,
            "villa",
            METER_44,
            6,
            VILLA_OFF_DIGEST,
            VILLA_ON_DIGEST,
            villa.VILLA_KEY,
            villa.VILLA_ABA,
            1,
            "villa_pattern",
            "4/4",
        ),
        id="villa",
    ),
    pytest.param(
        _GateCase(
            suite.use_suite_mazurka_aba,
            "villa",
            METER_34,
            8,
            SUITE_OFF_DIGEST,
            SUITE_ON_DIGEST,
            suite.SUITE_MAZURKA_KEY,
            suite.SUITE_MAZURKA_AABA,
            2,
            suite.SUITE_MAZURKA_PATTERN,
            suite.SUITE_MAZURKA_METER,
        ),
        id="suite_mazurka",
    ),
    pytest.param(
        _GateCase(
            brouwer.use_brouwer_aba,
            "brouwer",
            METER_44,
            6,
            BROUWER_OFF_DIGEST,
            BROUWER_ON_DIGEST,
            brouwer.BROUWER_KEY,
            brouwer.BROUWER_ABA,
            1,
            "brouwer_etude",
            "4/4",
        ),
        id="brouwer",
    ),
    pytest.param(
        _GateCase(
            barrios.use_barrios_period,
            "barrios",
            METER_44,
            12,
            BARRIOS_OFF_DIGEST,
            BARRIOS_ON_DIGEST,
            barrios.BARRIOS_PERIOD_KEY,
            barrios.BARRIOS_CATHEDRAL_PERIOD,
            1,
            barrios.BARRIOS_PERIOD_PATTERN,
            barrios.BARRIOS_PERIOD_METER,
        ),
        id="barrios",
    ),
    pytest.param(
        _GateCase(
            suite_valsa.use_suite_valsa_period,
            "villa",
            METER_34,
            8,
            SUITE_OFF_DIGEST,
            VALSA_ON_DIGEST,
            suite_valsa.SUITE_VALSA_KEY,
            suite_valsa.SUITE_VALSA_PERIOD,
            1,
            suite_valsa.SUITE_VALSA_PATTERN,
            suite_valsa.SUITE_VALSA_METER,
        ),
        id="suite_valsa",
    ),
    pytest.param(
        _GateCase(
            suite_gavotta.use_suite_gavotta_baab,
            "villa",
            METER_44,
            8,
            GAVOTTA_OFF_DIGEST,
            GAVOTTA_ON_DIGEST,
            suite_gavotta.SUITE_GAVOTTA_KEY,
            suite_gavotta.SUITE_GAVOTTA_BAAB,
            1,
            suite_gavotta.SUITE_GAVOTTA_PATTERN,
            suite_gavotta.SUITE_GAVOTTA_METER,
        ),
        id="suite_gavotta",
    ),
    pytest.param(
        _GateCase(
            suite_schottish.use_suite_schottish_abab,
            "villa",
            METER_44,
            8,
            GAVOTTA_OFF_DIGEST,
            SCHOTTISH_ON_DIGEST,
            suite_schottish.SUITE_SCHOTTISH_KEY,
            suite_schottish.SUITE_SCHOTTISH_ABAB,
            1,
            suite_schottish.SUITE_SCHOTTISH_PATTERN,
            suite_schottish.SUITE_SCHOTTISH_METER,
        ),
        id="suite_schottish",
    ),
    pytest.param(
        _GateCase(
            suite_choros1.use_suite_choros1_abba,
            "villa",
            METER_44,
            8,
            GAVOTTA_OFF_DIGEST,
            CHOROS1_ON_DIGEST,
            suite_choros1.SUITE_CHOROS1_KEY,
            suite_choros1.SUITE_CHOROS1_ABBA,
            1,
            suite_choros1.SUITE_CHOROS1_PATTERN,
            suite_choros1.SUITE_CHOROS1_METER,
        ),
        id="suite_choros1",
    ),
)


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch):
    """Start every test from the production defaults and restore the registry."""
    for name in (
        flags.VILLA_PRODUCTION_ENV,
        flags.SUITE_MAZURKA_ENV,
        flags.SUITE_VALSA_ENV,
        flags.SUITE_GAVOTTA_ENV,
        flags.SUITE_SCHOTTISH_ENV,
        flags.SUITE_CHOROS1_ENV,
        flags.BROUWER_PRODUCTION_ENV,
        barrios.BARRIOS_PERIOD_ENV,
        micro_writer.WRITERS_FLAG,
        texture_interpreter.INTERPRETER_FLAG,
    ):
        monkeypatch.delenv(name, raising=False)

    before = dict(specs.SENTENCE_SPECS)
    reset_spec_cache()
    try:
        yield
    finally:
        specs.SENTENCE_SPECS.clear()
        specs.SENTENCE_SPECS.update(before)
        reset_spec_cache()


def _bars(count: int) -> list[Bar]:
    """Enough source bars that every musical bar has a moving close."""
    return [Bar(100.0 + (index % 4) * 40, 250.0) for index in range(count * 4)]


def _form(bars: int, meter) -> FormSpec:
    return FormSpec(
        bars,
        120,
        (FormSection(0, bars, "phrase", 0),),
        meter=meter,
    )


def _render(ensemble: str, meter, bars: int):
    with compose_params({}):
        return render(
            _bars(bars),
            variant="guitar",
            ensemble=ensemble,
            form=_form(bars, meter),
            framed=True,
        )


def _digest(score) -> str:
    payload = [
        (
            event.voice,
            event.bar,
            round(event.beat, 6),
            round(event.duration_beats, 6),
            event.midi,
            event.velocity,
            event.tie_start,
            event.tie_stop,
        )
        for voice in (score.lead, score.comp, score.bass)
        for event in voice
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _by_bar(score) -> dict[int, list[tuple]]:
    found: dict[int, list[tuple]] = {}
    for voice in (score.lead, score.comp, score.bass):
        for event in voice:
            found.setdefault(event.bar, []).append(
                (
                    event.voice,
                    round(event.beat, 6),
                    round(event.duration_beats, 6),
                    event.midi,
                    event.velocity,
                    event.tie_start,
                    event.tie_stop,
                )
            )
    return found


def _contour(offset: int) -> MicroVelocity:
    return MicroVelocity(
        notes=(VelocityOffset(bar=0, beat=0.0, voice=1, offset=offset),)
    )


def _with_slot_contour(
    spec: specs.SentenceSpec,
    slot_index: int,
    contour: MicroVelocity,
) -> specs.SentenceSpec:
    slots = list(spec.slots)
    slots[slot_index] = replace(slots[slot_index], micro_velocity=contour)
    return dataclasses.replace(spec, slots=tuple(slots))


@contextmanager
def _installed(monkeypatch: pytest.MonkeyPatch, module: Any, key: Any, spec):
    """Install one authored spec without letting the owner replace it."""
    monkeypatch.setattr(module, "ensure_registered", lambda *args, **kwargs: False)
    monkeypatch.setattr(suite_gate, "ensure_registered", lambda *args, **kwargs: False)
    previous = specs.SENTENCE_SPECS.get(key)
    specs.SENTENCE_SPECS[key] = (spec,)
    try:
        yield
    finally:
        if previous is None:
            specs.SENTENCE_SPECS.pop(key, None)
        else:
            specs.SENTENCE_SPECS[key] = previous


# ---------------------------------------------------------------------------
# Full production tail: off/on parity and pinned digests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", GATED_CASES)
def test_flag_off_on_and_deterministic_digests(case: _GateCase) -> None:
    """The default is the historical render; on is new, stable, and repeatable."""
    off = _digest(_render(case.ensemble, case.meter, case.bars))
    assert off == case.off_digest

    with case.context(True):
        first = _digest(_render(case.ensemble, case.meter, case.bars))
        second = _digest(_render(case.ensemble, case.meter, case.bars))
        third = _digest(_render(case.ensemble, case.meter, case.bars))

    assert first == second == third == case.on_digest
    assert first != off

    # The context removed only its own entry, so the off path is restored.
    assert _digest(_render(case.ensemble, case.meter, case.bars)) == off


@pytest.mark.parametrize("case", GATED_CASES)
def test_gated_render_runs_the_whole_shared_tail(
    monkeypatch: pytest.MonkeyPatch, case: _GateCase
) -> None:
    wave_calls: list[int] = []
    scale_calls: list[int] = []
    hairpin_calls: list[int] = []
    pinned_checks: list[int] = []

    original_wave = guitar_wave.apply_guitar_wave

    def wave_spy(ctx, lead, support, low, patterns=None, relaxed=None, scale_eighths=None):
        wave_calls.append(ctx.bars)
        return original_wave(ctx, lead, support, low, patterns, relaxed, scale_eighths)

    original_scale = scale_passages.apply_scale_passages

    def scale_spy(ctx, patterns_, lead, support, low):
        scale_calls.append(ctx.bars)
        return original_scale(ctx, patterns_, lead, support, low)

    original_hairpin = scale_passages.restamp_passage_hairpins

    def hairpin_spy(ctx, patterns_, plan, lead, written_lead):
        hairpin_calls.append(ctx.bars)
        return original_hairpin(ctx, patterns_, plan, lead, written_lead)

    original_check = micro_writer.check_occurrences

    def check_spy(events):
        pinned_checks.append(len(events))
        return original_check(events)

    monkeypatch.setattr(guitar_wave, "apply_guitar_wave", wave_spy)
    monkeypatch.setattr(scale_passages, "apply_scale_passages", scale_spy)
    monkeypatch.setattr(scale_passages, "restamp_passage_hairpins", hairpin_spy)
    monkeypatch.setattr(micro_writer, "check_occurrences", check_spy)
    monkeypatch.setenv(micro_writer.WRITERS_FLAG, "on")

    with case.context(True):
        _render(case.ensemble, case.meter, case.bars)

    assert wave_calls == [case.bars], "the gated path skipped the volume wave"
    assert scale_calls == [case.bars], "the gated path skipped scale passages"
    assert hairpin_calls == [case.bars], "the gated path skipped the hairpin restamp"
    assert len(pinned_checks) == 1, "the post-wave pinned check must run once"
    assert pinned_checks[0] > 0


# ---------------------------------------------------------------------------
# Slot and texture micro-velocity overrides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", GATED_CASES)
def test_slot_override_reaches_production_only_with_writers_on(
    monkeypatch: pytest.MonkeyPatch, case: _GateCase
) -> None:
    override = _with_slot_contour(case.spec, case.slot_index, _contour(10))

    with case.context(True):
        slot_bars = {
            bar
            for slot in specs.plan_slots(
                case.pattern, case.pattern_meter, case.bars, 0
            )
            or ()
            if slot.slot_index == case.slot_index
            for bar in slot.bars
        }
        assert slot_bars, "the chosen slot must occur in this movement"

        # Writers on: the authored slot contour changes the production output.
        monkeypatch.setenv(micro_writer.WRITERS_FLAG, "on")
        with _installed(
            monkeypatch, _owner(case.context), case.key, case.spec
        ):
            base = _render(case.ensemble, case.meter, case.bars)
        with _installed(
            monkeypatch, _owner(case.context), case.key, override
        ):
            changed = _render(case.ensemble, case.meter, case.bars)

        base_bars = _by_bar(base)
        changed_bars = _by_bar(changed)
        assert sorted(base_bars) == sorted(changed_bars)
        differing = [
            bar for bar in base_bars if base_bars[bar] != changed_bars[bar]
        ]
        assert differing, "the slot override never reached the render"
        assert set(differing) <= slot_bars

        for bar in base_bars:
            if bar not in differing:
                assert changed_bars[bar] == base_bars[bar], bar
                continue
            # Velocity-only: pitch, rhythm, and ties are untouched.
            assert [
                event[:4] + event[5:] for event in changed_bars[bar]
            ] == [event[:4] + event[5:] for event in base_bars[bar]], bar
            assert any(
                after[4] > before[4]
                for before, after in zip(base_bars[bar], changed_bars[bar])
                if before[0] == 1
            ), bar

        # Writers off: the same authored override is byte-identical.
        monkeypatch.delenv(micro_writer.WRITERS_FLAG)
        with _installed(
            monkeypatch, _owner(case.context), case.key, case.spec
        ):
            base_off = _render(case.ensemble, case.meter, case.bars)
        with _installed(
            monkeypatch, _owner(case.context), case.key, override
        ):
            off = _render(case.ensemble, case.meter, case.bars)

    assert _digest(off) == _digest(base_off)


_OWNER_BY_CONTEXT = {
    villa.use_villa_aba: villa,
    suite.use_suite_mazurka_aba: suite,
    brouwer.use_brouwer_aba: brouwer,
    barrios.use_barrios_period: barrios,
    suite_valsa.use_suite_valsa_period: suite_valsa,
    suite_gavotta.use_suite_gavotta_baab: suite_gavotta,
    suite_schottish.use_suite_schottish_abab: suite_schottish,
    suite_choros1.use_suite_choros1_abba: suite_choros1,
}


def _owner(context) -> Any:
    """Map a gate context back to its owner module for the install helper."""
    return _OWNER_BY_CONTEXT[context]


@pytest.mark.parametrize("case", GATED_CASES)
def test_texture_override_reaches_the_tail_only_with_writers_on(
    monkeypatch: pytest.MonkeyPatch, case: _GateCase
) -> None:
    """The pattern-level contour is applied after figure/slot, before the wave."""
    owner = _owner(case.context)
    original = owner.render_sentence
    texture = _contour(10)

    def with_texture(ctx):
        sentence = original(ctx)
        if sentence is None:
            return None
        return dataclasses.replace(sentence, texture_contour=texture)

    with case.context(True):
        monkeypatch.setenv(micro_writer.WRITERS_FLAG, "on")
        base_on = _render(case.ensemble, case.meter, case.bars)
        monkeypatch.delenv(micro_writer.WRITERS_FLAG)
        base_off = _render(case.ensemble, case.meter, case.bars)

        monkeypatch.setattr(owner, "render_sentence", with_texture)
        monkeypatch.setenv(micro_writer.WRITERS_FLAG, "on")
        textured_on = _render(case.ensemble, case.meter, case.bars)
        monkeypatch.delenv(micro_writer.WRITERS_FLAG)
        textured_off = _render(case.ensemble, case.meter, case.bars)

    assert _digest(textured_on) != _digest(base_on)

    # Only the first bar is authored, and only its velocity may move.
    base_bars = _by_bar(base_on)
    changed_bars = _by_bar(textured_on)
    assert sorted(base_bars) == sorted(changed_bars)
    assert base_bars[0] != changed_bars[0]
    assert [
        event[:4] + event[5:] for event in changed_bars[0]
    ] == [event[:4] + event[5:] for event in base_bars[0]]
    for bar in base_bars:
        if bar != 0:
            assert changed_bars[bar] == base_bars[bar], bar

    assert _digest(textured_off) == _digest(base_off)


# ---------------------------------------------------------------------------
# Texture interpreter dispatch
# ---------------------------------------------------------------------------


def test_interpreter_dispatch_selects_44_and_34_and_falls_back() -> None:
    reset_spec_cache()
    ctx_44, _phrases = fixture.fixture_case()
    ctx_34, _phrases = fixture.fixture_case(fixture.SECOND_METER)

    match_44 = dispatch_spec(INTERPRETER_PATTERN, ctx_44)
    match_34 = dispatch_spec(INTERPRETER_PATTERN, ctx_34)

    assert match_44 is not None
    assert match_34 is not None
    assert match_44.spec.id == texture_interpreter.SPEC_ID
    assert match_34.spec.id == fixture.SECOND_SPEC_ID
    assert match_44.spec.id != match_34.spec.id
    assert dispatch_key(INTERPRETER_PATTERN, ctx_44)[1] != dispatch_key(
        INTERPRETER_PATTERN, ctx_34
    )[1]

    # Unknown pattern, wrong excerpt length, and a context the second spec
    # does not cover all fall back to code.
    assert dispatch_spec("villa_pattern", ctx_44) is None
    assert dispatch_spec(INTERPRETER_PATTERN, replace(ctx_44, bars=3)) is None
    assert dispatch_spec(INTERPRETER_PATTERN, replace(ctx_44, bar_beats=3.0)) is None
    six_eight, _phrases = fixture.fixture_case(METER_68)
    assert dispatch_spec(INTERPRETER_PATTERN, six_eight) is None


def test_interpreter_registry_failure_soft_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()

    original = texture_registry.load_default

    def explode(*_args, **_kwargs):
        raise RuntimeError("registry is unavailable")

    # Keep the cache handle so the fixture teardown can still clear it while
    # the failing loader is patched in.
    explode.cache_clear = original.cache_clear  # type: ignore[attr-defined]
    monkeypatch.setattr(texture_registry, "load_default", explode)

    assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
    with use_texture_interpreter(True):
        assert (
            texture_interpreter.render_chord_melody_bar(ctx, 0, phrases[0])
            is None
        )


# ---------------------------------------------------------------------------
# Release checklist wiring
# ---------------------------------------------------------------------------


def test_local_release_commands_are_wired() -> None:
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert {"test:studio", "test:unit", "web"} <= set(scripts)

    assert (BACKEND_ROOT / "pytest.ini").is_file()
    for name in (
        "test_studio_e2e.py",
        "test_production_wiring.py",
        "test_production_micro_velocity.py",
        "test_texture_interpreter.py",
        "test_studio_candidate_api.py",
        "test_studio_stabilization_gate.py",
    ):
        assert (BACKEND_ROOT / "tests" / name).is_file(), name
