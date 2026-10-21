"""Long-form layouts: one movement for a week, four for a month, three for a quarter, twelve for a year.

A movement is one FormSpec. The week pins each session but the last to 31 bars of
content plus one empty bar, so the close holds through the downbeat of the next session.
Longer spans let render spread the movement's own bars across the form.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from app.sonify.form import FormSection, FormSpec
from app.sonify.keys import (
    C_KEY,
    KeySpec,
    MovementCharacter,
    OutroOverride,
    boundary_regimes,
    finale_outro,
    month_keys,
    movement_character,
    quarter_keys,
    stock_home_key,
    year_key,
)
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

SectionPart = tuple[int, str, int]


def _sections(parts: tuple[SectionPart, ...]) -> tuple[FormSection, ...]:
    sections: list[FormSection] = []
    cursor = 0
    for length, kind, slot in parts:
        sections.append(FormSection(cursor, cursor + length, kind, slot))
        cursor += length
    return tuple(sections)


def _spec(
    bars: int,
    bpm: int,
    parts: tuple[SectionPart, ...],
    chunks: tuple[int, ...],
) -> FormSpec:
    built = _sections(parts)
    if built[-1].end != bars:
        raise ValueError(f"sections cover {built[-1].end} bars, form has {bars}")
    if chunks[-1] != bars:
        raise ValueError("the last chunk must end on the last bar")
    return FormSpec(bars, bpm, built, chunks, borrowed=True)


def week_spec(session_count: int) -> FormSpec:
    """One continuous movement. A short week is n sessions, not a stretched five."""
    count = max(1, min(5, session_count))
    parts: list[SectionPart] = []
    for index in range(count):
        for step in range(4):
            if index == 0 and step == 0:
                kind = "intro"
            elif index == count - 1 and step == 3:
                kind = "outro"
            else:
                kind = "phrase"
            parts.append((8, kind, index))
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


def month_specs() -> tuple[FormSpec, FormSpec, FormSpec, FormSpec]:
    first = _spec(
        96,
        96,
        ((8, "intro", 0), (32, "phrase", 0), (24, "phrase", 1), (24, "phrase", 2), (8, "outro", 2)),
        (40, 64, 96),
    )
    second = _spec(
        72,
        72,
        ((8, "intro", 0), (24, "phrase", 0), (16, "phrase", 1), (24, "phrase", 2)),
        (32, 72),
    )
    third = _spec(
        72,
        120,
        (
            (8, "intro", 0),
            (16, "phrase", 0),
            (16, "phrase", 1),
            (16, "phrase", 2),
            (8, "phrase", 2),
            (8, "outro", 2),
        ),
        (40, 72),
    )
    fourth = _spec(
        96,
        96,
        ((8, "intro", 0), (32, "phrase", 0), (24, "phrase", 1), (16, "phrase", 2), (16, "outro", 2)),
        (40, 64, 96),
    )
    return first, second, third, fourth


def quarter_specs() -> tuple[FormSpec, FormSpec, FormSpec]:
    first = _spec(
        192,
        96,
        ((8, "intro", 0), (56, "phrase", 0), (64, "phrase", 1), (48, "phrase", 2), (16, "outro", 2)),
        (64, 128, 192),
    )
    second = _spec(
        120,
        60,
        ((8, "intro", 0), (32, "phrase", 0), (40, "phrase", 1), (32, "phrase", 2), (8, "outro", 2)),
        (40, 80, 120),
    )
    third = _spec(
        216,
        108,
        ((8, "intro", 0), (56, "phrase", 0), (64, "phrase", 1), (48, "phrase", 2), (40, "outro", 2)),
        (64, 128, 216),
    )
    return first, second, third


def year_specs() -> tuple[FormSpec, ...]:
    opener = _spec(
        80,
        100,
        ((8, "intro", 0), (32, "phrase", 0), (32, "phrase", 1), (8, "outro", 2)),
        (40, 80),
    )
    center = _spec(
        72,
        66,
        ((8, "intro", 0), (24, "phrase", 0), (16, "phrase", 1), (16, "phrase", 2), (8, "outro", 2)),
        (32, 72),
    )
    closer = _spec(
        84,
        108,
        ((8, "intro", 0), (32, "phrase", 0), (32, "phrase", 1), (12, "outro", 2)),
        (40, 84),
    )
    finale = _spec(
        108,
        96,
        ((8, "intro", 0), (32, "phrase", 0), (32, "phrase", 1), (24, "phrase", 2), (12, "outro", 2)),
        (40, 72, 108),
    )
    by_month = (opener, center, closer, opener, center, closer, opener, center, closer, opener, center, finale)
    return by_month


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


def plan_month(session_counts: list[int]) -> tuple[Movement, ...]:
    specs = month_specs()
    if len(session_counts) != 4:
        raise ValueError("a month is four movements")
    labels = ("I", "II", "III", "IV")
    rests = (MONTH_REST_SECONDS, MONTH_REST_SECONDS, MONTH_REST_SECONDS, 0.0)
    return tuple(
        Movement(label, spec, count, rest)
        for label, spec, count, rest in zip(labels, specs, session_counts, rests)
    )


def plan_quarter(session_counts: list[int]) -> tuple[Movement, ...]:
    specs = quarter_specs()
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

    @property
    def candle_count(self) -> int:
        return len(self.bars)

    @property
    def scale_fingerprint(self) -> str:
        low = min(bar.close for bar in self.bars)
        high = max(bar.close for bar in self.bars)
        character = self.character or "std"
        coda = self.outro_override or "none"
        return f"{self.key.name}-{character}-{coda}-{low:.2f}-{high:.2f}"


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


def _edges(parts: list[list[Bar]]):
    return [
        boundary_regimes([bar.close for bar in part], [bar.ma20 for bar in part])
        for part in parts
    ]


def _home(symbol: str | None) -> KeySpec:
    if not symbol:
        return C_KEY
    return stock_home_key(symbol)


def _prepared(
    movements: tuple[Movement, ...],
    parts: list[list[Bar]],
    *,
    grouped: list[list[int]] | None = None,
    keys: tuple[KeySpec, ...] | None = None,
    characters: tuple[MovementCharacter, ...] | None = None,
    outros: tuple[OutroOverride | None, ...] | None = None,
) -> tuple[PreparedMovement, ...]:
    chosen_keys = keys or tuple(C_KEY for _ in movements)
    chosen_characters = characters or tuple(None for _ in movements)
    chosen_outros = outros or tuple(None for _ in movements)
    prepared: list[PreparedMovement] = []
    for movement, bars, key, character, outro in zip(
        movements, parts, chosen_keys, chosen_characters, chosen_outros
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
            )
        )
    if len(prepared) != len(movements):
        raise ValueError("every movement needs candles")
    return tuple(prepared)


def prepare_week(
    sessions: list[list[Bar]], symbol: str | None = None
) -> tuple[PreparedMovement, ...]:
    usable = [bars for bars in sessions if bars][-5:]
    if not usable:
        raise ValueError("a week needs one session")
    flat = [bar for bars in usable for bar in bars]
    movement = plan_week(len(usable))[0]
    return (
        PreparedMovement(
            label=movement.label,
            spec=movement.spec,
            bars=flat,
            groups=week_source_groups([len(bars) for bars in usable]),
            rest_after=0.0,
            key=_home(symbol),
            character=movement_character([bar.close for bar in flat], "1W"),
        ),
    )


def prepare_month(
    sessions: list[tuple[date, list[Bar]]], symbol: str | None = None
) -> tuple[PreparedMovement, ...]:
    parts = month_parts(sessions)
    movements = plan_month([len(part) for part in parts])
    characters = tuple(movement_character([bar.close for bar in part], "1M") for part in parts)
    edges = _edges(parts)
    home = _home(symbol)
    keys = month_keys(home, characters, edges)
    outros = (None, None, None, finale_outro(characters[0], characters[-1]))
    return _prepared(movements, parts, keys=keys, characters=characters, outros=outros)


def prepare_quarter(
    stamped: list[tuple[date, Bar]], symbol: str | None = None
) -> tuple[PreparedMovement, ...]:
    parts = quarter_parts(stamped)
    movements = plan_quarter([len(part) for part in parts])
    characters = tuple(movement_character([bar.close for bar in part], "3M") for part in parts)
    edges = _edges(parts)
    home = _home(symbol)
    keys = quarter_keys(home, characters, edges)
    outros = (None, None, finale_outro(characters[0], characters[-1]))
    return _prepared(movements, parts, keys=keys, characters=characters, outros=outros)


def prepare_year(
    stamped: list[tuple[date, Bar]], symbol: str | None = None
) -> tuple[PreparedMovement, ...]:
    """Months play in time order. The form follows the calendar month, so December is the finale whenever it falls."""
    specs = year_specs()
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
        prepared.append(
            PreparedMovement(
                label=f"{day.month:02d}/{day.year % 100:02d}",
                spec=specs[day.month - 1],
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
            )
        )
    return tuple(prepared)
