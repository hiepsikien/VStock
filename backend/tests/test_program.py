"""Chart names follow the pattern that is actually written."""

from datetime import date

from app.sonify.guitar_patterns import _HEADLINE, _SKIP_VOICES
from app.sonify.keys import work_key_label
from app.sonify.model import Bar
from app.sonify.program import guitar_movement_name, pattern_title
from app.sonify.render import render
from app.sonify.span import month_specs, movement_title, quarter_specs, year_as_of, year_specs


def _bars(closes: list[float]) -> list[Bar]:
    return [Bar(close, 1000.0) for close in closes]


def _pattern_id(bars: list[Bar], *, skip: bool, **kwargs) -> str:
    found: list[str] = []
    token_headline = _HEADLINE.set(found)
    token_skip = _SKIP_VOICES.set(skip)
    try:
        render(bars, variant="guitar", **kwargs)
    finally:
        _HEADLINE.reset(token_headline)
        _SKIP_VOICES.reset(token_skip)
    assert found
    return found[0]


def test_work_key_stays_major_unless_every_movement_is_minor():
    assert work_key_label("VIC", ["minor", "major"]) == "Mi♭"
    assert work_key_label("VIC", ["minor", "minor"]) == "Mi♭ thứ"
    assert work_key_label("VIC", []) == "Mi♭"


def test_a_thin_opening_month_does_not_date_the_year():
    stamped = [(date(2026, 1, day), Bar(10.0)) for day in range(1, 32)]
    stamped += [(date(2026, 2, day), Bar(11.0)) for day in range(1, 6)]
    assert year_as_of(stamped) == date(2026, 1, 31)


def test_minimalist_quarter_closer_is_not_a_finale():
    closer = quarter_specs("minimalist")[2]
    assert closer.meter.beats == 7 and closer.meter.beat_type == 8
    assert movement_title("minimalist", "3M", 2, closer) is None
    assert movement_title("minimalist", "1M", 3, month_specs("minimalist")[3]) == "Finale"
    assert movement_title("symphony", "1Y", 11, year_specs()[11], 12) == "Finale"
    assert movement_title("jazz", "1M", 2, month_specs("jazz")[2]) == "Waltz"


def test_barrios_day_names_the_pattern_the_writer_picks():
    held = _bars([100.0] * 80)
    # A calm day is Preludio even when every phrase holds. A volatile day with
    # almost no melody motion is Ultimo Tremolo, not Choro.
    assert guitar_movement_name(held, ensemble="barrios", character="calm") == "Prelude"
    assert guitar_movement_name(held, ensemble="barrios", character="volatile") == "Tremolo"
    running = _bars([100 + (index % 7) * 2 for index in range(160)])
    assert guitar_movement_name(running, ensemble="barrios", character="volatile") == "Choro"


def test_villa_slow_and_six_eight_are_not_prelude_and_etude():
    slow = month_specs("guitar")[1]
    scherzo = month_specs("guitar")[2]
    assert (slow.meter.beats, slow.meter.beat_type, slow.bpm) == (3, 4, 72)
    assert (scherzo.meter.beats, scherzo.meter.beat_type, scherzo.bpm) == (6, 8, 120)
    flat = _bars([100.0] * 80)
    assert guitar_movement_name(flat, ensemble="villa", character="calm", form=slow, framed=False) == "Chord Melody"
    assert guitar_movement_name(flat, ensemble="villa", character="rally", form=scherzo, framed=False) == "Arpeggio"


def test_bach_slow_selloff_with_a_contrast_stays_sarabande():
    slow = month_specs("guitar")[1]
    wide = _bars([100 - index * 0.2 for index in range(80)])
    assert (
        guitar_movement_name(wide, ensemble="bach", character="selloff", form=slow, mode="minor", framed=False)
        == "Sarabande"
    )


def test_headline_matches_a_full_render():
    bars = _bars([100.0] * 40)
    skipped = _pattern_id(bars, skip=True, ensemble="barrios", character="volatile")
    written = _pattern_id(bars, skip=False, ensemble="barrios", character="volatile")
    assert skipped == written == "tremolo"
    assert pattern_title(written, "barrios") == "Tremolo"
