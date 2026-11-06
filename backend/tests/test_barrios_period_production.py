"""The feature-gated Barrios Cathedral period in the production renderer.

Default off must be the current Barrios path. On must register the authored
`("preludio", "4/4")` spec and render `preludio -> tremolo -> preludio` through
the real per-bar figure renderer. Every test also asserts that it left the
global sentence registry exactly as it found it.
"""

from __future__ import annotations

import hashlib
import json

import pytest

import app.sonify.guitar_barrios_period as period
from app.sonify import sentence_specs as specs
from app.sonify.form import METER_44, FormSection, FormSpec
from app.sonify.guitar_barrios_figures import BARRIOS_PRELUDIO, BARRIOS_TREMOLO
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.render import render

PERIOD_KEY = period.BARRIOS_PERIOD_KEY
ENV = period.BARRIOS_PERIOD_ENV
ENABLED_VALUES = ("1", "true", "TRUE", "yes", "on", " On ")
DISABLED_VALUES = ("", "0", "false", "no", "off", "rollback", "banana", "2")


@pytest.fixture(autouse=True)
def _registry_does_not_leak():
    before = dict(specs.SENTENCE_SPECS)
    yield
    assert dict(specs.SENTENCE_SPECS) == before


def _bars(count: int) -> list[Bar]:
    """Enough source bars that every musical bar has a moving close."""
    return [Bar(100.0 + (index % 4) * 40, 250.0) for index in range(count * 4)]


def _form(bars: int = 12) -> FormSpec:
    return FormSpec(
        bars,
        120,
        (FormSection(0, bars, "phrase", 0),),
        meter=METER_44,
    )


def _render(form: FormSpec | None = None) -> object:
    body = _form() if form is None else form
    with compose_params({}):
        return render(
            _bars(body.bars),
            variant="guitar",
            ensemble="barrios",
            form=body,
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


def _spy_figures(monkeypatch) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []
    original = period.render_barrios_figure

    def spy(pen, figure):
        calls.append((pen.bar, figure))
        return original(pen, figure)

    monkeypatch.setattr(period, "render_barrios_figure", spy)
    return calls


def test_flag_defaults_off_and_unknown_values_roll_back(monkeypatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    assert period.barrios_period_enabled() is False
    for value in ENABLED_VALUES:
        monkeypatch.setenv(ENV, value)
        assert period.barrios_period_enabled() is True, value
    for value in DISABLED_VALUES:
        monkeypatch.setenv(ENV, value)
        assert period.barrios_period_enabled() is False, value


def test_context_override_can_roll_back_an_enabled_environment(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "on")
    assert period.barrios_period_enabled() is True
    with period.use_barrios_period(False):
        assert period.barrios_period_enabled() is False
        calls = _spy_figures(monkeypatch)
        _render()
        assert calls == []
    assert period.barrios_period_enabled() is True


def test_flag_off_is_the_existing_barrios_path(monkeypatch) -> None:
    monkeypatch.delenv(ENV, raising=False)
    before = dict(specs.SENTENCE_SPECS)
    calls = _spy_figures(monkeypatch)

    off = _render()

    assert PERIOD_KEY not in specs.SENTENCE_SPECS
    assert dict(specs.SENTENCE_SPECS) == before
    assert specs.plan_sentence("preludio", "4/4", 12, 0) is None
    assert calls == []

    # Every spelling that is not a true token, including a rollback value,
    # renders the same score as the default.
    baseline = _digest(off)
    for value in DISABLED_VALUES:
        monkeypatch.setenv(ENV, value)
        assert _digest(_render()) == baseline, value
    with period.use_barrios_period(False):
        assert _digest(_render()) == baseline


def test_flag_on_registers_and_renders_the_period(monkeypatch) -> None:
    off = _digest(_render())

    with period.use_barrios_period(True):
        assert specs.SENTENCE_SPECS.get(PERIOD_KEY) == (
            period.BARRIOS_CATHEDRAL_PERIOD,
        )
        assert specs.plan_sentence("preludio", "4/4", 12, 0) == [
            (BARRIOS_PRELUDIO, (0, 1, 2, 3)),
            (BARRIOS_TREMOLO, (4, 5, 6, 7)),
            (BARRIOS_PRELUDIO, (8, 9, 10, 11)),
        ]

        calls = _spy_figures(monkeypatch)
        on = _render()

        assert calls == [
            (0, BARRIOS_PRELUDIO),
            (1, BARRIOS_PRELUDIO),
            (2, BARRIOS_PRELUDIO),
            (3, BARRIOS_PRELUDIO),
            (4, BARRIOS_TREMOLO),
            (5, BARRIOS_TREMOLO),
            (6, BARRIOS_TREMOLO),
            (7, BARRIOS_TREMOLO),
            (8, BARRIOS_PRELUDIO),
            (9, BARRIOS_PRELUDIO),
            (10, BARRIOS_PRELUDIO),
            (11, BARRIOS_PRELUDIO),
        ]
        assert on.divisions == 4
        assert {event.bar for event in on.lead} == set(range(12))

        # The middle four bars are the sixteenth tremolo; the outer bars keep
        # the dotted preludio cells.
        tremolo = [event for event in on.lead if event.bar == 4]
        assert len(tremolo) == 16
        assert all(abs(event.duration_beats - 0.25) < 1e-9 for event in tremolo)
        opening = [event for event in on.lead if event.bar == 0]
        assert [event.duration_beats for event in opening] == [1.5, 0.5, 1.5, 0.5]

        assert _digest(on) != off

    assert PERIOD_KEY not in specs.SENTENCE_SPECS
    assert specs.plan_sentence("preludio", "4/4", 12, 0) is None
    assert _digest(_render()) == off


def test_flag_on_falls_back_when_the_plan_has_no_spans(monkeypatch) -> None:
    # The spec tiles exactly twelve bars. A sixteen-bar movement is eligible
    # only in length; the exact span declines it and the old path renders.
    off = _digest(_render(_form(16)))
    calls = _spy_figures(monkeypatch)
    with period.use_barrios_period(True):
        on = _render(_form(16))
    assert calls == []
    assert _digest(on) == off


def test_flag_on_falls_back_when_the_movement_is_framed(monkeypatch) -> None:
    # A pedal bar must keep its frame; the period does not overwrite it.
    framed = FormSpec(
        12,
        120,
        (
            FormSection(0, 4, "intro", 0),
            FormSection(4, 12, "phrase", 0),
        ),
        meter=METER_44,
    )
    off = _digest(_render(framed))
    calls = _spy_figures(monkeypatch)
    with period.use_barrios_period(True):
        on = _render(framed)
    assert calls == []
    assert _digest(on) == off


def test_flag_on_runs_the_shared_production_tail(monkeypatch) -> None:
    """The period must end in `_finish_voices`, not its old local shape pass."""
    import app.sonify.guitar_patterns as patterns
    import app.sonify.guitar_wave as guitar_wave

    finish_calls: list[dict] = []
    wave_calls: list[int] = []
    preludio_bass_calls: list[int] = []

    original_finish = patterns._finish_voices

    def finish_spy(ctx, patterns_, lead, support, low, **kwargs):
        finish_calls.append(kwargs)
        return original_finish(ctx, patterns_, lead, support, low, **kwargs)

    original_wave = guitar_wave.apply_guitar_wave

    def wave_spy(ctx, lead, support, low, patterns_=None, relaxed=None, scale_eighths=None):
        wave_calls.append(ctx.bars)
        return original_wave(
            ctx, lead, support, low, patterns_, relaxed, scale_eighths
        )

    monkeypatch.setattr(patterns, "_finish_voices", finish_spy)
    monkeypatch.setattr(guitar_wave, "apply_guitar_wave", wave_spy)
    monkeypatch.setattr(
        patterns,
        "_preludio_bass",
        lambda ctx, patterns_: preludio_bass_calls.append(ctx.bars) or [],
    )

    with period.use_barrios_period(True):
        _render()

    assert len(finish_calls) == 1
    # The period's own per-bar figure already writes the ringing pedal.
    assert finish_calls[0]["preludio_bass"] is False
    assert preludio_bass_calls == []
    assert wave_calls == [12]


def test_env_flag_auditions_without_the_context(monkeypatch) -> None:
    monkeypatch.setenv(ENV, "on")
    calls = _spy_figures(monkeypatch)
    try:
        score = _render()
        assert calls and len(calls) == 12
        assert PERIOD_KEY in specs.SENTENCE_SPECS
        assert score.divisions == 4
    finally:
        period.unregister()
    assert PERIOD_KEY not in specs.SENTENCE_SPECS


def test_use_context_removes_only_its_own_registration(monkeypatch) -> None:
    # The context adds exactly the authored tuple and removes it on exit,
    # including when nested; a different spec at the same key is tested below.
    assert PERIOD_KEY not in specs.SENTENCE_SPECS
    with period.use_barrios_period(True):
        assert PERIOD_KEY in specs.SENTENCE_SPECS
        with period.use_barrios_period(True):
            assert PERIOD_KEY in specs.SENTENCE_SPECS
        assert PERIOD_KEY in specs.SENTENCE_SPECS
    assert PERIOD_KEY not in specs.SENTENCE_SPECS


def test_ensure_registered_refuses_to_replace_a_different_spec() -> None:
    import dataclasses

    other = dataclasses.replace(period.BARRIOS_CATHEDRAL_PERIOD, id="future_archetype")
    specs.SENTENCE_SPECS[PERIOD_KEY] = (other,)
    try:
        with pytest.raises(ValueError, match="would replace it"):
            period.ensure_registered()
    finally:
        del specs.SENTENCE_SPECS[PERIOD_KEY]
    assert PERIOD_KEY not in specs.SENTENCE_SPECS
