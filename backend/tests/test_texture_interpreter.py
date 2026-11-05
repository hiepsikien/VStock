"""Phase 2 interpreter proof: one chord_melody bar behind a flag.

The committed spec is a deterministic one-bar fixture. These tests lock three
things:

* flag off is the existing code render, byte for byte;
* flag on applies the interpreter only to the authored ``chord_melody`` bar and
  reproduces the code bar writer exactly (velocity included, supplied by the
  host because the spec does not own it);
* every other context/pattern falls back, and the interpreter never mutates the
  production sentence registry.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.sonify import sentence_specs
from app.sonify.form import METER_44, compose_meter
from app.sonify.guitar_patterns import render_patterned_voices
from app.sonify.keys import C_KEY, compose_register, register_for
from app.sonify.model import NoteEvent
from app.sonify.params import DEFAULT_PARAMS, compose_params
from app.sonify.texture_interpreter import (
    INTERPRETER_FLAG,
    SPEC_ID,
    TextureInterpreterError,
    context_digest,
    interpreter_enabled,
    load_spec,
    render_chord_melody_bar,
    reset_spec_cache,
    runtime_spec,
    use_texture_interpreter,
)
from app.studio.texture_spec import (
    TextureSpec,
    parse_texture_spec,
    texture_spec_to_mapping,
    validate_texture_spec,
)
from tests import texture_interpreter_fixture as fixture

# sha256 of the flag-off full render for the one-bar fixture. Drift is a review
# event, not an auto-update.
OFF_RENDER_DIGEST = "sha256:29006e4b68a8c2ba565ef9ac33f1a239ad4bcf2d1f641b9a4dafd3aaf4ed2914"


def _render(ctx, *, patterns: list[str] | None = None):
    register = register_for(C_KEY)
    with (
        compose_meter(METER_44),
        compose_register(C_KEY, register),
        compose_params(DEFAULT_PARAMS),
        patch(
            "app.sonify.guitar_patterns._patterns",
            return_value=list(patterns or ["chord_melody"]),
        ),
    ):
        return render_patterned_voices(
            melody=list(ctx.melody),
            raw_pitches=list(ctx.raw),
            phrases=ctx.phrases,
            chord_at=dict(ctx.chord_at),
            kind_at=dict(ctx.kind_at),
            band_at=dict(ctx.band_at),
            musical_bars=ctx.bars,
            total_eighths=len(ctx.melody),
            bpm=ctx.bpm,
            ensemble=ctx.ensemble,
            mode=ctx.mode,
            character=ctx.character,
            character_at=ctx.character_at,
            sections=ctx.sections,
            rel_span=ctx.rel_span,
            register=register,
            regime_at=dict(ctx.regime_at),
        )


def _canonical(event: NoteEvent) -> list:
    return [
        event.bar,
        event.beat,
        event.midi,
        event.duration_beats,
        event.voice,
        event.staff,
        event.tie_start,
        event.tie_stop,
        event.slur_start,
        event.slur_stop,
        event.accent,
        event.velocity,
        event.tenuto,
        event.staccato,
        event.hairpin,
        event.pinned,
    ]


def _render_digest(rendered) -> str:
    lead, support, low, divisions = rendered
    payload = {
        "lead": [_canonical(event) for event in lead],
        "support": [_canonical(event) for event in support],
        "low": [_canonical(event) for event in low],
        "divisions": divisions,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _velocity(ctx, phrase, event, breaks):
    return fixture.velocity_for(ctx, phrase, event, breaks)


# ---------------------------------------------------------------------------
# Flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "0", "false", "no", "off", "rollback", "2"])
def test_flag_is_off_for_every_non_truthy_value(monkeypatch, value) -> None:
    if value is None:
        monkeypatch.delenv(INTERPRETER_FLAG, raising=False)
    else:
        monkeypatch.setenv(INTERPRETER_FLAG, value)
    assert interpreter_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_flag_is_on_for_the_truthy_spellings(monkeypatch, value) -> None:
    monkeypatch.setenv(INTERPRETER_FLAG, value)
    assert interpreter_enabled() is True


def test_context_manager_overrides_the_environment(monkeypatch) -> None:
    monkeypatch.setenv(INTERPRETER_FLAG, "1")
    with use_texture_interpreter(False):
        assert interpreter_enabled() is False
    assert interpreter_enabled() is True


# ---------------------------------------------------------------------------
# Spec parse / validate
# ---------------------------------------------------------------------------


def test_committed_spec_parses_validates_and_round_trips() -> None:
    reset_spec_cache()
    spec = load_spec()
    assert isinstance(spec, TextureSpec)
    assert spec.id == SPEC_ID
    assert spec.runtime == "interpreter"
    assert spec.composer == "villa"
    assert spec.kind == "pattern"
    assert len(spec.meter_variants) == 1
    assert validate_texture_spec(
        spec,
        meter=spec.meter_variants[0].meter,
        require_full_bars=True,
    ) == ()
    assert parse_texture_spec(texture_spec_to_mapping(spec)) == spec

    kinds = [event.pitch.kind for event in spec.authored]
    assert kinds.count("melody_eighth") == 8
    assert "literal_midi" in kinds
    assert all(event.review == "edited" for event in spec.authored)


def test_spec_declares_the_render_context_digest() -> None:
    ctx, _phrases = fixture.fixture_case()
    spec = load_spec()
    declared = spec.source["render_context"]
    assert declared["pattern"] == "chord_melody"
    assert declared["meter"] == "4/4"
    assert declared["ensemble"] == fixture.FIXTURE_ENSEMBLE
    assert declared["digest"] == context_digest(ctx)


# ---------------------------------------------------------------------------
# Interpreter output vs the code bar writer
# ---------------------------------------------------------------------------


def test_interpreter_reproduces_the_code_bar_exactly() -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    phrase = phrases[0]
    expected = fixture.code_bar(ctx, phrase, 0)
    with use_texture_interpreter(True):
        actual = render_chord_melody_bar(
            ctx,
            0,
            phrase,
            velocity_at=lambda event, breaks: _velocity(ctx, phrase, event, breaks),
        )
    assert actual is not None
    for voice, (got, want) in enumerate(zip(actual, expected)):
        assert got == want, (voice, got, want)


def test_interpreter_without_a_host_resolver_keeps_velocity_derived() -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with use_texture_interpreter(True):
        actual = render_chord_melody_bar(ctx, 0, phrases[0])
    assert actual is not None
    assert all(event.velocity is None for voice in actual for event in voice)
    # Placement/pitch still match the code writer; only the derived level differs.
    expected = fixture.code_bar(ctx, phrases[0], 0)
    for got_voice, want_voice in zip(actual, expected):
        assert [
            (event.bar, event.beat, event.midi, event.duration_beats, event.voice)
            for event in got_voice
        ] == [
            (event.bar, event.beat, event.midi, event.duration_beats, event.voice)
            for event in want_voice
        ]


def test_full_render_off_is_the_committed_code_path() -> None:
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        rendered = _render(ctx)
    assert _render_digest(rendered) == OFF_RENDER_DIGEST


def test_full_render_on_matches_off_for_the_authored_bar() -> None:
    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        off = _render(ctx)
    from app.sonify import texture_interpreter as interpreter_module

    original = interpreter_module.render_chord_melody_bar
    calls: list[bool] = []

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result is not None)
        return result

    with use_texture_interpreter(True):
        with patch.object(interpreter_module, "render_chord_melody_bar", side_effect=spy):
            on = _render(ctx)
    assert calls == [True], "the on render did not take the interpreter path"
    assert on == off


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------


def test_a_different_context_falls_back_to_code() -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    changed = replace(ctx, melody=[note + 1 for note in ctx.melody])
    with use_texture_interpreter(True):
        assert render_chord_melody_bar(changed, 0, phrases[0]) is None

    with use_texture_interpreter(False):
        off = _render(changed)
    with use_texture_interpreter(True):
        on = _render(changed)
    assert on == off


def test_another_pattern_falls_back_to_code() -> None:
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        off = _render(ctx, patterns=["villa_pattern"])
    with use_texture_interpreter(True):
        on = _render(ctx, patterns=["villa_pattern"])
    assert on == off


def test_flag_on_but_missing_spec_falls_back(tmp_path) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_PATH", tmp_path / "missing.json"):
        reset_spec_cache()
        assert runtime_spec() is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
    reset_spec_cache()


def test_a_spec_with_the_wrong_runtime_is_rejected(tmp_path) -> None:
    mapping = fixture.spec_mapping()
    mapping["runtime"] = "code"
    target = tmp_path / "wrong.json"
    target.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(TextureInterpreterError):
        load_spec(target)


# ---------------------------------------------------------------------------
# Registry is untouched
# ---------------------------------------------------------------------------


def test_interpreter_never_mutates_the_sentence_registry() -> None:
    before_keys = tuple(sorted(sentence_specs.SENTENCE_SPECS))
    before_values = {
        key: tuple(value) for key, value in sentence_specs.SENTENCE_SPECS.items()
    }

    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with use_texture_interpreter(True):
        assert render_chord_melody_bar(ctx, 0, phrases[0]) is not None
        _render(ctx)

    after_keys = tuple(sorted(sentence_specs.SENTENCE_SPECS))
    after_values = {
        key: tuple(value) for key, value in sentence_specs.SENTENCE_SPECS.items()
    }
    assert after_keys == before_keys
    assert after_values == before_values
