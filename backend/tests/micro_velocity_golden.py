"""Zero-diff baseline for the authored micro-velocity contours.

`docs/sonify-texture-studio.md` section 6.9 requires the production patterns
(Tremolo, Galop, Cathedral Preludio, Etude 1, Etude 11) to be compared as
`NoteEvent` lists plus a digest, not by a Studio `renderHash`. This module
builds a small deterministic fixture per figure/pattern and captures the
baseline events from the real production renderer, `render_patterned_voices`.

Every fixture is a pure function of the committed code and a frozen recipe:

* the bounded `pattern_case()` context supplies the contour, chords, bands,
  sections, phrases, meter and bar length;
* the one fixture that needs a hold (`tremolo_34`) replaces the contour with a
  fixed held line so the barred macro ladder reaches the tremolo, exactly the
  way the phrase ladder reaches it from a held phrase;
* the register is `C_KEY`; `compose_params(DEFAULT_PARAMS)` pins the technique
  knob so a leaked context cannot change the selected pattern.

The captured score is the output of `render_patterned_voices` after the guitar
wave and before humanize. That is the boundary section 6.9 names: figure writer
-> micro offsets -> `apply_guitar_wave` -> absolute writers -> humanize. The
extraction agent must compare its contour-rendered `NoteEvent` list and digest
against this artifact for the same fixture.

`build_manifest()` is the only writer. The test never updates the artifact; a
drift is a review event. Regenerate it by hand with:

    python3 -c "import json, pathlib; \\
from tests.micro_velocity_golden import build_manifest; \\
pathlib.Path('tests/fixtures/micro_velocity_golden.json').write_text( \\
    json.dumps(build_manifest(), indent=2, sort_keys=True) + '\\n', encoding='utf-8')"

Run from `backend/`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any, Mapping

from app.sonify.form import FormSection, Meter, compose_meter
from app.sonify.guitar_patterns import (
    _Ctx,
    _bar_pattern,
    _patterns,
    render_patterned_voices,
)
from app.sonify.keys import C_KEY, compose_register, register_for
from app.sonify.model import NoteEvent, Phrase, Run
from app.sonify.params import DEFAULT_PARAMS, compose_params
from tests.guitar_fixture import meter_named, pattern_case

KIND = "micro-velocity-golden"
VERSION = 1
FIXTURE_VERSION = 1
RENDERER = "render_patterned_voices"
REGISTER = "C"

# Order of every stored event. It is the full `NoteEvent` surface, not just the
# velocity fields: a contour must not move a tie, slur, accent, hairpin or the
# pinned bit either.
EVENT_FIELDS = (
    "bar",
    "beat",
    "midi",
    "duration_beats",
    "voice",
    "velocity",
    "staff",
    "tie_start",
    "tie_stop",
    "slur_start",
    "slur_stop",
    "accent",
    "tenuto",
    "staccato",
    "hairpin",
    "pinned",
)

NOTE_SORT = (
    "bar, beat, midi (rests last), duration_beats, voice, velocity, then the "
    "flags in EVENT_FIELDS order"
)

_HELD_34 = (67, 67, 67, 67, 65, 64)

# Frozen recipes. `sections` must tile the whole fixture and end in a pedal
# frame; that is what puts a pattern on the macro path in production.
# `contour: "held"` replaces the shared pattern_case contour with `_HELD_34`;
# every other field still comes from `pattern_case`.
FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "id": "tremolo_44",
        "figure": "tremolo",
        "label": "Tremolo, 4/4: -4/0/+4/+1 thumb offsets, fill -6/-3/-4/-6",
        "meter": "4/4",
        "ensemble": "barrios",
        "bpm": 96,
        "mood": "selloff",
        "band": "mf",
        "bars": 4,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 3, "phrase", 0),
            (3, 4, "outro", 0),
        ),
    },
    {
        "id": "tremolo_34",
        "figure": "tremolo",
        "label": "Tremolo, 3/4: -4/+4/0 thumb offsets over three quarters",
        "meter": "3/4",
        "ensemble": "barrios",
        "bpm": 96,
        "mood": "rally",
        "band": "mf",
        "bars": 4,
        "rel_span": 0.02,
        "contour": "held",
        "sections": (
            (0, 1, "intro", 0),
            (1, 3, "phrase", 0),
            (3, 4, "outro", 0),
        ),
    },
    {
        "id": "galop_1",
        "figure": "galop1",
        "label": "Galop statement cell, four bars",
        "meter": "4/4",
        "ensemble": "classic",
        "bpm": 96,
        "mood": "rally",
        "band": "mf",
        "bars": 6,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 5, "phrase", 0),
            (5, 6, "outro", 0),
        ),
    },
    {
        "id": "galop_2",
        "figure": "galop2",
        "label": "Galop answer cell, the second four bars of the cycle",
        "meter": "4/4",
        "ensemble": "classic",
        "bpm": 96,
        "mood": "rally",
        "band": "mf",
        "bars": 10,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 9, "phrase", 0),
            (9, 10, "outro", 0),
        ),
    },
    {
        "id": "catedral_preludio",
        "figure": "catedral_preludio",
        "label": "Cathedral Preludio: canto plus _catedral_level under voice",
        "meter": "4/4",
        "ensemble": "barrios",
        "bpm": 96,
        "mood": "rally",
        "band": "mf",
        "bars": 4,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 3, "phrase", 0),
            (3, 4, "outro", 0),
        ),
    },
    {
        "id": "etude1",
        "figure": "etude1",
        "label": "Etude 1: _ETUDE1_ARC over the sixteenth cycle",
        "meter": "4/4",
        "ensemble": "villa",
        "bpm": 96,
        "mood": "rally",
        "band": "mf",
        "bars": 4,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 3, "phrase", 0),
            (3, 4, "outro", 0),
        ),
    },
    {
        "id": "etude11",
        "figure": "etude11",
        "label": "Etude 11: sextuplet arch, _ETUDE11_TILT and lead hairpin",
        "meter": "4/4",
        "ensemble": "villa",
        "bpm": 96,
        "mood": "volatile",
        "band": "mf",
        "bars": 4,
        "rel_span": 0.02,
        "contour": "pattern_case",
        "sections": (
            (0, 1, "intro", 0),
            (1, 3, "phrase", 0),
            (3, 4, "outro", 0),
        ),
    },
)

REQUIRED_FIGURES: dict[str, tuple[str, ...]] = {
    "tremolo_44": ("tremolo",),
    "tremolo_34": ("tremolo",),
    "galop_1": ("galop1",),
    "galop_2": ("galop2",),
    "catedral_preludio": ("catedral_preludio",),
    "etude1": ("etude1",),
    "etude11": ("etude11",),
}


# ---------------------------------------------------------------------------
# fixture construction


def _meter_of(recipe: Mapping[str, Any]) -> Meter:
    name = recipe["meter"]
    if name not in {"3/4", "4/4"}:
        raise ValueError(f"unsupported meter {name!r}")
    return meter_named(name)


def _joined(start: int, pitches: list[int]) -> Phrase:
    """One phrase with runs collapsed exactly like `guitar_fixture` does."""
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs))


def _held_line(bars: int, epb: int) -> list[int]:
    return [_HELD_34[index % len(_HELD_34)] for index in range(bars * epb)]


def _sections(recipe: Mapping[str, Any]) -> tuple[FormSection, ...]:
    sections = tuple(FormSection(*values) for values in recipe["sections"])
    if not sections or sections[0].start != 0:
        raise ValueError(f"{recipe['id']}: sections must start at bar 0")
    if sections[-1].end != recipe["bars"]:
        raise ValueError(f"{recipe['id']}: sections must end at the last bar")
    for left, right in zip(sections, sections[1:]):
        if left.end != right.start:
            raise ValueError(f"{recipe['id']}: sections must tile without a gap")
    return sections


def build_context(recipe: Mapping[str, Any]) -> _Ctx:
    """The deterministic `_Ctx` a fixture renders from."""
    meter = _meter_of(recipe)
    sections = _sections(recipe)
    ctx, _phrases = pattern_case(
        str(recipe["figure"]),
        meter,
        ensemble=str(recipe["ensemble"]),
        mood=str(recipe["mood"]),
        band=str(recipe["band"]),
        bpm=int(recipe["bpm"]),
        bars=int(recipe["bars"]),
        sections=list(sections),
        rel_span=float(recipe["rel_span"]),
    )
    if recipe.get("contour", "pattern_case") == "held":
        melody = _held_line(ctx.bars, ctx.epb)
        if not melody:
            raise ValueError(f"{recipe['id']}: empty melody")
        phrase_start = next(
            section.start * ctx.epb
            for section in sections
            if section.kind not in {"intro", "outro", "warmup", "cooldown"}
        )
        ctx = replace(
            ctx,
            melody=list(melody),
            raw=list(melody),
            phrases=(_joined(phrase_start, melody[phrase_start:]),),
        )
    return ctx


def _render_context(ctx: _Ctx, register) -> _Ctx:
    """The `_Ctx` `render_patterned_voices` would build for this register."""
    return replace(
        ctx,
        semitones=40 - register.guitar_floor,
        bass_low=register.guitar_floor,
        bass_high=register.guitar_bass_top,
        mid_low=register.guitar_mid_low,
        mid_high=register.guitar_mid_high,
        treble_floor=register.guitar_treble_floor,
        treble_top=register.guitar_treble_top,
        ceiling=register.guitar_ceiling,
    )


# ---------------------------------------------------------------------------
# canonical events and digests


def event_tuple(event: NoteEvent) -> tuple[Any, ...]:
    """The full `NoteEvent` surface in `EVENT_FIELDS` order.

    Beat and duration are stored as the exact floats the renderer emits. JSON
    round-trips a float to its shortest exact repr, so a tiny numeric drift is
    a visible diff; there is no rounding tolerance here.
    """
    return (
        event.bar,
        event.beat,
        event.midi,
        event.duration_beats,
        event.voice,
        event.velocity,
        event.staff,
        event.tie_start,
        event.tie_stop,
        event.slur_start,
        event.slur_stop,
        event.accent,
        event.tenuto,
        event.staccato,
        event.hairpin,
        event.pinned,
    )


def _sort_key(row: tuple[Any, ...]) -> tuple[Any, ...]:
    bar, beat, midi, duration, voice, velocity, *flags = row
    return (
        bar,
        beat,
        -1 if midi is None else midi,
        duration,
        voice,
        -1 if velocity is None else velocity,
        tuple(flags),
    )


def canonical_events(events) -> list[list[Any]]:
    """Sorted, JSON-ready rows. Ties are impossible in practice, but stable."""
    return [list(row) for row in sorted((event_tuple(event) for event in events), key=_sort_key)]


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def digest(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _descriptor(recipe: Mapping[str, Any]) -> dict[str, Any]:
    """The frozen recipe, JSON-ready and independent of the code under test."""
    return {
        "id": recipe["id"],
        "figure": recipe["figure"],
        "label": recipe["label"],
        "meter": recipe["meter"],
        "ensemble": recipe["ensemble"],
        "bpm": recipe["bpm"],
        "mood": recipe["mood"],
        "band": recipe["band"],
        "bars": recipe["bars"],
        "rel_span": recipe["rel_span"],
        "contour": recipe.get("contour", "pattern_case"),
        "sections": [list(values) for values in recipe["sections"]],
    }


def _galop_cells(ctx: _Ctx, patterns: list[str]) -> dict[str, list[int]]:
    from app.sonify.guitar_sor import _galop_run_cell

    cells: dict[str, list[int]] = {}
    for bar in range(ctx.bars):
        if _bar_pattern(ctx, bar, patterns) != "galop":
            continue
        _index, cell = _galop_run_cell(ctx, bar, patterns)
        cells.setdefault(cell, []).append(bar)
    return {name: sorted(bars) for name, bars in sorted(cells.items())}


# ---------------------------------------------------------------------------
# the manifest


def build_fixture(recipe: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = _descriptor(recipe)
    if recipe.get("expected_uncovered"):
        reason = recipe.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{recipe['id']}: expected_uncovered needs a reason")
        return {
            "id": descriptor["id"],
            "figure": descriptor["figure"],
            "label": descriptor["label"],
            "descriptor": descriptor,
            "covered": False,
            "expected_uncovered": True,
            "reason": reason.strip(),
        }

    ctx = build_context(recipe)
    register = register_for(C_KEY)
    meter = _meter_of(recipe)
    render_ctx = _render_context(ctx, register)
    with (
        compose_params(DEFAULT_PARAMS),
        compose_meter(meter),
        compose_register(C_KEY, register),
    ):
        patterns = list(_patterns(render_ctx))
        lead, support, low, divisions = render_patterned_voices(
            melody=list(render_ctx.melody),
            raw_pitches=list(render_ctx.raw),
            phrases=render_ctx.phrases,
            chord_at=dict(render_ctx.chord_at),
            kind_at=dict(render_ctx.kind_at),
            band_at=dict(render_ctx.band_at),
            musical_bars=render_ctx.bars,
            total_eighths=len(render_ctx.melody),
            bpm=render_ctx.bpm,
            ensemble=render_ctx.ensemble,
            mode=render_ctx.mode,
            character=render_ctx.character,
            character_at=render_ctx.character_at,
            sections=render_ctx.sections,
            rel_span=render_ctx.rel_span,
            register=register,
            regime_at=dict(render_ctx.regime_at),
        )
        cells = (
            _galop_cells(render_ctx, patterns)
            if str(descriptor["figure"]).startswith("galop")
            else None
        )

    voices = {
        "lead": canonical_events(lead),
        "support": canonical_events(support),
        "low": canonical_events(low),
    }
    counts = {name: len(rows) for name, rows in voices.items()}
    counts["total"] = sum(counts.values())
    fixture_payload = {
        "descriptor": descriptor,
        "patterns": patterns,
        "divisions": int(divisions),
    }
    notes_payload = {"voices": voices, "note_counts": counts}
    row: dict[str, Any] = {
        "id": descriptor["id"],
        "figure": descriptor["figure"],
        "label": descriptor["label"],
        "descriptor": descriptor,
        "covered": True,
        "patterns": patterns,
        "divisions": int(divisions),
        "note_counts": counts,
        "voices": voices,
        "fixture_digest": digest(fixture_payload),
        "notes_digest": digest(notes_payload),
        "score_digest": digest({**fixture_payload, **notes_payload}),
    }
    if cells is not None:
        row["cells"] = cells
    return row


def build_manifest() -> dict[str, Any]:
    rows = [build_fixture(recipe) for recipe in sorted(FIXTURES, key=lambda item: item["id"])]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("fixture ids are not unique")
    return {
        "kind": KIND,
        "version": VERSION,
        "fixture_version": FIXTURE_VERSION,
        "renderer": RENDERER,
        "register": REGISTER,
        "event_fields": list(EVENT_FIELDS),
        "note_sort": NOTE_SORT,
        "digest": "sha256 over canonical JSON (sorted keys, compact separators)",
        "fixtures": rows,
    }


__all__ = [
    "EVENT_FIELDS",
    "FIXTURES",
    "FIXTURE_VERSION",
    "KIND",
    "NOTE_SORT",
    "REGISTER",
    "RENDERER",
    "REQUIRED_FIGURES",
    "VERSION",
    "build_context",
    "build_fixture",
    "build_manifest",
    "canonical_events",
    "digest",
    "event_tuple",
]
