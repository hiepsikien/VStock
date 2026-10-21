"""Home keys, movement plans, spelling, and the register shift that keeps them in range."""

import xml.etree.ElementTree as ET

import pytest

from app.sonify.chords import A7, AM, BF, BORROWED, CHORDS, D7, DM, REGIME_BIAS
from app.sonify.form import DAILY_SPEC, chord_bias, plan_slots
from app.sonify.keys import (
    A_KEY,
    EB_KEY,
    KEY_RING,
    midi_to_spelled_pitch,
    month_keys,
    movement_character,
    stock_home_key,
    transpose_chord,
    year_key,
)
from app.sonify.model import Bar
from app.sonify.musicxml import score_to_musicxml
from app.sonify.quantize import c_major_scale
from app.sonify.render import assign_source_bars, render
from app.sonify.span import prepare_month

_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SEASONS = {
    "Eb": ("Eb", "Bb", "C", "Eb"),
    "Bb": ("Bb", "C", "Eb", "Bb"),
    "C": ("C", "D", "Bb", "C"),
    "D": ("D", "A", "C", "D"),
    "A": ("A", "D", "C", "A"),
}


def _bars(count: int = 40) -> list[Bar]:
    return [Bar(10.0 + index * 0.4, volume=float(index + 1)) for index in range(count)]


def test_home_key_is_stable_and_case_insensitive():
    assert stock_home_key("hpg").name == "Eb"
    assert stock_home_key(" VCB ").name == "Bb"
    assert stock_home_key("fpt").name == "D"
    assert stock_home_key("vnm").name == "C"
    assert stock_home_key("gmd").name == "A"
    assert stock_home_key("zzz") == stock_home_key("ZZZ")
    assert stock_home_key("zzz") in KEY_RING


def test_year_seasons_match_the_ring_and_the_frame_stays_home():
    for key in KEY_RING:
        calm = tuple(year_key(key, season, "calm", frame=False).name for season in range(4))
        assert calm == _SEASONS[key.name]
        assert year_key(key, 1, "rally", frame=True) == key
        assert year_key(key, 3, "selloff", frame=False) == key
        assert year_key(key, 0, "rally", frame=False) == key


def test_month_movements_one_two_and_three_use_three_keys():
    edges = (("sideway", "sideway"),) * 4
    for home in KEY_RING:
        for character in ("calm", "rally", "selloff", "volatile"):
            keys = month_keys(home, (character,) * 4, edges)
            assert len({item.name for item in keys[:3]}) == 3
            assert keys[0] == home
            assert keys[3] == home


def test_borrowed_bias_does_not_follow_the_diatonic_root():
    assert chord_bias(A7, "uptrend", "rally") == pytest.approx(0.02)
    assert chord_bias(AM, "uptrend", "rally") == REGIME_BIAS["uptrend"][AM] + 0.06
    assert chord_bias(D7, "downtrend", "selloff") == 0.08
    assert chord_bias(DM, "downtrend", "selloff") == REGIME_BIAS["downtrend"][DM] - 0.08
    assert chord_bias(AM, "uptrend", None) == REGIME_BIAS["uptrend"][AM]


def test_neutral_character_matches_the_daily_plan():
    bars = _bars()
    regimes = ("uptrend", "sideway", "downtrend")
    scale = c_major_scale()
    groups = assign_source_bars(len(bars), DAILY_SPEC.bars)
    pitches: list[int] = []
    for group in groups:
        close = bars[group[-1]].close if group else bars[0].close
        pitches.extend([scale[min(len(scale) - 1, int(close))] for _ in range(8)])
    plain = plan_slots(regimes, pitches, scale, DAILY_SPEC)
    named = plan_slots(regimes, pitches, scale, DAILY_SPEC, character=None, outro_override=None)
    assert [slot.chord for slot in named] == [slot.chord for slot in plain]


def test_every_chord_spells_inside_its_key():
    shifted = transpose_chord(BF, EB_KEY)
    assert (shifted.root_step, shifted.alter) == ("D", -1)
    step, alter, _octave = midi_to_spelled_pitch(BF.pitches[0] + 3, EB_KEY, BF)
    assert (step, alter) == ("D", -1)
    third = transpose_chord(D7, EB_KEY)
    assert third.spelling(third.pitches[1] % 12) == ("A", 0)

    for key in KEY_RING:
        for chord in (*CHORDS, *BORROWED):
            written = transpose_chord(chord, key)
            assert written.pitches[0] - chord.pitches[0] == key.semitones
            assert abs(written.alter) <= 1
            for _pc, _step, tone_alter in written.tones:
                assert abs(tone_alter) <= 1
            for pitch in written.pitches:
                step, alter, octave = midi_to_spelled_pitch(pitch, key, chord)
                assert abs(alter) <= 1
                assert (octave + 1) * 12 + _NATURAL[step] + alter == pitch


def test_positive_shift_lowers_the_ceiling_and_negative_shift_raises_the_floor():
    bars = _bars()
    bright = render(bars, key=EB_KEY, title="bright")
    dark = render(bars, key=A_KEY, title="dark")
    assert all(note.midi is None or note.midi <= 84 - 3 for note in bright.lead)
    assert all(note.midi is None or note.midi <= 88 - 3 for note in bright.high)
    assert all(note.midi is None or note.midi >= 55 + 3 for note in dark.lead)
    jazz = render(bars, variant="jazz", key=A_KEY, title="sax")
    assert all(note.midi is None or note.midi >= 55 + 3 for note in jazz.lead)
    assert all(note.midi is None or note.midi <= 80 for note in jazz.lead)
    steep = [Bar(10.0 + index * 2.5, volume=float(100 + index)) for index in range(40)]
    eb_jazz = render(steep, variant="jazz", key=EB_KEY, title="sax-eb")
    assert all(note.midi is None or note.midi <= 77 for note in eb_jazz.lead)
    eb_bells = [note.midi + EB_KEY.semitones for note in eb_jazz.high if note.midi is not None]
    assert eb_bells
    assert max(eb_bells) <= 89
    eb_arp = [
        note.midi + EB_KEY.semitones
        for note in render(steep, variant="minimalist", key=EB_KEY, title="arp").lead
        if note.midi is not None
    ]
    a_arp = [
        note.midi + A_KEY.semitones
        for note in render(steep, variant="minimalist", key=A_KEY, title="arp-a").lead
        if note.midi is not None
    ]
    assert eb_arp and max(eb_arp) <= 84
    assert a_arp and min(a_arp) >= 48


def test_musicxml_uses_the_key_signature_once():
    score = render(_bars(), key=EB_KEY, title="E flat")
    root = ET.fromstring(score_to_musicxml(score))
    fifths = {node.text for node in root.iter("fifths")}
    assert fifths == {"-3"}


def test_span_fingerprint_includes_key_character_and_coda():
    from datetime import date

    stamped = []
    for week in range(4):
        for day in range(3):
            bars = [Bar(80.0 + week * 8 + index * 0.3, volume=100) for index in range(20)]
            stamped.append((date(2026, 3, 2 + week * 7 + day), bars))
    movements = prepare_month(stamped, "HPG")
    assert [item.key.name for item in movements[:3]] == ["Eb", "Bb", "C"]
    assert movements[3].key.name == "Eb"
    assert movements[0].scale_fingerprint.startswith("Eb-")
    assert "-none-" in movements[0].scale_fingerprint
    assert movement_character([80.0, 70.0], "1M") == "selloff"
