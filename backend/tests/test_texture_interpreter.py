"""Bounded Phase 2 interpreter proof: a two-bar chord_melody excerpt behind a flag.

The committed spec is a deterministic two-bar fixture, published through
``app.sonify.texture_registry``. These tests lock four things:

* flag off is the existing code render, byte for byte, and reads no registry;
* flag on applies the interpreter only to the authored ``chord_melody`` bars
  resolved from the registry and reproduces the code bar writer exactly for
  both bars (velocity included, supplied by the host because the spec does not
  own it);
* every other context/pattern, and every missing/malformed/registry-skipped
  spec, falls back to code without raising;
* the interpreter never mutates the production sentence or texture registries.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from app.sonify import sentence_specs, texture_interpreter, texture_registry
from app.sonify.form import METER_34, METER_44, METER_68, compose_meter
from app.sonify.guitar_patterns import render_patterned_voices
from app.sonify.keys import C_KEY, compose_register, register_for
from app.sonify.model import NoteEvent
from app.sonify.params import DEFAULT_PARAMS, compose_params
from app.sonify.texture_interpreter import (
    INTERPRETER_FLAG,
    INTERPRETER_PATTERN,
    SPEC_ID,
    TextureInterpreterError,
    context_digest,
    dispatch_key,
    dispatch_spec,
    excerpt_key,
    interpreter_enabled,
    load_spec,
    render_chord_melody_bar,
    reset_spec_cache,
    use_texture_interpreter,
)
from app.studio.texture_spec import (
    MeterSpec,
    TextureSpec,
    parse_texture_spec,
    texture_spec_to_mapping,
    validate_texture_spec,
)
from tests import texture_interpreter_fixture as fixture

# sha256 of the flag-off full render for the two-bar fixture. Drift is a review
# event, not an auto-update.
OFF_RENDER_DIGEST = "sha256:d20613ab9785c4095f84c9bebaab7c2b580c1d05923d3f282323befd19799a16"


def _render(ctx, *, meter=METER_44, patterns: list[str] | None = None):
    register = register_for(C_KEY)
    with (
        compose_meter(meter),
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


def _publish(root: Path, mapping, name: str = "chord_melody_phase2.json") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


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
    assert kinds.count("melody_eighth") == 8 * fixture.FIXTURE_BARS
    assert "literal_midi" in kinds
    assert {event.bar for event in spec.authored} == set(range(fixture.FIXTURE_BARS))
    assert all(event.review == "edited" for event in spec.authored)


def test_spec_declares_the_render_context_digest() -> None:
    ctx, _phrases = fixture.fixture_case()
    spec = load_spec()
    declared = spec.source["render_context"]
    assert declared["pattern"] == "chord_melody"
    assert declared["meter"] == "4/4"
    assert declared["ensemble"] == fixture.FIXTURE_ENSEMBLE
    assert declared["digest"] == context_digest(ctx)


def test_spec_source_declares_the_two_bar_excerpt() -> None:
    spec = load_spec()
    assert spec.source["bars"] == [1, fixture.FIXTURE_BARS]
    assert fixture.FIXTURE_BARS == 2


def test_context_digest_is_deterministic_and_covers_the_excerpt_length() -> None:
    ctx, _phrases = fixture.fixture_case()
    other, _phrases = fixture.fixture_case()
    digest = context_digest(ctx)
    assert digest == context_digest(other)
    assert digest.startswith("sha256:")
    # The digest includes ``bars``, so the one-bar excerpt is a different
    # context and cannot pass the spec gate.
    assert context_digest(replace(ctx, bars=1)) != digest


def test_registry_publishes_both_proof_specs() -> None:
    reset_spec_cache()
    report = texture_registry.load_report()
    assert report.issues == ()
    assert SPEC_ID in report.ids
    assert fixture.SECOND_SPEC_ID in report.ids

    for spec_id in (SPEC_ID, fixture.SECOND_SPEC_ID):
        spec = report.get(spec_id)
        assert spec is not None
        assert spec.runtime == "interpreter"
        assert spec.provenance["schema_version"] == texture_registry.CURRENT_SCHEMA_VERSION
        assert spec.provenance["renderer_version"] == fixture.RENDERER_VERSION


def test_dispatch_key_is_pattern_meter_and_excerpt_digest() -> None:
    ctx, _phrases = fixture.fixture_case()
    meter_key = dispatch_key(INTERPRETER_PATTERN, ctx)
    assert meter_key == (
        "chord_melody",
        (8, 4.0, (0, 4)),
        context_digest(ctx),
    )

    three_four, _phrases = fixture.fixture_case(fixture.SECOND_METER)
    other = dispatch_key(INTERPRETER_PATTERN, three_four)
    assert other[0] == "chord_melody"
    assert other[1] == (6, 3.0, (0,))
    assert other[2] == context_digest(three_four)
    assert other != meter_key


def test_excerpt_key_is_per_spec_not_one_global_constant() -> None:
    ctx, _phrases = fixture.fixture_case()
    primary = load_spec()
    secondary = load_spec(fixture.SECOND_SPEC_PATH)

    assert excerpt_key(primary) == (SPEC_ID, context_digest(ctx))
    assert excerpt_key(secondary) is not None
    assert excerpt_key(secondary)[0] == fixture.SECOND_SPEC_ID
    assert excerpt_key(secondary)[1] != excerpt_key(primary)[1]


def test_interpreter_resolves_the_spec_through_the_registry() -> None:
    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case()
    published = texture_registry.load_default()
    match = dispatch_spec(INTERPRETER_PATTERN, ctx)
    assert match is not None
    # Identity, not just equality: the interpreter returns the registry object.
    assert match.spec is next(
        candidate for candidate in published if candidate.id == SPEC_ID
    )
    assert match.pattern == INTERPRETER_PATTERN
    assert match.meter == MeterSpec.from_form_meter(METER_44)
    assert match.digest == context_digest(ctx)


def test_dispatch_by_pattern_and_meter_selects_the_matching_spec() -> None:
    reset_spec_cache()
    ctx_44, _phrases = fixture.fixture_case()
    ctx_34, _phrases = fixture.fixture_case(fixture.SECOND_METER)

    match_44 = dispatch_spec(INTERPRETER_PATTERN, ctx_44)
    match_34 = dispatch_spec(INTERPRETER_PATTERN, ctx_34)

    assert match_44 is not None and match_44.spec.id == SPEC_ID
    assert match_34 is not None and match_34.spec.id == fixture.SECOND_SPEC_ID
    assert match_44.meter != match_34.meter
    assert dispatch_spec("villa_pattern", ctx_44) is None


def test_three_four_and_six_eight_do_not_collide() -> None:
    reset_spec_cache()
    ctx_34, _phrases = fixture.fixture_case(METER_34)
    ctx_68, _phrases = fixture.fixture_case(METER_68)

    match = dispatch_spec(INTERPRETER_PATTERN, ctx_34)
    assert match is not None and match.spec.id == fixture.SECOND_SPEC_ID
    # Same eighths-per-bar and quarter-beat length as 3/4; only the strong
    # eighths differ, so the dispatch key must keep them apart.
    assert dispatch_key(INTERPRETER_PATTERN, ctx_34)[1] == (6, 3.0, (0,))
    assert dispatch_key(INTERPRETER_PATTERN, ctx_68)[1] == (6, 3.0, (0, 3))
    assert dispatch_spec(INTERPRETER_PATTERN, ctx_68) is None


def test_multiple_registry_entries_keep_their_own_excerpt(tmp_path) -> None:
    _publish(tmp_path, fixture.spec_mapping(), "chord_melody_44.json")
    _publish(
        tmp_path,
        fixture.spec_mapping(
            meter=fixture.SECOND_METER,
            spec_id=fixture.SECOND_SPEC_ID,
        ),
        "chord_melody_34.json",
    )
    reset_spec_cache()
    ctx_44, _phrases = fixture.fixture_case()
    ctx_34, _phrases = fixture.fixture_case(fixture.SECOND_METER)
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        report = texture_registry.load_report(tmp_path)
        assert report.ids == (SPEC_ID, fixture.SECOND_SPEC_ID)
        assert dispatch_spec(INTERPRETER_PATTERN, ctx_44).spec.id == SPEC_ID
        assert (
            dispatch_spec(INTERPRETER_PATTERN, ctx_34).spec.id
            == fixture.SECOND_SPEC_ID
        )
        assert dispatch_spec("villa_pattern", ctx_44) is None
    reset_spec_cache()


def test_digest_gate_is_per_spec_not_global(tmp_path) -> None:
    ctx, _phrases = fixture.fixture_case()
    wrong = fixture.spec_mapping(spec_id="chord_melody_wrong_digest")
    wrong["source"]["render_context"]["digest"] = "sha256:" + ("0" * 64)
    _publish(tmp_path, fixture.spec_mapping(), "correct.json")
    _publish(tmp_path, wrong, "wrong.json")

    reset_spec_cache()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        match = dispatch_spec(INTERPRETER_PATTERN, ctx)
        assert match is not None
        assert match.spec.id == SPEC_ID
        # The wrong-digest entry has the same pattern and meter, so only its
        # own digest keeps it out. Nothing global is overwritten.
        report = texture_registry.load_report(tmp_path)
        assert report.get("chord_melody_wrong_digest") is not None
    reset_spec_cache()


def test_interpreter_does_not_read_spec_path_at_runtime(tmp_path) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch(
        "app.sonify.texture_interpreter.SPEC_PATH", tmp_path / "missing.json"
    ):
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is not None
    reset_spec_cache()


def test_interpreter_uses_a_published_spec_from_the_configured_root(tmp_path) -> None:
    _publish(tmp_path, fixture.spec_mapping())
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        match = dispatch_spec(INTERPRETER_PATTERN, ctx)
        assert match is not None and match.spec.id == SPEC_ID
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is not None
    reset_spec_cache()


# ---------------------------------------------------------------------------
# Interpreter output vs the code bar writer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bar", range(fixture.FIXTURE_BARS))
def test_interpreter_reproduces_the_code_bar_exactly(bar: int) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    phrase = phrases[0]
    expected = fixture.code_bar(ctx, phrase, bar)
    with use_texture_interpreter(True):
        actual = render_chord_melody_bar(
            ctx,
            bar,
            phrase,
            velocity_at=lambda event, breaks: _velocity(ctx, phrase, event, breaks),
        )
    assert actual is not None
    for voice, (got, want) in enumerate(zip(actual, expected)):
        assert got == want, (voice, got, want)


def test_interpreter_reproduces_the_whole_two_bar_excerpt() -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    phrase = phrases[0]
    expected = fixture.code_events(ctx, phrase)
    actual = ([], [], [])
    with use_texture_interpreter(True):
        for bar in range(fixture.FIXTURE_BARS):
            part = render_chord_melody_bar(
                ctx,
                bar,
                phrase,
                velocity_at=lambda event, breaks: _velocity(
                    ctx, phrase, event, breaks
                ),
            )
            assert part is not None
            for voice in range(3):
                actual[voice].extend(part[voice])
    assert tuple(actual) == expected
    assert {event.bar for voice in actual for event in voice} == {0, 1}


@pytest.mark.parametrize("bar", range(fixture.FIXTURE_BARS))
def test_interpreter_without_a_host_resolver_keeps_velocity_derived(bar: int) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with use_texture_interpreter(True):
        actual = render_chord_melody_bar(ctx, bar, phrases[0])
    assert actual is not None
    assert all(event.velocity is None for voice in actual for event in voice)
    # Placement/pitch still match the code writer; only the derived level differs.
    expected = fixture.code_bar(ctx, phrases[0], bar)
    for got_voice, want_voice in zip(actual, expected):
        assert [
            (event.bar, event.beat, event.midi, event.duration_beats, event.voice)
            for event in got_voice
        ] == [
            (event.bar, event.beat, event.midi, event.duration_beats, event.voice)
            for event in want_voice
        ]


@pytest.mark.parametrize("bar", range(fixture.FIXTURE_BARS))
def test_interpreter_reproduces_the_three_four_bar_exactly(bar: int) -> None:
    reset_spec_cache()
    with compose_meter(METER_34):
        ctx, phrases = fixture.fixture_case(METER_34)
        phrase = phrases[0]
        expected = fixture.code_bar(ctx, phrase, bar)
        with use_texture_interpreter(True):
            actual = render_chord_melody_bar(
                ctx,
                bar,
                phrase,
                velocity_at=lambda event, breaks: _velocity(
                    ctx, phrase, event, breaks
                ),
            )
    assert actual is not None
    for voice, (got, want) in enumerate(zip(actual, expected)):
        assert got == want, (voice, got, want)


def test_interpreter_reproduces_the_whole_three_four_excerpt() -> None:
    reset_spec_cache()
    with compose_meter(METER_34):
        ctx, phrases = fixture.fixture_case(METER_34)
        phrase = phrases[0]
        expected = fixture.code_events(ctx, phrase)
        actual = ([], [], [])
        with use_texture_interpreter(True):
            for bar in range(fixture.FIXTURE_BARS):
                part = render_chord_melody_bar(
                    ctx,
                    bar,
                    phrase,
                    velocity_at=lambda event, breaks: _velocity(
                        ctx, phrase, event, breaks
                    ),
                )
                assert part is not None
                for voice in range(3):
                    actual[voice].extend(part[voice])
    assert tuple(actual) == expected
    assert {event.bar for voice in actual for event in voice} == {0, 1}


def test_full_render_off_is_the_committed_code_path() -> None:
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        rendered = _render(ctx)
    assert _render_digest(rendered) == OFF_RENDER_DIGEST


def test_full_render_on_matches_off_for_the_authored_bars() -> None:
    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        off = _render(ctx)

    original = texture_interpreter.render_chord_melody_bar
    calls: list[bool] = []

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result is not None)
        return result

    with use_texture_interpreter(True):
        with patch.object(
            texture_interpreter, "render_chord_melody_bar", side_effect=spy
        ):
            on = _render(ctx)
    assert calls == [True] * fixture.FIXTURE_BARS, (
        "the on render did not take the interpreter path for every bar"
    )
    assert on == off


def test_full_render_34_on_matches_off_for_the_authored_bars() -> None:
    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case(METER_34)
    with use_texture_interpreter(False):
        off = _render(ctx, meter=METER_34)

    original = texture_interpreter.render_chord_melody_bar
    calls: list[bool] = []

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result is not None)
        return result

    with use_texture_interpreter(True):
        with patch.object(
            texture_interpreter, "render_chord_melody_bar", side_effect=spy
        ):
            on = _render(ctx, meter=METER_34)
    assert calls == [True] * fixture.FIXTURE_BARS
    assert on == off
    assert {event.bar for voice in on[:3] for event in voice} == {0, 1}


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
    assert dispatch_spec("villa_pattern", ctx) is None
    with use_texture_interpreter(False):
        off = _render(ctx, patterns=["villa_pattern"])
    with use_texture_interpreter(True):
        on = _render(ctx, patterns=["villa_pattern"])
    assert on == off


def test_a_spec_for_an_unknown_pattern_is_ignored(tmp_path) -> None:
    ctx, phrases = fixture.fixture_case()
    unknown = fixture.spec_mapping(spec_id="chord_melody_unknown_pattern")
    unknown["source"]["render_context"]["pattern"] = "villa_pattern"
    _publish(tmp_path, unknown)

    reset_spec_cache()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert texture_registry.load_report(tmp_path).ids == (
            "chord_melody_unknown_pattern",
        )
        # The renderer asks for chord_melody; the unknown-pattern entry is not
        # eligible even though its meter and digest would otherwise match.
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
    reset_spec_cache()


def test_a_wrong_excerpt_length_or_meter_falls_back_to_code() -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with use_texture_interpreter(True):
        # The spec is authored for exactly two 4/4 bars.
        assert dispatch_spec(INTERPRETER_PATTERN, replace(ctx, bars=1)) is None
        assert (
            dispatch_spec(INTERPRETER_PATTERN, replace(ctx, bar_beats=3.0)) is None
        )
        assert render_chord_melody_bar(replace(ctx, bars=1), 0, phrases[0]) is None
        assert (
            render_chord_melody_bar(replace(ctx, bar_beats=3.0), 0, phrases[0])
            is None
        )

    one_bar = replace(ctx, bars=1)
    with use_texture_interpreter(False):
        off = _render(one_bar)
    with use_texture_interpreter(True):
        on = _render(one_bar)
    assert on == off


def test_flag_on_but_missing_spec_falls_back(tmp_path) -> None:
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
    reset_spec_cache()


def test_malformed_published_spec_falls_back(tmp_path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
    reset_spec_cache()


def test_a_broken_registry_entry_does_not_hide_a_valid_one(tmp_path) -> None:
    _publish(tmp_path, fixture.spec_mapping(), "good.json")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert texture_registry.load_report(tmp_path).ids == (SPEC_ID,)
        match = dispatch_spec(INTERPRETER_PATTERN, ctx)
        assert match is not None and match.spec.id == SPEC_ID
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is not None
    reset_spec_cache()


def test_wrong_digest_falls_back_to_code(tmp_path) -> None:
    mapping = fixture.spec_mapping()
    mapping["source"]["render_context"]["digest"] = "sha256:" + ("0" * 64)
    _publish(tmp_path, mapping)

    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
        with use_texture_interpreter(False):
            off = _render(ctx)
        with use_texture_interpreter(True):
            on = _render(ctx)
    assert on == off
    reset_spec_cache()


def test_registry_skipped_spec_falls_back(tmp_path) -> None:
    # A valid JSON spec that the registry's version gate rejects: runtime
    # ``interpreter`` without ``provenance.renderer_version``.
    mapping = fixture.spec_mapping()
    del mapping["provenance"]["renderer_version"]
    _publish(tmp_path, mapping)

    reset_spec_cache()
    ctx, phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        assert texture_registry.load_specs(tmp_path) == ()
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            assert render_chord_melody_bar(ctx, 0, phrases[0]) is None
    reset_spec_cache()


def test_a_broken_published_spec_does_not_change_the_render(tmp_path) -> None:
    mapping = fixture.spec_mapping()
    mapping["runtime"] = "code"
    _publish(tmp_path, mapping)

    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case()
    with patch("app.sonify.texture_interpreter.SPEC_ROOT", tmp_path):
        with use_texture_interpreter(False):
            off = _render(ctx)
        with use_texture_interpreter(True):
            on = _render(ctx)
    assert on == off
    reset_spec_cache()


def test_a_registry_failure_never_breaks_the_render() -> None:
    reset_spec_cache()
    ctx, _phrases = fixture.fixture_case()
    with use_texture_interpreter(False):
        off = _render(ctx)

    def explode(*args, **kwargs):
        raise RuntimeError("registry is unavailable")

    reset_spec_cache()
    with patch.object(texture_registry, "load_default", side_effect=explode):
        assert dispatch_spec(INTERPRETER_PATTERN, ctx) is None
        with use_texture_interpreter(True):
            on = _render(ctx)
    assert on == off
    reset_spec_cache()


def test_flag_off_never_reads_the_registry() -> None:
    ctx, _phrases = fixture.fixture_case()

    def explode(*args, **kwargs):
        raise AssertionError("flag-off render read the texture registry")

    reset_spec_cache()
    with patch.object(texture_registry, "load_specs", side_effect=explode):
        with patch.object(texture_registry, "load_default", side_effect=explode):
            with use_texture_interpreter(False):
                rendered = _render(ctx)
    assert _render_digest(rendered) == OFF_RENDER_DIGEST
    reset_spec_cache()


def test_a_spec_with_the_wrong_runtime_is_rejected(tmp_path) -> None:
    mapping = fixture.spec_mapping()
    mapping["runtime"] = "code"
    target = tmp_path / "wrong.json"
    target.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(TextureInterpreterError):
        load_spec(target)


def test_a_spec_with_the_wrong_pattern_is_rejected(tmp_path) -> None:
    mapping = fixture.spec_mapping()
    mapping["source"]["render_context"]["pattern"] = "villa_pattern"
    target = tmp_path / "wrong-pattern.json"
    target.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(TextureInterpreterError):
        load_spec(target)


def test_import_reads_no_files_and_loads_no_writer() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import pathlib\n"
        "def _boom(*args, **kwargs):\n"
        "    raise AssertionError('importing texture_interpreter read a file')\n"
        "pathlib.Path.read_text = _boom\n"
        "import sys\n"
        "import app.sonify.texture_interpreter\n"
        "print('app.sonify.guitar_patterns' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"


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


def test_interpreter_never_mutates_the_texture_registry() -> None:
    reset_spec_cache()
    before = texture_registry.load_default()
    ctx, phrases = fixture.fixture_case()
    with use_texture_interpreter(True):
        assert render_chord_melody_bar(ctx, 0, phrases[0]) is not None
        _render(ctx)
    after = texture_registry.load_default()
    assert after == before
    assert texture_registry.load_report().issues == ()
    reset_spec_cache()
