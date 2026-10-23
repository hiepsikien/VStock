"""Symphony flute, piano, bass, frame, and MuseSounds mix from the dynamics plan."""

from __future__ import annotations

import os
import re
import shutil
import sys
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
from app.sonify.form import METER_68, ChordSlot
from app.sonify.model import DynamicEvent, NoteEvent, Phrase, Run, WedgeEvent
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
