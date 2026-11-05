"""Feature-gated production sentences for Villa, Suite Mazurka, and Brouwer.

Every flag defaults off and must leave the historical render byte-identical.
On, the gate must register exactly its own sentence, render the candidate
figures, and remove the entry again when the context exits. The Barrios period
stays the first gate and is checked here for cross-ensemble interference.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

import app.sonify.guitar_barrios_period as barrios
import app.sonify.guitar_brouwer_production as brouwer
import app.sonify.guitar_patterns as patterns
import app.sonify.guitar_suite_mazurka as suite
import app.sonify.guitar_villa_production as villa
from app.sonify import production_flags as flags
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34, METER_44, FormSection, FormSpec
from app.sonify.guitar_brouwer_figures import BROUWER_ETUDE, BROUWER_NOVIEMBRE
from app.sonify.guitar_villa_figures import VILLA_ARPEGGIO, VILLA_CHORD_MELODY
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.program import guitar_form_description
from app.sonify.render import render

ENABLED_VALUES = ("1", "true", "TRUE", "yes", "on", " On ")
DISABLED_VALUES = ("", "0", "false", "no", "off", "rollback", "banana", "2")

# Rendered from this exact fixture before the gates existed. Off must not move.
VILLA_OFF_DIGEST = (
    "45c4f172e990c2c3fb204c9c01e7c2df33d62e4becd1c71b555390e692c6b51f"
)
SUITE_OFF_DIGEST = (
    "a958682cf3dc16f5922ac415d3e541d1fee0ffd384bc8cb896993fd67b69e1b1"
)
BROUWER_OFF_DIGEST = (
    "702224c05a8d0da6a4aaa4f0a73b0210fb1894eed00c699e409659e3725346de"
)


@pytest.fixture(autouse=True)
def _registry_does_not_leak():
    before = dict(specs.SENTENCE_SPECS)
    yield
    assert dict(specs.SENTENCE_SPECS) == before


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


def _spy(monkeypatch, module, name: str, calls: list) -> None:
    original = getattr(module, name)

    def spy(ctx, bar, *args, **kwargs):
        calls.append(bar)
        return original(ctx, bar, *args, **kwargs)

    monkeypatch.setattr(module, name, spy)


def _spy_figure(monkeypatch, module, name: str) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []
    original = getattr(module, name)

    def spy(ctx, bar, phrase, figure):
        calls.append((bar, figure))
        return original(ctx, bar, phrase, figure)

    monkeypatch.setattr(module, name, spy)
    return calls


def _spy_pen(monkeypatch, module, name: str) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []
    original = getattr(module, name)

    def spy(pen, figure):
        calls.append((pen.bar, figure))
        return original(pen, figure)

    monkeypatch.setattr(module, name, spy)
    return calls


# ---------------------------------------------------------------------------
# flag-off parity


@pytest.mark.parametrize(
    ("env", "ensemble", "meter", "bars", "baseline"),
    (
        (flags.VILLA_PRODUCTION_ENV, "villa", METER_44, 6, VILLA_OFF_DIGEST),
        (flags.SUITE_MAZURKA_ENV, "villa", METER_34, 8, SUITE_OFF_DIGEST),
        (flags.BROUWER_PRODUCTION_ENV, "brouwer", METER_44, 6, BROUWER_OFF_DIGEST),
    ),
    ids=("villa", "suite_mazurka", "brouwer"),
)
def test_off_is_the_historical_render(
    monkeypatch, env, ensemble, meter, bars, baseline
) -> None:
    monkeypatch.delenv(env, raising=False)
    assert _digest(_render(ensemble, meter, bars)) == baseline

    # Every spelling that is not a true token, including a rollback value,
    # renders the same score as the default.
    for value in DISABLED_VALUES:
        monkeypatch.setenv(env, value)
        assert _digest(_render(ensemble, meter, bars)) == baseline, value


def test_villa_off_keeps_the_existing_bar_writer(monkeypatch) -> None:
    monkeypatch.delenv(flags.VILLA_PRODUCTION_ENV, raising=False)
    old_calls: list[int] = []
    _spy(monkeypatch, patterns, "_render_villa_bar", old_calls)
    figure_calls = _spy_figure(monkeypatch, villa, "render_villa_figure")

    _render("villa", METER_44, 6)

    assert old_calls, "flag off must still call _render_villa_bar"
    assert figure_calls == []


def test_brouwer_off_keeps_the_existing_etude_writer(monkeypatch) -> None:
    monkeypatch.delenv(flags.BROUWER_PRODUCTION_ENV, raising=False)
    old_calls: list[int] = []
    _spy(monkeypatch, patterns, "_render_etude_bar", old_calls)
    figure_calls = _spy_pen(monkeypatch, brouwer, "render_brouwer_figure")

    _render("brouwer", METER_44, 6)

    assert old_calls, "flag off must still call _render_etude_bar"
    assert figure_calls == []


# ---------------------------------------------------------------------------
# Villa


def test_villa_on_registers_and_renders_the_aba(monkeypatch) -> None:
    off = _digest(_render("villa", METER_44, 6))
    calls = _spy_figure(monkeypatch, villa, "render_villa_figure")

    with villa.use_villa_aba(True):
        assert specs.SENTENCE_SPECS.get(villa.VILLA_KEY) == (villa.VILLA_ABA,)
        assert specs.plan_sentence("villa_pattern", "4/4", 6, 0) == [
            (VILLA_ARPEGGIO, (0,)),
            (VILLA_CHORD_MELODY, (1,)),
            (VILLA_ARPEGGIO, (2,)),
            (VILLA_ARPEGGIO, (3,)),
            (VILLA_CHORD_MELODY, (4,)),
            (VILLA_ARPEGGIO, (5,)),
        ]

        on = _render("villa", METER_44, 6)

        assert calls == [
            (0, VILLA_ARPEGGIO),
            (1, VILLA_CHORD_MELODY),
            (2, VILLA_ARPEGGIO),
            (3, VILLA_ARPEGGIO),
            (4, VILLA_CHORD_MELODY),
            (5, VILLA_ARPEGGIO),
        ]
        assert on.divisions == 2
        assert {event.bar for event in on.lead} == set(range(6))
        assert _digest(on) != off

    assert villa.VILLA_KEY not in specs.SENTENCE_SPECS
    assert specs.plan_sentence("villa_pattern", "4/4", 6, 0) is None
    assert _digest(_render("villa", METER_44, 6)) == off


def test_villa_on_falls_back_off_meter_or_frame(monkeypatch) -> None:
    # The candidate is 4/4 only: a 3/4 movement keeps the historical path.
    off = _digest(_render("villa", METER_34, 8))
    calls = _spy_figure(monkeypatch, villa, "render_villa_figure")
    with villa.use_villa_aba(True):
        on = _render("villa", METER_34, 8)
    assert calls == []
    assert _digest(on) == off

    # A pedal frame is never overwritten.
    framed = FormSpec(
        6,
        120,
        (
            FormSection(0, 1, "intro", 0),
            FormSection(1, 6, "phrase", 0),
        ),
        meter=METER_44,
    )
    with compose_params({}):
        off = render(
            _bars(6), variant="guitar", ensemble="villa", form=framed, framed=True
        )
    calls = _spy_figure(monkeypatch, villa, "render_villa_figure")
    with villa.use_villa_aba(True):
        with compose_params({}):
            on = render(
                _bars(6),
                variant="guitar",
                ensemble="villa",
                form=framed,
                framed=True,
            )
    assert calls == []
    assert _digest(on) == _digest(off)


def test_villa_env_auditions_without_the_context(monkeypatch) -> None:
    monkeypatch.setenv(flags.VILLA_PRODUCTION_ENV, "on")
    calls = _spy_figure(monkeypatch, villa, "render_villa_figure")
    try:
        score = _render("villa", METER_44, 6)
        assert len(calls) == 6
        assert villa.VILLA_KEY in specs.SENTENCE_SPECS
        assert score.divisions == 2
    finally:
        villa.unregister()
    assert villa.VILLA_KEY not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# Suite Mazurka


def test_suite_on_registers_selects_and_renders_the_aaba(monkeypatch) -> None:
    off = _digest(_render("villa", METER_34, 8))
    calls = _spy_figure(monkeypatch, suite, "render_villa_figure")

    with suite.use_suite_mazurka_aba(True):
        assert specs.SENTENCE_SPECS.get(suite.SUITE_MAZURKA_KEY) == (
            suite.SUITE_MAZURKA_AABA,
        )
        assert specs.plan_sentence("suite_mazurka", "3/4", 8, 0) == [
            (VILLA_ARPEGGIO, (0,)),
            (VILLA_ARPEGGIO, (1,)),
            (VILLA_CHORD_MELODY, (2,)),
            (VILLA_ARPEGGIO, (3,)),
            (VILLA_ARPEGGIO, (4,)),
            (VILLA_ARPEGGIO, (5,)),
            (VILLA_CHORD_MELODY, (6,)),
            (VILLA_ARPEGGIO, (7,)),
        ]

        on = _render("villa", METER_34, 8)

        assert calls == [
            (0, VILLA_ARPEGGIO),
            (1, VILLA_ARPEGGIO),
            (2, VILLA_CHORD_MELODY),
            (3, VILLA_ARPEGGIO),
            (4, VILLA_ARPEGGIO),
            (5, VILLA_ARPEGGIO),
            (6, VILLA_CHORD_MELODY),
            (7, VILLA_ARPEGGIO),
        ]
        assert on.divisions == 2
        assert {event.bar for event in on.lead} == set(range(8))
        assert _digest(on) != off
        assert (
            guitar_form_description(
                _bars(8),
                ensemble="villa",
                form=_form(8, METER_34),
            )
            == "Mazurka-Choro"
        )

    assert suite.SUITE_MAZURKA_KEY not in specs.SENTENCE_SPECS
    assert specs.plan_sentence("suite_mazurka", "3/4", 8, 0) is None
    assert _digest(_render("villa", METER_34, 8)) == off


def test_suite_pattern_taxonomy_is_a_topic_with_a_title(monkeypatch) -> None:
    from app.sonify.pattern_registry import PATTERN_META
    from app.sonify.program import pattern_title

    monkeypatch.delenv(flags.SUITE_MAZURKA_ENV, raising=False)
    found = PATTERN_META[suite.SUITE_MAZURKA_PATTERN]
    assert found == suite.SUITE_MAZURKA_META
    assert found.level == "topic"
    assert pattern_title(suite.SUITE_MAZURKA_PATTERN, "villa") == "Mazurka-Choro"


def test_suite_on_falls_back_when_the_movement_is_too_short(monkeypatch) -> None:
    # The spec tiles four bars; a three-bar 3/4 movement keeps the Villa path.
    off = _digest(_render("villa", METER_34, 3))
    calls = _spy_figure(monkeypatch, suite, "render_villa_figure")
    with suite.use_suite_mazurka_aba(True):
        on = _render("villa", METER_34, 3)
    assert calls == []
    assert _digest(on) == off
    assert suite.SUITE_MAZURKA_KEY not in specs.SENTENCE_SPECS


def test_suite_on_falls_back_in_4_4(monkeypatch) -> None:
    off = _digest(_render("villa", METER_44, 6))
    calls = _spy_figure(monkeypatch, suite, "render_villa_figure")
    with suite.use_suite_mazurka_aba(True):
        on = _render("villa", METER_44, 6)
    assert calls == []
    assert _digest(on) == off


def test_suite_selection_is_the_same_predicate_as_render(monkeypatch) -> None:
    with compose_params({}):
        with suite.use_suite_mazurka_aba(True):
            ctx, _phrases = _patterns_context("villa", METER_34, 8)
            assert patterns._patterns(ctx) == ["suite_mazurka"]
            short, _ = _patterns_context("villa", METER_34, 3)
            assert "suite_mazurka" not in patterns._patterns(short)
            other_meter, _ = _patterns_context("villa", METER_44, 6)
            assert "suite_mazurka" not in patterns._patterns(other_meter)


def test_suite_ensure_registered_refuses_to_replace_a_different_spec() -> None:
    other = dataclasses.replace(suite.SUITE_MAZURKA_AABA, id="future_archetype")
    specs.SENTENCE_SPECS[suite.SUITE_MAZURKA_KEY] = (other,)
    try:
        with pytest.raises(ValueError, match="would replace it"):
            suite.ensure_registered()
    finally:
        del specs.SENTENCE_SPECS[suite.SUITE_MAZURKA_KEY]
    assert suite.SUITE_MAZURKA_KEY not in specs.SENTENCE_SPECS


def test_suite_env_auditions_without_the_context(monkeypatch) -> None:
    monkeypatch.setenv(flags.SUITE_MAZURKA_ENV, "on")
    calls = _spy_figure(monkeypatch, suite, "render_villa_figure")
    try:
        score = _render("villa", METER_34, 8)
        assert len(calls) == 8
        assert suite.SUITE_MAZURKA_KEY in specs.SENTENCE_SPECS
        assert score.divisions == 2
    finally:
        suite.unregister()
    assert suite.SUITE_MAZURKA_KEY not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# Brouwer


def test_brouwer_on_registers_and_renders_the_aba(monkeypatch) -> None:
    off = _digest(_render("brouwer", METER_44, 6))
    calls = _spy_pen(monkeypatch, brouwer, "render_brouwer_figure")

    with brouwer.use_brouwer_aba(True):
        assert specs.SENTENCE_SPECS.get(brouwer.BROUWER_KEY) == (
            brouwer.BROUWER_ABA,
        )
        assert specs.plan_sentence("brouwer_etude", "4/4", 6, 0) == [
            (BROUWER_ETUDE, (0,)),
            (BROUWER_NOVIEMBRE, (1,)),
            (BROUWER_ETUDE, (2,)),
            (BROUWER_ETUDE, (3,)),
            (BROUWER_NOVIEMBRE, (4,)),
            (BROUWER_ETUDE, (5,)),
        ]

        on = _render("brouwer", METER_44, 6)

        assert calls == [
            (0, BROUWER_ETUDE),
            (1, BROUWER_NOVIEMBRE),
            (2, BROUWER_ETUDE),
            (3, BROUWER_ETUDE),
            (4, BROUWER_NOVIEMBRE),
            (5, BROUWER_ETUDE),
        ]
        assert on.divisions == 2
        assert {event.bar for event in on.lead} == set(range(6))
        assert _digest(on) != off

    assert brouwer.BROUWER_KEY not in specs.SENTENCE_SPECS
    assert specs.plan_sentence("brouwer_etude", "4/4", 6, 0) is None
    assert _digest(_render("brouwer", METER_44, 6)) == off


def test_brouwer_on_falls_back_off_meter(monkeypatch) -> None:
    off = _digest(_render("brouwer", METER_34, 6))
    calls = _spy_pen(monkeypatch, brouwer, "render_brouwer_figure")
    with brouwer.use_brouwer_aba(True):
        on = _render("brouwer", METER_34, 6)
    assert calls == []
    assert _digest(on) == off


def test_brouwer_env_auditions_without_the_context(monkeypatch) -> None:
    monkeypatch.setenv(flags.BROUWER_PRODUCTION_ENV, "on")
    calls = _spy_pen(monkeypatch, brouwer, "render_brouwer_figure")
    try:
        score = _render("brouwer", METER_44, 6)
        assert len(calls) == 6
        assert brouwer.BROUWER_KEY in specs.SENTENCE_SPECS
        assert score.divisions == 2
    finally:
        brouwer.unregister()
    assert brouwer.BROUWER_KEY not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# context cleanup and Barrios delegation


def test_nested_contexts_remove_only_their_own_registration() -> None:
    contexts = (
        (villa.use_villa_aba, villa.VILLA_KEY),
        (suite.use_suite_mazurka_aba, suite.SUITE_MAZURKA_KEY),
        (brouwer.use_brouwer_aba, brouwer.BROUWER_KEY),
    )
    for cm, key in contexts:
        assert key not in specs.SENTENCE_SPECS
        with cm(True):
            assert key in specs.SENTENCE_SPECS
            with cm(True):
                assert key in specs.SENTENCE_SPECS
            assert key in specs.SENTENCE_SPECS
        assert key not in specs.SENTENCE_SPECS


def test_barrios_period_still_delegates_and_renders_alongside_the_new_gates(
    monkeypatch,
) -> None:
    monkeypatch.delenv(barrios.BARRIOS_PERIOD_ENV, raising=False)
    assert flags.barrios_period_enabled() is False
    with barrios.use_barrios_period(True):
        assert flags.barrios_period_enabled() is True

    calls: list[tuple[int, int]] = []
    original = barrios.render_barrios_figure

    def spy(pen, figure):
        calls.append((pen.bar, figure))
        return original(pen, figure)

    monkeypatch.setattr(barrios, "render_barrios_figure", spy)
    with (
        barrios.use_barrios_period(True),
        villa.use_villa_aba(True),
        suite.use_suite_mazurka_aba(True),
        brouwer.use_brouwer_aba(True),
    ):
        score = _render("barrios", METER_44, 12)

    assert len(calls) == 12
    assert score.divisions == 4
    assert barrios.BARRIOS_PERIOD_KEY not in specs.SENTENCE_SPECS
    assert villa.VILLA_KEY not in specs.SENTENCE_SPECS
    assert suite.SUITE_MAZURKA_KEY not in specs.SENTENCE_SPECS
    assert brouwer.BROUWER_KEY not in specs.SENTENCE_SPECS


# ---------------------------------------------------------------------------
# authored candidates


def test_production_specs_match_the_authored_candidates() -> None:
    from app.studio.candidates import villa_candidate_spec
    from app.studio.candidates.brouwer import brouwer_aba_spec
    from app.studio.candidates.suite_mazurka import suite_mazurka_spec

    assert villa.VILLA_ABA == villa_candidate_spec()
    assert brouwer.BROUWER_ABA == brouwer_aba_spec()
    assert suite.SUITE_MAZURKA_AABA == dataclasses.replace(
        suite_mazurka_spec(), pattern=suite.SUITE_MAZURKA_PATTERN
    )


# ---------------------------------------------------------------------------
# helpers


def _patterns_context(ensemble: str, meter, bars: int):
    from tests.guitar_fixture import meter_named, pattern_case

    meter_name = "3/4" if meter is METER_34 else "4/4"
    section = FormSection(0, bars, "phrase", 0)
    return pattern_case(
        "probe",
        meter_named(meter_name),
        ensemble=ensemble,
        mood="calm",
        band="mf",
        bpm=96,
        bars=bars,
        first_body=True,
        previous=[],
        section=section,
    )
