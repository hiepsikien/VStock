"""Price-impulse detector: meters, retreats, tiers, snap, and pedal bars."""

import pytest

from app.sonify.guitar import BARRIOS_TREMOLO_MIN_BPM
from app.sonify.guitar_scales import SCALE_SIXTEENTH_MIN_BPM, detect_price_impulses
from app.sonify.model import PriceImpulse

METERS = [
    pytest.param(8, (0, 4), id="4/4"),
    pytest.param(6, (0,), id="3/4"),
    pytest.param(6, (0, 3), id="6/8"),
]


def _climb(length: int, net: int, origin: int, sign: int) -> list[int]:
    """Strictly monotone path so a plateau cannot split the leg."""
    if net < length:
        raise ValueError("net must be at least one semitone per eighth")
    steps = [1] * length
    for index in range(net - length):
        steps[index % length] += 1
    pitches = [origin]
    for step in steps:
        pitches.append(pitches[-1] + sign * step)
    return pitches


def _join(*paths: list[int]) -> list[int]:
    merged = list(paths[0])
    for path in paths[1:]:
        if path[0] != merged[-1]:
            raise AssertionError((merged[-1], path[0]))
        merged.extend(path[1:])
    return merged


def _score(net: int, length: int, path: int, depths: tuple[int, ...]) -> tuple[float, float]:
    numer = net + 2 * sum(depths)
    adjusted = 1.0 if numer >= path else numer / path
    multiplier = 1.15 if depths else 1.0
    score = net * (1.0 + 0.5 * (net / length)) * adjusted * multiplier
    return adjusted, score


def _detect(
    raw: list[int],
    epb: int,
    strong: tuple[int, ...],
    *,
    sections: tuple[int, ...] = (0,),
    pedal_bars: frozenset[int] = frozenset(),
) -> tuple[PriceImpulse, ...]:
    return detect_price_impulses(
        raw,
        sections,
        epb=epb,
        strong_eighths=strong,
        pedal_bars=pedal_bars,
    )


def test_scale_sixteenth_floor_stays_below_the_tremolo_gate() -> None:
    assert SCALE_SIXTEENTH_MIN_BPM == 88
    assert BARRIOS_TREMOLO_MIN_BPM == 90


def test_strong_eighths_is_required() -> None:
    with pytest.raises(TypeError):
        detect_price_impulses([60, 62, 64, 68], (0,), epb=8)  # type: ignore[call-arg]


@pytest.mark.parametrize(("epb", "strong"), METERS)
def test_short_sub_bar_is_a_straight_leap(epb: int, strong: tuple[int, ...]) -> None:
    raw = _climb(3, 4, 60, 1)
    impulses = _detect(raw, epb, strong)
    adjusted, score = _score(4, 3, 4, ())
    assert impulses == (
        PriceImpulse(
            start=0,
            target=3,
            direction="up",
            net_span=4,
            adjusted_efficiency=adjusted,
            score=score,
            retreat_spans=(),
            sub_bar=True,
        ),
    )


@pytest.mark.parametrize(("epb", "strong"), METERS)
def test_medium_sub_bar_accepts_one_eighth_retreat(epb: int, strong: tuple[int, ...]) -> None:
    # Drop is exactly half the previous impulse. L=4 is below every meter.
    raw = _join(_climb(2, 6, 60, 1), _climb(1, 3, 66, -1), _climb(1, 4, 63, 1))
    impulses = _detect(raw, epb, strong)
    adjusted, score = _score(7, 4, 13, (3,))
    assert impulses == (
        PriceImpulse(
            start=0,
            target=4,
            direction="up",
            net_span=7,
            adjusted_efficiency=adjusted,
            score=score,
            retreat_spans=((2, 3),),
            sub_bar=True,
        ),
    )


@pytest.mark.parametrize(("epb", "strong"), METERS)
def test_one_to_two_bars_accept_up_retreat_up(epb: int, strong: tuple[int, ...]) -> None:
    retreat = 2 if (epb * 30) // 100 >= 2 else 1
    i1 = epb - 2 - retreat
    raw = _join(
        _climb(i1, 10, 72, 1),
        _climb(retreat, 4, 82, -1),
        _climb(2, 6, 78, 1),
    )
    impulses = _detect(raw, epb, strong)
    adjusted, score = _score(12, epb, 20, (4,))
    assert impulses == (
        PriceImpulse(
            start=0,
            target=epb,
            direction="up",
            net_span=12,
            adjusted_efficiency=adjusted,
            score=score,
            retreat_spans=((i1, i1 + retreat),),
            sub_bar=False,
        ),
    )


@pytest.mark.parametrize(("epb", "strong"), METERS)
def test_one_to_two_bars_accept_down_retreat_down(epb: int, strong: tuple[int, ...]) -> None:
    retreat = 2 if (epb * 30) // 100 >= 2 else 1
    i1 = epb - 2 - retreat
    raw = _join(
        _climb(i1, 10, 84, -1),
        _climb(retreat, 4, 74, 1),
        _climb(2, 6, 78, -1),
    )
    impulses = _detect(raw, epb, strong)
    adjusted, score = _score(12, epb, 20, (4,))
    assert impulses == (
        PriceImpulse(
            start=0,
            target=epb,
            direction="down",
            net_span=12,
            adjusted_efficiency=adjusted,
            score=score,
            retreat_spans=((i1, i1 + retreat),),
            sub_bar=False,
        ),
    )


@pytest.mark.parametrize(("epb", "strong"), METERS)
def test_long_tier_accepts_two_retreats(epb: int, strong: tuple[int, ...]) -> None:
    raw = _join(
        _climb(6, 12, 60, 1),
        _climb(3, 6, 72, -1),
        _climb(4, 12, 66, 1),
        _climb(2, 4, 78, -1),
        _climb(2, 8, 74, 1),
    )
    impulses = _detect(raw, epb, strong)
    length = 17
    adjusted, score = _score(22, length, 42, (6, 4))
    assert length > 2 * epb
    assert length <= 4 * epb
    assert impulses == (
        PriceImpulse(
            start=0,
            target=length,
            direction="up",
            net_span=22,
            adjusted_efficiency=adjusted,
            score=score,
            retreat_spans=((6, 9), (13, 15)),
            sub_bar=False,
        ),
    )


def test_retreat_deeper_than_half_does_not_coalesce() -> None:
    # 70 → 58 drops 12 against a prior rise of 10.
    raw = [60, 62, 64, 66, 68, 70, 64, 58, 63, 68, 73, 78]
    impulses = _detect(raw, 8, (0, 4))
    assert [(imp.direction, imp.start, imp.target, imp.retreat_spans) for imp in impulses] == [
        ("up", 0, 5, ()),
        ("down", 5, 7, ()),
        ("up", 7, 11, ()),
    ]


def test_retreat_of_four_eighths_is_not_absorbed() -> None:
    # The dip is 4 eighths and only 3 semitones, so it is neither a retreat nor its own impulse.
    raw = [60, 62, 64, 66, 68, 67, 67, 66, 65, 67, 69, 71, 73]
    impulses = _detect(raw, 8, (0, 4))
    assert [(imp.direction, imp.start, imp.target) for imp in impulses] == [
        ("up", 0, 4),
        ("up", 8, 12),
    ]
    assert all(imp.retreat_spans == () for imp in impulses)


def test_efficiency_below_0_45_rejects_the_wave() -> None:
    # Two half-depth retreats: net 37, path 85, efficiency 37/85 < 0.45.
    # A later straight leap must still be found; the rejected wave is not split open.
    raw = [
        60, 63, 66, 69, 72, 75, 78, 81, 84,
        80, 76, 72,
        78, 84, 90, 96,
        92, 88, 84,
        91, 97,
        97, 97, 97,
        101, 105, 109,
    ]
    impulses = _detect(raw, 8, (0, 4))
    assert len(impulses) == 1
    assert impulses[0].start == 23
    assert impulses[0].target == 26
    assert impulses[0].direction == "up"
    assert impulses[0].retreat_spans == ()


def test_wave_longer_than_four_bars_emits_one_window() -> None:
    epb = 8
    raw = _join(_climb(24, 48, 40, 1), _climb(2, 10, 88, -1), _climb(22, 66, 78, 1))
    impulses = _detect(raw, epb, (0, 4))
    assert len(impulses) == 1
    impulse = impulses[0]
    assert impulse.start == 26
    assert impulse.target == 48
    assert impulse.target - impulse.start <= 4 * epb
    assert impulse.net_span == 66
    assert impulse.retreat_spans == ()
    assert impulse.score == 165.0


def test_failed_snap_keeps_the_raw_extreme_and_a_near_beat_may_snap() -> None:
    # Peak first touched at eighth 2, then held through the next downbeat.
    raw = [60, 62, 64, 64, 64, 64, 64]
    compound = _detect(raw, 6, (0, 3))
    simple = _detect(raw, 6, (0,))
    assert len(compound) == 1
    assert compound[0].start == 0
    assert compound[0].target == 3
    assert compound[0].net_span == 4
    assert compound[0].sub_bar is True
    assert len(simple) == 1
    assert simple[0].start == 0
    assert simple[0].target == 2
    assert simple[0].net_span == 4
    assert simple[0].sub_bar is True


def test_failed_snap_on_four_four_keeps_the_offbeat_extreme() -> None:
    # Raw target is eighth 5. Extending the hold to eighth 8 makes L=6 and net 4 < 6.
    raw = [70, 65, 60, 62, 63, 64, 64, 64, 64]
    impulses = _detect(raw, 8, (0, 4))
    up = [impulse for impulse in impulses if impulse.direction == "up"]
    assert len(up) == 1
    assert up[0].start == 2
    assert up[0].target == 5
    assert up[0].net_span == 4
    assert up[0].sub_bar is True


def test_pedal_bars_are_not_scanned() -> None:
    body = [60, 63, 66, 69, 72, 72, 72, 72]
    pedal = [40, 46, 52, 58, 64, 64, 64, 64]
    later = [48, 52, 56, 60, 64, 64, 64, 64]
    impulses = _detect(body + pedal + later, 8, (0, 4), pedal_bars=frozenset({1}))
    assert [(impulse.start, impulse.target) for impulse in impulses] == [(0, 4), (16, 20)]


def test_section_boundary_is_a_hard_wall() -> None:
    raw = [60 + index for index in range(25)]
    whole = _detect(raw, 8, (0, 4))
    assert [(impulse.start, impulse.target) for impulse in whole] == [(0, 24)]

    split = _detect(raw, 8, (0, 4), sections=(0, 12))
    assert [(impulse.start, impulse.target) for impulse in split] == [(0, 11), (12, 24)]
    assert all(impulse.target <= 12 or impulse.start >= 12 for impulse in split)


def test_three_eighth_plateau_stays_in_the_leg_and_four_splits_it() -> None:
    held = _detect([60, 62, 62, 62, 66], 8, (0, 4))
    assert len(held) == 1
    assert held[0].start == 0
    assert held[0].target == 4
    assert held[0].net_span == 6

    split = _detect([60, 62, 62, 62, 62, 66], 8, (0, 4))
    assert split == ()


def test_flat_edges_trim_back_to_the_first_extreme() -> None:
    raw = [60, 60, 60, 64, 68, 70, 70]
    impulses = _detect(raw, 8, (0, 4))
    assert len(impulses) == 1
    assert impulses[0].start == 2
    assert impulses[0].target == 5
    assert impulses[0].net_span == 10
    assert impulses[0].sub_bar is True
