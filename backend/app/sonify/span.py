"""Long-form layouts: one movement for a week, four for a month, three for a quarter, twelve for a year.

A movement is one FormSpec. The week pins each session but the last to 31 bars of
content plus one empty bar, so the close holds through the downbeat of the next session.
Longer spans let render spread the movement's own bars across the form.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from app.sonify.groove import gap_direction
from app.sonify.form import (
    METER_34,
    METER_44,
    METER_54,
    METER_64,
    METER_68,
    METER_78,
    METER_128,
    FormSection,
    FormSpec,
    Meter,
    swing_for,
)
from app.sonify.keys import (
    C_KEY,
    KeySpec,
    Mode,
    MovementCharacter,
    OutroOverride,
    boundary_regimes,
    finale_outro,
    jazz_month_keys,
    jazz_quarter_keys,
    month_keys,
    movement_character,
    movement_mode,
    quarter_keys,
    stock_home_key,
    year_key,
)
from app.sonify.model import Ensemble, Variant
from app.sonify.model import (
    Bar,
    DynamicEvent,
    HarmonyEvent,
    NoteEvent,
    Score,
    WedgeEvent,
)
from app.sonify.render import assign_source_bars

BARS_PER_SESSION = 32
WEEK_BPM = 90
MONTH_REST_SECONDS = 6.0
QUARTER_REST_SECONDS = 8.0
SEASON_REST_SECONDS = 4.0
YEAR_SEASON_REST_SECONDS = 8.0
MIN_YEAR_CANDLES = 30
# About three HOSE sessions of 5-minute bars. A month that has only just opened
# joins the previous month instead of becoming its own eight-minute movement.
MIN_QUARTER_MONTH_CANDLES = 150

SectionPart = tuple[int, str, int, bool]


def _part(length: int, kind: str, slot: int, bridge: bool = False) -> SectionPart:
    return (length, kind, slot, bridge)


def _sections(parts: tuple[SectionPart, ...]) -> tuple[FormSection, ...]:
    sections: list[FormSection] = []
    cursor = 0
    for length, kind, slot, bridge in parts:
        sections.append(FormSection(cursor, cursor + length, kind, slot, bridge))  # type: ignore[arg-type]
        cursor += length
    return tuple(sections)


def _spec(
    bars: int,
    bpm: int,
    parts: tuple[SectionPart, ...],
    chunks: tuple[int, ...],
    meter: Meter = METER_44,
) -> FormSpec:
    built = _sections(parts)
    if built[-1].end != bars:
        raise ValueError(f"sections cover {built[-1].end} bars, form has {bars}")
    if chunks[-1] != bars:
        raise ValueError("the last chunk must end on the last bar")
    return FormSpec(bars, bpm, built, chunks, borrowed=True, meter=meter)


def _retarget_pedal(spec: FormSpec, *, intro: int | None = None, outro: int | None = None) -> FormSpec:
    """Give surplus intro and outro bars to the neighbouring phrase. Total length stays put."""
    sections = list(spec.sections)
    if intro is not None:
        index = next((i for i, section in enumerate(sections) if section.kind == "intro"), None)
        if index is not None and index + 1 < len(sections):
            current = sections[index]
            extra = current.end - current.start - intro
            if extra > 0:
                nxt = sections[index + 1]
                sections[index] = replace(current, end=current.start + intro)
                sections[index + 1] = replace(nxt, start=current.start + intro)
    if outro is not None:
        index = next((i for i, section in enumerate(sections) if section.kind == "outro"), None)
        if index is not None and index > 0:
            current = sections[index]
            extra = current.end - current.start - outro
            if extra > 0:
                previous = sections[index - 1]
                start = current.end - outro
                sections[index - 1] = replace(previous, end=start)
                sections[index] = replace(current, start=start)
    return replace(spec, sections=tuple(sections))


def _with_trio(spec: FormSpec) -> FormSpec:
    return replace(
        spec,
        sections=tuple(
            replace(section, trio=True)
            if section.kind == "phrase" and section.regime_slot == 1
            else section
            for section in spec.sections
        ),
    )


def frame_bars_for(meter: Meter, span: str) -> int:
    """Bars of warm-up and of cool-down. 1Y is the short frame."""
    key = (meter.beats, meter.beat_type)
    if span == "1Y":
        table = {(4, 4): 2, (3, 4): 3, (6, 8): 3, (12, 8): 1, (6, 4): 1, (5, 4): 2, (7, 8): 2}
    else:
        table = {(4, 4): 4, (3, 4): 6, (6, 8): 6, (12, 8): 3, (6, 4): 3, (5, 4): 4, (7, 8): 5}
    return table[key]


def attach_frame(spec: FormSpec, span: str) -> FormSpec:
    """Shift the body right and pedal a warm-up and a cool-down outside it."""
    if span not in ("1M", "3M", "1Y"):
        return spec
    count = frame_bars_for(spec.meter, span)
    shifted = [
        FormSection(
            section.start + count,
            section.end + count,
            section.kind,
            section.regime_slot,
            section.bridge,
            section.trio,
        )
        for section in spec.sections
    ]
    last_slot = spec.sections[-1].regime_slot
    sections = (
        FormSection(0, count, "warmup", 0),
        *shifted,
        FormSection(spec.bars + count, spec.bars + 2 * count, "cooldown", last_slot),
    )
    chunks = tuple(end + count for end in spec.chunks[:-1]) + (spec.bars + 2 * count,)
    return FormSpec(
        spec.bars + 2 * count,
        spec.bpm,
        sections,
        chunks,
        borrowed=spec.borrowed,
        meter=spec.meter,
    )


def frame_bounds(spec: FormSpec) -> tuple[int, int]:
    """Body start and cool-down start. A spec with no frame returns (0, bars)."""
    warmup = 0
    cooldown = spec.bars
    for section in spec.sections:
        if section.kind == "warmup":
            warmup = section.end
        elif section.kind == "cooldown":
            cooldown = section.start
    return warmup, cooldown


def frame_seconds(spec: FormSpec) -> tuple[float, float]:
    warmup, cooldown = frame_bounds(spec)
    eighth = spec.meter.eighths_per_bar * 30.0 / spec.bpm
    return warmup * eighth, (spec.bars - cooldown) * eighth


def week_spec(session_count: int) -> FormSpec:
    """One continuous movement. A short week is n sessions, not a stretched five."""
    count = max(1, min(5, session_count))
    parts: list[SectionPart] = []
    for index in range(count):
        for step in range(4):
            if index == 0 and step == 0:
                parts.append(_part(4, "intro", index))
                parts.append(_part(4, "phrase", index))
            elif index == count - 1 and step == 3:
                parts.append(_part(4, "phrase", index))
                parts.append(_part(4, "outro", index))
            else:
                parts.append(_part(8, "phrase", index))
    chunks = tuple((index + 1) * BARS_PER_SESSION for index in range(count))
    return _spec(count * BARS_PER_SESSION, WEEK_BPM, tuple(parts), chunks)


def week_source_groups(session_lengths: list[int]) -> list[list[int]]:
    """31 content bars and one held close per session, except the last session, which fills 32."""
    if not session_lengths or any(length < 1 for length in session_lengths):
        raise ValueError("each session needs at least one bar")
    groups: list[list[int]] = []
    offset = 0
    last = len(session_lengths) - 1
    for index, length in enumerate(session_lengths):
        content = BARS_PER_SESSION if index == last else BARS_PER_SESSION - 1
        local = assign_source_bars(length, content)
        groups.extend([[item + offset for item in group] for group in local])
        if index != last:
            groups.append([])
        offset += length
    return groups


def _fast(bridge: bool = False) -> FormSpec:
    """Movement I, still 4/4. The 24-bar phrase is the contrast."""
    return _spec(
        96,
        96,
        (
            _part(8, "intro", 0),
            _part(32, "phrase", 0),
            _part(24, "phrase", 1, bridge),
            _part(24, "phrase", 2),
            _part(8, "outro", 2),
        ),
        (40, 64, 96),
    )


def _finale(bridge: bool = False) -> FormSpec:
    return _spec(
        96,
        96,
        (
            _part(8, "intro", 0),
            _part(32, "phrase", 0),
            _part(24, "phrase", 1, bridge),
            _part(16, "phrase", 2),
            _part(16, "outro", 2),
        ),
        (40, 64, 96),
    )


def _scherzo(bridge: bool = False) -> FormSpec:
    return _spec(
        96,
        120,
        (
            _part(8, "intro", 0),
            _part(24, "phrase", 0),
            _part(24, "phrase", 1, bridge),
            _part(24, "phrase", 2),
            _part(8, "phrase", 2),
            _part(8, "outro", 2),
        ),
        (56, 96),
        METER_34,
    )


def _guitar_meter(spec: FormSpec) -> FormSpec:
    """Keep the symphony bars and tempo. Slow movements become 3/4 and the scherzo becomes 6/8."""
    if spec.meter == METER_68:
        meter: Meter = METER_34
    elif spec.meter == METER_34:
        meter = METER_68
    else:
        return spec
    return replace(spec, meter=meter)


def retarget_torroba_meter(spec: FormSpec, character: MovementCharacter | None) -> FormSpec:
    """Move a 4/4 Torroba movement to 3/4 when it is calm or a selloff.

    3/4 and 6/8 stay on the meter `_guitar_meter` already chose. Rally and
    volatile stay in 4/4. Tempo stays. Call this before `attach_frame`.
    """
    if (spec.meter.beats, spec.meter.beat_type) != (4, 4):
        return spec
    if character not in ("calm", "selloff"):
        return spec
    return replace(spec, meter=METER_34)


def retarget_torroba_tempo(spec: FormSpec, character: MovementCharacter | None) -> FormSpec:
    """Lift a Torroba movement into 96–140 BPM. Nothing slower than 96 survives.

    The floor is read from the meter the movement has *after*
    `retarget_torroba_meter`, so a 4/4 calm that just became 3/4 takes the 3/4
    row. An unknown mood takes the calm row; an unknown meter takes the band's
    minimum. Call this right after `retarget_torroba_meter`.
    """
    from app.sonify.guitar_torroba import TORROBA_TEMPO_FLOOR, TORROBA_TEMPO_MAX, TORROBA_TEMPO_MIN

    kind = f"{spec.meter.beats}/{spec.meter.beat_type}"
    floor = TORROBA_TEMPO_FLOOR.get((character or "calm", kind), TORROBA_TEMPO_MIN)
    bpm = min(TORROBA_TEMPO_MAX, max(spec.bpm, floor))
    if bpm == spec.bpm:
        return spec
    return replace(spec, bpm=bpm)


def _torroba_span(variant: str, ensemble: str) -> bool:
    return variant == "guitar" and ensemble == "torroba"


def _framed_torroba(
    bodies: tuple[FormSpec, ...],
    characters: Sequence[MovementCharacter],
    counts: Sequence[int],
    span: str,
    labels: tuple[str, ...],
    rests: tuple[float, ...],
) -> tuple[Movement, ...]:
    """Retarget each unframed body, then attach the frame for that meter."""
    if not (len(bodies) == len(characters) == len(counts) == len(labels) == len(rests)):
        raise ValueError(f"a {span} Torroba plan needs one character per movement")
    specs = tuple(
        attach_frame(
            retarget_torroba_tempo(retarget_torroba_meter(body, character), character),
            span,
        )
        for body, character in zip(bodies, characters)
    )
    return tuple(
        Movement(label, spec, count, rest)
        for label, spec, count, rest in zip(labels, specs, counts, rests)
    )


def month_specs(variant: str = "symphony") -> tuple[FormSpec, FormSpec, FormSpec, FormSpec]:
    """Body only. `attach_frame` adds the warm-up and the cool-down."""
    if variant == "guitar":
        return tuple(_guitar_meter(spec) for spec in month_specs("symphony"))
    bridge = variant in ("jazz", "ambient")
    if variant == "minimalist":
        first = _spec(
            76,
            96,
            (
                _part(8, "intro", 0),
                _part(24, "phrase", 0),
                _part(20, "phrase", 1),
                _part(16, "phrase", 2),
                _part(8, "outro", 2),
            ),
            (32, 52, 76),
            METER_54,
        )
        second = _spec(
            72,
            72,
            (
                _part(8, "intro", 0),
                _part(24, "phrase", 0),
                _part(16, "phrase", 1, True),
                _part(24, "phrase", 2),
            ),
            (32, 72),
        )
        third = _spec(
            82,
            120,
            (
                _part(8, "intro", 0),
                _part(16, "phrase", 0),
                _part(16, "phrase", 1),
                _part(16, "phrase", 2),
                _part(14, "phrase", 2),
                _part(12, "outro", 2),
            ),
            (40, 82),
            METER_78,
        )
        return (
            _retarget_pedal(first, intro=4, outro=4),
            _retarget_pedal(second, intro=4),
            _with_trio(_retarget_pedal(third, intro=4, outro=6)),
            _retarget_pedal(_finale(), intro=4, outro=8),
        )
    if variant == "jazz":
        second = _spec(
            48,
            72,
            (
                _part(4, "intro", 0),
                _part(16, "phrase", 0),
                _part(12, "phrase", 1, True),
                _part(16, "phrase", 2),
            ),
            (20, 48),
            METER_128,
        )
        return (
            _retarget_pedal(_fast(True), intro=4, outro=4),
            second,
            _with_trio(_retarget_pedal(_scherzo(), intro=4, outro=4)),
            _retarget_pedal(_finale(True), intro=4, outro=8),
        )
    if variant == "ambient":
        second = _spec(
            48,
            72,
            (
                _part(4, "intro", 0),
                _part(16, "phrase", 0),
                _part(12, "phrase", 1, True),
                _part(16, "phrase", 2),
            ),
            (20, 48),
            METER_64,
        )
        return (
            _retarget_pedal(_fast(True), intro=4, outro=4),
            second,
            _with_trio(_retarget_pedal(_scherzo(True), intro=4, outro=4)),
            _retarget_pedal(_finale(True), intro=4, outro=8),
        )
    second = _spec(
        96,
        72,
        (
            _part(8, "intro", 0),
            _part(32, "phrase", 0),
            _part(24, "phrase", 1, True),
            _part(32, "phrase", 2),
        ),
        (40, 96),
        METER_68,
    )
    return (
        _retarget_pedal(_fast(bridge), intro=4, outro=4),
        _retarget_pedal(second, intro=4),
        _with_trio(_retarget_pedal(_scherzo(), intro=4, outro=4)),
        _retarget_pedal(_finale(bridge), intro=4, outro=8),
    )


def quarter_specs(variant: str = "symphony") -> tuple[FormSpec, FormSpec, FormSpec]:
    if variant == "guitar":
        return tuple(_guitar_meter(spec) for spec in quarter_specs("symphony"))
    if variant == "minimalist":
        first = _spec(
            153,
            96,
            (
                _part(6, "intro", 0),
                _part(45, "phrase", 0),
                _part(51, "phrase", 1),
                _part(38, "phrase", 2),
                _part(13, "outro", 2),
            ),
            (51, 102, 153),
            METER_54,
        )
        second = _spec(
            120,
            60,
            (
                _part(8, "intro", 0),
                _part(32, "phrase", 0),
                _part(40, "phrase", 1, True),
                _part(32, "phrase", 2),
                _part(8, "outro", 2),
            ),
            (40, 80, 120),
        )
        third = _spec(
            246,
            108,
            (
                _part(9, "intro", 0),
                _part(64, "phrase", 0),
                _part(73, "phrase", 1),
                _part(55, "phrase", 2),
                _part(45, "outro", 2),
            ),
            (73, 146, 246),
            METER_78,
        )
        return (
            _retarget_pedal(first, intro=3, outro=4),
            _retarget_pedal(second, intro=4, outro=4),
            _retarget_pedal(third, intro=4, outro=10),
        )
    drone = variant == "ambient"
    first = _spec(
        192,
        96,
        (
            _part(8, "intro", 0),
            _part(56, "phrase", 0),
            _part(64, "phrase", 1, drone),
            _part(48, "phrase", 2),
            _part(16, "outro", 2),
        ),
        (64, 128, 192),
    )
    if variant == "jazz":
        second = _spec(
            80,
            60,
            (
                _part(4, "intro", 0),
                _part(24, "phrase", 0),
                _part(24, "phrase", 1, True),
                _part(24, "phrase", 2),
                _part(4, "outro", 2),
            ),
            (28, 52, 80),
            METER_128,
        )
    elif variant == "ambient":
        second = _spec(
            80,
            60,
            (
                _part(4, "intro", 0),
                _part(24, "phrase", 0),
                _part(24, "phrase", 1, True),
                _part(24, "phrase", 2),
                _part(4, "outro", 2),
            ),
            (28, 52, 80),
            METER_64,
        )
    else:
        second = _spec(
            160,
            60,
            (
                _part(8, "intro", 0),
                _part(44, "phrase", 0),
                _part(56, "phrase", 1, True),
                _part(44, "phrase", 2),
                _part(8, "outro", 2),
            ),
            (52, 108, 160),
            METER_68,
        )
    third = _spec(
        216,
        108,
        (
            _part(8, "intro", 0),
            _part(56, "phrase", 0),
            _part(64, "phrase", 1, drone),
            _part(48, "phrase", 2),
            _part(40, "outro", 2),
        ),
        (64, 128, 216),
    )
    second_outro = 2 if variant in ("jazz", "ambient") else 4
    return (
        _retarget_pedal(first, intro=4, outro=4),
        _retarget_pedal(second, intro=4, outro=second_outro),
        _retarget_pedal(third, intro=4, outro=8),
    )


def year_specs(variant: str = "symphony") -> tuple[FormSpec, ...]:
    if variant == "guitar":
        return tuple(_guitar_meter(spec) for spec in year_specs("symphony"))
    drone = variant == "ambient"
    if variant == "minimalist":
        opener = _spec(
            64,
            100,
            (
                _part(8, "intro", 0),
                _part(24, "phrase", 0),
                _part(24, "phrase", 1),
                _part(8, "outro", 2),
            ),
            (32, 64),
            METER_54,
        )
        closer = _spec(
            96,
            108,
            (
                _part(8, "intro", 0),
                _part(36, "phrase", 0),
                _part(36, "phrase", 1),
                _part(16, "outro", 2),
            ),
            (44, 96),
            METER_78,
        )
    else:
        opener = _spec(
            80,
            100,
            (
                _part(8, "intro", 0),
                _part(32, "phrase", 0),
                _part(32, "phrase", 1, drone),
                _part(8, "outro", 2),
            ),
            (40, 80),
        )
        closer = _spec(
            111,
            108,
            (
                _part(4, "intro", 0),
                _part(46, "phrase", 0),
                _part(42, "phrase", 1, drone),
                _part(13, "phrase", 2),
                _part(6, "outro", 2),
            ),
            (50, 111),
            METER_34,
        )
    if variant == "jazz":
        center = _spec(
            48,
            66,
            (
                _part(4, "intro", 0),
                _part(16, "phrase", 0),
                _part(12, "phrase", 1, True),
                _part(12, "phrase", 2),
                _part(4, "outro", 2),
            ),
            (20, 48),
            METER_128,
        )
    elif variant == "ambient":
        center = _spec(
            48,
            66,
            (
                _part(4, "intro", 0),
                _part(16, "phrase", 0),
                _part(12, "phrase", 1, True),
                _part(12, "phrase", 2),
                _part(4, "outro", 2),
            ),
            (20, 48),
            METER_64,
        )
    elif variant == "minimalist":
        center = _spec(
            72,
            66,
            (
                _part(8, "intro", 0),
                _part(24, "phrase", 0),
                _part(16, "phrase", 1, True),
                _part(16, "phrase", 2),
                _part(8, "outro", 2),
            ),
            (32, 72),
        )
    else:
        center = _spec(
            96,
            66,
            (
                _part(8, "intro", 0),
                _part(32, "phrase", 0),
                _part(24, "phrase", 1, True),
                _part(24, "phrase", 2),
                _part(8, "outro", 2),
            ),
            (40, 96),
            METER_68,
        )
    finale = _spec(
        108,
        96,
        (
            _part(8, "intro", 0),
            _part(32, "phrase", 0),
            _part(32, "phrase", 1, drone),
            _part(24, "phrase", 2),
            _part(12, "outro", 2),
        ),
        (40, 72, 108),
    )
    opener = _retarget_pedal(opener, intro=4, outro=4)
    if variant in ("jazz", "ambient"):
        center = _retarget_pedal(center, outro=2)
    else:
        center = _retarget_pedal(center, intro=4, outro=4)
    if variant == "minimalist":
        closer = _with_trio(_retarget_pedal(closer, intro=4, outro=6))
    else:
        closer = _with_trio(closer)
    finale = _retarget_pedal(finale, intro=4, outro=8)
    return (
        opener, center, closer,
        opener, center, closer,
        opener, center, closer,
        opener, center, finale,
    )


def split_into(count: int, parts: int) -> list[int]:
    """Contiguous sizes that differ by at most one. The remainder stays on the last part."""
    if parts < 1 or count < parts:
        raise ValueError("need at least one item in each part")
    base, extra = divmod(count, parts)
    # The last `extra` parts are one larger, so the finale carries the remainder
    # and neighboring parts differ by at most one.
    return [base] * (parts - extra) + [base + 1] * extra


def slice_score(score: Score, start: int, end: int) -> Score:
    """Rebase one section of a score. Ties that crossed the cut are cleared.

    The live export writes a whole movement in one MuseScore call and does not
    use this. It stays so a movement can be cut into files again without
    leaving a tie that points outside the file.
    """
    if not 0 <= start < end <= score.bars:
        raise ValueError("chunk is outside the movement")

    def notes(events: tuple[NoteEvent, ...]) -> tuple[NoteEvent, ...]:
        kept: list[NoteEvent] = []
        for event in events:
            if not start <= event.bar < end:
                continue
            kept.append(
                replace(
                    event,
                    bar=event.bar - start,
                    tie_stop=event.tie_stop and event.bar != start,
                    tie_start=event.tie_start and event.bar != end - 1,
                )
            )
        return tuple(kept)

    def wedges(events: tuple[WedgeEvent, ...]) -> tuple[WedgeEvent, ...]:
        return tuple(replace(event, bar=event.bar - start) for event in events if start <= event.bar < end)

    def dynamics(events: tuple[DynamicEvent, ...]) -> tuple[DynamicEvent, ...]:
        return tuple(replace(event, bar=event.bar - start) for event in events if start <= event.bar < end)

    def harmonies(events: tuple[HarmonyEvent, ...]) -> tuple[HarmonyEvent, ...]:
        return tuple(replace(event, bar=event.bar - start) for event in events if start <= event.bar < end)

    return replace(
        score,
        bars=end - start,
        high=notes(score.high),
        lead=notes(score.lead),
        support=notes(score.support),
        comp=notes(score.comp),
        low=notes(score.low),
        lead_wedges=wedges(score.lead_wedges),
        support_wedges=wedges(score.support_wedges),
        lead_dynamics=dynamics(score.lead_dynamics),
        support_dynamics=dynamics(score.support_dynamics),
        low_wedges=wedges(score.low_wedges),
        high_wedges=wedges(score.high_wedges),
        high_dynamics=dynamics(score.high_dynamics),
        comp_wedges=wedges(score.comp_wedges),
        comp_dynamics=dynamics(score.comp_dynamics),
        harmonies=harmonies(score.harmonies),
        dynamics=dynamics(score.dynamics),
    )


@dataclass(frozen=True)
class Movement:
    label: str
    spec: FormSpec
    session_count: int
    rest_after: float


def plan_week(session_count: int) -> tuple[Movement, ...]:
    spec = week_spec(session_count)
    return (Movement("Tuần", spec, session_count, 0.0),)


def plan_month(session_counts: list[int], variant: str = "symphony") -> tuple[Movement, ...]:
    specs = tuple(attach_frame(spec, "1M") for spec in month_specs(variant))
    if len(session_counts) != 4:
        raise ValueError("a month is four movements")
    labels = ("I", "II", "III", "IV")
    rests = (MONTH_REST_SECONDS, MONTH_REST_SECONDS, MONTH_REST_SECONDS, 0.0)
    return tuple(
        Movement(label, spec, count, rest)
        for label, spec, count, rest in zip(labels, specs, session_counts, rests)
    )


def plan_quarter(session_counts: list[int], variant: str = "symphony") -> tuple[Movement, ...]:
    specs = tuple(attach_frame(spec, "3M") for spec in quarter_specs(variant))
    if len(session_counts) != 3:
        raise ValueError("a quarter is three movements")
    labels = ("I", "II", "III")
    rests = (QUARTER_REST_SECONDS, QUARTER_REST_SECONDS, 0.0)
    return tuple(
        Movement(label, spec, count, rest)
        for label, spec, count, rest in zip(labels, specs, session_counts, rests)
    )


def _season(day: date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3


@dataclass(frozen=True)
class PreparedMovement:
    """One movement ready for `render`: its own bars, form, key, and chart slice."""

    label: str
    spec: FormSpec
    bars: list[Bar]
    groups: list[list[int]] | None
    rest_after: float
    key: KeySpec = C_KEY
    character: MovementCharacter | None = None
    outro_override: OutroOverride | None = None
    mode: Mode = "major"
    swing: bool = False
    home_pedal: bool = False
    session_characters: tuple[MovementCharacter, ...] = ()
    bar_characters: tuple[MovementCharacter | None, ...] | None = None
    gap_leads: tuple[str | None, ...] | None = None

    @property
    def candle_count(self) -> int:
        return len(self.bars)

    @property
    def scale_fingerprint(self) -> str:
        low = min(bar.close for bar in self.bars)
        high = max(bar.close for bar in self.bars)
        character = self.character or "std"
        coda = self.outro_override or "none"
        meter = self.spec.meter
        sessions = "".join(item[0] for item in self.session_characters)
        bridges = ""
        if self.gap_leads:
            bridges = "".join(
                (self.gap_leads[index] or "-")[0]
                for index in range(31, len(self.gap_leads), 32)
            )
        return (
            f"{self.key.name}-{self.mode}-{character}-{coda}-"
            f"{meter.beats}-{meter.beat_type}-{int(self.swing)}-"
            f"{low:.2f}-{high:.2f}-rhythm4-{sessions}-{bridges}"
        )


def _flatten(sessions: list[tuple[date, list[Bar]]], sizes: list[int]) -> list[list[Bar]]:
    parts: list[list[Bar]] = []
    cursor = 0
    for size in sizes:
        chunk = sessions[cursor : cursor + size]
        cursor += size
        parts.append([bar for _day, bars in chunk for bar in bars])
    return parts


def month_parts(sessions: list[tuple[date, list[Bar]]]) -> list[list[Bar]]:
    """Four movements. A fifth calendar week folds into the finale. A short month is split evenly."""
    usable = [(day, bars) for day, bars in sessions if bars]
    if len(usable) < 4:
        raise ValueError("a month sonata needs four sessions")
    weeks: list[list[tuple[date, list[Bar]]]] = []
    week_key: tuple[int, int] | None = None
    for day, bars in usable:
        key = day.isocalendar()[:2]
        if key != week_key:
            weeks.append([])
            week_key = key
        weeks[-1].append((day, bars))
    if len(weeks) >= 4:
        folded = [*weeks[:3], [item for week in weeks[3:] for item in week]]
        return [[bar for _day, bars in week for bar in bars] for week in folded]
    return _flatten(usable, split_into(len(usable), 4))


def quarter_parts(stamped: list[tuple[date, Bar]]) -> list[list[Bar]]:
    """Three movements. A month that has only just opened joins the month before it."""
    months: list[list[Bar]] = []
    key: tuple[int, int] | None = None
    for day, bar in stamped:
        stamp = (day.year, day.month)
        if stamp != key:
            months.append([])
            key = stamp
        months[-1].append(bar)
    months = [month for month in months if month]
    if len(months) >= 2 and len(months[-1]) < MIN_QUARTER_MONTH_CANDLES:
        months[-2].extend(months[-1])
        months.pop()
    if len(months) >= 3:
        return months[-3:]
    flat = [bar for month in months for bar in month]
    if len(flat) < 3:
        raise ValueError("a quarter needs three candles")
    sizes = split_into(len(flat), 3)
    parts: list[list[Bar]] = []
    cursor = 0
    for size in sizes:
        parts.append(flat[cursor : cursor + size])
        cursor += size
    return parts


def movement_title(
    variant: str,
    span: str,
    index: int,
    spec: FormSpec,
    month: int | None = None,
) -> str | None:
    """Chart name of one movement. None keeps the meter on the line.

    Finale is a 4/4 close. A 7/8 closer is not a finale, so the line can still say 7/8.
    Guitar dances are named by the pattern picker, not by this table.
    """
    if variant == "guitar" or span in ("1D", "1W"):
        return None
    finale = spec.meter.beats == 4 and spec.meter.beat_type == 4 and _closing_slot(span, index, month)
    if finale:
        return "Finale"
    if variant == "minimalist":
        return None
    if span == "1Y":
        slot = ((month or (index + 1)) - 1) % 3
        if variant == "jazz":
            return ("Swing", "Ballad", "Waltz")[slot]
        if variant == "ambient":
            return ("Allegretto", "Adagio", "Minuet")[slot]
        return ("Allegretto", "Siciliana", "Minuet")[slot]
    if span == "1M":
        if variant == "jazz":
            return ("Swing", "Ballad", "Waltz", "Finale")[min(index, 3)]
        if variant == "ambient":
            return ("Allegretto", "Adagio", "Minuet", "Finale")[min(index, 3)]
        return ("Allegretto", "Siciliana", "Minuet", "Finale")[min(index, 3)]
    if span == "3M":
        if variant == "jazz":
            return ("Swing", "Ballad", "Finale")[min(index, 2)]
        if variant == "ambient":
            return ("Allegretto", "Adagio", "Finale")[min(index, 2)]
        return ("Allegretto", "Adagio", "Finale")[min(index, 2)]
    return None


def _closing_slot(span: str, index: int, month: int | None) -> bool:
    if span == "1Y":
        return month == 12
    if span == "1M":
        return index == 3
    if span == "3M":
        return index == 2
    return False


def year_groups(stamped: list[tuple[date, Bar]]) -> list[tuple[date, list[Bar]]]:
    """Chronological calendar months, keeping the latest twelve in the series."""
    groups: list[tuple[date, list[Bar]]] = []
    key: tuple[int, int] | None = None
    for day, bar in stamped:
        stamp = (day.year, day.month)
        if stamp != key:
            groups.append((date(day.year, day.month, 1), []))
            key = stamp
        groups[-1][1].append(bar)
    return groups[-12:]


def year_as_of(stamped: list[tuple[date, Bar]]) -> date:
    """Last candle day that is actually played.

    `prepare_year` drops a month under 30 candles. Early in a new month the
    newest stamp is that thin month, and the piece stopped on the month before.
    """
    played = [(day, bars) for day, bars in year_groups(stamped) if len(bars) >= MIN_YEAR_CANDLES]
    if not played:
        raise ValueError("a year needs one month with enough candles")
    last_month = played[-1][0]
    last = last_month
    for day, _bar in stamped:
        if (day.year, day.month) == (last_month.year, last_month.month):
            last = day
    return last


def _edges(parts: list[list[Bar]]):
    return [
        boundary_regimes([bar.close for bar in part], [bar.ma20 for bar in part])
        for part in parts
    ]


def _home(symbol: str | None) -> KeySpec:
    if not symbol:
        return C_KEY
    return stock_home_key(symbol)


def _modes(
    variant: str,
    characters: Sequence[MovementCharacter],
    edges: Sequence[tuple[str, str]],
) -> tuple[Mode, ...]:
    if variant == "minimalist":
        return tuple("major" for _ in characters)
    return tuple(
        movement_mode(character, edge[1])  # type: ignore[arg-type]
        for character, edge in zip(characters, edges)
    )


def _span_keys(
    variant: str,
    span: str,
    home: KeySpec,
    characters: tuple[MovementCharacter, ...],
    edges: list[tuple[str, str]],
) -> tuple[KeySpec, ...]:
    if variant == "minimalist":
        if span == "1M":
            return month_keys(home, characters, edges)  # type: ignore[arg-type]
        return quarter_keys(home, characters, edges)  # type: ignore[arg-type]
    if variant == "jazz" and span == "1M":
        return jazz_month_keys(home, characters, edges)  # type: ignore[arg-type]
    if variant == "jazz" and span == "3M":
        return jazz_quarter_keys(home, characters, edges)  # type: ignore[arg-type]
    return tuple(home for _ in characters)


def _prepared(
    movements: tuple[Movement, ...],
    parts: list[list[Bar]],
    *,
    grouped: list[list[int]] | None = None,
    keys: tuple[KeySpec, ...] | None = None,
    characters: tuple[MovementCharacter, ...] | None = None,
    outros: tuple[OutroOverride | None, ...] | None = None,
    modes: tuple[Mode, ...] | None = None,
    swings: tuple[bool, ...] | None = None,
    home_pedal: bool = False,
) -> tuple[PreparedMovement, ...]:
    chosen_keys = keys or tuple(C_KEY for _ in movements)
    chosen_characters = characters or tuple(None for _ in movements)
    chosen_outros = outros or tuple(None for _ in movements)
    chosen_modes = modes or tuple("major" for _ in movements)
    chosen_swings = swings or tuple(False for _ in movements)
    prepared: list[PreparedMovement] = []
    for movement, bars, key, character, outro, mode, swing in zip(
        movements,
        parts,
        chosen_keys,
        chosen_characters,
        chosen_outros,
        chosen_modes,
        chosen_swings,
    ):
        if not bars:
            continue
        prepared.append(
            PreparedMovement(
                label=movement.label,
                spec=movement.spec,
                bars=bars,
                groups=grouped,
                rest_after=movement.rest_after,
                key=key,
                character=character,
                outro_override=outro,
                mode=mode,
                swing=swing,
                home_pedal=home_pedal,
            )
        )
    if len(prepared) != len(movements):
        raise ValueError("every movement needs candles")
    return tuple(prepared)


def prepare_week(
    sessions: list[list[Bar]],
    symbol: str | None = None,
    openings: Sequence[float | None] | None = None,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> tuple[PreparedMovement, ...]:
    usable = [bars for bars in sessions if bars][-5:]
    if not usable:
        raise ValueError("a week needs one session")
    flat = [bar for bars in usable for bar in bars]
    movement = plan_week(len(usable))[0]
    session_characters = tuple(
        movement_character([bar.close for bar in bars], "1W") for bars in usable
    )
    bar_characters = tuple(
        character
        for character in session_characters
        for _ in range(BARS_PER_SESSION)
    )
    leads: list[str | None] = [None] * (len(usable) * BARS_PER_SESSION)
    if openings is not None and len(usable) >= 2:
        chosen_openings = list(openings)[-len(usable) :]
        if len(chosen_openings) == len(usable):
            for index in range(len(usable) - 1):
                direction = gap_direction(usable[index][-1].close, chosen_openings[index + 1])
                if direction is not None:
                    leads[(index + 1) * BARS_PER_SESSION - 1] = direction
    outro = None
    if len(usable) >= 2:
        outro = finale_outro(session_characters[0], session_characters[-1])
    # A week has no frame. The opening session is the region the Torroba
    # pattern reads, which can differ from the whole-week character.
    spec = movement.spec
    if _torroba_span(variant, ensemble):
        spec = retarget_torroba_tempo(
            retarget_torroba_meter(spec, session_characters[0]), session_characters[0]
        )
    return (
        PreparedMovement(
            label=movement.label,
            spec=spec,
            bars=flat,
            groups=week_source_groups([len(bars) for bars in usable]),
            rest_after=0.0,
            key=_home(symbol),
            character=movement_character([bar.close for bar in flat], "1W"),
            outro_override=outro,
            session_characters=session_characters,
            bar_characters=bar_characters,
            gap_leads=tuple(leads),
        ),
    )


def prepare_month(
    sessions: list[tuple[date, list[Bar]]],
    symbol: str | None = None,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> tuple[PreparedMovement, ...]:
    parts = month_parts(sessions)
    characters = tuple(movement_character([bar.close for bar in part], "1M") for part in parts)
    counts = [len(part) for part in parts]
    if _torroba_span(variant, ensemble):
        # plan_month frames before the character is known. Torroba retargets
        # the unframed body first, then takes the frame for the new meter.
        movements = _framed_torroba(
            month_specs(variant),
            characters,
            counts,
            "1M",
            ("I", "II", "III", "IV"),
            (MONTH_REST_SECONDS, MONTH_REST_SECONDS, MONTH_REST_SECONDS, 0.0),
        )
    else:
        movements = plan_month(counts, variant)
    edges = _edges(parts)
    home = _home(symbol)
    keys = _span_keys(variant, "1M", home, characters, edges)
    modes = _modes(variant, characters, edges)
    outros = (None, None, None, finale_outro(characters[0], characters[-1]))
    swings = tuple(swing_for(variant, movement.spec.meter) for movement in movements)
    return _prepared(
        movements,
        parts,
        keys=keys,
        characters=characters,
        outros=outros,
        modes=modes,
        swings=swings,
        home_pedal=variant != "minimalist",
    )


def prepare_quarter(
    stamped: list[tuple[date, Bar]],
    symbol: str | None = None,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> tuple[PreparedMovement, ...]:
    parts = quarter_parts(stamped)
    characters = tuple(movement_character([bar.close for bar in part], "3M") for part in parts)
    counts = [len(part) for part in parts]
    if _torroba_span(variant, ensemble):
        movements = _framed_torroba(
            quarter_specs(variant),
            characters,
            counts,
            "3M",
            ("I", "II", "III"),
            (QUARTER_REST_SECONDS, QUARTER_REST_SECONDS, 0.0),
        )
    else:
        movements = plan_quarter(counts, variant)
    edges = _edges(parts)
    home = _home(symbol)
    keys = _span_keys(variant, "3M", home, characters, edges)
    modes = _modes(variant, characters, edges)
    outros = (None, None, finale_outro(characters[0], characters[-1]))
    swings = tuple(swing_for(variant, movement.spec.meter) for movement in movements)
    return _prepared(
        movements,
        parts,
        keys=keys,
        characters=characters,
        outros=outros,
        modes=modes,
        swings=swings,
        home_pedal=variant != "minimalist",
    )


def prepare_year(
    stamped: list[tuple[date, Bar]],
    symbol: str | None = None,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> tuple[PreparedMovement, ...]:
    """Months play in time order. The form follows the calendar month, so December is the finale whenever it falls."""
    torroba = _torroba_span(variant, ensemble)
    bodies = year_specs(variant)
    framed = () if torroba else tuple(attach_frame(spec, "1Y") for spec in bodies)
    kept = [(day, bars) for day, bars in year_groups(stamped) if len(bars) >= MIN_YEAR_CANDLES]
    if not kept:
        raise ValueError("a year needs one month with enough candles")
    home = _home(symbol)
    prepared: list[PreparedMovement] = []
    last = len(kept) - 1
    for position, (day, bars) in enumerate(kept):
        if position == last:
            rest = 0.0
        else:
            rest = (
                YEAR_SEASON_REST_SECONDS
                if _season(kept[position + 1][0]) != _season(day)
                else SEASON_REST_SECONDS
            )
        character = movement_character([bar.close for bar in bars], "1Y")
        if torroba:
            spec = attach_frame(
                retarget_torroba_tempo(
                    retarget_torroba_meter(bodies[day.month - 1], character), character
                ),
                "1Y",
            )
        else:
            spec = framed[day.month - 1]
        closing = boundary_regimes(
            [bar.close for bar in bars], [bar.ma20 for bar in bars]
        )[1]
        prepared.append(
            PreparedMovement(
                label=f"{day.month:02d}/{day.year % 100:02d}",
                spec=spec,
                bars=bars,
                groups=None,
                rest_after=rest,
                key=year_key(
                    home,
                    (day.month - 1) // 3,
                    character,
                    frame=position in (0, last),
                ),
                character=character,
                mode="major" if variant == "minimalist" else movement_mode(character, closing),
                swing=swing_for(variant, spec.meter),
                home_pedal=variant != "minimalist",
            )
        )
    return tuple(prepared)
