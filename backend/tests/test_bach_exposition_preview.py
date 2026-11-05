"""Preview-only Bach exposition: data model, candidate, and note lock.

The prototype must not change production: no `SENTENCE_SPECS` entry, no
`PROCEDURES` entry, no edit to the fuga renderer. The last test re-renders one
bounded production Fugue case from `tests/fixtures/bach_imitation.json`, so a
renderer edit that changes the fuga shows up here as well as in the parity
test.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import replace

import pytest

from app.sonify.bach_exposition import (
    BACH_EXPOSITION,
    EXPOSITIONS,
    Entry,
    ExpositionSpec,
    resolve_exposition,
)
from app.sonify.procedure_specs import (
    BACH_IMITATION,
    CONTOUR_ONE_TO_ONE,
    PROCEDURES,
    ImitationSpec,
    validate_procedure,
)
from app.sonify.sentence_specs import SENTENCE_SPECS
from app.studio.bach_exposition_preview import (
    preview_bach_exposition,
    preview_bach_exposition_candidate,
    validate_candidate,
    validate_exposition,
)
from app.studio.sentence_spec import parse_payload

CANDIDATE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "app"
    / "studio"
    / "candidates"
    / "bach_exposition.json"
)
FUGA_FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "bach_imitation.json"


def _candidate_spec():
    payload = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    specs = parse_payload(payload)
    assert len(specs) == 1
    return specs[0]


def _subject(voice: str, start: int, role: str = "subject") -> Entry:
    return Entry(voice=voice, start_bar=start, bars=2, role=role)


def _spec(entries: tuple[Entry, ...], **kwargs) -> ExpositionSpec:
    data = {
        "id": "unit_exposition",
        "pattern": "bach_fuga",
        "meter": "4/4",
        "subject_bars": 2,
        "entries": entries,
    }
    data.update(kwargs)
    return ExpositionSpec(**data)


# ---------------------------------------------------------------------------
# entry plan


def test_the_named_spec_is_a_three_voice_subject_answer_subject_plan() -> None:
    assert EXPOSITIONS == {"bach_exposition": BACH_EXPOSITION}
    assert BACH_EXPOSITION.length == 6
    assert [
        (entry.voice, entry.start_bar, entry.bars, entry.role)
        for entry in BACH_EXPOSITION.entries
    ] == [
        ("soprano", 0, 2, "subject"),
        ("bass", 2, 2, "answer"),
        ("alto", 4, 2, "subject"),
    ]
    assert validate_exposition(BACH_EXPOSITION) == []


def test_unknown_exposition_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown exposition procedure 'episode'"):
        resolve_exposition("episode")
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_exposition("")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"voice": "tenor"}, "unknown exposition voice"),
        ({"role": "episode"}, "unknown exposition role"),
        ({"role": "answer", "voice": "soprano"}, "only answers in the bass"),
        ({"bars": 0}, "at least one bar"),
        ({"start_bar": -1}, "start_bar must be >= 0"),
    ],
)
def test_an_entry_refuses_what_the_renderer_cannot_play(kwargs, message) -> None:
    data = {"voice": "soprano", "start_bar": 0, "bars": 2}
    data.update(kwargs)
    with pytest.raises(ValueError, match=message):
        Entry(**data)


def test_a_countersubject_is_data_but_the_preview_refuses_to_fake_it() -> None:
    entry = Entry(
        voice="soprano",
        start_bar=0,
        bars=2,
        role="subject",
        countersubject=True,
    )
    spec = _spec((entry, _subject("bass", 2, "answer")))
    # The data model keeps the flag; the preview does not pretend to realize it.
    errors = validate_exposition(spec)
    assert [
        (error.path, "countersubject is not realized" in error.message)
        for error in errors
    ] == [("entries", True)]
    result = preview_bach_exposition(spec)
    assert not result.ok
    assert result.notes == ()
    assert result.render_hash is None


def test_entries_are_ordered_contiguous_and_bounded() -> None:
    with pytest.raises(ValueError, match="start_bar must be 0"):
        _spec((_subject("soprano", 2), _subject("bass", 0, "answer")))

    # An overlap and a gap are both refused before any notes are written.
    with pytest.raises(ValueError, match="overlaps or is out of order"):
        _spec((_subject("soprano", 0), _subject("bass", 1, "answer")))
    with pytest.raises(ValueError, match="start_bar must be 2"):
        _spec((_subject("soprano", 0), _subject("bass", 3, "answer")))

    with pytest.raises(ValueError, match="entries\\[1\\].role must be 'answer'"):
        _spec((_subject("soprano", 0), _subject("alto", 2)))

    five = tuple(
        _subject(voice, index * 2, role)
        for index, (voice, role) in enumerate(
            (
                ("soprano", "subject"),
                ("bass", "answer"),
                ("alto", "subject"),
                ("bass", "answer"),
                ("soprano", "subject"),
            )
        )
    )
    with pytest.raises(ValueError, match="2..4 entries"):
        _spec(five)


def test_subject_bars_and_the_answer_lag_must_agree() -> None:
    one_bar_lag = ImitationSpec(
        lag=1,
        contour=CONTOUR_ONE_TO_ONE,
        retrograde=False,
        inversion=False,
    )
    with pytest.raises(ValueError, match="lag must equal subject_bars"):
        _spec(
            (_subject("soprano", 0), _subject("bass", 2, "answer")),
            imitation=one_bar_lag,
        )

    with pytest.raises(ValueError, match="subject_bars must be an integer in 1..4"):
        _spec(
            (_subject("soprano", 0), _subject("bass", 2, "answer")),
            subject_bars=5,
            imitation=BACH_IMITATION,
        )


# ---------------------------------------------------------------------------
# preview


def test_preview_renders_the_planned_entries_in_their_voices() -> None:
    result = preview_bach_exposition(BACH_EXPOSITION)
    assert result.ok, result.errors
    assert result.plan is not None
    assert result.plan["kind"] == "procedure"
    assert result.plan["procedure"] == "bach_exposition"
    assert result.plan["length"] == 6
    assert result.row == [
        "soprano:subject",
        "soprano:subject",
        "bass:answer",
        "bass:answer",
        "alto:subject",
        "alto:subject",
    ]

    voices = {bar: set() for bar in range(6)}
    for note in result.notes:
        voices[note["bar"]].add(note["voice"])
    assert voices == {
        0: {1},
        1: {1},
        2: {3},
        3: {3},
        4: {2},
        5: {2},
    }
    assert result.notes
    assert len(result.matrix) == 3
    assert all(row["render"] for row in result.matrix)


def test_preview_is_deterministic_and_clips_to_the_fixture_window() -> None:
    first = preview_bach_exposition(BACH_EXPOSITION)
    second = preview_bach_exposition(BACH_EXPOSITION)
    assert first.ok and second.ok
    assert first.plan == second.plan
    assert first.row == second.row
    assert first.notes == second.notes
    assert first.render_hash == second.render_hash
    assert first.matrix == second.matrix
    assert first.render_hash is not None
    assert first.render_hash.startswith("sha256:")

    clipped = preview_bach_exposition(BACH_EXPOSITION, {"bars": 3})
    assert clipped.ok
    assert {note["bar"] for note in clipped.notes} == {0, 1, 2}
    assert [row["render"] for row in clipped.matrix] == [True, True, False]
    assert clipped.render_hash != first.render_hash


def test_preview_rejects_bad_fixtures_and_meters() -> None:
    result = preview_bach_exposition(BACH_EXPOSITION, {"bars": "three"})
    assert not result.ok
    assert result.errors[0].path == "fixture"

    result = preview_bach_exposition(BACH_EXPOSITION, {"meter": "6/8"})
    assert not result.ok
    assert result.errors[0].path == "fixture"

    result = preview_bach_exposition(BACH_EXPOSITION, {"tempo": 120})
    assert not result.ok
    assert result.errors[0].path == "fixture"


def test_preview_does_not_touch_production_registries() -> None:
    saved = dict(SENTENCE_SPECS)
    procedures = dict(PROCEDURES)

    preview_bach_exposition(BACH_EXPOSITION)

    assert SENTENCE_SPECS == saved
    assert PROCEDURES == procedures == {"bach_imitation": BACH_IMITATION}
    assert "bach_exposition" not in PROCEDURES
    with pytest.raises(ValueError, match="unknown procedure 'bach_exposition'"):
        validate_procedure("bach_exposition")


# ---------------------------------------------------------------------------
# candidate


def test_the_candidate_json_names_the_exposition_and_previews() -> None:
    spec = _candidate_spec()
    assert spec.pattern == "bach_fuga"
    assert spec.meter == "4/4"
    assert spec.span.tile == 6
    assert spec.slots[0].procedure == "bach_exposition"
    assert validate_candidate(spec) == []

    result = preview_bach_exposition_candidate(spec)
    assert result.ok, result.errors
    assert result.plan == preview_bach_exposition(BACH_EXPOSITION).plan
    assert result.render_hash == preview_bach_exposition(BACH_EXPOSITION).render_hash


def test_an_unknown_or_mismatched_candidate_is_rejected() -> None:
    spec = _candidate_spec()

    typo = replace(spec, slots=(replace(spec.slots[0], procedure="episode"),))
    result = preview_bach_exposition_candidate(typo)
    assert not result.ok
    assert [(error.path, "unknown exposition procedure" in error.message) for error in result.errors] == [
        ("slots[0].procedure", True)
    ]

    wrong_pattern = replace(spec, pattern="castillo")
    result = preview_bach_exposition_candidate(wrong_pattern)
    assert not result.ok
    assert [error.path for error in result.errors] == ["pattern"]

    wrong_tile = replace(spec, span=replace(spec.span, tile=5))
    result = preview_bach_exposition_candidate(wrong_tile)
    assert not result.ok
    assert "span.tile" in [error.path for error in result.errors]

    figure_slot = replace(spec, slots=(replace(spec.slots[0], procedure=None, figure=1),))
    result = preview_bach_exposition_candidate(figure_slot)
    assert not result.ok
    assert "slots[0].procedure" in [error.path for error in result.errors]


# ---------------------------------------------------------------------------
# production lock


def _fixture_notes(events) -> list[list[int | float]]:
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


def _joined(start: int, pitches: list[int]):
    from app.sonify.model import Phrase, Run

    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs))


def _render_production_fuga_case():
    from app.sonify.chords import C, F, G
    from app.sonify.form import METER_44, ChordSlot, compose_meter
    from app.sonify.guitar import render_guitar_score
    from app.sonify.params import compose_params

    pitches = [67, 69, 71, 72, 74, 76, 77, 79] * 2
    bars = len(pitches) // METER_44.eighths_per_bar
    chords = (C, F, G)
    slots = tuple(
        ChordSlot(bar, 1, chords[bar % len(chords)], "sideway", "phrase")
        for bar in range(bars)
    )
    with compose_params({}):
        with compose_meter(METER_44):
            score = render_guitar_score(
                title="Guitar",
                chosen=(),
                sample_indexes=None,
                slots=slots,
                pitches=list(pitches),
                phrases=(_joined(0, pitches),),
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
                sections=(),
                rel_span=0.02,
            )
    return {
        "lead": _fixture_notes(score.lead),
        "support": _fixture_notes(score.support),
        "low": _fixture_notes(score.low),
    }


def test_production_fuga_notes_match_the_locked_fixture() -> None:
    expected = json.loads(FUGA_FIXTURE.read_text(encoding="utf-8"))
    assert _render_production_fuga_case() == expected["4/4|rising|2|cycle"]
