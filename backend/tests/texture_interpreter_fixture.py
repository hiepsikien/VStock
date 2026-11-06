"""Authoring and oracle helpers for the Phase 2 ``chord_melody`` interpreter.

The committed specs ``app/sonify/textures/chord_melody_phase2.json`` (4/4) and
``chord_melody_phase2_34.json`` (3/4) are data, not runtime builders. This
module is the deterministic authoring tool that made them and the test oracle
that keeps them honest:

* :func:`code_bar` calls the production bar writers (``_chord_grid``,
  ``_render_block_bar``, ``_sustain``) for one fixture bar. That is the golden
  side of the comparison; :func:`code_events` concatenates every authored bar.
* :func:`spec_mapping` converts the same events into ``authored.events``.
  Pitch references use ``melody_eighth`` for the sung line and ``literal_midi``
  for the derived inner/bass tones, because a fixed ``chord_degree`` does not
  reproduce the register fold and inner-voice policy. The reason is recorded in
  ``provenance.notes``.
* :func:`velocity_for` is the host resolver the interpreter asks for realized
  velocity. The spec does not own velocity (docs §6.1/§6.5).

The builder never mutates ``SENTENCE_SPECS`` and is not imported by runtime
code.

The proof is a two-bar excerpt. ``validate_authored`` segments overlap by
``(voice, bar)`` before comparing beats, so a note that reaches the bar line no
longer collides with the next bar's first note. That fixed geometry is what
lets the authored events cover both bars honestly; a one-bar proof would not
exercise the bar boundary at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.sonify.form import METER_34, METER_44, Meter, compose_meter
from app.sonify.guitar import _apex_eighths
from app.sonify.guitar_patterns import (
    _covering_melody_velocity,
    _render_block_bar,
    _rises,
    _sustain,
    _swell_band,
    _under_lead,
)
from app.sonify.guitar_villa import _chord_grid
from app.sonify.model import NoteEvent, Phrase
from app.sonify.phrasing import swell
from app.studio.texture_spec import MeterSpec, PitchRef
from app.studio.texture_resolve import TextureResolveError, resolve_pitch
from tests.guitar_fixture import pattern_case

FIXTURE_BARS = 2
FIXTURE_ENSEMBLE = "villa"
FIXTURE_MOOD = "calm"
FIXTURE_BAND = "mf"
FIXTURE_BPM = 96
FIXTURE_METER = METER_44
SPEC_ID = "chord_melody_phase2"
SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "sonify"
    / "textures"
    / f"{SPEC_ID}.json"
)
#: The second bounded proof: same pattern, different meter. Dispatch must pick
#: it for a 3/4 context and the 4/4 spec for a 4/4 context.
SECOND_METER = METER_34
SECOND_SPEC_ID = "chord_melody_phase2_34"
SECOND_SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "sonify"
    / "textures"
    / f"{SECOND_SPEC_ID}.json"
)
RENDERER_VERSION = "chord-melody-interpreter-1"
SPEC_NOTES = (
    "Phase 2 interpreter prove-out for chord_melody over a fixed two-bar 4/4 "
    "excerpt. The sung line uses melody_eighth for every eighth of the "
    "excerpt. Inner and bass tones use chord_degree where it resolves to the "
    "written pitch and literal_midi otherwise, because the code writer folds "
    "chord tones into the bass/mid registers and moves the inner voice with "
    "the melody; a fixed chord_degree cannot reproduce every fold. Velocity "
    "is host-derived, not authored."
)


def _spec_notes(meter_label: str) -> str:
    return SPEC_NOTES.replace(
        "fixed two-bar 4/4 excerpt", f"fixed two-bar {meter_label} excerpt"
    )


def fixture_case(meter: Meter = FIXTURE_METER) -> tuple[Any, list[Phrase]]:
    return pattern_case(
        "chord_melody",
        meter,
        ensemble=FIXTURE_ENSEMBLE,
        mood=FIXTURE_MOOD,
        band=FIXTURE_BAND,
        bpm=FIXTURE_BPM,
        bars=FIXTURE_BARS,
    )


def code_bar(
    ctx: Any, phrase: Phrase, bar: int
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """The production ``chord_melody`` branch for one bar, before postprocess."""
    points, spans = _chord_grid(ctx, bar, phrase)
    support, low = _render_block_bar(
        ctx, bar, points, spans, inner="color", phrase=phrase
    )
    lead = _sustain(
        ctx.melody,
        bar * ctx.epb,
        (bar + 1) * ctx.epb,
        ctx.epb,
        _apex_eighths(ctx.phrases),
        {bar * ctx.epb + point for point in points},
        phrase=phrase,
    )
    return lead, support, low


def code_events(ctx: Any, phrase: Phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for bar in range(FIXTURE_BARS):
        part_lead, part_support, part_low = code_bar(ctx, phrase, bar)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    return lead, support, low


def velocity_for(
    ctx: Any,
    phrase: Phrase,
    event: NoteEvent,
    breaks: set[int],
) -> int | None:
    """The host resolver: the same written velocity the code branch writes."""
    eighth = event.bar * ctx.epb + int(round(event.beat * 2))
    lead_velocity = _covering_melody_velocity(ctx, eighth, breaks)
    if event.voice == 1:
        return lead_velocity
    band = ctx.band(event.bar)
    if _rises(phrase):
        band = _swell_band(swell(phrase, min(eighth, phrase.end - 1)))
    support, bass = _under_lead(lead_velocity, band)
    if event.voice == 3:
        return bass
    if event.voice == 2:
        return support
    return None


def _pitch_mapping(ctx: Any, event: NoteEvent) -> dict[str, Any]:
    if event.midi is None:
        raise ValueError("the proof fixture has no rests")
    eighth = event.bar * ctx.epb + int(round(event.beat * 2))
    if (
        event.voice == 1
        and 0 <= eighth < len(ctx.melody)
        and event.midi == ctx.melody[eighth]
    ):
        return {"kind": "melody_eighth", "eighth": eighth}

    try:
        chord = ctx.chord(event.bar)
    except (KeyError, IndexError, TypeError, ValueError):
        chord = None
    if chord is not None:
        degree = 1
        while degree <= 12:
            pitch = PitchRef.chord_degree(degree)
            try:
                resolved = resolve_pitch(pitch, ctx, bar=event.bar)
            except TextureResolveError:
                break
            if resolved == event.midi:
                return {"kind": "chord_root"} if degree == 1 else {
                    "kind": "chord_degree",
                    "degree": degree,
                }
            degree += 1
    return {"kind": "literal_midi", "value": event.midi}


def _tie_mapping(event: NoteEvent) -> str:
    if event.tie_start and event.tie_stop:
        return "continue"
    if event.tie_start:
        return "start"
    if event.tie_stop:
        return "stop"
    return "none"


def _slur_mapping(event: NoteEvent) -> str:
    if event.slur_start and event.slur_stop:
        return "continue"
    if event.slur_start:
        return "start"
    if event.slur_stop:
        return "stop"
    return "none"


def _authored_event(ctx: Any, event: NoteEvent) -> dict[str, Any]:
    return {
        "bar": event.bar,
        "beat": event.beat,
        "duration_beats": event.duration_beats,
        "voice": event.voice,
        "pitch": _pitch_mapping(ctx, event),
        "staff": event.staff,
        "tie": _tie_mapping(event),
        "slur": _slur_mapping(event),
        "accent": event.accent,
        "tenuto": event.tenuto,
        "staccato": event.staccato,
        "conflict": False,
        "review": "edited",
    }


def authored_events(ctx: Any, phrase: Phrase) -> list[dict[str, Any]]:
    lead, support, low = code_events(ctx, phrase)
    return [
        _authored_event(ctx, event)
        for event in (*lead, *support, *low)
    ]


def spec_mapping(
    *,
    meter: Meter = FIXTURE_METER,
    spec_id: str = SPEC_ID,
) -> dict[str, Any]:
    from app.sonify.texture_interpreter import context_digest

    meter_label = f"{meter.beats}/{meter.beat_type}"
    with compose_meter(meter):
        ctx, phrases = fixture_case(meter)
        phrase = phrases[0]
        events = authored_events(ctx, phrase)
        return {
            "id": spec_id,
            "composer": FIXTURE_ENSEMBLE,
            "kind": "pattern",
            "level": "topic",
            "parent": None,
            "runtime": "interpreter",
            "status": "reviewed",
            "source": {
                "piece": "Texture interpreter prove-out — chord_melody",
                "bars": [1, FIXTURE_BARS],
                "notation": "fixture",
                "render_context": {
                    "pattern": "chord_melody",
                    "meter": meter_label,
                    "ensemble": FIXTURE_ENSEMBLE,
                    "bpm": FIXTURE_BPM,
                    "digest": context_digest(ctx),
                },
            },
            "meter_variants": [
                {
                    "meter": MeterSpec.from_form_meter(meter).to_mapping(),
                    "materializer": "chord_melody_phase2",
                    "transform": "none",
                    "unsupported": False,
                    "reason": None,
                    "sentences": [],
                }
            ],
            "authored": {"events": events},
            "derived": {
                "resolved_midi": "from_render_context",
                "velocity": "host_resolver",
                "hairpin": "phrase",
                "humanize": "params",
            },
            "routing": {
                "price": {"voice": 1, "source": "melody"},
                "bass": {"voice": 3, "mode": "chord_root"},
                "density": {"voice": 2, "mode": "block_grid"},
            },
            "traits": {
                "family": "arpeggio",
                "kinetic": False,
                "narrow_rows": [6, 24, 80],
                "scale_host": False,
                "plucked": False,
                "loud_down": True,
                "has_door": False,
                "pedal_door": False,
                "sentence_registry": "none",
            },
            "provenance": {
                "model": "hand-authored",
                "prompt_version": "interpreter-phase2",
                "schema_version": "texture-spec-1",
                "renderer_version": RENDERER_VERSION,
                "confidence": 1.0,
                "reviewed_by": "human",
                "notes": _spec_notes(meter_label),
            },
        }


def write_spec(
    path: Path | None = None,
    *,
    meter: Meter = FIXTURE_METER,
    spec_id: str = SPEC_ID,
) -> Path:
    target = Path(path) if path is not None else SPEC_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            spec_mapping(meter=meter, spec_id=spec_id),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


__all__ = [
    "FIXTURE_BARS",
    "FIXTURE_METER",
    "RENDERER_VERSION",
    "SECOND_METER",
    "SECOND_SPEC_ID",
    "SECOND_SPEC_PATH",
    "SPEC_ID",
    "SPEC_PATH",
    "authored_events",
    "code_bar",
    "code_events",
    "fixture_case",
    "spec_mapping",
    "velocity_for",
    "write_spec",
]
