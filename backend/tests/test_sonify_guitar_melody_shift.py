"""Octave-shift lock for a price impulse that crosses guitar phrases.

Impulses are plain objects with ``start`` and ``target``. The tests do not
import ``PriceImpulse``; that dataclass is added on another branch.
"""

from app.sonify.chords import C
from app.sonify.form import DAILY_ENSEMBLE_SPEC, ChordSlot, FormSection
from app.sonify.guitar import _place_melody, render_guitar_score
from app.sonify.guitar_scales import SCALE_SIXTEENTH_MIN_BPM, detect_price_impulses
from app.sonify.model import Bar, Phrase, Run, Score
from app.sonify.render import render


class _Impulse:
    def __init__(self, start: int, target: int) -> None:
        self.start = start
        self.target = target


def _phrase(start: int, notes: list[int]) -> Phrase:
    runs = tuple(Run(start + index, 1, note) for index, note in enumerate(notes))
    return Phrase(start, start + len(notes), runs)


def _phrases(parts: list[list[int]]) -> tuple[list[int], tuple[Phrase, ...]]:
    pitches: list[int] = []
    phrases: list[Phrase] = []
    cursor = 0
    for notes in parts:
        phrases.append(_phrase(cursor, notes))
        pitches.extend(notes)
        cursor += len(notes)
    return pitches, tuple(phrases)


def _placed(parts: list[list[int]], impulse: _Impulse | None = None, raw: list[int] | None = None) -> list[int]:
    pitches, phrases = _phrases(parts)
    impulses = () if impulse is None else (impulse,)
    return _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=pitches if raw is None else raw,
        impulses=impulses,
    )


def _score_kwargs(pitches: list[int], **extra):
    bars = max(1, len(pitches) // 8)
    slots = tuple(ChordSlot(bar, 1, C, "sideway", "phrase") for bar in range(bars))
    phrase = _phrase(0, pitches)
    body = dict(
        title="Guitar",
        chosen=(),
        sample_indexes=None,
        slots=slots,
        pitches=list(pitches),
        phrases=(phrase,),
        dynamics=(),
        bands=["mf"] * bars,
        band_at={bar: "mf" for bar in range(bars)},
        musical_bars=bars,
        total_eighths=len(pitches),
        bpm=88,
        ensemble="classic",
        harmonies=(),
    )
    body.update(extra)
    return body


def test_scale_stub_exposes_the_bpm_floor_and_an_empty_detector() -> None:
    assert SCALE_SIXTEENTH_MIN_BPM == 88
    assert detect_price_impulses([60, 62], (0,), epb=8, strong_eighths=(0, 4)) == ()


def test_render_without_raw_pitches_does_not_detect_on_quantized_pitches(monkeypatch) -> None:
    calls: list[tuple] = []

    def detect(*args, **kwargs):
        calls.append((args, kwargs))
        return (_Impulse(0, 1),)

    monkeypatch.setattr("app.sonify.guitar_scales.detect_price_impulses", detect)
    seen: dict = {}

    def voices(**kwargs):
        seen.update(kwargs)
        return [], [], [], 2

    monkeypatch.setattr("app.sonify.guitar_patterns.render_patterned_voices", voices)
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    render_guitar_score(**_score_kwargs(pitches))
    assert calls == []
    assert seen["impulses"] == ()
    assert seen["raw_pitches"] == pitches


def test_direct_raw_pitches_are_forwarded_not_the_quantized_series(monkeypatch) -> None:
    detected: dict = {}

    def detect(raw, section_starts, *, epb, strong_eighths, pedal_bars=frozenset()):
        detected["raw"] = list(raw)
        detected["starts"] = section_starts
        detected["epb"] = epb
        detected["strong"] = strong_eighths
        detected["pedal"] = pedal_bars
        detected["calls"] = detected.get("calls", 0) + 1
        return ()

    monkeypatch.setattr("app.sonify.guitar_scales.detect_price_impulses", detect)
    seen: dict = {}

    def voices(**kwargs):
        seen["raw"] = list(kwargs["raw_pitches"])
        seen["impulses"] = kwargs["impulses"]
        return [], [], [], 2

    monkeypatch.setattr("app.sonify.guitar_patterns.render_patterned_voices", voices)
    raw = [60, 62, 64, 65, 67, 69, 71, 72]
    quantized = [67, 67, 64, 65, 67, 69, 71, 72]
    slots = (
        ChordSlot(0, 1, C, "sideway", "intro"),
        ChordSlot(1, 1, C, "sideway", "phrase"),
    )
    render_guitar_score(
        **_score_kwargs(
            quantized,
            slots=slots,
            musical_bars=2,
            bands=["mf", "mf"],
            band_at={0: "mf", 1: "mf"},
            raw_pitches=raw,
            sections=(FormSection(0, 1, "intro", 0), FormSection(1, 2, "phrase", 0)),
        )
    )
    assert detected["calls"] == 1
    assert detected["raw"] == raw
    assert detected["raw"] != quantized
    assert detected["starts"] == (0, 8)
    assert detected["epb"] == 8
    assert detected["strong"] == (0, 4)
    assert detected["pedal"] == frozenset({0})
    assert seen["raw"] == raw
    assert seen["impulses"] == ()


def test_supplied_impulses_skip_a_second_detection(monkeypatch) -> None:
    calls: list[tuple] = []

    def detect(*args, **kwargs):
        calls.append(args)
        return ()

    monkeypatch.setattr("app.sonify.guitar_scales.detect_price_impulses", detect)
    seen: dict = {}

    def voices(**kwargs):
        seen["raw"] = list(kwargs["raw_pitches"])
        seen["impulses"] = kwargs["impulses"]
        return [], [], [], 2

    monkeypatch.setattr("app.sonify.guitar_patterns.render_patterned_voices", voices)
    raw = [60, 62, 64, 65]
    quantized = [67, 67, 64, 65]
    impulse = _Impulse(0, 2)
    render_guitar_score(**_score_kwargs(quantized, raw_pitches=raw, impulses=(impulse,)))
    assert calls == []
    assert seen["raw"] == raw
    assert seen["impulses"] == (impulse,)


def test_empty_impulses_leave_the_melody_from_choose_shifts() -> None:
    parts = [[48, 50, 52, 53], [64, 65, 67, 69], [84, 86, 88, 89]]
    pitches, phrases = _phrases(parts)
    baseline = _place_melody(pitches, phrases, 59, 81, {}, "major")
    assert _place_melody(pitches, phrases, 59, 81, {}, "major", impulses=()) == baseline
    assert _place_melody(pitches, phrases, 59, 81, {}, "major", raw_pitches=None, impulses=None) == baseline
    # The same pitches do move once an impulse is actually supplied.
    moved = _placed(parts, _Impulse(1, 9))
    assert moved != baseline
    assert moved[4:8] == [76, 77, 79, 81]


def test_impulse_ending_inside_p1_does_not_octave_jump_at_the_entry() -> None:
    """P1's shift is -12. Sharing it back onto P0 would drop the entry an octave."""
    parts = [[60, 62, 62, 62], [84, 86, 88, 89]]
    pitches, phrases = _phrases(parts)
    # target 5 sits inside P1 (eighths 4..8), before that phrase's last eighth.
    placed = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=pitches,
        impulses=(_Impulse(2, 5),),
    )
    assert placed[1] == 62
    assert placed[2] == 62
    assert placed[2] - placed[1] == 0
    # The rejected shared shift would have been pitches[2] - 12 == 50.
    assert abs((pitches[2] - 12) - placed[1]) >= 12


def test_shared_shift_failure_then_p2_one_shift_and_conditional_restore() -> None:
    """P0 | P1 | P2. P2's own shift is 0, but the phrase was compressed.

    B.1 (P1's +12) fails the exit. Restoring P2's shift on the impulse slice
    is kept only when (P1.end - 1, P2.start) is seam_ok.
    """
    parts = [[60, 62, 64, 65], [48, 50, 52, 53], [60, 62, 64, 65, 84]]
    pitches, phrases = _phrases(parts)
    # Impulse eighths inside P2 are indexes 8..10. Index 7 is P1's last note.
    impulse = _Impulse(5, 10)
    baseline = _place_melody(pitches, phrases, 59, 81, {}, "major")
    assert baseline[4:8] == [60, 62, 64, 65]
    assert baseline[8:13] == [59, 60, 62, 64, 81]

    held = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=pitches,
        impulses=(impulse,),
    )
    # Cut under shift 0 is placed 65 -> 60 (step -5) against raw +7, so seam_ok fails.
    # The failed exit therefore does not install the pure shift; the slice stays compressed.
    assert held[8:11] == [59, 60, 62]
    assert held[8:11] != pitches[8:11]
    assert held[5] - held[4] == 2

    raw = pitches[:]
    raw[8] = raw[7] - 5
    raw[11] = raw[10]
    restored = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=raw,
        impulses=(impulse,),
    )
    # (P1.end - 1, P2.start) now matches, so P2's impulse eighths share shift 0.
    assert restored[8:11] == [60, 62, 64]
    assert len({restored[index] - pitches[index] for index in range(8, 11)}) == 1
    assert restored[11:] == baseline[11:]


def test_three_phrase_impulse_checks_the_exit_in_the_target_phrase() -> None:
    """The far side of P1 is not the exit. The exit is (target, target + 1) inside P2."""
    parts = [[48, 50, 52, 53], [64, 65, 67, 69], [84, 86, 88, 89]]
    pitches, phrases = _phrases(parts)
    impulse = _Impulse(1, 9)
    baseline = _place_melody(pitches, phrases, 59, 81, {}, "major")
    assert baseline[4:8] == [64, 65, 67, 69]
    assert baseline[8:12] == [72, 74, 76, 77]

    raw = pitches[:]
    # Placed step across P1|P2 after propagating +12 onto the slice is -2.
    raw[8] = raw[7] - 2
    blocked = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=raw,
        impulses=(impulse,),
    )
    # P1 still takes the propagated shift: the intermediate phrase end was not an exit test.
    assert blocked[4:8] == [76, 77, 79, 81]
    # Real exit (9, 10) does not match raw +2, and P2's own shift does not clear the cut,
    # so P2 keeps the shift _choose_shifts chose.
    assert blocked[8:12] == [72, 74, 76, 77]
    # P1's new ending against P2's own start is not seam_ok, and P1 moved anyway.
    assert blocked[8] - blocked[7] != raw[8] - raw[7]

    raw[10] = raw[9] - 5
    opened = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=raw,
        impulses=(impulse,),
    )
    assert opened[4:8] == [76, 77, 79, 81]
    # One shift on the impulse eighths inside P2; the eighth after target stays put.
    assert opened[8:10] == [79, 81]
    assert len({opened[index] - pitches[index] for index in (8, 9)}) == 1
    assert opened[10:12] == baseline[10:12]


def test_impulse_starting_at_p0_checks_the_previous_phrase() -> None:
    parts = [[60, 62, 64, 65], [65, 67, 69, 71], [84, 86, 88, 89]]
    pitches, phrases = _phrases(parts)
    # P0 starts at eighth 4. A previous phrase exists, so the entry is (3, 4).
    placed = _place_melody(
        pitches,
        phrases,
        59,
        81,
        {},
        "major",
        raw_pitches=pitches,
        impulses=(_Impulse(4, 9),),
    )
    assert phrases[1].start == 4
    assert placed[3] == 65
    assert placed[4] == 65
    assert placed[4] - placed[3] == 0
    # Sharing P2's -12 shift would move eighth 4; folding that slice still leaves 59.
    assert placed[4] != 59
    assert placed[4] != pitches[4] - 12


def test_render_detects_once_on_raw_pitches_before_quantize(monkeypatch) -> None:
    import sys

    from app.sonify.phrasing import quantize_strong_beats as real_quantize

    detected: dict = {}

    def detect(raw, section_starts, *, epb, strong_eighths, pedal_bars=frozenset()):
        detected["raw"] = list(raw)
        detected["starts"] = section_starts
        detected["epb"] = epb
        detected["strong"] = tuple(strong_eighths)
        detected["pedal"] = set(pedal_bars)
        detected["calls"] = detected.get("calls", 0) + 1
        return ()

    monkeypatch.setattr("app.sonify.guitar_scales.detect_price_impulses", detect)

    def bumped(raw, chord_at, scale, mode="major", ensemble=""):
        return [note + 1 for note in real_quantize(raw, chord_at, scale, mode)]

    monkeypatch.setattr(sys.modules["app.sonify.render"], "quantize_strong_beats", bumped)
    captured: dict = {}

    def spy(**kwargs):
        captured["raw"] = list(kwargs["raw_pitches"])
        captured["pitches"] = list(kwargs["pitches"])
        captured["impulses"] = kwargs["impulses"]
        captured["slots"] = kwargs["slots"]
        return Score(
            title="Guitar",
            bpm=88,
            bars=1,
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
            variant="guitar",
        )

    monkeypatch.setattr("app.sonify.guitar.render_guitar_score", spy)
    bars = [Bar(close=100 + (index % 9) * 0.4, volume=1000 + index * 10) for index in range(48)]
    render(bars, title="Guitar", variant="guitar", ensemble="classic")
    assert detected["calls"] == 1
    assert captured["raw"] == detected["raw"]
    assert captured["pitches"] != captured["raw"]
    assert all(quantized == raw + 1 for quantized, raw in zip(captured["pitches"], captured["raw"]))
    assert captured["impulses"] == ()
    assert detected["epb"] == 8
    assert detected["strong"] == (0, 4)
    assert detected["starts"] == tuple(
        start * detected["epb"] for start in DAILY_ENSEMBLE_SPEC.section_starts
    )
    pedal = {
        bar
        for slot in captured["slots"]
        for bar in slot.bars()
        if slot.section in {"intro", "outro", "warmup", "cooldown"}
    }
    assert detected["pedal"] == pedal
    assert pedal
    assert isinstance(captured["impulses"], tuple)
