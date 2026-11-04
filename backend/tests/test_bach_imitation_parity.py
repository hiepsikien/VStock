"""Note-data lock for the Fugue's imitation procedure.

The procedure is data (`procedure_specs.BACH_IMITATION`): lag two bars, 1:1
contour, forward, uninverted. This fixture records every voice of a bounded
matrix of fuga renders, so a renderer edit or a spec edit that changes the
answer shows up as a diff.

Regenerate on purpose with:

    VSTOCK_WRITE_BACH_IMITATION=1 python3 -m pytest tests/test_bach_imitation_parity.py -q
"""

from __future__ import annotations

import json
import os
import pathlib
from functools import lru_cache

import pytest

from app.sonify.chords import C, F, G, Chord
from app.sonify.form import (
    METER_44,
    METER_68,
    ChordSlot,
    FormSection,
    Meter,
    compose_meter,
)
from app.sonify.guitar import render_guitar_score
from app.sonify.model import NoteEvent, Phrase, Run
from app.sonify.params import compose_params
from app.sonify.procedure_specs import (
    BACH_IMITATION,
    CONTOUR_ONE_TO_ONE,
    ImitationSpec,
)
from app.sonify.guitar_bach import _bach_lag_bar, _fuga_motif

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "bach_imitation.json"
WRITE = os.environ.get("VSTOCK_WRITE_BACH_IMITATION") == "1"

BARS = (2, 3, 4, 6)
SHAPES = {
    "rising": [67, 69, 71, 72, 74, 76, 77, 79],
    "falling": [79, 77, 76, 74, 72, 71, 69, 67],
    "flat": [72] * 8,
    "zigzag": [67, 72, 65, 74, 64, 76, 62, 69],
    "hold": [72, 72, 72, 72, 74, 76, 77, 79],
    "leap": [64, 76, 65, 74, 67, 79, 69, 72],
}
PROGRESSION = (C, F, G)


def _joined(start: int, pitches: list[int]) -> Phrase:
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs))


def _notes(events: list[NoteEvent]) -> list[list[int | float]]:
    return [
        [
            event.bar,
            round(event.beat, 4),
            round(event.duration_beats, 4),
            event.midi,
            event.velocity,
            int(event.accent),
            int(event.staccato),
        ]
        for event in events
        if event.midi is not None
    ]


def _render(
    pitches: list[int],
    *,
    meter: Meter,
    chords: tuple[Chord, ...] = PROGRESSION,
    sections: tuple[FormSection, ...] = (),
    kinds: dict[int, str] | None = None,
    phrases: tuple[Phrase, ...] | None = None,
):
    epb = meter.eighths_per_bar
    bars = len(pitches) // epb
    kinds = kinds or {bar: "phrase" for bar in range(bars)}
    slots = tuple(
        ChordSlot(bar, 1, chords[bar % len(chords)], "sideway", kinds[bar])
        for bar in range(bars)
    )
    with compose_meter(meter):
        return render_guitar_score(
            title="Guitar",
            chosen=(),
            sample_indexes=None,
            slots=slots,
            pitches=list(pitches),
            phrases=phrases or (_joined(0, pitches),),
            dynamics=(),
            bands=["mf"] * bars,
            band_at={bar: "mf" for bar in range(bars)},
            musical_bars=bars,
            total_eighths=len(pitches),
            bpm=96,
            ensemble="bach",
            harmonies=(),
            mode="major",
            character="volatile",
            character_at=None,
            sections=sections,
            rel_span=0.02,
        )


def _melody(shape: str, bars: int, epb: int) -> list[int]:
    unit = SHAPES[shape][:epb]
    return unit * bars


def _pedal_case(shape: str, bars: int, epb: int):
    """One intro bar, then a body. The answer must skip the pedal bar."""
    intro = [72] * epb
    body = _melody(shape, bars, epb)
    pitches = intro + body
    kinds = {0: "intro", **{bar: "phrase" for bar in range(1, bars + 1)}}
    sections = (
        FormSection(0, 1, "intro", 0),
        FormSection(1, bars + 1, "phrase", 0),
    )
    return _render(
        pitches,
        meter=METER_44,
        sections=sections,
        kinds=kinds,
        phrases=(_joined(0, intro), _joined(epb, body)),
    )


def _case(key: str):
    parts = key.split("|")
    meter_name, shape, bars_text, *rest = parts
    bars = int(bars_text)
    meter = METER_44 if meter_name == "4/4" else METER_68
    epb = meter.eighths_per_bar
    if rest and rest[0] == "pedal":
        return _pedal_case(shape, bars, epb)
    chords = (C,) if rest and rest[0] == "static" else PROGRESSION
    return _render(_melody(shape, bars, epb), meter=meter, chords=chords)


def _keys() -> list[str]:
    keys: list[str] = []
    for shape in SHAPES:
        for bars in BARS:
            keys.append(f"4/4|{shape}|{bars}|cycle")
    # 6/8 uses six eighths per bar; three shapes and two lengths are enough.
    for shape in ("rising", "flat", "zigzag"):
        for bars in (3, 4):
            keys.append(f"6/8|{shape}|{bars}|cycle")
    # A static harmony and a pedal intro exercise the other two answer paths.
    keys.append("4/4|flat|4|static")
    keys.append("4/4|rising|5|pedal")
    return keys


@lru_cache(maxsize=1)
def _rows() -> dict[str, dict[str, list[list[int | float]]]]:
    with compose_params({}):
        rows: dict[str, dict[str, list[list[int | float]]]] = {}
        for key in _keys():
            score = _case(key)
            rows[key] = {
                "lead": _notes(score.lead),
                "support": _notes(score.support),
                "low": _notes(score.low),
            }
        return rows


def _load() -> dict[str, dict[str, list[list[int | float]]]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_bach_imitation_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate bach_imitation.json in CI")
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        lines = ["{"]
        items = sorted(rows.items())
        for index, (key, row) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            lines.append(f"  {json.dumps(key)}: {json.dumps(row)}{comma}")
        lines.append("}")
        FIXTURE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    expected = _load()
    missing = sorted(set(rows) - set(expected))
    extra = sorted(set(expected) - set(rows))
    assert not missing and not extra, (missing[:5], extra[:5])

    mismatched = {key: (rows[key], expected[key]) for key in rows if rows[key] != expected[key]}
    assert not mismatched, list(mismatched.items())[:1]


def test_matrix_has_the_bounded_bars_and_meters() -> None:
    keys = _keys()
    assert len(keys) == 32, len(keys)
    assert {key.split("|")[0] for key in keys} == {"4/4", "6/8"}
    body = [key for key in keys if not key.endswith("|pedal")]
    assert {int(key.split("|")[2]) for key in body} == set(BARS)


def test_lag_is_read_from_the_spec() -> None:
    class Fake:
        kind_at = {0: "phrase", 1: "phrase", 2: "phrase"}

    fake = Fake()
    assert _bach_lag_bar(fake, 5) == 3
    lag_one = ImitationSpec(
        lag=1,
        contour=CONTOUR_ONE_TO_ONE,
        retrograde=False,
        inversion=False,
    )
    assert _bach_lag_bar(fake, 5, lag_one) == 4
    # Not enough history: fall back one bar, then to the current bar.
    assert _bach_lag_bar(fake, 1) == 0
    assert _bach_lag_bar(fake, 0) == 0

    class WithPedal:
        kind_at = {0: "phrase", 1: "warmup", 2: "phrase", 3: "phrase"}

    # The lag bar is a pedal: skip one bar closer, then close on this bar.
    assert _bach_lag_bar(WithPedal(), 3) == 2
    assert _bach_lag_bar(WithPedal(), 2) == 0


def test_the_realizer_refuses_a_spec_it_cannot_play() -> None:
    for spec in (
        ImitationSpec(2, "2:1", False, False),
        ImitationSpec(2, CONTOUR_ONE_TO_ONE, True, False),
        ImitationSpec(2, CONTOUR_ONE_TO_ONE, False, True),
        ImitationSpec(0, CONTOUR_ONE_TO_ONE, False, False),
    ):
        with pytest.raises(ValueError):
            spec.check_realized()

    class Fake:
        kind_at = {0: "phrase", 1: "phrase"}
        epb = 8
        melody = [72] * 16

    with pytest.raises(ValueError):
        _fuga_motif(Fake(), 0, ImitationSpec(2, "2:1", False, False))


def test_the_spec_names_the_realized_procedure() -> None:
    assert BACH_IMITATION == ImitationSpec(
        lag=2,
        contour=CONTOUR_ONE_TO_ONE,
        retrograde=False,
        inversion=False,
    )
