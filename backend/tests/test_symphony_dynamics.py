"""Symphony flute, piano, bass, frame, and MuseSounds mix from the dynamics plan."""

from __future__ import annotations

import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from math import log10

import pytest

from app.sonify.audio import (
    _VOICE_VOLUME_DB,
    _assign_installed_sounds,
    _installed_muse_sounds,
    _mute_mscx_harmony,
    _run_musescore,
    _wav_samples,
    find_musescore,
)
from app.sonify.chords import C, F
from app.sonify.daily_frame import _flute_body_dynamics, _piano_frame_dynamics, _trim_frame_wedges
from app.sonify.dynamics import PIANO_VELOCITY, SOUND
from app.sonify.form import METER_44, METER_68, ChordSlot
from app.sonify.groove import BarGroove, compose_groove, groove_at
from app.sonify.model import DynamicEvent, NoteEvent, Phrase, Run, Score, WedgeEvent
from app.sonify.movement_frame import _curtain_comp
from app.sonify.musicxml import score_to_musicxml
from app.sonify.phrasing import BREAKOUT, WEDGE_MIN, left_hand
from app.sonify.render import _bass_bar, _right_hand, _shape_flute_span


def _phrase(*runs: Run) -> Phrase:
    return Phrase(runs[0].start, runs[-1].end, runs)


def _pitches(runs: tuple[Run, ...], length: int) -> list[int]:
    pitches = [60] * length
    for run in runs:
        for eighth in range(run.start, run.end):
            pitches[eighth] = run.midi
    return pitches


def _shape(
    phrase: Phrase,
    span: tuple[int, int],
    flute_runs: list[Run],
    *,
    band: str = "mp",
    ensemble: str = "classic",
    level: str = "mp",
    tie_first_in: bool = False,
    colours: dict[int, str] | None = None,
):
    pitches = _pitches(phrase.runs, span[1] + 1)
    bands = {eighth // 8: band for eighth in range(span[1] + 1)}
    return _shape_flute_span(
        phrase,
        pitches,
        span[0],
        span[1],
        flute_runs,
        tie_first_in,
        colours or {},
        bands,
        ensemble,  # type: ignore[arg-type]
        level,
    )


def test_quiet_flute_stays_flat_mp() -> None:
    runs = (Run(0, 4, 60), Run(4, 4, 64), Run(8, 4, 67))
    wedges, dynamics, velocities, level = _shape(_phrase(*runs), (0, 12), list(runs), band="mp")
    assert wedges == []
    assert dynamics == []
    assert level == "mp"
    assert all(64 <= velocity <= 72 for velocity in velocities)


def test_long_single_flute_note_swells_at_the_midpoint_without_mf() -> None:
    phrase = _phrase(Run(0, 4, 60), Run(4, 8, 72))
    wedges, dynamics, _velocities, level = _shape(phrase, (4, 12), [Run(4, 8, 72)], band="mf")
    assert [wedge.kind for wedge in wedges] == ["crescendo", "stop", "diminuendo", "stop"]
    assert all(event.marking != "mf" for event in dynamics)
    assert level == "mp"


def test_rising_flute_hairpin_uses_the_first_high_eighth_and_does_not_print_mf() -> None:
    runs = (Run(0, 4, 60), Run(4, 4, 72), Run(8, 4, 64))
    wedges, dynamics, _velocities, level = _shape(_phrase(*runs), (0, 12), list(runs), band="f")
    assert [wedge.kind for wedge in wedges] == ["crescendo", "stop", "diminuendo", "stop"]
    assert (wedges[1].bar, wedges[1].beat) == (0, 2.0)
    assert all(event.marking != "mf" for event in dynamics)
    assert level == "mp"


def test_crescendo_that_ends_on_the_apex_drifts_so_the_next_span_reprints() -> None:
    runs = (Run(0, 4, 60), Run(4, 1, 72))
    _wedges, dynamics, _velocities, level = _shape(_phrase(*runs), (0, 5), list(runs), band="mf")
    assert [wedge.kind for wedge in _wedges] == ["crescendo", "stop"]
    assert dynamics == []
    assert level == "drifted"
    nxt = _phrase(Run(8, 4, 60), Run(12, 4, 64))
    _again, reprinted, _vel, _again_level = _shape(nxt, (8, 16), list(nxt.runs), band="mp", level=level)
    assert reprinted[0].marking == "mp"


def test_flute_that_enters_on_the_apex_opens_mf_and_diminuendos() -> None:
    runs = (Run(0, 4, 72), Run(4, 4, 60))
    wedges, dynamics, _velocities, level = _shape(_phrase(*runs), (0, 8), list(runs), band="mf")
    assert dynamics[0].marking == "mf"
    assert [wedge.kind for wedge in wedges] == ["diminuendo", "stop"]
    assert level == "drifted"


def test_tied_opening_skips_the_letter_and_a_breakout_run_is_velocity_80() -> None:
    runs = (Run(0, 4, 60), Run(4, 4, 72))
    wedges, dynamics, velocities, _level = _shape(
        _phrase(*runs),
        (0, 8),
        list(runs),
        band="mp",
        tie_first_in=True,
        colours={4: BREAKOUT},
    )
    assert dynamics[0].beat == 2.0
    assert wedges[0].beat == 2.0
    assert velocities[1] == 80


def test_one_eighth_peak_80_splits_glock_and_flute() -> None:
    phrase = _phrase(Run(0, 4, 66), Run(4, 1, 72))
    flute_run = [Run(4, 1, 72)]
    _wedges, dynamics, velocities, level = _shape(phrase, (4, 5), flute_run, band="mf")
    assert _wedges == []
    assert dynamics == []
    assert velocities == [round(64 + 16 * 0.5)]
    assert level == "mp"

    glock_wedges, glock_dynamics, glock_velocities, glock_level = _shape(
        phrase, (4, 5), flute_run, band="mf", ensemble="brass"
    )
    assert glock_wedges == []
    assert glock_dynamics[0].marking == "mf"
    assert glock_velocities == [80]
    assert glock_level == "drifted"


def test_glock_that_enters_on_the_apex_opens_mp_and_diminuendos() -> None:
    runs = (Run(0, 2, 72), Run(2, 4, 60))
    wedges, dynamics, _velocities, level = _shape(
        _phrase(*runs), (0, 6), list(runs), band="mf", ensemble="brass", level="drifted"
    )
    assert dynamics[0].marking == "mp"
    assert dynamics[0].bar == 0 and dynamics[0].beat == 0.0
    assert all(event.marking != "mf" for event in dynamics)
    assert [wedge.kind for wedge in wedges] == ["diminuendo", "stop"]
    assert level == "drifted"


def test_flute_apex_entry_at_the_downbeat_prints_one_mf_tag() -> None:
    runs = (Run(0, 2, 72), Run(2, 4, 60))
    wedges, dynamics, _velocities, level = _shape(_phrase(*runs), (0, 6), list(runs), band="mf")
    assert dynamics[0] == DynamicEvent(0, "mf", SOUND["mf"], 0.0)
    assert [wedge.kind for wedge in wedges] == ["diminuendo", "stop"]
    assert level == "drifted"
    nxt = _phrase(Run(8, 4, 60), Run(12, 4, 64))
    _again, reprinted, _vel, _again_level = _shape(nxt, (8, 16), list(nxt.runs), level=level)
    score = _bare_score(
        bars=3,
        high=(NoteEvent(0, 0.0, 72, 4.0, 1), NoteEvent(1, 0.0, 64, 4.0, 1)),
        high_wedges=tuple(wedges),
        high_dynamics=(*dynamics, *reprinted),
    )
    root = ET.fromstring(score_to_musicxml(score))
    first = root.find("part[@id='P5']/measure[@number='1']")
    assert first is not None
    letters = first.findall("direction/direction-type/dynamics")
    assert len(letters) == 1
    assert letters[0].find("mf") is not None
    second = root.find("part[@id='P5']/measure[@number='2']")
    assert second is not None
    assert second.find("direction/direction-type/dynamics/mp") is not None


def test_glock_with_two_runs_keeps_the_hairpin_and_never_prints_mf() -> None:
    runs = (Run(0, 4, 60), Run(4, 4, 72))
    wedges, dynamics, velocities, _level = _shape(
        _phrase(*runs), (0, 8), list(runs), band="mf", ensemble="brass"
    )
    assert wedges
    assert all(event.marking != "mf" for event in dynamics)
    assert velocities[0] < 80
    assert velocities[1] == 80


def test_cello_lead_folds_every_bass_note_under_c3() -> None:
    folded = _bass_bar(F, "f", 0, under_cello=True)
    assert folded
    assert all(note.midi is not None and note.midi < 48 for note in folded)
    open_pattern = _bass_bar(C, "f", 0, under_cello=False)
    assert any(note.midi is not None and note.midi >= 48 for note in open_pattern)
    assert max(METER_68.quarter_beats / 2, 2.0) == 2.0


def test_a_short_cello_dovetail_keeps_the_open_bass_pattern() -> None:
    short = 1.5
    for meter in (METER_44, METER_68):
        threshold = max(meter.quarter_beats / 2, 2.0) - 1e-6
        assert short < threshold
        assert 2.0 >= threshold
    lead = {bar for bar, beats in {0: short, 1: 2.0}.items() if beats >= max(METER_44.quarter_beats / 2, 2.0) - 1e-6}
    assert lead == {1}
    open_line = [note.midi for note in _bass_bar(F, "f", 0, under_cello=0 in lead)]
    folded = [note.midi for note in _bass_bar(F, "f", 1, under_cello=1 in lead)]
    assert open_line == [note.midi for note in _bass_bar(F, "f", 0, under_cello=False)]
    assert any(midi is not None and midi >= 48 for midi in open_line)
    assert all(midi is not None and midi < 48 for midi in folded)


def test_piano_fill_rises_from_the_bed_and_a_fall_reprints_it() -> None:
    rising = _phrase(Run(0, 4, 60), Run(4, 8, 67))
    notes, marks, wedges = _right_hand(
        (ChordSlot(0, 2, C, "sideway", "phrase"),),
        [(9, 1, 60), (10, 1, 64), (11, 1, 67)],
        16,
        bed_velocity_at={0: PIANO_VELOCITY["p"], 1: PIANO_VELOCITY["p"]},
        bed_marking_at={0: "p", 1: "p"},
        phrases=(rising,),
    )
    fills = [note for note in notes if note.staff == 1 and note.midi is not None and note.beat > 0]
    assert [note.velocity for note in fills] == [46, 55, 64]
    assert marks == [(1, 0.5, "p", True)]
    assert [wedge.kind for wedge in wedges] == ["crescendo", "stop"]

    falling = _phrase(Run(0, 4, 67), Run(4, 8, 60))
    _notes, fall_marks, fall_wedges = _right_hand(
        (ChordSlot(0, 2, C, "sideway", "phrase"),),
        [(9, 1, 64), (10, 1, 60)],
        16,
        bed_velocity_at={0: 46, 1: 46},
        bed_marking_at={0: "p", 1: "p"},
        phrases=(falling,),
    )
    assert fall_marks == [(1, 0.5, "mp", True)]
    assert [wedge.kind for wedge in fall_wedges] == ["diminuendo", "stop"]
    assert [note.velocity for note in _notes if note.staff == 1 and note.beat > 0 and note.midi] == [64, 56]


def test_flat_and_single_fills_print_the_step_above_the_bed_without_a_wedge() -> None:
    flat = _phrase(Run(0, 4, 60), Run(4, 8, 60))
    notes, marks, wedges = _right_hand(
        (ChordSlot(0, 2, C, "sideway", "phrase"),),
        [(9, 1, 64), (10, 1, 67)],
        16,
        bed_velocity_at={0: 46, 1: 46},
        bed_marking_at={0: "p", 1: "p"},
        phrases=(flat,),
    )
    assert marks == [(1, 0.5, "mp", False)]
    assert wedges == []
    assert [note.velocity for note in notes if note.staff == 1 and note.beat > 0 and note.midi] == [64, 64]

    _alone, alone_marks, alone_wedges = _right_hand(
        (ChordSlot(0, 2, C, "sideway", "phrase"),),
        [(9, 1, 67)],
        16,
        bed_velocity_at={0: 62, 1: 62},
        bed_marking_at={0: "mp", 1: "mp"},
        phrases=(flat,),
    )
    assert alone_marks == [(1, 0.5, "mf", False)]
    assert alone_wedges == []
    assert [
        note.velocity for note in _alone if note.staff == 1 and note.beat > 0 and note.midi
    ] == [80]


def test_an_mp_bed_ramps_a_rise_to_80_and_a_fall_down_to_72() -> None:
    rising = _phrase(Run(0, 4, 60), Run(4, 8, 67))
    for bed_vel in (62, 68):
        notes, marks, wedges = _right_hand(
            (ChordSlot(0, 2, C, "sideway", "phrase"),),
            [(9, 1, 64), (11, 1, 67)],
            16,
            bed_velocity_at={0: bed_vel, 1: bed_vel},
            bed_marking_at={0: "mp", 1: "mp"},
            phrases=(rising,),
        )
        fills = [note for note in notes if note.staff == 1 and note.beat > 0 and note.midi]
        assert [note.velocity for note in fills] == [bed_vel, 80]
        assert marks == [(1, 0.5, "mp", True)]
        assert [wedge.kind for wedge in wedges] == ["crescendo", "stop"]

    falling = _phrase(Run(0, 4, 67), Run(4, 8, 60))
    notes, marks, wedges = _right_hand(
        (ChordSlot(0, 2, C, "sideway", "phrase"),),
        [(9, 1, 67), (11, 1, 64)],
        16,
        bed_velocity_at={0: 62, 1: 62},
        bed_marking_at={0: "mp", 1: "mp"},
        phrases=(falling,),
    )
    fills = [note for note in notes if note.staff == 1 and note.beat > 0 and note.midi]
    assert [note.velocity for note in fills] == [80, 72]
    assert marks == [(1, 0.5, "mf", True)]
    assert [wedge.kind for wedge in wedges] == ["diminuendo", "stop"]


def test_selloff_falls_and_rally_rises_whatever_the_phrase_does() -> None:
    rising = _phrase(Run(0, 4, 60), Run(4, 8, 67))
    with compose_groove({1: BarGroove(selloff=True)}):
        _notes, marks, wedges = _right_hand(
            (ChordSlot(0, 2, C, "sideway", "phrase"),),
            [(9, 1, 64), (11, 1, 67)],
            16,
            bed_velocity_at={0: 46, 1: 46},
            bed_marking_at={0: "p", 1: "p"},
            phrases=(rising,),
        )
    assert marks == [(1, 0.5, "mp", True)]
    assert [wedge.kind for wedge in wedges] == ["diminuendo", "stop"]

    falling = _phrase(Run(0, 4, 67), Run(4, 8, 60))
    with compose_groove({1: BarGroove(rally=True)}):
        _notes, marks, wedges = _right_hand(
            (ChordSlot(0, 2, C, "sideway", "phrase"),),
            [(9, 1, 67), (11, 1, 60)],
            16,
            bed_velocity_at={0: 46, 1: 46},
            bed_marking_at={0: "p", 1: "p"},
            phrases=(falling,),
        )
    assert marks == [(1, 0.5, "p", True)]
    assert [wedge.kind for wedge in wedges] == ["crescendo", "stop"]


def test_jazz_left_hand_stays_on_every_other_bar_without_velocity() -> None:
    events = left_hand(ChordSlot(0, 4, C, "sideway", "phrase"))
    sounding = [note for note in events if note.midi is not None]
    assert [note.bar for note in sounding] == [0, 2]
    assert all(note.velocity is None for note in sounding)


def test_outro_root_restrikes_every_marked_bar() -> None:
    slot = ChordSlot(0, 4, C, "sideway", "outro")
    plain = [note.bar for note in left_hand(slot) if note.midi is not None]
    marked = [
        note.bar
        for note in left_hand(slot, every_bar_at=frozenset({1, 3}))
        if note.midi is not None
    ]
    assert plain == [0]
    assert marked == [0, 1, 3]


def test_f_and_rally_bars_restrike_inside_an_outro() -> None:
    slot = ChordSlot(0, 4, C, "sideway", "outro")
    eff = {0: "p", 1: "f", 2: "mp", 3: "p"}
    with compose_groove({2: BarGroove(rally=True)}):
        dense = frozenset(bar for bar in range(4) if eff[bar] == "f" or groove_at(bar).rally)
        sounded = [note.bar for note in left_hand(slot, every_bar_at=dense) if note.midi is not None]
    assert dense == frozenset({1, 2})
    assert sounded == [0, 1, 2]
    jazz = [note.bar for note in left_hand(slot) if note.midi is not None]
    assert jazz == [0]


def test_frame_reopens_a_wedge_and_restores_mf_without_dropping_a_later_mp() -> None:
    wedges = (
        WedgeEvent(0, 0.0, "crescendo"),
        WedgeEvent(3, 0.0, "stop"),
    )
    trimmed = _trim_frame_wedges(wedges, body=2, cool=32, beats=4.0, eighths_per_bar=8)
    assert trimmed[0] == WedgeEvent(2, 0.0, "crescendo")
    assert trimmed[1] == WedgeEvent(3, 0.0, "stop")
    assert _eighth_span(trimmed) >= WEDGE_MIN

    notes = (NoteEvent(2, 0.0, 72, 1.0, 1),)
    dynamics = (
        DynamicEvent(0, "mf", SOUND["mf"]),
        DynamicEvent(4, "mp", SOUND["mp"], 1.0),
    )
    restored = _flute_body_dynamics(dynamics, notes, 2, 32)
    assert restored[0] == DynamicEvent(2, "mf", SOUND["mf"], 0.0)
    assert restored[1].marking == "mp"

    piano = _piano_frame_dynamics(
        (DynamicEvent(1, "mp", SOUND["mp"]), DynamicEvent(6, "p", SOUND["p"])),
        2,
        32,
        dynamic=False,
        warm_start=0,
        tag=0,
    )
    assert piano[0].marking == "mp"
    assert piano[0].bar == 2

    risen = _piano_frame_dynamics(
        (DynamicEvent(4, "p", SOUND["p"]),),
        2,
        8,
        dynamic=True,
        warm_start=0,
        tag=2,
        wedges=(WedgeEvent(4, 2.0, "crescendo"), WedgeEvent(4, 4.0, "stop")),
    )
    assert risen[-1] == DynamicEvent(8, "p", SOUND["p"], 0.0)
    settled = _piano_frame_dynamics(
        (DynamicEvent(4, "p", SOUND["p"]),),
        2,
        8,
        dynamic=True,
        warm_start=0,
        tag=2,
    )
    assert settled[-1].bar != 8


def test_curtain_notes_are_velocity_49_and_the_body_is_left_alone() -> None:
    body = NoteEvent(3, 0.0, 60, 4.0, 1, velocity=62)
    score = _bare_score(bars=8, comp=(body,))
    notes = _curtain_comp(score, 0, 2, 6, 8, C, C, 2)
    curtain = [note for note in notes if note.midi is not None and (note.bar < 2 or note.bar >= 6)]
    kept = [note for note in notes if note.midi is not None and 2 <= note.bar < 6]
    assert curtain
    assert all(note.velocity == 49 for note in curtain)
    assert [note.velocity for note in kept] == [62]


def _bare_score(**overrides) -> Score:
    fields = dict(
        title="dynamics",
        bpm=96,
        bars=2,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(),
        high=(),
        lead=(),
        support=(),
        comp=(),
        low=(),
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
    )
    fields.update(overrides)
    return Score(**fields)


_ENSEMBLE_GAINS = (
    ("Flute 1", 5),
    ("Violins 1", 2),
    ("Cellos", 4),
    ("Piano", -2),
    ("Electric Bass", -6),
    ("Piccolo", 0),
    ("Oboe", 6),
    ("Clarinet in Bb", 3),
    ("Harp", 8),
    ("Contrabassoon", 10),
    ("Glockenspiel", 10),
    ("Trumpet", 6),
    ("Trombone", 8),
    ("French Horns a6", -5),
    ("Tuba", -5),
    ("Vibraphone", 3),
    ("Alto Saxophone", 0),
    ("Tenor Saxophone", 0),
    ("Suitcase Piano", -2),
    ("Electric LP - Clean", 4),
    ("Wurly 200A", 0),
    ("Electric SC - Clean", 4),
    ("Soprano Saxophone", 0),
    ("Baritone Saxophone", 0),
    ("Hammond Organ", 0),
    ("Synth Bell", 0),
    ("Synth Arpeggio", 0),
    ("Synth Pad", 0),
    ("Synth Pulse", 0),
    ("Sub-Bass", 0),
    ("Crotales", 12),
    ("Marimba", 10),
    ("Full Choir", 8),
    ("Harpsichord", 0),
    ("Flute 2", 0),
    ("Acoustic Steel Plucked", 8),
    ("Upright Piano", 0),
    ("Celesta", 6),
    ("Alto Flute", 0),
    ("Bass Flute", -5),
    ("French Horn", 0),
    ("Contrabasses", 0),
    ("Handchimes", 0),
    ("English Horn", 0),
    ("Bass Clarinet", 0),
    ("Trombones a3", 0),
    ("Handbells", 0),
    ("Tenors", 2),
    ("Violas", 3),
    ("Basses", 0),
)


def test_voice_gains_match_the_twelve_ensembles() -> None:
    assert {sound: _VOICE_VOLUME_DB.get(sound, 0) for sound, _gain in _ENSEMBLE_GAINS} == dict(
        _ENSEMBLE_GAINS
    )
    assert "French Horn" not in _VOICE_VOLUME_DB
    assert "Contrabasses" not in _VOICE_VOLUME_DB
    assert _VOICE_VOLUME_DB["French Horns a6"] == -5


def _eighth_span(wedges: tuple[WedgeEvent, ...]) -> int:
    start = wedges[0].bar * 8 + int(round(wedges[0].beat * 2))
    stop = wedges[1].bar * 8 + int(round(wedges[1].beat * 2))
    return stop - start


def test_mute_harmony_is_idempotent_and_voice_gain_is_stored(tmp_path) -> None:
    body = (
        '<?xml version="1.0"?><museScore><Score>'
        "<Harmony><root>0</root></Harmony>"
        "<Harmony><root>1</root><play>0</play></Harmony>"
        '<Part id="1"><Instrument id="violin">'
        "<instrumentId>strings.violin</instrumentId></Instrument></Part>"
        "</Score></museScore>"
    )
    source = body.encode()
    once = _mute_mscx_harmony(source)
    twice = _mute_mscx_harmony(once)
    assert twice == once
    text = once.decode()
    assert text.count("<play>0</play>") == 2
    assert "<root>0</root>" in text

    loud = (
        '<?xml version="1.0"?><museScore><Score>'
        "<Harmony><root>0</root><play>1</play></Harmony>"
        "<tail>keep</tail></Score></museScore>"
    ).encode()
    muted = _mute_mscx_harmony(loud)
    assert b"<play>1</play>" not in muted
    assert muted.count(b"<play>0</play>") == 1
    assert b"<tail>keep</tail>" in muted
    odd = b"\xff\xfe"
    assert _mute_mscx_harmony(odd) is odd

    mscz = tmp_path / "piece.mscz"
    with zipfile.ZipFile(mscz, "w") as archive:
        archive.writestr("score.mscx", body)
        archive.writestr("audiosettings.json", '{"tracks": []}')
    assert _assign_installed_sounds(mscz, {"Violins 1": ("91", "Muse Strings")})
    with zipfile.ZipFile(mscz) as archive:
        written = archive.read("score.mscx")
        settings = archive.read("audiosettings.json")
    assert b"<play>0</play>" in written
    assert _VOICE_VOLUME_DB["Violins 1"] == 2
    assert b'"volumeDb": 2' in settings or b'"volumeDb": 2.0' in settings


_ONE_BAR = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P3">
      <part-name>Piano</part-name>
      <score-instrument id="P3-I1"><instrument-name>Piano</instrument-name></score-instrument>
    </score-part>
  </part-list>
  <part id="P3">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <harmony><root><root-step>C</root-step></root><kind text="maj7">major-seventh</kind></harmony>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>whole</type>
      </note>
      <note>
        <chord/>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>whole</type>
      </note>
      <note>
        <chord/>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>whole</type>
      </note>
      <note>
        <chord/>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""


def _rms(path) -> float:
    channels, _rate, samples = _wav_samples(path)
    if channels < 1 or len(samples) < channels:
        return 0.0
    total = 0.0
    count = 0
    for index in range(0, len(samples) - channels + 1, channels):
        for channel in range(channels):
            value = float(samples[index + channel])
            total += value * value
            count += 1
    return (total / count) ** 0.5 if count else 0.0


def _score_parts(mscz) -> tuple[bytes, bytes]:
    with zipfile.ZipFile(mscz) as archive:
        name = next(item for item in archive.namelist() if item.endswith(".mscx"))
        return archive.read(name), archive.read("audiosettings.json")


def _set_harmony_play(mscz, value: str) -> None:
    pattern = re.compile(r"<Harmony\b[^>]*>.*?</Harmony>", re.DOTALL)
    with zipfile.ZipFile(mscz) as archive:
        payload = {item: archive.read(item) for item in archive.namelist()}
    mscx_name = next(item for item in payload if item.endswith(".mscx"))

    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        if "<play>" in block:
            return re.sub(r"<play>\s*[^<]*\s*</play>", f"<play>{value}</play>", block)
        return block.replace("</Harmony>", f"<play>{value}</play></Harmony>", 1)

    payload[mscx_name] = pattern.sub(repl, payload[mscx_name].decode("utf-8")).encode("utf-8")
    with zipfile.ZipFile(mscz, "w") as archive:
        for item, blob in payload.items():
            archive.writestr(item, blob)


def test_muted_harmony_piano_is_about_six_db_quieter(tmp_path) -> None:
    binary = find_musescore()
    if binary is None:
        pytest.skip("MuseScore is not installed")
    library = _installed_muse_sounds()
    if "Piano" not in library:
        pytest.skip("MuseSounds Piano is not installed")
    xml = tmp_path / "bar.musicxml"
    xml.write_text(_ONE_BAR, encoding="utf-8")
    quiet_score = tmp_path / "quiet.mscz"
    env = os.environ.copy()
    if sys.platform.startswith("linux"):
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    runtime = env.get("XDG_RUNTIME_DIR", "/tmp/runtime-mscore")
    os.makedirs(runtime, exist_ok=True)
    env["XDG_RUNTIME_DIR"] = runtime
    _run_musescore([binary, "-o", str(quiet_score), str(xml)], env)
    assert _assign_installed_sounds(quiet_score, library, xml)
    loud_score = tmp_path / "loud.mscz"
    shutil.copy(quiet_score, loud_score)
    _set_harmony_play(loud_score, "1")
    quiet_xml, quiet_settings = _score_parts(quiet_score)
    loud_xml, loud_settings = _score_parts(loud_score)
    assert quiet_settings == loud_settings
    assert b"<play>0</play>" in quiet_xml and b"<play>1</play>" not in quiet_xml
    assert b"<play>1</play>" in loud_xml
    quiet = tmp_path / "quiet.wav"
    loud = tmp_path / "loud.wav"
    _run_musescore([binary, "-o", str(quiet), str(quiet_score)], env)
    _run_musescore([binary, "-o", str(loud), str(loud_score)], env)
    loud_rms = _rms(loud)
    quiet_rms = _rms(quiet)
    assert loud_rms > 0 and quiet_rms > 0
    drop = 20 * log10(loud_rms / quiet_rms)
    assert 4.0 <= drop <= 8.0, drop
