"""Tests for the deterministic solo-guitar MusicXML importer.

The small fixture in ``tests/fixtures/musicxml/solo_guitar_small.musicxml`` is
three bars of 3/4 with two voices, three chord groups, a tie across the bar
line, a grace note, and an eighth-note triplet. It is synthetic on purpose: it
exercises the parser without checking in a real edition.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.studio.musicxml_import import (
    ImportedNote,
    MusicXmlImportError,
    parse_musicxml,
    score_summary,
    slice_score,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "musicxml" / "solo_guitar_small.musicxml"
)


def _score(**overrides):
    return parse_musicxml(
        FIXTURE.read_bytes(),
        filename="solo_guitar_small.musicxml",
        **overrides,
    )


def _notes_at(score, bar: int, beat: float, voice: int) -> list[ImportedNote]:
    return [
        note
        for note in score.notes
        if note.bar == bar
        and abs(note.beat - beat) < 1e-9
        and note.voice == voice
    ]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def test_summary_fields() -> None:
    score = _score()

    assert score.filename == "solo_guitar_small.musicxml"
    assert score.title == "Nylon Guitar"
    assert score.meter == "3/4"
    assert score.key_fifths == 1
    assert score.key_mode == "major"
    assert score.tempo == pytest.approx(110.0)
    assert score.measure_count == 3
    assert score.part_count == 1
    assert len(score.source_hash) == 64
    assert score.id == f"musicxml:{score.source_hash[:16]}"


def test_parse_is_deterministic() -> None:
    assert _score() == _score()


# ---------------------------------------------------------------------------
# Placement, voices, chords, rests
# ---------------------------------------------------------------------------


def test_bar_beat_voice_and_sort_order() -> None:
    score = _score()

    # Bar 0, voice 1: dotted half at beat 0.
    (lead,) = _notes_at(score, 0, 0.0, 1)
    assert lead.duration == pytest.approx(3.0)
    assert (lead.midi, lead.written_midi) == (64, 76)
    assert lead.source_measure == "1"

    # Voice 2 starts with a quarter rest and then two chord groups.
    rest = _notes_at(score, 0, 0.0, 2)
    assert len(rest) == 1 and rest[0].rest and rest[0].midi is None

    keys = [(note.bar, note.beat, note.voice) for note in score.notes]
    assert keys == sorted(keys)
    assert {note.voice for note in score.notes} == {1, 2}


def test_chord_notes_share_the_onset() -> None:
    score = _score()

    first_chord = _notes_at(score, 0, 1.0, 2)
    assert [note.midi for note in first_chord] == [52, 55, 60]
    assert [note.written_midi for note in first_chord] == [64, 67, 72]
    assert [note.chord for note in first_chord] == [False, True, True]
    assert all(note.duration == pytest.approx(1.0) for note in first_chord)

    second_chord = _notes_at(score, 0, 2.0, 2)
    assert [note.midi for note in second_chord] == [52, 55, 60]


def test_rests_have_no_pitch_and_keep_their_voice() -> None:
    score = _score()

    rests = [note for note in score.notes if note.rest]
    assert len(rests) == 5
    assert all(note.midi is None and note.written_midi is None for note in rests)
    assert {(note.bar, note.voice) for note in rests} == {
        (0, 2),
        (1, 2),
        (2, 1),
        (2, 2),
    }


# ---------------------------------------------------------------------------
# Tie, grace, tuplet
# ---------------------------------------------------------------------------


def test_tie_start_and_stop() -> None:
    score = _score()

    (start,) = _notes_at(score, 1, 0.0, 1)
    (stop,) = _notes_at(score, 2, 0.0, 1)
    assert start.midi == stop.midi == 60
    assert start.tie_start and not start.tie_stop
    assert stop.tie_stop and not stop.tie_start


def test_grace_is_skipped_and_warned() -> None:
    score = _score()

    # The grace B4 is not a performed note.
    assert all(note.written_midi != 71 for note in score.notes)
    assert any("grace" in warning for warning in score.warnings)


def test_fixture_warnings_are_only_grace_and_tuplet() -> None:
    score = _score()

    assert len(score.warnings) == 2
    assert "grace" in score.warnings[0]
    assert "tuplet" in score.warnings[1]


def test_tuplet_uses_fractional_duration_units() -> None:
    score = _score()

    triplet = [note for note in score.notes if note.bar == 2 and note.voice == 1]
    assert [note.midi for note in triplet] == [60, 65, 69, 74, None]
    assert [note.beat for note in triplet] == pytest.approx(
        [0.0, 1.0, 4.0 / 3.0, 5.0 / 3.0, 2.0]
    )
    assert [note.duration for note in triplet] == pytest.approx(
        [1.0, 1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0, 1.0]
    )
    assert any("tuplet" in warning for warning in score.warnings)


# ---------------------------------------------------------------------------
# Written vs sounding pitch
# ---------------------------------------------------------------------------


def test_guitar_transpose_defaults_to_one_octave_down() -> None:
    score = _score()
    (lead,) = _notes_at(score, 0, 0.0, 1)
    assert lead.written_midi == 76
    assert lead.midi == 64


def test_guitar_transpose_zero_keeps_written_pitch() -> None:
    score = _score(guitar_transpose=0)
    (lead,) = _notes_at(score, 0, 0.0, 1)
    assert lead.written_midi == lead.midi == 76
    # The file declares -12, so using 0 is reported.
    assert any("declares a transpose of -12" in warning for warning in score.warnings)


@pytest.mark.parametrize("transpose", [60, -60])
def test_out_of_range_midi_is_rejected(transpose: int) -> None:
    with pytest.raises(MusicXmlImportError, match="0\\.\\.127"):
        _score(guitar_transpose=transpose)


# ---------------------------------------------------------------------------
# Slicing
# ---------------------------------------------------------------------------


def test_slice_is_inclusive_and_sorted() -> None:
    score = _score()

    sliced = slice_score(score, bar_start=1, bar_end=2)
    assert {note.bar for note in sliced} == {1, 2}
    assert sliced == tuple(note for note in score.notes if note.bar >= 1)

    only_bar_one = slice_score(score, bar_start=1, bar_end=1)
    assert only_bar_one
    assert all(note.bar == 1 for note in only_bar_one)


def test_slice_voice_filter() -> None:
    score = _score()

    low = slice_score(score, bar_start=0, bar_end=2, voices={2})
    assert low
    assert all(note.voice == 2 for note in low)
    assert slice_score(score, bar_start=0, bar_end=2, voices=2) == low
    assert slice_score(score, bar_start=0, bar_end=2, voices={}) == ()


@pytest.mark.parametrize(
    "bar_start, bar_end, voices",
    [
        (-1, 1, None),
        (2, 1, None),
        (0, 3, None),
        (0, 1, {0}),
    ],
)
def test_slice_rejects_invalid_ranges(bar_start, bar_end, voices) -> None:
    score = _score()
    with pytest.raises((TypeError, ValueError)):
        slice_score(
            score,
            bar_start=bar_start,
            bar_end=bar_end,
            voices=voices,
        )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def test_score_summary_counts() -> None:
    score = _score()
    summary = score_summary(score)

    assert summary["id"] == score.id
    assert summary["sourceHash"] == score.source_hash
    assert summary["title"] == "Nylon Guitar"
    assert summary["meter"] == "3/4"
    assert summary["measureMeters"] == ["3/4", "3/4", "3/4"]
    assert summary["measureCount"] == 3
    assert summary["partCount"] == 1
    assert summary["eventCount"] == 20
    assert summary["noteCount"] == 15
    assert summary["restCount"] == 5
    assert summary["voices"] == [1, 2]
    assert summary["lowestMidi"] == 43
    assert summary["highestMidi"] == 74
    assert summary["tieStarts"] == 1
    assert summary["tieStops"] == 1
    assert summary["warnings"] == list(score.warnings)


# ---------------------------------------------------------------------------
# Errors and warnings for unsupported documents
# ---------------------------------------------------------------------------


def _single_bar(
    *,
    time_signature: str | None = (
        "<time><beats>3</beats><beat-type>4</beat-type></time>"
    ),
    key_signature: str | None = "<key><fifths>1</fifths><mode>major</mode></key>",
    extra_measure: str = "",
    second_part: str = "",
    second_score_part: str = "",
) -> bytes:
    attributes = "<divisions>6</divisions>"
    if key_signature:
        attributes += key_signature
    if time_signature:
        attributes += time_signature
    attributes += "<clef><sign>G</sign><line>2</line></clef>"
    note = (
        "<note><pitch><step>E</step><octave>5</octave></pitch>"
        "<duration>6</duration><voice>1</voice><type>quarter</type></note>"
    )
    second = (
        f'<part id="P2"><measure number="1">{note}</measure></part>'
        if second_part
        else ""
    )
    extra_score_part = (
        '<score-part id="P2"><part-name>Second</part-name></score-part>'
        if second_score_part
        else ""
    )
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f"{extra_score_part}</part-list>"
        f'<part id="P1"><measure number="1"><attributes>{attributes}'
        f"</attributes>{note}</measure>{extra_measure}</part>"
        f"{second}</score-partwise>"
    ).encode("utf-8")


def test_score_timewise_is_rejected() -> None:
    with pytest.raises(MusicXmlImportError, match="score-timewise"):
        parse_musicxml(b'<score-timewise version="4.0"></score-timewise>')


def test_malformed_xml_is_rejected() -> None:
    with pytest.raises(MusicXmlImportError, match="not well-formed"):
        parse_musicxml(b"<score-partwise><part>")


def test_empty_and_compressed_documents_are_rejected() -> None:
    with pytest.raises(MusicXmlImportError, match="empty"):
        parse_musicxml(b"")
    with pytest.raises(MusicXmlImportError, match="compressed"):
        parse_musicxml(b"PK\x03\x04not really a zip")


def test_wrong_root_is_rejected() -> None:
    with pytest.raises(MusicXmlImportError, match="score-partwise"):
        parse_musicxml(b"<score><part/></score>")


def test_first_part_only_with_warning() -> None:
    score = parse_musicxml(
        _single_bar(second_part="yes", second_score_part="yes")
    )
    assert score.part_count == 2
    assert score.measure_count == 1
    assert any("2 parts found" in warning for warning in score.warnings)
    assert score.title == "Guitar"


def test_meter_change_is_kept_as_a_warning() -> None:
    second_measure = (
        '<measure number="2"><attributes><time><beats>4</beats>'
        "<beat-type>4</beat-type></time></attributes>"
        "<note><rest/><duration>6</duration><voice>1</voice>"
        "<type>quarter</type></note></measure>"
    )
    score = parse_musicxml(_single_bar(extra_measure=second_measure))

    assert score.meter == "3/4"
    assert score.measure_count == 2
    assert score.measure_meters == ("3/4", "4/4")
    assert score_summary(score)["measureMeters"] == ["3/4", "4/4"]
    assert any(
        "meter changes from 3/4 to 4/4" in warning
        for warning in score.warnings
    )


def _meter_change_score() -> bytes:
    """Bar 1 is 1/4, bar 2 changes to 2/4, bar 3 inherits 2/4."""

    def note(step: str, duration: int, note_type: str) -> str:
        return (
            "<note><pitch><step>"
            f"{step}"
            "</step><octave>5</octave></pitch>"
            f"<duration>{duration}</duration><voice>1</voice>"
            f"<type>{note_type}</type></note>"
        )

    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        "</part-list><part id=\"P1\">"
        '<measure number="1"><attributes><divisions>1</divisions>'
        "<time><beats>1</beats><beat-type>4</beat-type></time>"
        "</attributes>"
        + note("E", 1, "quarter")
        + '</measure><measure number="2">'
        "<attributes><time><beats>2</beats><beat-type>4</beat-type></time>"
        "</attributes>"
        + note("F", 2, "half")
        + '</measure><measure number="3">'
        + note("G", 2, "half")
        + "</measure></part></score-partwise>"
    ).encode("utf-8")


def test_measure_meters_change_and_inherit() -> None:
    score = parse_musicxml(_meter_change_score())

    assert score.meter == "1/4"
    assert score.measure_meters == ("1/4", "2/4", "2/4")
    assert score_summary(score)["measureMeters"] == ["1/4", "2/4", "2/4"]
    assert any(
        "meter changes from 1/4 to 2/4" in warning for warning in score.warnings
    )


def test_missing_time_fills_every_measure_with_assumed_meter() -> None:
    second = (
        '<measure number="2"><note><rest/><duration>24</duration>'
        "<voice>1</voice></note></measure>"
    )
    score = parse_musicxml(
        _single_bar(time_signature=None, extra_measure=second)
    )

    assert score.measure_meters == ("4/4", "4/4")
    assert score_summary(score)["measureMeters"] == ["4/4", "4/4"]


def test_missing_time_and_key_get_deterministic_defaults() -> None:
    score = parse_musicxml(
        _single_bar(time_signature=None, key_signature=None)
    )
    assert score.meter == "4/4"
    assert (score.key_fifths, score.key_mode) == (0, "major")
    assert any("no time signature" in warning for warning in score.warnings)
    assert any("no key signature" in warning for warning in score.warnings)


def test_repeat_is_reported_not_expanded() -> None:
    repeat = (
        '<measure number="2"><barline location="left"><repeat '
        'direction="forward"/></barline><note><rest/><duration>18</duration>'
        "<voice>1</voice><type>half</type><dot/></note></measure>"
    )
    score = parse_musicxml(_single_bar(extra_measure=repeat))
    assert score.measure_count == 2
    assert any("repeat (forward)" in warning for warning in score.warnings)


def test_parse_accepts_namespaced_documents() -> None:
    document = _single_bar().decode("utf-8")
    namespaced = document.replace(
        "<score-partwise version=\"4.0\">",
        '<score-partwise xmlns="http://www.musicxml.org/ns" version="4.0">',
    ).encode("utf-8")
    score = parse_musicxml(namespaced)
    assert score.measure_count == 1
    assert score.notes[0].midi == 64


def test_forward_staff_and_slur() -> None:
    document = b"""<score-partwise version="4.0">
      <part-list>
        <score-part id="P1"><part-name>Guitar</part-name></score-part>
      </part-list>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>6</divisions>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes>
          <forward><duration>6</duration></forward>
          <note>
            <pitch><step>G</step><octave>4</octave></pitch>
            <duration>6</duration>
            <voice>1</voice>
            <type>quarter</type>
            <staff>2</staff>
            <notations><slur type="start" number="1"/></notations>
          </note>
          <note>
            <pitch><step>A</step><octave>4</octave></pitch>
            <duration>6</duration>
            <voice>1</voice>
            <type>quarter</type>
            <staff>2</staff>
            <notations><slur type="stop" number="1"/></notations>
          </note>
        </measure>
      </part>
    </score-partwise>"""
    score = parse_musicxml(document)

    assert score.notes[0].beat == pytest.approx(1.0)
    assert score.notes[0].staff == 2
    assert score.notes[0].slur_start and not score.notes[0].slur_stop
    assert score.notes[1].slur_stop and not score.notes[1].slur_start
