"""Deterministic `_Ctx`/phrase fixture shared by the texture-matrix tests.

The four guitar test modules each carry their own copy of the bounded context
builder (`test_sonify_guitar_torroba.py`, `test_guitar_wave.py`,
`test_sonify_guitar_scale_passages.py`, `test_torroba_lowered_melody.py`).
Those copies stay where they are: they encode different scenarios. This module
adds the one shape the Phase 0 selection/render matrix needs, `pattern_case()`,
so a matrix run is not another copy-paste.

`pattern_case()` is deliberately dumb: the melody is a fixed contour, chords,
bands and regimes are constant per bar, and nothing reads the clock, the
environment, or a random source. The same arguments always build an equal
`_Ctx` and equal phrases.

`first_body`, `previous` and `section` are selection inputs, not `_Ctx`
fields: `_select_body(ctx, phrase, *, first_body, previous, section)` takes
them beside the context. The fixture accepts all three so a matrix can vary
them, and folds `section` into `ctx.sections`/`kind_at`. Callers pass the same
three values to `_select_body` when they replay the row; there is no hidden
state in the fixture.

A macro row needs a framed context, not a single phrase region. `sections=`
takes a whole deterministic form (intro + phrase, or all-pedal) and
`phrase_start=` places the one phrase inside the non-pedal part; when omitted,
the phrase starts on the first non-pedal bar. `rel_span=` pins the Bach
narrow/wide predicate. Both options keep the original call shape: a caller
that only passes `section=` gets the same context as before.
"""

from __future__ import annotations

from app.sonify.chords import C, CM
from app.sonify.form import (
    METER_34,
    METER_44,
    METER_68,
    FormSection,
    Meter,
)
from app.sonify.guitar import _PEDAL
from app.sonify.guitar_patterns import _Ctx, _meter_kind
from app.sonify.model import Phrase, Run

# One bar of movement in the guitar's singing range. It repeats to fill the
# requested length, so the shape is stable at every bars count.
_CONTOUR = (67, 65, 64, 62, 60, 62, 64, 65)

_METERS: dict[str, Meter] = {
    "3/4": METER_34,
    "4/4": METER_44,
    "6/8": METER_68,
}

# Registers copied from the Torroba fixture. They are the guitar body the
# matrix tests were written against; changing them changes rendered notes.
_BASS_LOW = 40
_BASS_HIGH = 55
_MID_LOW = 50
_MID_HIGH = 65
_TREBLE_FLOOR = 59
_TREBLE_TOP = 81
_CEILING = 83


def meter_named(name: str) -> Meter:
    """The meter a selection key names, with `"*"` resolving to 4/4."""
    if name == "*":
        return METER_44
    try:
        return _METERS[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown meter {name!r}; expected one of {sorted(_METERS)} or '*'"
        ) from exc


def _joined(start: int, pitches: list[int]) -> Phrase:
    """One phrase with runs collapsed exactly like the test helpers do."""
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs))


def _kind_at_bar(sections: tuple[FormSection, ...], bar: int) -> str:
    """The region kind covering `bar`, or the body default when none does."""
    for section in sections:
        if section.start <= bar < section.end:
            return section.kind
    return "phrase"


def pattern_case(
    pattern: str,
    meter: Meter,
    *,
    ensemble: str,
    mood: str,
    band: str,
    bpm: int,
    bars: int = 8,
    first_body: bool = True,
    previous: list[str] | None = None,
    section: FormSection | None = None,
    sections: list[FormSection] | None = None,
    phrase_start: int | None = None,
    rel_span: float = 0.02,
) -> tuple[_Ctx, list[Phrase]]:
    """Build the fixed context/phrases for one `(pattern, meter)` row.

    The returned context is complete enough for both `_select_body` and a
    figure render: melody/raw, chord slots, bands, regimes, sections, phrase,
    register bounds, meter kind/strong beats and bar length. `first_body`,
    `previous` and `section` are accepted here because `_select_body` requires
    them beside the context; the caller forwards the same values.

    `sections=` is the macro form (more than one region, possibly with a pedal
    intro). It cannot be combined with `section=`. `phrase_start=` is an eighth
    offset; by default the phrase starts at the first bar whose kind is not a
    pedal kind, which is what a framed movement's body phrase does.
    """
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    if not isinstance(ensemble, str) or not ensemble:
        raise ValueError("ensemble must be a non-empty string")
    if bars < 1:
        raise ValueError("bars must be >= 1")
    if bpm < 1:
        raise ValueError("bpm must be >= 1")
    if previous is not None:
        if not isinstance(previous, (list, tuple)) or not all(
            isinstance(item, str) for item in previous
        ):
            raise ValueError("previous must be a list of pattern ids")
    if section is not None and sections is not None:
        raise ValueError("pass section or sections, not both")
    if section is not None:
        if not isinstance(section, FormSection):
            raise ValueError("section must be a FormSection")
        if section.start < 0 or section.end > bars or section.end <= section.start:
            raise ValueError("section must fit inside the fixture's bars")
    form_sections: tuple[FormSection, ...]
    if sections is not None:
        if not sections:
            raise ValueError("sections must contain at least one FormSection")
        for region in sections:
            if not isinstance(region, FormSection):
                raise ValueError("sections must contain FormSection values")
            if region.start < 0 or region.end > bars or region.end <= region.start:
                raise ValueError("sections must fit inside the fixture's bars")
        form_sections = tuple(sections)
    elif section is None:
        form_sections = (
            FormSection(0, bars, "phrase", 0 if first_body else 1),
        )
    else:
        form_sections = (section,)
    if rel_span < 0:
        raise ValueError("rel_span must be >= 0")

    epb = meter.eighths_per_bar
    melody = [_CONTOUR[index % len(_CONTOUR)] for index in range(bars * epb)]
    mode = "major" if ensemble == "classic" else "minor"
    chord = C if mode == "major" else CM

    if phrase_start is None:
        first_body_bar = next(
            (
                bar
                for bar in range(bars)
                if _kind_at_bar(form_sections, bar) not in _PEDAL
            ),
            0,
        )
        phrase_start = first_body_bar * epb
    if not 0 <= phrase_start < bars * epb:
        raise ValueError("phrase_start must land inside the fixture's bars")

    kind_at = {bar: "phrase" for bar in range(bars)}
    for region in form_sections:
        for bar in range(region.start, region.end):
            kind_at[bar] = region.kind

    ctx = _Ctx(
        melody=list(melody),
        raw=list(melody),
        chord_at={bar: chord for bar in range(bars)},
        kind_at=kind_at,
        band_at={bar: band for bar in range(bars)},
        phrases=(_joined(phrase_start, melody[phrase_start:]),),
        bars=bars,
        bpm=bpm,
        ensemble=ensemble,
        mode=mode,
        character=mood,
        character_at=None,
        sections=form_sections,
        rel_span=rel_span,
        semitones=0,
        bass_low=_BASS_LOW,
        bass_high=_BASS_HIGH,
        mid_low=_MID_LOW,
        mid_high=_MID_HIGH,
        treble_floor=_TREBLE_FLOOR,
        treble_top=_TREBLE_TOP,
        ceiling=_CEILING,
        epb=epb,
        kind=_meter_kind(meter),
        strong=tuple(meter.strong_eighths),
        bar_beats=meter.quarter_beats,
        regime_at={bar: "sideway" for bar in range(bars)},
    )
    return ctx, list(ctx.phrases)


__all__ = ["meter_named", "pattern_case"]
