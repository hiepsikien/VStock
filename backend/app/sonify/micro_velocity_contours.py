"""Default micro-velocity contours extracted from the production figure writers.

This module owns the data half of the extraction described by
``docs/sonify-texture-studio.md`` section 6.9: the contours the production
renderer currently hardcodes inside its figure writers, expressed as
:class:`~app.studio.micro_velocity.MicroVelocity` values.

* Fixed shapes (Tremolo 4/4 and 3/4, Étude No. 1) are ``kind: "offsets"``.
* Shapes whose target velocity depends on a written level are ``kind: "rule"``
  with a rule id/version and explicit params (Galop 1/2, Étude No. 11,
  Cathedral Preludio).
* A rule is flattened to per-note offsets by :func:`flatten_rule` for the
  figure occurrence being rendered. The stored value stays the rule.

The module is inert at import. The production writer reaches it only through
``app.sonify.micro_velocity_writer`` when ``VSTOCK_MICRO_VELOCITY_WRITERS`` is
on; with the flag off (the default) ``render_patterned_voices`` keeps using the
hardcoded writers and every ``NoteEvent`` stays byte-identical.

Neutral levels used by the extraction harness and the feature-gated writer path
live in :data:`NEUTRAL_LEVELS`. They are verification and rendering metadata,
not part of the contour schema: section 6.9 forbids a stored ``base``. A
mapping entry means the writer writes that level when the contour is absent;
the contour is the delta on top of it. A family whose layers sit on different
role centres (Cathedral Preludio) maps each voice to its centre.

Coverage in this workstream:

* exact: Tremolo 4/4, Tremolo 3/4, Étude No. 1, Étude No. 11, Galop 1, Galop 2,
  Cathedral Preludio cell attacks.
* Cathedral Preludio's rule reads cross-voice context at flatten time: the
  covering canto velocity and the phrase raw level. The stored contour keeps
  only the cell shape, so it never duplicates the bar plan. Its 3/4 and 6/8
  tail whisper stays a written layer (the rule skips tail attacks).

Scope of the extracted values: a contour is the authored delta layer on the
figure's written level. The fixed/dynamic layers the golden fixture labels name
(Tremolo thumb and fill, Étude No. 1 inner arc, Étude No. 11 middle arch and
tilt, Galop step table, Cathedral cell nudge and canto clamp) are here.
Cross-voice accompaniment balances that the writers derive from the lead
(Étude No. 1 bass ``sung - 4``, Étude No. 11 lead echo ``hairpin - 8`` and bass
``hairpin - 4``) stay in the writer as written level/accompaniment for now;
absorbing them needs a composite rule and is a separate writer integration, not
invented offsets here. The absolute writers (snap/stab/fan/tremolo trim) stay
after the wave and are pinned/checked, not stored as relative offsets.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.sonify.guitar import (
    _TREMOLO_FILL_OFFSETS,
    _TREMOLO_QUARTER_OFFSETS,
    _TREMOLO_THUMB,
)
from app.sonify.guitar_sor import _GALOP_FLOOR, _GALOP_STEP
from app.sonify.guitar_villa import _ETUDE11_TILT, _ETUDE1_ARC, _ETUDE_MIDDLE
from app.sonify.model import NoteEvent
from app.studio.micro_velocity import (
    MicroVelocity,
    VelocityOffset,
    apply_relative_offsets,
)

__all__ = [
    "CATHEDRAL_PRELUDIO",
    "DEFAULT_CONTOURS",
    "ETUDE1",
    "ETUDE11",
    "EXTRACTED_FIGURES",
    "GALOP1",
    "GALOP2",
    "NEUTRAL_LEVELS",
    "TREMOLO_34",
    "TREMOLO_44",
    "TREMOLO_CONTOURS",
    "UNEXTRACTED_REASONS",
    "apply_flattened_rule",
    "covering_canto",
    "flatten_rule",
]

# ---------------------------------------------------------------------------
# Neutral written levels (verification metadata, not schema)
# ---------------------------------------------------------------------------

# Tremolo's writer places every cluster around `_TREMOLO_THUMB`; the quarter
# arch and the finger fill are the deltas.
TREMOLO_NEUTRAL = _TREMOLO_THUMB
# Étude No. 1 writes its middle voice at `_ETUDE_MIDDLE` plus `_ETUDE1_ARC`.
ETUDE1_NEUTRAL = _ETUDE_MIDDLE
# Étude No. 11's middle voice floors at 44; the arch, band nudge and tilt are
# the deltas.
ETUDE11_NEUTRAL = 44

# Cathedral Preludio writes two inner roles at their own centres; the phrase
# swell, the per-cell nudge and the canto clamp are the deltas.
CATHEDRAL_NEUTRAL: dict[int, int] = {2: 50, 4: 40}

# A family with a single written level maps to an int; Cathedral maps each
# inner voice to its role centre.
NeutralLevel = int | Mapping[int, int]

NEUTRAL_LEVELS: dict[str, NeutralLevel] = {
    "tremolo": TREMOLO_NEUTRAL,
    "etude1": ETUDE1_NEUTRAL,
    "etude11": ETUDE11_NEUTRAL,
    "catedral_preludio": CATHEDRAL_NEUTRAL,
}

# ---------------------------------------------------------------------------
# Fixed contours
# ---------------------------------------------------------------------------


def _tremolo_contour(quarters: int) -> MicroVelocity:
    """One tremolo bar: the quarter arch on the thumb and the finger fill.

    ``quarters`` is 4 for 4/4 and 3 for 3/4. Thumb entries use voice 3 so
    they apply to both the root and the fifth that strike with the thumb. The
    colour under a chord change takes the first quarter's level (voice 2,
    beat 0); non-chord-change clusters carry no sounding colour.
    """
    offsets = _TREMOLO_QUARTER_OFFSETS[quarters]
    notes: list[VelocityOffset] = []
    thumb: list[VelocityOffset] = []
    for quarter, quarter_offset in enumerate(offsets):
        beat = float(quarter)
        thumb.append(
            VelocityOffset(bar=0, beat=beat, voice=3, offset=quarter_offset)
        )
        if quarter == 0:
            notes.append(
                VelocityOffset(bar=0, beat=beat, voice=2, offset=quarter_offset)
            )
        for repeat, fill in enumerate(_TREMOLO_FILL_OFFSETS):
            notes.append(
                VelocityOffset(
                    bar=0,
                    beat=beat + repeat * 0.25,
                    voice=1,
                    offset=quarter_offset + fill,
                )
            )
    return MicroVelocity(kind="offsets", notes=tuple(notes), thumb=tuple(thumb))


TREMOLO_44 = _tremolo_contour(4)
TREMOLO_34 = _tremolo_contour(3)
# Tremolo is the one figure whose contour depends on the meter.
TREMOLO_CONTOURS: dict[str, MicroVelocity] = {
    "4/4": TREMOLO_44,
    "3/4": TREMOLO_34,
}

# Étude No. 1: the fixed inner arch. Indexes absent from `_ETUDE1_ARC` are
# either the two sung attacks or a rest, so the writer emits no middle note.
ETUDE1 = MicroVelocity(
    kind="offsets",
    notes=tuple(
        VelocityOffset(bar=0, beat=index / 4, voice=2, offset=offset)
        for index, offset in sorted(_ETUDE1_ARC.items())
    ),
)

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

# Étude No. 11: the inner sextuplet arch, the band nudge, and the tilt toward
# the last pluck. `_etude11_middle_vel` computes:
#
#   echo    = max(44, hairpin - 8)
#   ceiling = max(44, echo if band == "f" else echo - 1)
#   shaped  = min(ceiling, max(44, hairpin + arch[slot] + band_nudge))
#   level   = max(44, shaped + tilt[slot])
#
# `hairpin` is the written lead level at the quarter's first attack.
ETUDE11 = MicroVelocity(
    kind="rule",
    rule_id="etude11_middle",
    rule_version=1,
    params={
        "floor": ETUDE11_NEUTRAL,
        "echoDrop": 8,
        "ceilingDrop": 1,
        "arch": {"1": -10, "2": -6, "4": -7, "5": -10},
        "bandNudge": {"p": -2, "mp": -1, "mf": 0, "f": 2},
        "tilt": {str(slot): offset for slot, offset in _ETUDE11_TILT.items()},
    },
)

# Galop: one written peak for the bar, then a fixed step table under it.
# `_galop1_steps` / `_galop2_steps` are the shapes; the step size and floor
# are the params. `peakQuarter` is the quarter the statement cell rises to.
GALOP1 = MicroVelocity(
    kind="rule",
    rule_id="galop1",
    rule_version=1,
    params={"step": _GALOP_STEP, "floor": _GALOP_FLOOR, "peakQuarter": 3},
)

GALOP2 = MicroVelocity(
    kind="rule",
    rule_id="galop2",
    rule_version=1,
    params={"step": _GALOP_STEP, "floor": _GALOP_FLOOR},
)

# Cathedral Preludio: a two-beat cell writes the canto on the high voice and
# two inner roles under it. `_catedral_level(center, raw, nudge)` is the role
# centre plus the phrase swell plus a small repeat nudge; `_catedral_under`
# then keeps the inner attack six steps below the canto it sounds with:
#
#   level  = clamp(40, 70, center + raw - 64) + nudge + cellParity
#   target = min(level, canto - 6)        # inner voices only
#
# `center` is the neutral written level per voice (NEUTRAL_LEVELS); `raw` and
# `canto` are flatten-time context from the writer plan. The stored rule holds
# only the figure's cell shape, never the bar plan.
_CATEDRAL_RAW_CENTER = 64
_CATEDRAL_CENTER_WINDOW = (40, 70)

CATHEDRAL_PRELUDIO = MicroVelocity(
    kind="rule",
    rule_id="catedral_preludio",
    rule_version=1,
    params={
        "cellEighths": 4,
        "nudges": {
            "2": {"1": 2, "3": -2, "5": -4, "7": 1},
            "4": {"2": 3, "4": -3},
        },
        "cantoDrop": 6,
        "clampedVoices": [2, 4],
    },
)

# Registry keys are contour variant names: ``tremolo_44``/``tremolo_34`` are
# the two meters, the rest are figure ids. A future figure registry can attach
# one of these as `figure.microVelocity`.
DEFAULT_CONTOURS: dict[str, MicroVelocity] = {
    "tremolo_44": TREMOLO_44,
    "tremolo_34": TREMOLO_34,
    "etude1": ETUDE1,
    "etude11": ETUDE11,
    "galop1": GALOP1,
    "galop2": GALOP2,
    "catedral_preludio": CATHEDRAL_PRELUDIO,
}

EXTRACTED_FIGURES: tuple[str, ...] = (
    "tremolo",
    "etude1",
    "etude11",
    "galop1",
    "galop2",
    "catedral_preludio",
)

# Every required figure is exact now. The map stays because the harness offers
# a place to name a future uncovered figure, but no entry is silent: an absent
# key means the figure is extracted.
UNEXTRACTED_REASONS: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Rule flattening (pure; used by the extraction harness and a future Studio)
# ---------------------------------------------------------------------------


def flatten_rule(
    contour: MicroVelocity,
    events: Sequence[NoteEvent],
    *,
    origin_bar: int = 0,
    peak: int | None = None,
    base_at: Callable[[NoteEvent], int | None] | None = None,
    hairpin_at: Callable[[NoteEvent], int | None] | None = None,
    band_at: Callable[[NoteEvent], str | None] | None = None,
    raw_at: Callable[[NoteEvent], int | None] | None = None,
    canto_at: Callable[[NoteEvent], int | None] | None = None,
    beats_per_bar: float | None = None,
) -> MicroVelocity:
    """Flatten a rule contour into per-note offsets for one figure occurrence.

    ``origin_bar`` is the absolute bar the occurrence starts on; emitted
    entries are figure-relative (bar 0..). ``base_at`` returns the written
    level the offset is a delta on; it defaults to the event's own velocity,
    which is what a writer that has not yet been neutralised emits.

    ``peak`` is required by the Galop rules: the bar's written lead peak.
    ``hairpin_at`` is required by the Étude No. 11 rule: the written lead
    level at the same bar and quarter. ``band_at`` resolves the bar's band.

    ``raw_at``, ``canto_at`` and ``beats_per_bar`` are the context the Cathedral
    Preludio rule needs. ``raw_at`` is the writer's phrase level at the event's
    attack (the ``raw`` of ``_catedral_level``). ``canto_at`` is the velocity
    of the voice-1 attack covering the same beat, i.e. the cross-voice canto
    that ``_catedral_under`` clamps against. ``beats_per_bar`` bounds the
    2-beat cell so a 3/4 or 6/8 tail is skipped rather than mistaken for a
    cell. For that rule ``base_at`` must return the voice's role centre.

    This is deliberately fixture-scoped: a rule keeps its params and is
    flattened only when a concrete event list exists. Unsupported rule ids
    raise ``ValueError`` instead of guessing offsets.
    """
    if not isinstance(contour, MicroVelocity) or contour.kind != "rule":
        raise ValueError("flatten_rule requires a kind 'rule' MicroVelocity")
    rule_id = contour.rule_id
    params = dict(contour.params or {})
    clamped_voices = {
        int(voice) for voice in params.get("clampedVoices", ())
    }
    canto_drop = int(params.get("cantoDrop", 6))
    entries: list[VelocityOffset] = []
    for event in events:
        if (
            not isinstance(event, NoteEvent)
            or event.midi is None
            or event.velocity is None
        ):
            continue
        base: int | None = None
        if rule_id in {"galop1", "galop2"}:
            if peak is None:
                raise ValueError(f"{rule_id} needs the bar's written peak")
            steps = _galop_steps(rule_id, event.beat, event.duration_beats, params)
            target = max(
                int(params["floor"]),
                int(peak) - steps * int(params["step"]),
            )
        elif rule_id == "etude11_middle":
            if hairpin_at is None:
                raise ValueError("etude11_middle needs the written hairpin")
            hairpin = hairpin_at(event)
            if hairpin is None:
                continue
            band = band_at(event) if band_at is not None else None
            slot = _etude11_slot(event.beat)
            if slot is None:
                continue
            target = _etude11_target(hairpin, slot, band, params)
        elif rule_id == "catedral_preludio":
            if beats_per_bar is None:
                raise ValueError("catedral_preludio needs beats_per_bar")
            if raw_at is None:
                raise ValueError("catedral_preludio needs the phrase raw level")
            if canto_at is None:
                raise ValueError("catedral_preludio needs the covering canto")
            if base_at is None:
                raise ValueError("catedral_preludio needs the role centre")
            cell = _catedral_cell(event.beat, event.bar, beats_per_bar, params)
            if cell is None:
                continue
            nudge = _catedral_nudge(event.voice, cell[0], params)
            if nudge is None:
                continue
            centre = base_at(event)
            if centre is None:
                continue
            raw = raw_at(event)
            if raw is None:
                continue
            level = _catedral_level(centre, raw, nudge + cell[1])
            if event.voice in clamped_voices:
                canto = canto_at(event)
                if canto is None:
                    continue
                level = min(level, int(canto) - canto_drop)
            target = level
            base = centre
        else:
            raise ValueError(f"unsupported rule id {rule_id!r}")

        if base is None:
            base = base_at(event) if base_at is not None else event.velocity
        if base is None:
            continue
        entries.append(
            VelocityOffset(
                bar=event.bar - origin_bar,
                beat=event.beat,
                voice=event.voice,
                offset=int(target) - int(base),
            )
        )
    return MicroVelocity(kind="offsets", notes=tuple(entries))


def covering_canto(
    events: Sequence[NoteEvent],
    bar: int,
    beat: float,
    *,
    voice: int = 1,
    epsilon: float = 1e-6,
) -> int | None:
    """Velocity of the ``voice`` attack sounding on ``(bar, beat)``, if any.

    This is the cross-voice context the Cathedral rule clamps under: an inner
    attack is held a few steps below the high note it sounds with, so the rule
    cannot be flattened from the inner voice alone. Callers pass the writer's
    already-planned canto events; this never infers or moves the plan.
    """
    for event in events:
        if (
            not isinstance(event, NoteEvent)
            or event.voice != voice
            or event.bar != bar
            or event.midi is None
            or event.velocity is None
        ):
            continue
        if event.beat <= beat + epsilon < event.beat + event.duration_beats:
            return int(event.velocity)
    return None


def _galop_steps(
    rule_id: str, beat: float, duration: float, params: Mapping[str, Any]
) -> int:
    """Steps under the written peak, mirroring the writer's step table.

    Mirror of `guitar_sor._galop1_steps` / `_galop2_steps`. Bump the contour
    `ruleVersion` whenever the writer's step table changes.
    """
    if rule_id == "galop1":
        peak_quarter = int(params.get("peakQuarter", 3))
        quarter = min(max(int(math.floor(beat + 1e-9)), 0), peak_quarter)
        local = round(beat - quarter, 2)
        if local <= 0.0:
            inner = 0
        elif duration >= 0.49:
            inner = 1
        elif local < 0.7:
            inner = 1
        else:
            inner = 2
        return inner + peak_quarter - quarter

    second = beat >= 1.99
    local = round(beat % 2.0, 2)
    if local >= 2.0:
        local = 0.0
    cell = 0 if second else 2
    if local <= 0.0:
        inner = 2
    elif local < 1.0:
        inner = 0
    else:
        inner = 4
    return inner + cell


def _etude11_slot(beat: float) -> int | None:
    """Sextuplet slot 1, 2, 4 or 5, or None for an off-sextuplet attack.

    Mirror of the writer's `_etude11_middle_vel` slot assumption. Bump the
    contour `ruleVersion` whenever the writer's arch/nudge/tilt changes.
    """
    quarter = int(math.floor(beat + 1e-9))
    raw = (beat - quarter) * 6
    slot = int(round(raw))
    if abs(raw - slot) > 1e-6:
        return None
    return slot


def _etude11_target(
    hairpin: int, slot: int, band: str | None, params: Mapping[str, Any]
) -> int:
    floor = int(params.get("floor", 44))
    echo = max(floor, int(hairpin) - int(params.get("echoDrop", 8)))
    ceiling = max(
        floor,
        echo if band == "f" else echo - int(params.get("ceilingDrop", 1)),
    )
    arch = int((params.get("arch") or {}).get(str(slot), 0))
    nudge = int((params.get("bandNudge") or {}).get(band, 0))
    shaped = min(ceiling, max(floor, int(hairpin) + arch + nudge))
    tilt = int((params.get("tilt") or {}).get(str(slot), 0))
    return max(floor, shaped + tilt)


def _catedral_cell(
    beat: float,
    bar: int,
    beats_per_bar: float,
    params: Mapping[str, Any],
) -> tuple[int, int] | None:
    """(local sixteenth, cell parity) for a full two-beat cell, else None.

    Mirror of `guitar_barrios._render_catedral_preludio_bar`'s cell loop: a
    cell is `cellEighths` eighths and only exists when it fits inside the bar.
    The parity alternates with the cell's absolute position, exactly as the
    writer's `parity = 1 if (eighth // 4) % 2 else 0`. Tail attacks in 3/4 or
    6/8 fail the fit test and are skipped. Bump the contour `ruleVersion`
    whenever the writer's cell layout changes.
    """
    cell = int(params.get("cellEighths", 4))
    if cell <= 0 or beats_per_bar is None or beats_per_bar <= 0:
        return None
    cell_beats = cell / 2
    index = int(math.floor(beat / cell_beats + 1e-9))
    start = index * cell_beats
    if start + cell_beats > float(beats_per_bar) + 1e-9:
        return None
    raw = (beat - start) * 4
    local16 = int(round(raw))
    if abs(raw - local16) > 1e-6:
        return None
    cell_start_eighth = bar * int(round(float(beats_per_bar) * 2)) + index * cell
    parity = 1 if (cell_start_eighth // 4) % 2 else 0
    return local16, parity


def _catedral_nudge(
    voice: int, local16: int, params: Mapping[str, Any]
) -> int | None:
    """The figure's repeat nudge for one inner voice and cell slot."""
    nudges = params.get("nudges") or {}
    lane = nudges.get(str(voice))
    if not isinstance(lane, Mapping):
        return None
    value = lane.get(str(local16))
    return None if value is None else int(value)


def _catedral_level(center: int, raw: int, nudge: int) -> int:
    """Role centre, phrase swell, then the nudge.

    Mirror of `guitar_barrios._catedral_level`: the centre stays inside 40..70
    and the nudge may step just outside it. Bump the contour `ruleVersion`
    whenever the writer's window or raw centre changes.
    """
    low, high = _CATEDRAL_CENTER_WINDOW
    base = max(low, min(high, int(center) + int(raw) - _CATEDRAL_RAW_CENTER))
    return base + int(nudge)


def apply_flattened_rule(
    events: Sequence[NoteEvent],
    contour: MicroVelocity,
    *,
    origin_bar: int = 0,
    peak: int | None = None,
    base_at: Callable[[NoteEvent], int | None] | None = None,
    hairpin_at: Callable[[NoteEvent], int | None] | None = None,
    band_at: Callable[[NoteEvent], str | None] | None = None,
    raw_at: Callable[[NoteEvent], int | None] | None = None,
    canto_at: Callable[[NoteEvent], int | None] | None = None,
    beats_per_bar: float | None = None,
) -> list[NoteEvent]:
    """Flatten ``contour`` and apply it to ``events`` in one step."""
    flat = flatten_rule(
        contour,
        events,
        origin_bar=origin_bar,
        peak=peak,
        base_at=base_at,
        hairpin_at=hairpin_at,
        band_at=band_at,
        raw_at=raw_at,
        canto_at=canto_at,
        beats_per_bar=beats_per_bar,
    )
    return apply_relative_offsets(events, flat, origin_bar=origin_bar)
