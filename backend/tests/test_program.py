"""Chart names follow the pattern that is actually written."""

import json
from datetime import date
from pathlib import Path

from app.sonify.audio import RecapStore
from app.sonify.chords import C
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _Ctx, _HEADLINE, _SKIP_VOICES, _barrios_region_patterns, form_pattern_ids
from app.sonify.keys import work_key_label
from app.sonify.model import Bar, Phrase, Run
from app.sonify.program import guitar_movement_name, pattern_form, pattern_title, span_movement_name
from app.sonify.render import render
from app.sonify.span import (
    PreparedMovement,
    attach_frame,
    month_specs,
    movement_title,
    quarter_specs,
    week_spec,
    year_as_of,
    year_specs,
)


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


def test_long_barrios_movements_walk_a_pattern_row():
    flat = _bars([100.0] * 80)
    opening = attach_frame(month_specs("guitar")[0], "1M")
    slow = attach_frame(month_specs("guitar")[1], "1M")
    scherzo = attach_frame(month_specs("guitar")[2], "1M")
    finale = attach_frame(month_specs("guitar")[3], "1M")
    # Three parts reprise. Two parts end on the guest. A week of five hears
    # Tremolo in the center, and the title names that center rather than the
    # second region.
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=opening) == (
        "Prelude — Andante — Prelude"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="calm", form=slow) == (
        "Andante — Cantabile — Andante"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=scherzo) == (
        "Polka — Waltz — Polka"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=finale) == (
        "Tremolo — Prelude — Tremolo"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=week_spec(2)) == (
        "Prelude — Andante"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=week_spec(4)) == (
        "Prelude — Tremolo — Prelude"
    )
    assert guitar_movement_name(flat, ensemble="barrios", character="rally", form=week_spec(5)) == (
        "Prelude — Tremolo — Prelude"
    )


def test_barrios_region_row_reprises_from_the_third_part():
    row = ("preludio", "andante", "tremolo")
    assert _barrios_region_patterns(row, 2) == ["preludio", "andante"]
    assert _barrios_region_patterns(row, 3) == ["preludio", "andante", "preludio"]
    assert _barrios_region_patterns(row, 4) == ["preludio", "andante", "tremolo", "preludio"]
    assert _barrios_region_patterns(row, 5) == ["preludio", "andante", "tremolo", "andante", "preludio"]
    # One guest repeats between the two openings. There is no second guest to walk.
    slow = ("andante", "thumb_cantabile")
    assert _barrios_region_patterns(slow, 6) == ["andante", *["thumb_cantabile"] * 4, "andante"]


def _region_ids(ids: list[str], *, framed: bool) -> list[str]:
    epb = 8
    span = 16
    phrases: list[Phrase] = []
    sections: list[FormSection] = []
    patterns: list[str] = []
    kinds: dict[int, str] = {}
    bar = 0
    if framed:
        sections.append(FormSection(0, 4, "warmup", 0))
        phrases.append(Phrase(0, 4 * epb, (Run(0, 4 * epb, 60),)))
        patterns.append("pedal")
        kinds.update({index: "warmup" for index in range(4)})
        bar = 4
    for slot, pattern in enumerate(ids):
        start, end = bar, bar + span
        sections.append(FormSection(start, end, "phrase", slot))
        phrases.append(Phrase(start * epb, end * epb, (Run(start * epb, span * epb, 60),)))
        patterns.append(pattern)
        kinds.update({index: "phrase" for index in range(start, end)})
        bar = end
    if framed:
        sections.append(FormSection(bar, bar + 4, "cooldown", 0))
        phrases.append(Phrase(bar * epb, (bar + 4) * epb, (Run(bar * epb, 4 * epb, 60),)))
        patterns.append("pedal")
        kinds.update({index: "cooldown" for index in range(bar, bar + 4)})
        bar += 4
    ctx = _Ctx(
        melody=[60] * (bar * epb),
        raw=[60] * (bar * epb),
        chord_at={0: C},
        kind_at=kinds,
        band_at={index: "mf" for index in range(bar)},
        phrases=tuple(phrases),
        bars=bar,
        bpm=96,
        ensemble="barrios",
        mode="major",
        character="rally",
        character_at=None,
        sections=tuple(sections),
        rel_span=0.0,
        semitones=0,
        bass_low=40,
        bass_high=55,
        mid_low=48,
        mid_high=67,
        treble_floor=60,
        treble_top=84,
        ceiling=88,
        epb=epb,
        kind="4/4",
        strong=(0, 4),
        bar_beats=4.0,
    )
    return form_pattern_ids(ctx, patterns)


def test_a_uniform_barrios_row_names_the_headline_once():
    # Three regions of one id must not come back as that id repeated.
    assert _region_ids(["preludio", "preludio", "preludio"], framed=True) == ["preludio"]
    # Two different ids still name the row. An unframed score does not.
    assert _region_ids(["andante", "thumb_cantabile", "andante"], framed=True) == [
        "andante",
        "thumb_cantabile",
        "andante",
    ]
    assert _region_ids(["preludio", "andante", "tremolo"], framed=False) == ["preludio"]


def test_pattern_form_keeps_three_names_and_centers_a_longer_row():
    assert pattern_form(["preludio", "andante", "tremolo"], "barrios") == "Prelude — Andante — Tremolo"
    assert pattern_form(["preludio", "andante", "andante"], "barrios") == "Prelude — Andante"
    assert pattern_form(["preludio", "andante", "tremolo", "andante", "preludio"], "barrios") == (
        "Prelude — Tremolo — Prelude"
    )
    # The row ends on Andante, so the short title does not pretend it reprises.
    assert pattern_form(["preludio", "andante", "preludio", "andante"], "barrios") == "Prelude — Andante"


def test_villa_slow_and_six_eight_keep_their_body_and_show_the_contrast():
    slow = month_specs("guitar")[1]
    scherzo = month_specs("guitar")[2]
    assert (slow.meter.beats, slow.meter.beat_type, slow.bpm) == (3, 4, 72)
    assert (scherzo.meter.beats, scherzo.meter.beat_type, scherzo.bpm) == (6, 8, 120)
    flat = _bars([100.0] * 80)
    assert (
        guitar_movement_name(flat, ensemble="villa", character="calm", form=slow, framed=False)
        == "Chord Melody — Prelude — Chord Melody"
    )
    assert (
        guitar_movement_name(flat, ensemble="villa", character="rally", form=scherzo, framed=False)
        == "Arpeggio — Prelude — Arpeggio"
    )


def test_bach_slow_selloff_with_a_contrast_stays_sarabande():
    slow = month_specs("guitar")[1]
    wide = _bars([100 - index * 0.2 for index in range(80)])
    assert (
        guitar_movement_name(wide, ensemble="bach", character="selloff", form=slow, mode="minor", framed=False)
        == "Sarabande — Chaconne — Sarabande"
    )


def test_an_unknown_pattern_is_not_titled_etude():
    assert pattern_title("not-a-pattern", "classic") == ""
    assert pattern_title("study", "classic") == "Etude"


def test_span_manifest_reads_a_stored_dance_and_does_not_plan(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("render")

    monkeypatch.setattr("app.sonify.program.render", boom)
    movement = PreparedMovement(
        label="2",
        spec=month_specs("symphony")[1],
        bars=_bars([10.0, 11.0]),
        groups=None,
        rest_after=0,
    )
    assert (
        span_movement_name(movement, variant="guitar", span="1Y", index=1, stored="Gigue")
        == "Gigue"
    )
    assert span_movement_name(movement, variant="guitar", span="1Y", index=1, stored="") == ""
    assert span_movement_name(movement, variant="symphony", span="1M", index=1) == (
        movement_title("symphony", "1M", 1, movement.spec) or ""
    )


def _write_audio(folder: Path, name: str, payload: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"m4a")
    (folder / f"{Path(name).stem}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_cached_audio_returns_its_dance_without_rendering(tmp_path: Path):
    def exporter(*_args, **_kwargs):
        raise AssertionError("export")

    store = RecapStore(tmp_path, exporter)
    day = date(2026, 1, 20)
    bars = [Bar(10.0), Bar(11.0)]
    stem = store._stem("VIC", day, "guitar", len(bars), "barrios")
    payload = {
        "symbol": "VIC",
        "date": day.isoformat(),
        "variant": "guitar",
        "ensemble": "barrios",
        "durationSec": 1.0,
        "mapDurationSec": 1.0,
        "barCount": len(bars),
        "peaks": [0.2],
        "audio": f"{stem}.m4a",
        "closed": True,
        "movementName": "Tremolo",
    }
    _write_audio(tmp_path, f"{stem}.m4a", payload)
    asset = store.ensure("VIC", day, "guitar", bars, None, "barrios")
    assert asset.movement_name == "Tremolo"

    payload["movementName"] = ""
    _write_audio(tmp_path, f"{stem}.m4a", payload)
    assert store.ensure("VIC", day, "guitar", bars, None, "barrios").movement_name == ""


def test_cached_span_keeps_the_dance_written_beside_the_file(tmp_path: Path):
    store = RecapStore(tmp_path, lambda *_args, **_kwargs: None)
    fingerprint = "C-major-std-none-4-4-0-10.00-11.00-rhythm4--"
    stem = store._span_stem("VIC", "1Y", 3, "guitar", 2, fingerprint, "barrios")
    payload = {
        "audio": f"{stem}.m4a",
        "fingerprint": fingerprint,
        "durationSec": 2,
        "mapDurationSec": 2,
        "barCount": 2,
        "peaks": [],
        "movementName": "Sarabande",
    }
    _write_audio(tmp_path / "spans", f"{stem}.m4a", payload)
    asset = store.get_movement("VIC", "1Y", 3, "guitar", 2, fingerprint, "barrios")
    assert asset is not None
    assert asset.movement_name == "Sarabande"

    payload.pop("movementName")
    _write_audio(tmp_path / "spans", f"{stem}.m4a", payload)
    missing = store.get_movement("VIC", "1Y", 3, "guitar", 2, fingerprint, "barrios")
    assert missing is not None
    assert missing.movement_name == ""


def test_headline_matches_a_full_render():
    bars = _bars([100.0] * 40)
    skipped = _pattern_id(bars, skip=True, ensemble="barrios", character="volatile")
    written = _pattern_id(bars, skip=False, ensemble="barrios", character="volatile")
    assert skipped == written == "tremolo"
    assert pattern_title(written, "barrios") == "Tremolo"


def test_contrast_form_matches_a_full_render():
    from app.sonify.audio import _compose

    slow = month_specs("guitar")[1]
    wide = _bars([100 - index * 0.2 for index in range(80)])
    skipped = guitar_movement_name(wide, ensemble="bach", character="selloff", form=slow, mode="minor", framed=False)
    _score, written = _compose(
        "guitar",
        "bach",
        wide,
        character="selloff",
        form=slow,
        mode="minor",
        framed=False,
    )
    assert skipped == written == "Sarabande — Chaconne — Sarabande"
