"""Meters, frames, and parallel mode from the 1M plan."""

import xml.etree.ElementTree as ET

from app.sonify.chords import AFMAJ7, C, F, FM9, G, G9, JAZZ_VOICING_BY_NAME
from app.sonify.form import (
    FormSection,
    FormSpec,
    METER_128,
    METER_34,
    METER_44,
    METER_54,
    METER_64,
    METER_68,
    METER_78,
    compose_meter,
    liquidity_windows_for,
    plan_slots,
    swing_for,
)
from app.sonify.phrasing import Run, fills, written
from app.sonify.keys import C_KEY, EB_KEY, jazz_month_keys, movement_mode, signature_fifths
from app.sonify.model import Bar, NoteEvent
from app.sonify.musicxml import score_to_musicxml
from app.sonify.playback import span_candle_index
from app.sonify.render import render
from app.sonify.span import (
    SEASON_REST_SECONDS,
    YEAR_SEASON_REST_SECONDS,
    attach_frame,
    month_specs,
    plan_month,
    plan_quarter,
    quarter_specs,
    year_specs,
)


def _covered(notes: list) -> float:
    cursor = 0.0
    covered = 0.0
    for note in sorted(notes, key=lambda item: (item.beat, item.duration_beats)):
        end = note.beat + note.duration_beats
        if end <= cursor:
            continue
        covered += end - max(note.beat, cursor)
        cursor = max(cursor, end)
    return covered


def _clock(movements) -> float:
    return sum(
        movement.spec.eighths * 30.0 / movement.spec.bpm + movement.rest_after
        for movement in movements
    )


def _year_clock(variant: str) -> float:
    specs = tuple(attach_frame(spec, "1Y") for spec in year_specs(variant))
    total = 0.0
    for index, spec in enumerate(specs):
        total += spec.eighths * 30.0 / spec.bpm
        if index == 11:
            continue
        season = index // 3
        next_season = (index + 1) // 3
        total += YEAR_SEASON_REST_SECONDS if next_season != season else SEASON_REST_SECONDS
    return total


def test_piece_clocks_include_the_frame_and_the_rests() -> None:
    expected = {
        "symphony": (970.0, 1530.0, 2840.1),
        "jazz": (970.0, 1530.0, 2818.3),
        "minimalist": (968.0, 1529.0, 2840.8),
        "ambient": (970.0, 1530.0, 2818.3),
        "guitar": (970.0, 1530.0, 2840.1),
    }
    for variant, (month, quarter, year) in expected.items():
        assert abs(_clock(plan_month([1, 1, 1, 1], variant)) - month) < 1.5
        assert abs(_clock(plan_quarter([1, 1, 1], variant)) - quarter) < 1.5
        assert abs(_year_clock(variant) - year) < 1.5


def test_month_frame_sits_outside_the_body_and_the_liquidity_windows() -> None:
    spec = plan_month([1, 1, 1, 1])[0].spec
    assert spec.bars == 104
    assert spec.sections[0] == FormSection(0, 4, "warmup", 0)
    assert spec.sections[-1].kind == "cooldown"
    assert spec.sections[-1].start == 100
    assert all(start >= 4 for start, _length in liquidity_windows_for(spec))


def test_parallel_minor_signature_and_jazz_step() -> None:
    assert signature_fifths(C_KEY, "minor") == -3
    assert signature_fifths(EB_KEY, "minor") == -6
    assert movement_mode("selloff", "uptrend") == "minor"
    assert movement_mode("volatile", "downtrend") == "minor"
    assert movement_mode("volatile", "uptrend") == "major"
    assert movement_mode("rally", "downtrend") == "major"
    keys = jazz_month_keys(
        C_KEY,
        ("rally", "calm", "rally", "calm"),
        (("sideway", "sideway"),) * 4,
    )
    assert [key.name for key in keys] == ["C", "C", "D", "C"]
    assert swing_for("jazz", METER_44) is True
    assert swing_for("jazz", METER_128) is False


def test_home_pedal_opens_on_the_parallel_tonic_and_the_bridge_prefers_the_fourth() -> None:
    month = plan_month([1, 1, 1, 1], "jazz")
    head = month[0].spec
    slots = plan_slots(
        ("downtrend", "downtrend", "downtrend"),
        [60] * head.eighths,
        spec=head,
        mode="minor",
        home_pedal=True,
        character="selloff",
    )
    assert slots[0].section == "warmup"
    assert slots[0].chord.name == "Cm"
    assert slots[-1].chord.name == "Cm"
    assert JAZZ_VOICING_BY_NAME["Cm"].name == "Cm9"
    ballad = month[1].spec
    bridge = next(section for section in ballad.sections if section.bridge)
    bridged = plan_slots(
        ("sideway", "sideway", "sideway"),
        [65] * ballad.eighths,
        spec=ballad,
        mode="major",
        home_pedal=True,
    )
    opening = next(slot for slot in bridged if slot.start == bridge.start)
    assert opening.chord.name in ("F", "Fmaj7")


def test_span_playhead_holds_the_ends() -> None:
    assert span_candle_index(1.0, 10, 100.0, 10.0, 10.0) == 0
    assert span_candle_index(50.0, 10, 100.0, 10.0, 10.0) == 5
    assert span_candle_index(95.0, 10, 100.0, 10.0, 10.0) == 9
    assert span_candle_index(40.0, 10, 100.0, 0.0, 0.0) == 4


def test_symphony_frame_layers_the_strings() -> None:
    spec = FormSpec(
        12,
        96,
        (
            FormSection(0, 4, "warmup", 0),
            FormSection(4, 8, "phrase", 0),
            FormSection(8, 12, "cooldown", 0),
        ),
        (12,),
        meter=METER_44,
    )
    score = render(
        [Bar(100.0, 10.0, 100.0) for _ in range(12)],
        variant="symphony",
        form=spec,
        home_pedal=True,
    )
    lead = {note.bar for note in score.lead if note.midi is not None}
    assert 0 not in lead and 1 not in lead
    assert 2 in lead and 11 in lead
    assert 0 in {note.bar for note in score.low if note.midi is not None}
    assert any(wedge.kind == "crescendo" and wedge.bar == 2 for wedge in score.lead_wedges)
    assert any(wedge.kind == "diminuendo" and wedge.bar == 8 for wedge in score.lead_wedges)
    assert any(event.marking == "p" and event.bar == 2 for event in score.lead_dynamics)
    assert any(event.marking == "mp" and event.bar == 4 for event in score.lead_dynamics)
    assert any(event.marking == "p" and event.bar == 0 for event in score.dynamics)
    assert any(note.bar == 4 and note.beat == 0.0 and note.tie_stop for note in score.lead)
    frame = {note.bar for note in score.comp if note.midi is not None and (note.bar < 4 or note.bar >= 8)}
    assert frame == set()


def test_five_four_rest_off_the_grid_exports() -> None:
    with compose_meter(METER_54):
        gap = written(1, 5, None)
    assert [note.duration_beats for note in gap] == [2.0, 0.5]
    spec = FormSpec(
        8,
        96,
        (
            FormSection(0, 2, "warmup", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "cooldown", 0),
        ),
        (8,),
        meter=METER_54,
    )
    closes = [40.0 + (index % 5) for index in range(8)]
    score = render(
        [Bar(close, 50_000.0, close) for close in closes],
        variant="minimalist",
        form=spec,
    )
    score_to_musicxml(score)
    assert not any(note.midi is not None and (note.bar < 2 or note.bar >= 6) for note in score.comp)


def test_jazz_warmup_replaces_the_body_comping() -> None:
    spec = FormSpec(
        8,
        96,
        (
            FormSection(0, 2, "warmup", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "cooldown", 0),
        ),
        (8,),
        meter=METER_44,
    )
    score = render(
        [Bar(100.0 + index, 10_000.0, 100.0) for index in range(8)],
        variant="jazz",
        form=spec,
        home_pedal=True,
    )
    warm = [note for note in score.comp if note.bar < 2 and note.midi is not None]
    assert warm
    assert {note.duration_beats for note in warm} == {2.0}
    assert all(note.beat == 0.0 for note in warm)
    assert not any(note.midi is not None and note.bar >= 6 for note in score.comp)


def test_jazz_warmup_fills_three_four_and_twelve_eight() -> None:
    prices = [Bar(100.0 + index, 10_000.0, 100.0) for index in range(6)]
    for meter in (METER_34, METER_128):
        spec = FormSpec(
            6,
            96,
            (
                FormSection(0, 2, "warmup", 0),
                FormSection(2, 4, "phrase", 0),
                FormSection(4, 6, "cooldown", 0),
            ),
            (6,),
            meter=meter,
        )
        score = render(prices, variant="jazz", form=spec, home_pedal=True)
        for bar in (0, 1):
            hand = [note for note in score.comp if note.bar == bar and note.staff == 1]
            assert abs(_covered(hand) - meter.quarter_beats) < 1e-6
            assert any(note.midi is None for note in hand)
        score_to_musicxml(score)


def test_long_form_ambient_writes_its_meter_mode_and_frame() -> None:
    slow = FormSpec(
        6,
        72,
        (
            FormSection(0, 1, "warmup", 0),
            FormSection(1, 5, "phrase", 0),
            FormSection(5, 6, "cooldown", 0),
        ),
        (6,),
        meter=METER_64,
    )
    scherzo = FormSpec(
        6,
        108,
        (
            FormSection(0, 1, "warmup", 0),
            FormSection(1, 5, "phrase", 0),
            FormSection(5, 6, "cooldown", 0),
        ),
        (6,),
        meter=METER_34,
    )
    prices = [Bar(40.0, 10.0, 40.0) for _ in range(6)]
    slow_score = render(prices, variant="ambient", form=slow, mode="minor", home_pedal=True)
    assert (slow_score.beats, slow_score.beat_type, slow_score.bar_beats, slow_score.mode) == (
        6,
        4,
        6.0,
        "minor",
    )
    assert 0 in {note.bar for note in slow_score.lead if note.midi is not None}
    root = ET.fromstring(score_to_musicxml(slow_score))
    assert {node.text for node in root.iter("beats")} == {"6"}
    assert {node.text for node in root.iter("beat-type")} == {"4"}
    assert {node.text for node in root.iter("fifths")} == {"-3"}
    waltz = render(prices, variant="ambient", form=scherzo, mode="major", home_pedal=True)
    assert (waltz.beats, waltz.beat_type, waltz.bar_beats) == (3, 4, 3.0)
    day = render([Bar(80.0, 0.0, 80.0) for _ in range(30)], variant="ambient")
    assert day.bars == 34
    assert (day.beats, day.beat_type, day.bar_beats, day.mode) == (4, 4, 4.0, "major")


def test_five_four_whole_rest_has_no_type() -> None:
    spec = FormSpec(
        2,
        96,
        (FormSection(0, 2, "phrase", 0),),
        (2,),
        meter=METER_54,
    )
    score = render(
        [Bar(40.0, 0.0, 40.0), Bar(40.0, 0.0, 40.0)],
        variant="minimalist",
        form=spec,
    )
    root = ET.fromstring(score_to_musicxml(score))
    whole = [
        note
        for note in root.iter("note")
        if any(child.tag == "rest" and child.get("measure") == "yes" for child in note)
    ]
    assert whole
    assert all(child.tag != "type" for note in whole for child in note)
    fifths = {node.text for node in root.iter("fifths")}
    assert "5" in {node.text for node in root.iter("beats")}
    assert fifths == {"0"}


def test_jazz_bridge_is_only_the_documented_phrases_and_cadences_on_g() -> None:
    month = month_specs("jazz")
    assert [any(section.bridge for section in spec.sections) for spec in month] == [
        True,
        True,
        False,
        True,
    ]
    quarter = quarter_specs("jazz")
    assert [any(section.bridge for section in spec.sections) for spec in quarter] == [
        False,
        True,
        False,
    ]
    year = year_specs("jazz")
    assert any(section.bridge for section in year[1].sections)
    assert not any(section.bridge for section in year[0].sections)
    assert not any(section.bridge for section in year[2].sections)
    assert not any(section.bridge for section in year[-1].sections)

    ballad = plan_month([1, 1, 1, 1], "jazz")[1].spec
    bridge = next(section for section in ballad.sections if section.bridge)
    pitches = [60] * ballad.eighths
    epb = ballad.meter.eighths_per_bar
    for bar in range(bridge.end - 2, bridge.end):
        pitches[bar * epb : (bar + 1) * epb] = [71] * epb
    bridged = plan_slots(
        ("sideway", "sideway", "sideway"),
        pitches,
        spec=ballad,
        mode="major",
        home_pedal=True,
        harmonic_bridge=True,
    )
    at: dict[int, str] = {}
    for slot in bridged:
        for bar in slot.bars():
            at[bar] = slot.chord.name
    assert at[bridge.end - 2] in ("G", "G7")
    assert at[bridge.end - 1] in ("G", "G7")
    assert at[bridge.end] in ("C", "Cmaj7")


def test_minor_walking_keeps_b_flat_off_the_dominant() -> None:
    from app.sonify.jazz import _walking_bass_bar
    from app.sonify.quantize import C_NATURAL_MINOR_PCS, scale_from_classes

    scale = scale_from_classes(33, 60, C_NATURAL_MINOR_PCS)
    with compose_meter(METER_44):
        home = _walking_bass_bar(FM9, AFMAJ7, "mf", 0, "phrase", scale, mode="minor")
        dominant = _walking_bass_bar(G9, AFMAJ7, "mf", 0, "phrase", scale, mode="minor")
    assert home[-1].midi % 12 == 10
    assert dominant[-1].midi % 12 == 11


def test_ambient_middle_drone_is_one_tonic_note() -> None:
    spec = FormSpec(
        12,
        72,
        (
            FormSection(0, 2, "warmup", 0),
            FormSection(2, 4, "phrase", 0),
            FormSection(4, 8, "phrase", 1, True),
            FormSection(8, 10, "phrase", 2),
            FormSection(10, 12, "cooldown", 0),
        ),
        (12,),
    )
    score = render(
        [Bar(40.0, 10.0, 40.0) for _ in range(12)],
        variant="ambient",
        form=spec,
        home_pedal=True,
    )
    middle = [note.midi for note in score.low if note.midi is not None and 4 <= note.bar < 8]
    tonic = next(slot.chord.bass_midi for slot in score.slots if slot.start <= 2 < slot.start + slot.length)
    assert middle
    assert set(middle) == {tonic}


def test_minimalist_pad_covers_only_the_frame() -> None:
    from app.sonify.model import ChordSlot, Score
    from app.sonify.movement_frame import apply_span_frame

    slots = (
        ChordSlot(0, 2, C, "sideway", "warmup"),
        ChordSlot(2, 2, F, "sideway", "phrase"),
        ChordSlot(4, 2, G, "sideway", "phrase"),
        ChordSlot(6, 2, C, "sideway", "cooldown"),
    )
    body = tuple(
        NoteEvent(bar=bar, beat=0.0, midi=60, duration_beats=4.0, voice=1) for bar in range(2, 6)
    )
    score = Score(
        title="pad",
        bpm=96,
        bars=8,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=slots,
        high=(),
        lead=(),
        support=body,
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
        variant="minimalist",
    )
    spec = FormSpec(
        8,
        96,
        (
            FormSection(0, 2, "warmup", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "cooldown", 0),
        ),
        (8,),
    )
    framed = apply_span_frame(score, spec)
    warm = {note.midi for note in framed.support if note.bar < 2 and note.midi is not None}
    body_midis = {note.midi for note in framed.support if 2 <= note.bar < 6 and note.midi is not None}
    cool = {note.midi for note in framed.support if note.bar >= 6 and note.midi is not None}
    assert warm == {53}
    assert body_midis == {60}
    assert cool == {55}


def test_minimalist_cooldown_honors_the_outro_override() -> None:
    spec = FormSpec(
        8,
        96,
        (
            FormSection(0, 2, "intro", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "cooldown", 0),
        ),
        (8,),
    )
    slots = plan_slots(
        ("downtrend",),
        [60] * spec.eighths,
        spec=spec,
        outro_override="major",
        home_pedal=False,
    )
    assert slots[-1].section == "cooldown"
    assert slots[-1].chord.name in ("C", "Cmaj7")


def test_six_eight_fill_starts_on_the_second_beat() -> None:
    with compose_meter(METER_68):
        notes = fills([(Run(0, 6, 76), "violin")], {0: C})
    assert [start % 6 for start, _length, _midi in notes] == [3, 4, 5]


def test_seven_eight_arp_accents_the_strong_eighths() -> None:
    spec = FormSpec(
        8,
        120,
        (
            FormSection(0, 2, "intro", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "outro", 0),
        ),
        (8,),
        meter=METER_78,
    )
    closes = [10.0 + index * 12 for index in range(8)]
    score = render(
        [Bar(close, 20_000.0, close) for close in closes],
        variant="minimalist",
        form=spec,
    )
    accents = {note.beat for note in score.lead if note.bar == 7 and note.accent}
    assert accents == {0.0, 1.0, 2.0}


def test_seven_eight_sub_bass_and_driving_pulse() -> None:
    from app.sonify.minimalist import _sub_bass_part, _synth_pulse_part

    with compose_meter(METER_78):
        bass = _sub_bass_part({0: C}, {0: "f"}, 1)
        pulse = [note for note in _synth_pulse_part({0: C}, {0: "f"}, 1) if note.staff == 1]
    assert [(note.beat, note.duration_beats) for note in bass] == [(0.0, 1.0), (1.0, 1.0), (2.0, 1.5)]
    sounding = [note for note in pulse if note.midi is not None]
    assert len(sounding) == 14
    assert {note.beat for note in sounding if note.accent} == {0.0, 1.0, 2.0}


def test_ballad_walking_picks_up_into_each_half() -> None:
    from app.sonify.jazz import _walking_bass_bar
    from app.sonify.quantize import c_major_scale

    with compose_meter(METER_128):
        notes = _walking_bass_bar(C, G, "mf", 0, "phrase", c_major_scale(33, 60))
    assert [note.beat for note in notes] == [0.0, 1.5, 2.5, 3.0, 4.5, 5.5]


def test_flute_harmony_keeps_the_minor_third() -> None:
    from app.sonify.chords import CM, FM
    from app.sonify.quantize import c_natural_minor_scale, leading_scale
    from app.sonify.render import flute_harmony_pitch

    scale = c_natural_minor_scale()
    assert flute_harmony_pitch(60, CM, scale) % 12 == 3
    assert flute_harmony_pitch(65, FM, scale) % 12 == 8
    assert flute_harmony_pitch(67, G, leading_scale(scale)) % 12 == 11


def test_rhodes_yields_the_bar_to_a_cadence_fill() -> None:
    from app.sonify.jazz import _before_fill

    with compose_meter(METER_128):
        assert _before_fill(0, 4.5, 1.5, {0: 9}) is None
        assert _before_fill(0, 1.5, 1.5, {0: 6}) == 1.5
    with compose_meter(METER_34):
        assert _before_fill(0, 0.0, 1.5, {0: 2}) == 1.0
        assert _before_fill(0, 1.5, 0.5, {0: 2}) is None


def test_frame_keeps_body_bass_letters_and_rests_the_glass() -> None:
    from app.sonify.model import ChordSlot, DynamicEvent, Score
    from app.sonify.movement_frame import apply_span_frame

    slots = (
        ChordSlot(0, 2, C, "sideway", "warmup"),
        ChordSlot(2, 4, C, "sideway", "phrase"),
        ChordSlot(6, 2, C, "sideway", "cooldown"),
    )
    spec = FormSpec(
        8,
        96,
        (
            FormSection(0, 2, "warmup", 0),
            FormSection(2, 6, "phrase", 0),
            FormSection(6, 8, "cooldown", 0),
        ),
        (8,),
    )
    bass = Score(
        title="bass",
        bpm=96,
        bars=8,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=slots,
        high=(),
        lead=(),
        support=(),
        comp=(),
        low=(),
        dynamics=(DynamicEvent(3, "f", 80),),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="symphony",
    )
    framed = apply_span_frame(bass, spec)
    assert [(event.bar, event.marking) for event in framed.dynamics] == [
        (0, "p"),
        (2, "mp"),
        (3, "f"),
        (7, "ppp"),
    ]

    glass = Score(
        title="glass",
        bpm=96,
        bars=8,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=slots,
        high=(),
        lead=(NoteEvent(bar=2, beat=0.0, midi=72, duration_beats=1.0, voice=1),),
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
        variant="ambient",
    )
    rested = apply_span_frame(glass, spec)
    assert [wedge.kind for wedge in rested.lead_wedges] == ["crescendo", "stop"]
    assert all(event.marking != "ppp" for event in rested.lead_dynamics)


def test_six_eight_and_three_four_bass_patterns() -> None:
    from app.sonify.render import _bass_pattern

    with compose_meter(METER_68):
        assert _bass_pattern("p") == ((0, 6, 0),)
        assert _bass_pattern("mp")[0][0:2] == (0, 3)
    with compose_meter(METER_34):
        assert _bass_pattern("p") == ((0, 6, 0),)
        assert _bass_pattern("mf")[0] == (0, 2, 0)


def _pedal(spec: FormSpec, kind: str) -> int:
    section = next((item for item in spec.sections if item.kind == kind), None)
    if section is None:
        return 0
    return section.end - section.start


def test_pedal_table_matches_the_market_rhythm_plan() -> None:
    from app.sonify.span import month_specs, quarter_specs, week_spec, year_specs

    week = week_spec(5)
    assert week.bars == 160
    assert _pedal(week, "intro") == 4
    assert _pedal(week, "outro") == 4
    for variant in ("symphony", "jazz", "ambient"):
        month = month_specs(variant)
        assert _pedal(month[0], "intro") == 4
        assert _pedal(month[2], "intro") == 4
        assert _pedal(month[3], "intro") == 4
        assert _pedal(month[0], "outro") == 4
        assert _pedal(month[1], "outro") == 0
        assert _pedal(month[2], "outro") == 4
        assert _pedal(month[3], "outro") == 8
        quarter = quarter_specs(variant)
        assert _pedal(quarter[0], "intro") == 4
        assert _pedal(quarter[1], "intro") == 4
        assert _pedal(quarter[2], "intro") == 4
        assert _pedal(quarter[0], "outro") == 4
        assert _pedal(quarter[2], "outro") == 8
    assert _pedal(quarter_specs("symphony")[1], "outro") == 4
    assert _pedal(quarter_specs("jazz")[1], "outro") == 2
    assert _pedal(quarter_specs("ambient")[1], "outro") == 2
    assert _pedal(quarter_specs("minimalist")[1], "outro") == 4
    minimalist = quarter_specs("minimalist")
    assert _pedal(minimalist[0], "intro") == 3
    assert _pedal(minimalist[0], "outro") == 4
    assert _pedal(minimalist[2], "intro") == 4
    assert _pedal(minimalist[2], "outro") == 10
    year = year_specs("symphony")
    assert year[2].meter.beats == 3 and year[2].bars == 111
    assert _pedal(year[2], "outro") == 6
    assert _pedal(year[1], "outro") == 4
    assert _pedal(year_specs("jazz")[1], "outro") == 2
    assert _pedal(year_specs("ambient")[1], "outro") == 2
    assert _pedal(year_specs("minimalist")[2], "outro") == 6
    assert _pedal(year[-1], "outro") == 8
    scherzo = month_specs("symphony")[2]
    assert any(section.trio for section in scherzo.sections)
    framed = attach_frame(scherzo, "1M")
    assert any(section.trio for section in framed.sections)
    assert not any(section.trio for section in month_specs("symphony")[1].sections)
    phrases = [
        section
        for section in quarter_specs("symphony")[2].sections
        if section.kind == "phrase"
    ]
    assert phrases[-1].end == next(
        section.start for section in quarter_specs("symphony")[2].sections if section.kind == "outro"
    )


def test_gap_bridge_stays_inside_the_hose_band() -> None:
    from app.sonify.groove import gap_direction

    assert gap_direction(100, 101) == "up"
    assert gap_direction(100, 99) == "down"
    assert gap_direction(100, 100.5) is None
    assert gap_direction(100, 107) is None


def test_dynamic_frame_attacks_on_a_fast_rally_and_stays_still_when_calm() -> None:
    from app.sonify.form import ChordSlot
    from app.sonify.model import Score
    from app.sonify.movement_frame import apply_span_frame

    slots = (
        ChordSlot(0, 4, C, "uptrend", "warmup"),
        ChordSlot(4, 4, F, "uptrend", "phrase"),
        ChordSlot(8, 4, C, "uptrend", "cooldown"),
    )
    body = tuple(
        NoteEvent(bar=bar, beat=0.0, midi=60, duration_beats=4.0, voice=1) for bar in range(4, 8)
    )
    spec = FormSpec(
        12,
        96,
        (
            FormSection(0, 4, "warmup", 0),
            FormSection(4, 8, "phrase", 0),
            FormSection(8, 12, "cooldown", 0),
        ),
        (12,),
    )

    def score(variant: str) -> Score:
        return Score(
            title="frame",
            bpm=96,
            bars=12,
            regimes=("uptrend", "uptrend", "uptrend"),
            regime_samples=None,
            slots=slots,
            high=(),
            lead=body,
            support=body,
            comp=(),
            low=body,
            dynamics=(),
            harmonies=(),
            liquidity=(),
            phrases=(),
            lead_wedges=(),
            support_wedges=(),
            lead_dynamics=(),
            support_dynamics=(),
            variant=variant,  # type: ignore[arg-type]
        )

    rally = apply_span_frame(score("symphony"), spec, "rally")
    assert any(note.midi is not None and note.bar < 4 for note in rally.comp)
    for bar in range(4):
        attacks = [
            note
            for note in rally.low
            if note.bar == bar and note.midi is not None and not note.tie_stop
        ]
        assert len(attacks) > 1
    calm = apply_span_frame(score("symphony"), spec, "calm")
    assert all(note.midi is None or note.bar >= 4 for note in calm.comp if note.bar < 4)
    jazz = apply_span_frame(score("jazz"), spec, "rally")
    assert any(note.midi is not None and 8 <= note.bar < 10 for note in jazz.comp)
    assert all(note.midi is None for note in jazz.comp if note.bar >= 10)
    minimal = apply_span_frame(score("minimalist"), spec, "volatile")
    assert any(note.midi is not None and note.bar < 4 for note in minimal.lead)
    assert any(note.midi is not None and 8 <= note.bar < 10 for note in minimal.lead)


def test_caesura_belongs_only_to_a_slow_bridge() -> None:
    from app.sonify.groove import build_groove

    ballad = month_specs("jazz")[1]
    fast = month_specs("jazz")[0]
    slow = build_groove(ballad, [(0, ballad.bars)], ["mf"], "jazz", "calm")
    quick = build_groove(fast, [(0, fast.bars)], ["mf"], "jazz", "rally")
    assert any(item.caesura for item in slow.values())
    assert not any(item.caesura for item in quick.values())


def test_jazz_compound_meters_take_half_feel_and_a_caesura() -> None:
    from app.sonify.groove import BarGroove, compose_groove
    from app.sonify.jazz import _before_fill, _walking_bass_bar

    scale = tuple(range(36, 72))
    with compose_meter(METER_34), compose_groove({0: BarGroove(half=True), 1: BarGroove(caesura=True)}):
        thinned = _walking_bass_bar(C, G, "mf", 0, "phrase", scale)
        assert [note.beat for note in thinned] == [0.0, 2.0]
        breath = _walking_bass_bar(C, G, "mf", 1, "phrase", scale)
        sounding = [note for note in breath if note.midi is not None]
        assert sounding
        assert all(note.beat + note.duration_beats <= 1.5 + 1e-6 for note in sounding)
        assert sum(note.duration_beats for note in breath) == 3
    with compose_meter(METER_128), compose_groove(
        {0: BarGroove(trio_thin=True), 1: BarGroove(caesura=True)}
    ):
        ballad = _walking_bass_bar(C, G, "f", 0, "phrase", scale)
        assert [note.beat for note in ballad] == [0.0, 3.0]
        rested = _walking_bass_bar(C, G, "p", 1, "phrase", scale)
        assert any(note.midi is None and note.beat == 3 for note in rested)
        assert sum(note.duration_beats for note in rested) == 6
    from app.sonify.render import _bass_bar

    with compose_meter(METER_68), compose_groove({0: BarGroove(half=True, caesura=True)}):
        held = _bass_bar(C, "mp", 0)
        assert any(note.midi is None and note.beat == 1.5 for note in held)
        assert sum(note.duration_beats for note in held) == 3
        assert all(
            note.beat + note.duration_beats <= 1.5 + 1e-6
            for note in held
            if note.midi is not None
        )
    with compose_meter(METER_44):
        assert _before_fill(0, 3.5, 0.5, {0: 4}) is None
        assert _before_fill(0, 0.0, 0.5, {0: 4}) == 0.5


def test_volatile_straight_bass_is_tresillo_and_jazz_stays_in_swing() -> None:
    from app.sonify.form import swing_for
    from app.sonify.groove import BarGroove, compose_groove
    from app.sonify.render import _bass_pattern

    with compose_meter(METER_44), compose_groove({0: BarGroove(tresillo=True)}):
        assert [start for start, _length, _interval in _bass_pattern("mf", 0)] == [0, 3, 6]
    assert swing_for("jazz", METER_44)
    assert not swing_for("symphony", METER_44)


def test_calm_week_chambers_the_middle_sixteen_bars() -> None:
    from app.sonify.groove import build_groove
    from app.sonify.span import week_spec

    week = week_spec(1)
    plan = build_groove(week, [(0, week.bars)], ["f"], "symphony", "calm")
    assert all(plan[bar].chamber and plan[bar].half for bar in range(8, 24))
    assert not any(plan[bar].chamber for bar in (0, 7, 24, 31))


def test_minimalist_slow_movement_has_a_caesura_bar() -> None:
    from app.sonify.groove import build_groove

    slow = month_specs("minimalist")[1]
    assert any(section.bridge for section in slow.sections)
    plan = build_groove(slow, [(0, slow.bars)], ["mf"], "minimalist", "calm")
    assert any(item.caesura for item in plan.values())


def test_bear_bounce_downbeat_requires_an_uptrend() -> None:
    from app.sonify.form import plan_markov_chords
    from app.sonify.quantize import c_natural_minor_scale

    spec = FormSpec(
        4,
        120,
        (FormSection(0, 4, "phrase", 0, False, True),),
        (4,),
        meter=METER_34,
    )
    pitches = [63, 67, 70] * 8
    scale = c_natural_minor_scale()
    rising = plan_markov_chords(("uptrend",), pitches, scale, spec, mode="minor")
    flat = plan_markov_chords(("sideway",), pitches, scale, spec, mode="minor")
    assert rising[0].name in ("Eb", "Ebmaj7")
    assert flat[0].name not in ("Eb", "Ebmaj7")


def test_daily_coda_prefers_subdominant_then_dominant() -> None:
    from app.sonify.form import DAILY_ENSEMBLE_SPEC, c_major_scale

    spec = DAILY_ENSEMBLE_SPEC
    epb = spec.meter.eighths_per_bar
    pitches = [60] * (spec.bars * epb)
    for bar in (28, 29):
        pitches[bar * epb : (bar + 1) * epb] = [65] * epb
    for bar in (30, 31):
        pitches[bar * epb : (bar + 1) * epb] = [67] * epb
    slots = plan_slots(("sideway", "sideway", "sideway"), pitches, c_major_scale(), spec)
    by_bar = {bar: slot.chord.name for slot in slots for bar in slot.bars()}
    assert by_bar[28] in ("F", "Fmaj7")
    assert by_bar[29] in ("F", "Fmaj7")
    assert by_bar[30] in ("G", "G7", "G9")
    assert by_bar[31] in ("G", "G7", "G9")
    assert by_bar[32] in ("C", "Cmaj7")


def test_week_gap_lead_reaches_the_hold_bar_and_plan_slots() -> None:
    from app.sonify.form import c_major_scale
    from app.sonify.span import prepare_week

    first = [Bar(100.0) for _ in range(8)]
    second = [Bar(100.0) for _ in range(8)]
    rising = prepare_week([first, second], openings=[100.0, 101.0])[0]
    assert rising.gap_leads is not None
    assert rising.gap_leads[31] == "up"
    assert rising.gap_leads[63] is None
    wide = prepare_week([first, second], openings=[100.0, 107.0])[0]
    assert wide.gap_leads is not None
    assert wide.gap_leads[31] is None
    tiny = prepare_week([first, second], openings=[100.0, 100.4])[0]
    assert tiny.gap_leads is not None
    assert tiny.gap_leads[31] is None

    epb = rising.spec.meter.eighths_per_bar
    pitches = [60] * (rising.spec.bars * epb)
    # The hold is a two-bar chord. B on bar 31 alone still spells Cmaj7 with the C before it.
    for bar in (30, 31):
        pitches[bar * epb : (bar + 1) * epb] = [71] * epb

    def chord_at(leads: tuple[str | None, ...] | None) -> str:
        slots = plan_slots(
            ("sideway", "sideway"),
            pitches,
            c_major_scale(),
            rising.spec,
            gap_leads=leads,
        )
        return next(slot.chord.name for slot in slots if 31 in slot.bars())

    assert chord_at(rising.gap_leads) == "G7"
    assert chord_at(tiny.gap_leads) == "G"


def test_chamber_bar_drops_the_symphony_right_hand() -> None:
    from app.sonify.form import ChordSlot
    from app.sonify.groove import BarGroove, compose_groove
    from app.sonify.render import _right_hand

    with compose_meter(METER_44), compose_groove({0: BarGroove(chamber=True)}):
        notes, *_ = _right_hand((ChordSlot(0, 1, C, "sideway", "phrase"),), [])
    assert not any(note.midi is not None for note in notes)
