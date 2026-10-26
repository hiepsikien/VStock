"""Volume-wave rebase for classical guitar velocities.

Written pattern velocities are replaced, after the notes exist, by a smoothed
per-bar trading-intensity envelope. Warm notes stay at or below 63. Rare snaps
land in 66..76, and only on the patterns that actually need a nail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from app.sonify.dynamics import percentile
from app.sonify.guitar import _PEDAL, _TREMOLO_FILL_OFFSETS, _TREMOLO_QUARTER_OFFSETS
from app.sonify.model import NoteEvent

BAND_VOLUME = {"p": 1.0, "mp": 2.0, "mf": 4.0, "f": 8.0}
BAND_LEVEL = {"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}
_KERNEL = (1, 4, 6, 4, 1)
_ETUDE1_ARC = {
    1: -2,
    2: -2,
    3: -2,
    4: 0,
    5: 0,
    6: 2,
    8: 2,
    10: 2,
    11: 0,
    12: 0,
    13: -2,
    14: -2,
    15: -2,
}
_ETUDE11_ARCH = {1: -10, 2: -6, 4: -7, 5: -10}
_ETUDE11_TILT = {1: -1, 2: -1, 4: 0, 5: 1}
_BAND_NUDGE = {"p": -2, "mp": -1, "mf": 0, "f": 2}
_EXEMPT = frozenset({"tremolo", "etude1", "etude11", "preludio"})
_STAB = {"lead": 70, "low": 66, "support": 62}
# The morendo lands inside 20..26. The plan names the curve but does not lock
# the decay constant, so the last bar arrives at this midpoint.
MORENDO_END = 23
JOIN_FLOOR = 20
PREJOIN_CEILING = 56
CREST_CAP = 4


@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int
    floor_wide: int
    ceil_calm: int
    ceil_wide: int
    snap_calm: int | None
    snap_wide: int | None
    bass_floor: int
    bass_ceil: int
    sup_floor: int
    sup_ceil: int
    gamma: float
    max_units_per_phrase: int
    max_units_per_sec: int
    snap_targets: str


def _profile(
    floor_calm: int,
    floor_wide: int,
    ceil_calm: int,
    ceil_wide: int,
    snap_calm: int | None,
    snap_wide: int | None,
    bass_floor: int,
    bass_ceil: int,
    sup_floor: int,
    sup_ceil: int,
    gamma: float,
    per_phrase: int,
    per_sec: int,
    targets: str,
) -> PatternWaveProfile:
    return PatternWaveProfile(
        floor_calm,
        floor_wide,
        ceil_calm,
        ceil_wide,
        snap_calm,
        snap_wide,
        bass_floor,
        bass_ceil,
        sup_floor,
        sup_ceil,
        gamma,
        per_phrase,
        per_sec,
        targets,
    )


# Exactly the 28 (ensemble, pattern) rows. Pedal is a frame path, not a 29th row.
PROFILES: dict[tuple[str, str], PatternWaveProfile] = {
    ("bach", "bach_sarabande"): _profile(26, 30, 56, 62, None, None, 24, 56, 20, 46, 1.30, 0, 0, "none"),
    ("bach", "bach_gavotte"): _profile(28, 32, 58, 62, 66, 68, 26, 58, 22, 48, 1.20, 1, 2, "gavotte"),
    ("bach", "bach_bourree"): _profile(28, 32, 58, 63, 66, 68, 26, 58, 22, 48, 1.15, 1, 3, "bourree"),
    ("bach", "bach_fuga"): _profile(28, 32, 58, 63, 66, 68, 26, 61, 20, 46, 1.15, 1, 2, "fuga"),
    ("bach", "bach_gigue"): _profile(28, 32, 58, 63, 68, 70, 26, 58, 22, 50, 1.15, 1, 3, "gigue"),
    ("bach", "bach_chaconne"): _profile(26, 30, 58, 63, 68, 70, 24, 58, 20, 48, 1.25, 1, 3, "chaconne"),
    ("classic", "cantabile"): _profile(24, 28, 54, 58, None, None, 20, 46, 18, 48, 1.35, 0, 0, "none"),
    ("classic", "elegiaque"): _profile(24, 28, 56, 62, 66, 68, 22, 56, 18, 46, 1.30, 1, 2, "appoggiatura"),
    ("classic", "study"): _profile(26, 30, 56, 63, 68, 70, 24, 58, 20, 50, 1.20, 1, 2, "study"),
    ("classic", "mozart_var"): _profile(26, 30, 56, 62, 66, 68, 24, 56, 20, 50, 1.20, 1, 2, "apex_rise"),
    ("classic", "galop"): _profile(28, 32, 58, 63, 68, 70, 26, 58, 22, 50, 1.10, 1, 3, "galop"),
    ("barrios", "preludio"): _profile(26, 30, 56, 62, 66, 68, 22, 54, 18, 46, 1.40, 1, 2, "canto"),
    ("barrios", "andante"): _profile(24, 28, 54, 60, None, None, 22, 54, 18, 46, 1.35, 0, 0, "none"),
    ("barrios", "thumb_cantabile"): _profile(26, 30, 56, 62, 66, 68, 20, 44, 18, 40, 1.35, 1, 2, "thumb"),
    ("barrios", "tremolo"): _profile(28, 32, 58, 63, 68, 72, 28, 63, 22, 50, 1.30, 1, 2, "tremolo"),
    ("barrios", "choro"): _profile(28, 32, 58, 63, 70, 74, 26, 58, 22, 50, 1.15, 1, 4, "offbeat"),
    ("barrios", "polca"): _profile(28, 32, 58, 63, 70, 72, 26, 58, 22, 50, 1.15, 1, 3, "offbeat"),
    ("barrios", "hemiola"): _profile(28, 32, 58, 63, 70, 74, 26, 58, 22, 50, 1.15, 1, 4, "hemiola"),
    ("barrios", "vals"): _profile(26, 30, 58, 62, 68, 72, 24, 56, 20, 48, 1.20, 1, 3, "vals"),
    ("villa", "chord_melody"): _profile(24, 28, 54, 60, None, None, 22, 54, 18, 48, 1.35, 0, 0, "none"),
    ("villa", "thumb_cantabile"): _profile(28, 32, 58, 63, 68, 70, 22, 46, 20, 42, 1.25, 1, 2, "thumb"),
    ("villa", "villa_pattern"): _profile(26, 30, 58, 63, 68, 72, 24, 58, 20, 50, 1.20, 1, 3, "tresillo"),
    ("villa", "etude1"): _profile(28, 32, 58, 63, 68, 70, 24, 58, 22, 52, 1.20, 1, 2, "etude1"),
    ("villa", "etude11"): _profile(28, 32, 58, 63, 70, 74, 24, 58, 22, 55, 1.20, 1, 3, "etude11"),
    ("brouwer", "noviembre"): _profile(22, 26, 52, 58, None, None, 20, 50, 18, 42, 1.45, 0, 0, "none"),
    ("brouwer", "sarabande"): _profile(24, 28, 56, 62, 68, 72, 22, 56, 18, 48, 1.35, 1, 2, "sarabande"),
    ("brouwer", "brouwer_etude"): _profile(24, 28, 58, 63, 68, 72, 22, 58, 20, 50, 1.15, 1, 3, "tumbao"),
    ("brouwer", "elogio_pizz"): _profile(24, 28, 56, 62, 72, 76, 22, 56, 20, 48, 1.15, 1, 4, "slap"),
}


def profile_for(ensemble: str, pattern: str) -> PatternWaveProfile | None:
    return PROFILES.get((ensemble, pattern))


def resolve_bar_volumes(ctx) -> list[float]:
    """Per-bar intensity. Missing data falls back to the printed band."""
    if getattr(ctx, "bar_volumes", None):
        values = [max(0.0, float(value)) for value in ctx.bar_volumes]
    else:
        values = [BAND_VOLUME.get(ctx.band(bar), 4.0) for bar in range(ctx.bars)]
    if len(values) < ctx.bars:
        pad = values[-1] if values else 4.0
        values.extend([pad] * (ctx.bars - len(values)))
    return values[: ctx.bars]


def _reflect(index: int, start: int, end: int) -> int:
    span = end - start
    if span <= 1:
        return start
    guard = 0
    while index < start or index >= end:
        if index < start:
            index = start + (start - index)
        else:
            index = (end - 1) - (index - (end - 1))
        guard += 1
        if guard > 8:
            return min(end - 1, max(start, index))
    return index


def smooth_log(volumes: list[float], start: int, end: int) -> list[float]:
    """Zero-phase 5-tap smooth of ln(1 + v) over [start, end)."""
    if end <= start:
        return []
    raw = [math.log1p(max(0.0, volumes[bar])) for bar in range(start, end)]
    smoothed: list[float] = []
    for index in range(len(raw)):
        total = 0.0
        for offset, weight in enumerate(_KERNEL):
            source = _reflect(start + index + offset - 2, start, end) - start
            total += weight * raw[source]
        smoothed.append(total / 16.0)
    return smoothed


def _snap01(value: float) -> float:
    if value <= 1e-9:
        return 0.0
    if value >= 1.0 - 1e-9:
        return 1.0
    return value


def range_lock(smoothed: list[float], bands: list[str]) -> list[float]:
    """Lock a section onto [0, 1], or the band step when the section is flat."""
    if not smoothed:
        return []
    low = percentile(smoothed, 0.05)
    high = percentile(smoothed, 0.95)
    if high - low <= 1e-6:
        return [_snap01(BAND_LEVEL.get(band, 0.65)) for band in bands]
    raw = [min(1.0, max(0.0, (value - low) / (high - low))) for value in smoothed]
    floor = min(raw)
    ceiling = max(raw)
    if ceiling - floor <= 1e-12:
        return [_snap01(value) for value in raw]
    return [_snap01((value - floor) / (ceiling - floor)) for value in raw]


def alpha_price(rel_span: float) -> float:
    return min(1.0, max(0.0, (rel_span - 0.004) / (0.024 - 0.004)))


def alpha_volume(smoothed: list[float], price: float) -> float:
    if not smoothed:
        return price
    restored = [math.exp(value) - 1.0 for value in smoothed]
    high = percentile(restored, 0.90)
    low = percentile(restored, 0.10)
    ratio = high / max(low, 1e-6)
    if ratio <= 1.01:
        return price
    span = math.log(3.50) - math.log(1.35)
    return min(1.0, max(0.0, (math.log(ratio) - math.log(1.35)) / span))


def warm_alpha(price: float, volume: float, *, inward: bool) -> float:
    opened = max(price, 0.75 * volume)
    if inward:
        opened *= 0.50
    return opened


def window_for(profile: PatternWaveProfile, opened: float) -> tuple[int, int]:
    floor = int(round(profile.floor_calm + opened * (profile.floor_wide - profile.floor_calm)))
    ceiling = int(round(profile.ceil_calm + opened * (profile.ceil_wide - profile.ceil_calm)))
    ceiling = min(63, ceiling)
    if ceiling < floor:
        ceiling = floor
    return floor, ceiling


def bar_edges(levels: list[float]) -> list[tuple[float, float]]:
    """Two-way barline edges. Extremum bars stay flat; neighbours meet them."""
    edges: list[tuple[float, float]] = []
    for index, level in enumerate(levels):
        extreme = level in (0.0, 1.0)
        if index == 0 or extreme:
            start = level
        else:
            start = edges[-1][1]
        if extreme:
            end = level
        elif index + 1 < len(levels) and levels[index + 1] in (0.0, 1.0):
            end = levels[index + 1]
        else:
            end = level
        edges.append((start, end))
    return edges


def u_vol(u_start: float, u_end: float, epb: int, k: float) -> float:
    if epb <= 1:
        ratio = 1.0
    else:
        ratio = min(1.0, max(0.0, k / (epb - 1)))
    return u_start + (1.0 - math.cos(math.pi * ratio)) / 2.0 * (u_end - u_start)


def _flat_phrase(phrase) -> bool:
    if phrase is None or not phrase.runs:
        return True
    return phrase.rise <= 0 or len({run.midi for run in phrase.runs}) <= 1


def phrase_curve(phrase, t: float) -> float:
    """Cosine breath: 0 at the edges, 1 at the apex (or the centre when flat)."""
    if phrase is None or not phrase.runs:
        return 1.0
    start = float(phrase.start)
    end = float(phrase.end)
    if end <= start:
        return 1.0
    if _flat_phrase(phrase):
        if end - start <= 1:
            return 1.0
        mid = (start + end - 1.0) / 2.0
        half = (end - start - 1.0) / 2.0
        if half <= 0:
            return 1.0
        position = 1.0 - min(1.0, abs(t - mid) / half)
        return (1.0 - math.cos(math.pi * position)) / 2.0
    apex = phrase.apex
    if apex.start <= t < apex.end:
        return 1.0
    if t <= apex.start:
        span = apex.start - start
        if span <= 0:
            return 1.0
        position = min(1.0, max(0.0, (t - start) / span))
        return (1.0 - math.cos(math.pi * position)) / 2.0
    span = (end - 1.0) - (apex.end - 1.0)
    if span <= 0:
        return 1.0
    position = min(1.0, max(0.0, ((end - 1.0) - t) / span))
    return (1.0 - math.cos(math.pi * position)) / 2.0


def phrase_delta(phrase, t: float, level: float) -> float:
    depth = 1.0 if _flat_phrase(phrase) else 3.0
    breath = phrase_curve(phrase, t)
    return -depth * (1.0 - breath) * (1.0 - (level ** 4))


def hat_from(v_floor: int, v_ceil: int, level: float, gamma: float, phrase, t: float) -> int:
    shaped = 0.0 if level <= 0.0 else level ** gamma
    envelope = v_floor + shaped * (v_ceil - v_floor)
    delta = 0.0 if phrase is None else phrase_delta(phrase, t, level)
    return max(v_floor, min(v_ceil, int(round(envelope + delta))))


def _powered(floor: int, ceiling: int, level: float, gamma: float, power: float) -> int:
    """E_vol(t) = U^gamma, then the voice curve raises that envelope again."""
    if level <= 0.0:
        shaped = 0.0
    else:
        shaped = (level ** gamma) ** power
    return int(round(floor + shaped * (ceiling - floor)))


def etude11_middle_velocity(hairpin: int, slot: int, band: str, sup_floor: int = 22) -> int:
    """Four-step inner arch. At hairpin 60 / mf / floor 22 this is 49, 50, 51, 51."""
    echo = max(sup_floor, hairpin - 8)
    ceiling = max(sup_floor, echo if band == "f" else echo - 1)
    shaped = min(ceiling, max(sup_floor, hairpin + _ETUDE11_ARCH[slot] + _BAND_NUDGE.get(band, 0)))
    return max(sup_floor, shaped + _ETUDE11_TILT[slot])


def shape_join_velocity(written: int, written_max: int, written_last: int, v_join: int) -> int:
    crest = max(0, written_max - written_last)
    scale = 1.0 if crest <= CREST_CAP else CREST_CAP / crest
    return max(JOIN_FLOOR, int(round(v_join - (written_max - written) * scale)))


def prejoin_envelope(count: int, v_open: int) -> list[int]:
    """Pre-join bars aim at the join bar's first lead note. 56 is only a ceiling."""
    if count <= 0:
        return []
    cap = min(int(v_open), PREJOIN_CEILING)
    if count == 1:
        return [cap]
    return [int(round(27 + (cap - 27) * index / (count - 1))) for index in range(count)]


def shape_prejoin_velocity(written: int, peak_written: int, target: int) -> int:
    return max(JOIN_FLOOR, min(PREJOIN_CEILING, int(round(target - (peak_written - written)))))


def morendo_peak(v_close: int, index: int, count: int) -> int:
    """Exponential fade from the body exit down into 20..26 on the last bar."""
    close = max(JOIN_FLOOR, int(v_close))
    end = MORENDO_END
    if close <= end:
        return max(JOIN_FLOOR, min(26, close))
    if count <= 1:
        return end
    frac = index / (count - 1)
    value = close * ((end / close) ** frac)
    return max(JOIN_FLOOR, min(63, int(round(value))))


@dataclass
class _Wave:
    start: int
    end: int
    levels: list[float]
    edges: list[tuple[float, float]]
    alpha_price: float
    alpha_vol: float
    alpha_warm: float
    smoothed: list[float]


def _pedal_regions(ctx) -> tuple[list[int], list[int]]:
    leading: list[int] = []
    bar = 0
    while bar < ctx.bars and ctx.kind_at.get(bar, "phrase") in _PEDAL:
        leading.append(bar)
        bar += 1
    trailing: list[int] = []
    bar = ctx.bars - 1
    while bar >= 0 and bar not in leading and ctx.kind_at.get(bar, "phrase") in _PEDAL:
        trailing.append(bar)
        bar -= 1
    trailing.reverse()
    return leading, trailing


def _rel_span(ctx, section) -> float:
    spans = getattr(ctx, "section_rel_spans", None) or {}
    if section is not None and section.start in spans:
        return float(spans[section.start])
    return float(ctx.rel_span)


def _build_waves(ctx, volumes: list[float]) -> dict[int, _Wave]:
    pedal = set(_pedal_regions(ctx)[0]) | set(_pedal_regions(ctx)[1])
    ranges: list[tuple[object, int, int]] = []
    if ctx.sections:
        for section in ctx.sections:
            if getattr(section, "kind", None) in _PEDAL:
                continue
            if section.end <= section.start:
                continue
            ranges.append((section, section.start, section.end))
    covered = {bar for _section, start, end in ranges for bar in range(start, end) if bar not in pedal}
    leftover = [bar for bar in range(ctx.bars) if bar not in pedal and bar not in covered]
    cursor = 0
    while cursor < len(leftover):
        end = cursor
        while end + 1 < len(leftover) and leftover[end + 1] == leftover[end] + 1:
            end += 1
        ranges.append((None, leftover[cursor], leftover[end] + 1))
        cursor = end + 1
    found: dict[int, _Wave] = {}
    for section, start, end in ranges:
        start = max(0, start)
        end = min(ctx.bars, end)
        if end <= start:
            continue
        smoothed = smooth_log(volumes, start, end)
        bands = [ctx.band(bar) for bar in range(start, end)]
        levels = range_lock(smoothed, bands)
        price = alpha_price(_rel_span(ctx, section))
        volume = alpha_volume(smoothed, price)
        inward = bool(section is not None and (getattr(section, "trio", False) or getattr(section, "bridge", False)))
        opened = warm_alpha(price, volume, inward=inward)
        wave = _Wave(start, end, levels, bar_edges(levels), price, volume, opened, smoothed)
        for bar in range(start, end):
            if bar not in pedal:
                found[bar] = wave
    return found


def _pattern_at(ctx, bar: int, patterns: list[str]) -> str:
    from app.sonify.guitar_patterns import _bar_pattern

    return _bar_pattern(ctx, bar, patterns)


def _phrase_at(ctx, t: float):
    for phrase in ctx.phrases:
        if phrase.start <= t < phrase.end:
            return phrase
    return None


def _k_of(event) -> float:
    return float(event.beat) * 2.0


def _onset(event, epb: int) -> float:
    return event.bar * epb + _k_of(event)


def _level_at(wave: _Wave, bar: int, k: float, epb: int) -> float:
    index = min(len(wave.levels) - 1, max(0, bar - wave.start))
    start, end = wave.edges[index]
    return u_vol(start, end, epb, k)


def _window(ctx, wave: _Wave, pattern: str) -> tuple[PatternWaveProfile, int, int] | None:
    profile = profile_for(ctx.ensemble, pattern)
    if profile is None:
        return None
    floor, ceiling = window_for(profile, wave.alpha_warm)
    if pattern == "preludio":
        ceiling = min(ceiling, 62)
    return profile, floor, ceiling


def _hat_at(ctx, waves: dict[int, _Wave], patterns: list[str], bar: int, k: float) -> int:
    wave = waves.get(bar)
    pattern = _pattern_at(ctx, bar, patterns)
    if wave is None:
        return 48
    found = _window(ctx, wave, pattern)
    if found is None:
        return 48
    _profile, floor, ceiling = found
    level = _level_at(wave, bar, k, ctx.epb)
    t = bar * ctx.epb + k
    return hat_from(floor, ceiling, level, _profile.gamma, _phrase_at(ctx, t), t)


def _curves_at(ctx, wave: _Wave, pattern: str, bar: int, k: float) -> tuple[int, int, int] | None:
    found = _window(ctx, wave, pattern)
    if found is None:
        return None
    profile, floor, ceiling = found
    level = _level_at(wave, bar, k, ctx.epb)
    t = bar * ctx.epb + k
    hat = hat_from(floor, ceiling, level, profile.gamma, _phrase_at(ctx, t), t)
    bass = _powered(profile.bass_floor, profile.bass_ceil, level, profile.gamma, 1.05)
    support = _powered(profile.sup_floor, profile.sup_ceil, level, profile.gamma, 1.20)
    return hat, bass, support


def _put(events: list[NoteEvent], index: int, velocity: int, **flags) -> None:
    velocity = max(1, min(127, int(velocity)))
    events[index] = replace(events[index], velocity=velocity, **flags)


def _attacks(events: list[NoteEvent], bar: int) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if event.bar == bar and event.midi is not None and event.velocity is not None and not event.tie_stop
    ]


def _assign_generic(ctx, events: list[NoteEvent], voice: str, bar: int, pattern: str, wave: _Wave) -> None:
    for index in _attacks(events, bar):
        event = events[index]
        curves = _curves_at(ctx, wave, pattern, bar, _k_of(event))
        if curves is None:
            continue
        hat, bass, support = curves
        if pattern == "thumb_cantabile":
            chosen = {"low": hat, "lead": bass, "support": support}[voice]
        else:
            chosen = {"lead": hat, "low": bass, "support": support}[voice]
        _put(events, index, min(63, chosen))


def _assign_tremolo(ctx, lead, support, low, bar: int, wave: _Wave, pattern: str) -> None:
    found = _window(ctx, wave, pattern)
    if found is None:
        return
    profile, _floor, _ceiling = found
    k_mid = ctx.epb / 2.0
    curves = _curves_at(ctx, wave, pattern, bar, k_mid)
    anchor = profile.floor_calm + 8 if curves is None else curves[0]
    anchor = max(profile.floor_calm + 4, min(59, anchor))
    quarters = 4 if ctx.epb >= 8 else 3
    offsets = _TREMOLO_QUARTER_OFFSETS.get(quarters, _TREMOLO_QUARTER_OFFSETS[3])
    thumbs: dict[int, int] = {}
    for index in _attacks(low, bar):
        event = low[index]
        if event.duration_beats < 0.75:
            continue
        quarter = min(quarters - 1, max(0, int(math.floor(event.beat + 1e-9))))
        level = anchor + offsets[min(quarter, len(offsets) - 1)]
        level = max(profile.floor_calm, min(63, level))
        thumbs[quarter] = level
        _put(low, index, level)
    groups: dict[int, list[int]] = {}
    for index in _attacks(lead, bar):
        event = lead[index]
        if event.duration_beats > 0.3:
            curves = _curves_at(ctx, wave, pattern, bar, _k_of(event))
            if curves is not None:
                _put(lead, index, min(63, curves[0]))
            continue
        quarter = min(quarters - 1, max(0, int(math.floor(event.beat + 1e-9))))
        groups.setdefault(quarter, []).append(index)
    for quarter, indexes in groups.items():
        indexes.sort(key=lambda item: lead[item].beat)
        thumb = thumbs.get(quarter, anchor)
        for slot, index in enumerate(indexes[:4]):
            fill = max(18, min(60, thumb + _TREMOLO_FILL_OFFSETS[slot]))
            _put(lead, index, fill)
    for index in _attacks(support, bar):
        event = support[index]
        quarter = min(quarters - 1, max(0, int(math.floor(event.beat + 1e-9))))
        if abs(event.beat) < 1e-6 or quarter == 0:
            _put(support, index, thumbs.get(0, max(18, anchor + offsets[0])))
        else:
            _put(support, index, min(63, thumbs.get(quarter, anchor)))


def _assign_etude1(ctx, lead, support, low, bar: int, wave: _Wave, pattern: str) -> None:
    found = _window(ctx, wave, pattern)
    if found is None:
        return
    profile, _floor, _ceiling = found
    sung: list[int] = []
    for index in _attacks(lead, bar):
        event = lead[index]
        curves = _curves_at(ctx, wave, pattern, bar, _k_of(event))
        if curves is None:
            continue
        _put(lead, index, curves[0])
        sung.append(lead[index].velocity or curves[0])
    if not sung:
        sung = [profile.floor_calm]
    quiet = min(sung)
    k_mid = ctx.epb / 2.0
    curves = _curves_at(ctx, wave, pattern, bar, k_mid)
    sup_curve = curves[2] if curves is not None else profile.sup_floor
    low_bound = profile.sup_floor + 2
    high_bound = min(profile.sup_ceil - 2, quiet - 8)
    if high_bound < low_bound:
        middle = high_bound
    else:
        middle = min(max(sup_curve, low_bound), high_bound)
    sup_levels: list[int] = []
    for index in _attacks(support, bar):
        slot = int(round(support[index].beat * 4))
        arc = _ETUDE1_ARC.get(slot, 0)
        level = max(profile.sup_floor, min(profile.sup_ceil, middle + arc))
        _put(support, index, level)
        sup_levels.append(level)
    peak_sup = max(sup_levels) if sup_levels else profile.sup_floor
    bass = min(61, max(peak_sup + 2, quiet - 4))
    for index in _attacks(low, bar):
        _put(low, index, bass)


def _assign_etude11(ctx, lead, support, low, bar: int, wave: _Wave, pattern: str) -> None:
    found = _window(ctx, wave, pattern)
    if found is None:
        return
    profile, _floor, _ceiling = found
    band = ctx.band(bar)
    by_quarter: dict[int, dict[str, list[int]]] = {}
    for voice, events in (("lead", lead), ("low", low), ("support", support)):
        for index in _attacks(events, bar):
            event = events[index]
            quarter = min(3, max(0, int(math.floor(event.beat + 1e-9))))
            slot = int(round((event.beat - quarter) * 6))
            kind = "middle" if voice == "support" and slot in _ETUDE11_ARCH else "down" if slot == 0 else "echo"
            by_quarter.setdefault(quarter, {}).setdefault(voice + ":" + kind, []).append(index)
    for quarter in range(4):
        k = float(quarter * 2)
        curves = _curves_at(ctx, wave, pattern, bar, k)
        if curves is None:
            continue
        hairpin = curves[0]
        echo = max(profile.sup_floor + 6, hairpin - 8)
        bass = min(59, max(echo + 2, hairpin - 4))
        bucket = by_quarter.get(quarter, {})
        for index in bucket.get("lead:down", []):
            _put(lead, index, hairpin, accent=False)
        for index in bucket.get("lead:echo", []):
            _put(lead, index, min(63, echo), accent=False)
        for index in bucket.get("low:down", []):
            _put(low, index, bass, accent=False)
        for index in bucket.get("support:middle", []):
            slot = int(round((support[index].beat - quarter) * 6))
            _put(support, index, min(profile.sup_ceil, etude11_middle_velocity(hairpin, slot, band, profile.sup_floor)))


def _assign_preludio(ctx, lead, support, low, bar: int, wave: _Wave, pattern: str) -> None:
    found = _window(ctx, wave, pattern)
    if found is None:
        return
    profile, _floor, _ceiling = found
    lead_indexes = _attacks(lead, bar)
    sixteenths = any(
        event.duration_beats <= 0.3 for event in (*lead, *support) if event.bar == bar and event.midi is not None
    )
    if not sixteenths:
        for index in lead_indexes:
            curves = _curves_at(ctx, wave, pattern, bar, _k_of(lead[index]))
            if curves is not None:
                _put(lead, index, min(62, curves[0]))
        written = [support[index].velocity or 0 for index in _attacks(support, bar)]
        peak = max(written) if written else 0
        for index in _attacks(support, bar):
            curves = _curves_at(ctx, wave, pattern, bar, _k_of(support[index]))
            top = 40 if curves is None else min(46, max(20, curves[2]))
            shifted = top if peak <= 0 else top - (peak - (support[index].velocity or peak))
            _put(support, index, max(18, min(46, shifted)))
        for index in _attacks(low, bar):
            curves = _curves_at(ctx, wave, pattern, bar, _k_of(low[index]))
            if curves is None:
                continue
            canto = min(sung for sung in (lead[item].velocity or 0 for item in lead_indexes) if sung) if lead_indexes else curves[0]
            top = min(46, max(20, curves[2]))
            _put(low, index, min(canto - 4, max(top + 3, curves[1])))
        return
    canto1: list[int] = []
    canto2: list[int] = []
    for index in lead_indexes:
        event = lead[index]
        curves = _curves_at(ctx, wave, pattern, bar, _k_of(event))
        if curves is None:
            continue
        slot = int(round(event.beat * 4)) % 8
        if event.duration_beats >= 0.9 or slot == 0:
            _put(lead, index, curves[0])
            canto1.append(index)
        else:
            canto2.append(index)
    for index in canto2:
        earlier = [item for item in canto1 if lead[item].beat <= lead[index].beat + 1e-9]
        source_index = earlier[-1] if earlier else (canto1[0] if canto1 else None)
        source = lead[source_index].velocity if source_index is not None else profile.floor_calm
        _put(lead, index, max(profile.floor_calm - 2, (source or profile.floor_calm) - 2))
    canto2_level = min((lead[index].velocity or 40) for index in canto2) if canto2 else (lead[canto1[0]].velocity or 40) - 2 if canto1 else 40
    for index in _attacks(support, bar):
        event = support[index]
        curves = _curves_at(ctx, wave, pattern, bar, _k_of(event))
        sup_curve = curves[2] if curves is not None else profile.sup_floor
        top = min(sup_curve, canto2_level - 8)
        top = max(20, min(46, top))
        slot = int(round(event.beat * 4)) % 8
        level = top - 2 if slot == 3 else top
        _put(support, index, max(18, level))
    v_top = 20
    support_levels = [support[index].velocity or 20 for index in _attacks(support, bar)]
    if support_levels:
        v_top = max(support_levels)
    for index in _attacks(low, bar):
        curves = _curves_at(ctx, wave, pattern, bar, _k_of(low[index]))
        bass_curve = curves[1] if curves is not None else profile.bass_floor
        _put(low, index, min(canto2_level - 4, max(v_top + 3, bass_curve)))


def _assign_body(ctx, lead, support, low, patterns, waves) -> None:
    for bar, wave in waves.items():
        if ctx.kind_at.get(bar, "phrase") in _PEDAL:
            continue
        pattern = _pattern_at(ctx, bar, patterns)
        if pattern == "tremolo":
            _assign_tremolo(ctx, lead, support, low, bar, wave, pattern)
        elif pattern == "etude1":
            _assign_etude1(ctx, lead, support, low, bar, wave, pattern)
        elif pattern == "etude11":
            _assign_etude11(ctx, lead, support, low, bar, wave, pattern)
        elif pattern == "preludio":
            _assign_preludio(ctx, lead, support, low, bar, wave, pattern)
        else:
            for voice, events in (("lead", lead), ("support", support), ("low", low)):
                _assign_generic(ctx, events, voice, bar, pattern, wave)


def _spans(events: list[NoteEvent], bar_beats: float) -> dict[int, tuple[float, float]]:
    order = sorted(range(len(events)), key=lambda index: (events[index].bar, events[index].beat))
    spans: dict[int, tuple[float, float]] = {}
    active: dict[int, int] = {}
    for index in order:
        event = events[index]
        if event.midi is None or event.velocity is None:
            continue
        start = event.bar * bar_beats + event.beat
        end = start + max(event.duration_beats, 1e-6)
        if event.tie_stop and event.midi in active:
            attack = active[event.midi]
            prev_start, prev_end = spans[attack]
            spans[attack] = (prev_start, max(prev_end, end))
            if not event.tie_start:
                active.pop(event.midi, None)
            continue
        spans[index] = (start, end)
        if event.tie_start:
            active[event.midi] = index
        else:
            active.pop(event.midi, None)
    return spans


def _overlap(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return left[0] < right[1] - 1e-9 and right[0] < left[1] - 1e-9


def _pedal_bar(ctx, bar: int) -> bool:
    return ctx.kind_at.get(bar, "phrase") in _PEDAL


def _order_voices(ctx, lead, support, low, patterns) -> None:
    bar_beats = ctx.bar_beats
    lead_spans = _spans(lead, bar_beats)
    low_spans = _spans(low, bar_beats)
    sup_spans = _spans(support, bar_beats)

    def pattern_of(event: NoteEvent) -> str:
        return _pattern_at(ctx, event.bar, patterns)

    def mode_of(pattern: str) -> str:
        if pattern in _EXEMPT:
            return "skip"
        if pattern == "thumb_cantabile":
            return "thumb"
        if pattern == "bach_fuga":
            return "fuga"
        return "strict"

    def usable(event: NoteEvent) -> bool:
        return not _pedal_bar(ctx, event.bar) and mode_of(pattern_of(event)) != "skip"

    # Thumb sings in the bass. Lower the written upper voices before the
    # inner voice is capped against them.
    for index, span in lead_spans.items():
        event = lead[index]
        if pattern_of(event) != "thumb_cantabile" or _pedal_bar(ctx, event.bar):
            continue
        caps = [
            (low[other].velocity or 0) - 4
            for other, low_span in low_spans.items()
            if _overlap(span, low_span) and pattern_of(low[other]) == "thumb_cantabile"
        ]
        if caps:
            _put(lead, index, max(18, min(event.velocity or 0, min(caps))))

    for index, span in low_spans.items():
        event = low[index]
        if not usable(event):
            continue
        mode = mode_of(pattern_of(event))
        if mode == "thumb":
            continue
        caps: list[int] = []
        for lead_index, lead_span in lead_spans.items():
            if not _overlap(span, lead_span):
                continue
            other = lead[lead_index]
            if not usable(other):
                continue
            level = other.velocity or 0
            if mode == "fuga" or (event.accent and other.accent and abs(event.beat - other.beat) < 1e-6):
                caps.append(level)
            else:
                gap = 2 if level < 30 else 3
                caps.append(level - gap)
        if caps:
            _put(low, index, min(event.velocity or 0, min(caps)))

    for index, span in sup_spans.items():
        event = support[index]
        if not usable(event):
            continue
        mode = mode_of(pattern_of(event))
        if mode == "thumb":
            caps = [
                (lead[other].velocity or 20) - 1
                for other, lead_span in lead_spans.items()
                if _overlap(span, lead_span) and (lead[other].velocity or 0) >= 20 and pattern_of(lead[other]) == "thumb_cantabile"
            ]
            if caps:
                _put(support, index, max(18, min(event.velocity or 0, min(caps))))
            continue
        overlapping_lows = [
            low[other].velocity or 0
            for other, low_span in low_spans.items()
            if _overlap(span, low_span) and usable(low[other])
        ]
        if mode == "fuga":
            floor_voice = min(overlapping_lows) if overlapping_lows else (event.velocity or 0)
            caps = [floor_voice - 2]
        elif event.accent and overlapping_lows:
            caps = [min(overlapping_lows)]
        else:
            caps = [(level - 2) for level in overlapping_lows]
            for lead_index, lead_span in lead_spans.items():
                if not _overlap(span, lead_span) or not usable(lead[lead_index]):
                    continue
                level = lead[lead_index].velocity or 0
                gap = 2 if level < 30 else 3
                caps.append(level - gap - 2)
        if caps:
            _put(support, index, max(18, min(event.velocity or 0, min(caps))))

    for index, span in lead_spans.items():
        event = lead[index]
        if not usable(event) or mode_of(pattern_of(event)) in {"thumb", "fuga"}:
            continue
        if (event.velocity or 0) >= 22:
            continue
        when = span[0]
        lows = [
            other
            for other, low_span in low_spans.items()
            if low_span[0] - 1e-9 <= when < low_span[1] and usable(low[other])
        ]
        inners = [
            other
            for other, sup_span in sup_spans.items()
            if sup_span[0] - 1e-9 <= when < sup_span[1] and usable(support[other])
        ]
        if lows and inners:
            _put(lead, index, 22)
            for other in lows:
                _put(low, other, max(low[other].velocity or 0, 20))
            for other in inners:
                _put(support, other, max(support[other].velocity or 0, 18))


def _at_apex(phrase, onset: float) -> bool:
    return phrase is not None and phrase.apex.start <= onset < phrase.apex.end


def _is_target(ctx, pattern: str, event: NoteEvent, voice: str, phrase, onset: float, level: float) -> bool:
    profile = profile_for(ctx.ensemble, pattern)
    if profile is None or profile.snap_wide is None:
        return False
    rise = 0 if phrase is None else phrase.rise
    apex = _at_apex(phrase, onset)
    beat = event.beat
    eighth = int(round(beat * 2))
    if pattern == "bach_gavotte":
        return voice == "lead" and rise >= 3 and phrase is not None and abs(onset - phrase.start) < 1e-6
    if pattern == "bach_bourree":
        return voice == "lead" and rise >= 3 and apex
    if pattern == "bach_fuga":
        return voice == "lead" and rise >= 3 and apex
    if pattern == "bach_gigue":
        return voice == "lead" and ((apex and (event.accent or abs(beat) < 1e-6)) or (event.accent and rise >= 3))
    if pattern == "bach_chaconne":
        return voice == "lead" and event.accent and (apex or (phrase is not None and onset >= phrase.end - 1))
    if pattern == "elegiaque":
        return voice == "lead" and event.accent
    if pattern == "study":
        rally = ctx.mood(event.bar) == "rally"
        return voice == "lead" and (event.accent or (rally and apex and rise > 0))
    if pattern == "mozart_var":
        return voice == "lead" and rise >= 3 and apex
    if pattern == "galop":
        return voice == "lead" and ctx.mood(event.bar) == "rally" and abs(beat) < 1e-6 and rise >= 1
    if pattern == "preludio":
        return voice == "lead" and (event.duration_beats >= 0.9 or int(round(beat * 4)) % 8 == 0) and level >= 0.85
    if pattern == "thumb_cantabile":
        return voice == "low" and apex and rise > 0
    if pattern == "tremolo":
        return voice == "low" and event.duration_beats >= 0.75 and level >= 0.999
    if pattern in {"choro", "polca"}:
        return voice == "lead" and (event.accent or apex)
    if pattern == "hemiola":
        return voice == "lead" and event.accent
    if pattern == "vals":
        return voice == "lead" and event.accent and eighth == 4
    if pattern == "villa_pattern":
        return voice == "lead" and (eighth in {0, 3, 6} or apex)
    if pattern == "etude1":
        slot = int(round(beat * 4))
        return voice == "lead" and slot in {7, 9}
    if pattern == "etude11":
        return voice == "lead" and abs(beat - round(beat)) < 1e-6 and apex
    if pattern == "sarabande":
        return voice == "lead" and (event.accent or abs(beat - 1.0) < 1e-6)
    if pattern == "brouwer_etude":
        return voice == "lead" and event.accent
    if pattern == "elogio_pizz":
        return voice == "lead" and event.accent and event.staccato
    return False


@dataclass
class _Unit:
    score: float
    pattern: str
    bar: int
    phrase_key: int
    voice: str
    indexes: list[int]
    ceiling: int


def _phrase_key(phrase) -> int:
    if phrase is None:
        return -1
    return phrase.start


def _snap_ceiling(profile: PatternWaveProfile, price: float, pattern: str) -> int:
    if pattern == "elogio_pizz" and price < 0.25:
        return int(profile.snap_calm or 72)
    calm = profile.snap_calm if profile.snap_calm is not None else 66
    wide = profile.snap_wide if profile.snap_wide is not None else calm
    return int(round(calm + price * (wide - calm)))


def _snapped_velocity(score: float, ceiling: int) -> int:
    clipped = min(1.0, max(0.70, score))
    return int(round(66 + (ceiling - 66) * ((clipped - 0.70) / 0.30)))


def _collect_units(ctx, voices: dict[str, list[NoteEvent]], patterns, waves) -> list[_Unit]:
    units: list[_Unit] = []
    tresillo: dict[int, _Unit] = {}
    for voice, events in voices.items():
        for index, event in enumerate(events):
            if event.midi is None or event.velocity is None or event.tie_stop:
                continue
            if ctx.kind_at.get(event.bar, "phrase") in _PEDAL:
                continue
            wave = waves.get(event.bar)
            if wave is None:
                continue
            pattern = _pattern_at(ctx, event.bar, patterns)
            profile = profile_for(ctx.ensemble, pattern)
            if profile is None or profile.snap_wide is None:
                continue
            onset = _onset(event, ctx.epb)
            phrase = _phrase_at(ctx, onset)
            level = _level_at(wave, event.bar, _k_of(event), ctx.epb)
            if not _is_target(ctx, pattern, event, voice, phrase, onset, level):
                continue
            breath = phrase_curve(phrase, onset)
            score = 0.70 * level + 0.30 * breath
            if score < 0.70 - 1e-9:
                continue
            if pattern == "tremolo":
                quarters = 4 if ctx.epb >= 8 else 3
                offsets = _TREMOLO_QUARTER_OFFSETS.get(quarters, _TREMOLO_QUARTER_OFFSETS[3])
                quarter = min(quarters - 1, int(math.floor(event.beat + 1e-9)))
                if offsets[quarter] != max(offsets):
                    continue
            ceiling = _snap_ceiling(profile, wave.alpha_price, pattern)
            if pattern == "villa_pattern" and int(round(event.beat * 2)) in {0, 3, 6}:
                existing = tresillo.get(event.bar)
                if existing is None:
                    tresillo[event.bar] = _Unit(score, pattern, event.bar, _phrase_key(phrase), voice, [index], ceiling)
                else:
                    existing.indexes.append(index)
                    existing.score = max(existing.score, score)
                continue
            if pattern == "etude1":
                units.append(_Unit(score, pattern, event.bar, _phrase_key(phrase), voice, [index], ceiling))
                continue
            units.append(_Unit(score, pattern, event.bar, _phrase_key(phrase), voice, [index], ceiling))
    units.extend(tresillo.values())
    # Etude 1 keeps a single sung note per bar: index 9, or the higher pitch.
    chosen_bars: dict[int, _Unit] = {}
    kept: list[_Unit] = []
    for unit in units:
        if unit.pattern != "etude1":
            kept.append(unit)
            continue
        events = voices[unit.voice]
        event = events[unit.indexes[0]]
        slot = int(round(event.beat * 4))
        current = chosen_bars.get(unit.bar)
        better = current is None
        if current is not None:
            other = events[current.indexes[0]]
            other_slot = int(round(other.beat * 4))
            if slot == 9 and (event.midi or 0) >= (other.midi or 0):
                better = True
            elif other_slot != 9 and (event.midi or 0) > (other.midi or 0):
                better = True
            elif other_slot != 9 and slot == 9:
                better = True
        if better:
            chosen_bars[unit.bar] = unit
    kept.extend(chosen_bars.values())
    return kept


def _budget(ctx, pattern: str, wave: _Wave, voices, start: int, end: int) -> int:
    profile = profile_for(ctx.ensemble, pattern)
    if profile is None or profile.snap_wide is None:
        return 0
    if wave.alpha_price < 0.25:
        return 1 if pattern == "elogio_pizz" else 0
    singing = "low" if pattern in {"thumb_cantabile", "tremolo"} else "lead"
    events = voices[singing]
    if pattern == "tremolo":
        count = len({int(math.floor(event.beat + 1e-9)) for event in events if start <= event.bar < end and event.midi is not None and not event.tie_stop and event.duration_beats >= 0.75})
    else:
        count = sum(1 for event in events if start <= event.bar < end and event.midi is not None and not event.tie_stop)
    return min(profile.max_units_per_sec, max(1, int(math.floor(0.045 * count))))


def _select_units(ctx, units: list[_Unit], waves, voices) -> list[_Unit]:
    by_section: dict[tuple[int, int, str], list[_Unit]] = {}
    for unit in units:
        wave = waves.get(unit.bar)
        if wave is None:
            continue
        by_section.setdefault((wave.start, wave.end, unit.pattern), []).append(unit)
    chosen: list[_Unit] = []
    for (start, end, pattern), group in by_section.items():
        wave = waves[group[0].bar]
        profile = profile_for(ctx.ensemble, pattern)
        if profile is None:
            continue
        per_phrase: dict[int, list[_Unit]] = {}
        for unit in group:
            per_phrase.setdefault(unit.phrase_key, []).append(unit)
        limited: list[_Unit] = []
        for phrase_units in per_phrase.values():
            phrase_units.sort(key=lambda item: (-item.score, item.bar, item.indexes[0]))
            limited.extend(phrase_units[: max(0, profile.max_units_per_phrase)])
        limit = _budget(ctx, pattern, wave, voices, start, end)
        limited.sort(key=lambda item: (-item.score, item.bar, item.indexes[0]))
        chosen.extend(limited[:limit])
    return chosen


def _apply_unit(ctx, unit: _Unit, voices, waves) -> None:
    velocity = _snapped_velocity(unit.score, unit.ceiling)
    velocity = max(66, min(unit.ceiling, velocity))
    lead = voices["lead"]
    support = voices["support"]
    low = voices["low"]
    events = voices[unit.voice]
    pattern = unit.pattern
    if pattern == "tremolo":
        event = events[unit.indexes[0]]
        quarter = int(math.floor(event.beat + 1e-9))
        for index in _attacks(low, event.bar):
            if int(math.floor(low[index].beat + 1e-9)) == quarter and low[index].duration_beats >= 0.75:
                _put(low, index, velocity)
        fills = [
            index
            for index in _attacks(lead, event.bar)
            if int(math.floor(lead[index].beat + 1e-9)) == quarter and lead[index].duration_beats <= 0.3
        ]
        fills.sort(key=lambda index: lead[index].beat)
        for slot, index in enumerate(fills[:4]):
            if slot == 1:
                _put(lead, index, min(velocity - 3, 69))
            elif slot == 2:
                _put(lead, index, min(63, velocity - 4))
            else:
                _put(lead, index, min(61, velocity - 6))
        for index in _attacks(support, event.bar):
            if int(math.floor(support[index].beat + 1e-9)) == quarter:
                _put(support, index, min(63, support[index].velocity or 63))
        return
    if pattern == "etude1":
        event = events[unit.indexes[0]]
        _put(lead, unit.indexes[0], velocity)
        for index in _attacks(lead, event.bar):
            if index != unit.indexes[0]:
                _put(lead, index, min(63, velocity - 5))
        for index in _attacks(low, event.bar):
            _put(low, index, min(61, velocity - 6))
        return
    if pattern == "etude11":
        event = events[unit.indexes[0]]
        quarter = int(math.floor(event.beat + 1e-9))
        for index in _attacks(lead, event.bar):
            slot = int(round((lead[index].beat - quarter) * 6))
            if int(math.floor(lead[index].beat + 1e-9)) != quarter:
                continue
            if abs(lead[index].beat - quarter) < 1e-6:
                _put(lead, index, velocity, accent=True)
            elif slot == 3 or abs(lead[index].beat - (quarter + 0.5)) < 1e-6:
                _put(lead, index, min(60, velocity - 10), accent=False)
        for index in _attacks(low, event.bar):
            if int(math.floor(low[index].beat + 1e-9)) == quarter:
                _put(low, index, min(62, velocity - 6), accent=True)
        return
    if pattern == "elogio_pizz":
        event = events[unit.indexes[0]]
        if velocity >= 72:
            low_level = min(70, max(68, velocity - 6))
            sup_level = min(66, max(64, velocity - 10))
        else:
            low_level = min(63, velocity - 4)
            sup_level = min(63, low_level - 2)
        if low_level >= velocity:
            low_level = velocity - 2
        if sup_level >= low_level:
            sup_level = max(18, low_level - 2)
        when = round(event.beat, 4)
        _put(lead, unit.indexes[0], velocity)
        for index in _attacks(low, event.bar):
            if abs(low[index].beat - event.beat) < 1e-6 or round(low[index].beat, 4) == when:
                if low[index].accent or low[index].staccato:
                    _put(low, index, low_level)
        for index in _attacks(support, event.bar):
            if abs(support[index].beat - event.beat) < 1e-6:
                if support[index].accent or support[index].staccato:
                    _put(support, index, sup_level)
        return
    if pattern == "preludio":
        event = events[unit.indexes[0]]
        _put(lead, unit.indexes[0], min(68, velocity))
        for index in _attacks(lead, event.bar):
            if index == unit.indexes[0]:
                continue
            slot = int(round(lead[index].beat * 4)) % 8
            if slot == 6 or lead[index].duration_beats <= 0.6:
                _put(lead, index, min(62, velocity - 4))
        return
    for index in unit.indexes:
        flags = {"accent": True} if pattern == "etude11" else {}
        _put(events, index, velocity, **flags)


def _apply_snaps(ctx, lead, support, low, patterns, waves) -> None:
    voices = {"lead": lead, "support": support, "low": low}
    units = _collect_units(ctx, voices, patterns, waves)
    for unit in _select_units(ctx, units, waves, voices):
        _apply_unit(ctx, unit, voices, waves)


def _pitched(events: list[NoteEvent], bar: int) -> list[int]:
    return [index for index, event in enumerate(events) if event.bar == bar and event.midi is not None and event.velocity is not None]


def _lead_peak(events: list[NoteEvent], indexes: list[int]) -> tuple[int, int, int] | None:
    lead = [events[index] for index in indexes if not events[index].tie_stop]
    if not lead:
        lead = [events[index] for index in indexes]
    if not lead:
        return None
    ordered = sorted(lead, key=lambda event: (event.beat, event.midi or 0))
    peak = max(event.velocity or 0 for event in ordered)
    last = ordered[-1].velocity or 0
    first = ordered[0].velocity or 0
    return peak, last, first


def shape_intro_region(lead, support, low, v_join: int) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Join bar crest cap, then pre-join bars aimed at that bar's first lead note."""
    lead = list(lead)
    support = list(support)
    low = list(low)
    bars = sorted({event.bar for event in (*lead, *support, *low) if event.midi is not None})
    if not bars:
        return lead, support, low
    last = bars[-1]
    groups = {
        "lead": _pitched(lead, last),
        "support": _pitched(support, last),
        "low": _pitched(low, last),
    }
    stats = _lead_peak(lead, groups["lead"])
    if stats is None:
        stats = _lead_peak(low, groups["low"]) or (v_join, v_join, v_join)
    written_max, written_last, _first = stats
    for voice, events in (("lead", lead), ("support", support), ("low", low)):
        for index in groups[voice]:
            written = events[index].velocity or 0
            _put(events, index, shape_join_velocity(written, written_max, written_last, v_join))
    first_lead = [
        lead[index]
        for index in _pitched(lead, last)
        if not lead[index].tie_stop
    ]
    first_lead.sort(key=lambda event: (event.beat, event.midi or 0))
    v_open = first_lead[0].velocity if first_lead else v_join
    earlier = [bar for bar in bars if bar < last]
    targets = prejoin_envelope(len(earlier), v_open or v_join)
    for bar, target in zip(earlier, targets):
        lead_indexes = _pitched(lead, bar)
        peak_stats = _lead_peak(lead, lead_indexes)
        peak = peak_stats[0] if peak_stats else target
        for events in (lead, support, low):
            for index in _pitched(events, bar):
                written = events[index].velocity or 0
                _put(events, index, shape_prejoin_velocity(written, peak, target))
    return lead, support, low


def shape_outro_region(lead, support, low, v_close: int) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    lead = list(lead)
    support = list(support)
    low = list(low)
    bars = sorted({event.bar for event in (*lead, *support, *low) if event.midi is not None})
    for index, bar in enumerate(bars):
        target = morendo_peak(v_close, index, len(bars))
        lead_indexes = _pitched(lead, bar)
        peak_stats = _lead_peak(lead, lead_indexes)
        peak = peak_stats[0] if peak_stats else target
        for events in (lead, support, low):
            for note_index in _pitched(events, bar):
                written = events[note_index].velocity or 0
                shifted = int(round(target - (peak - written)))
                _put(events, note_index, max(JOIN_FLOOR, min(63, shifted)))
    return lead, support, low


def _bright(ctx, bar: int) -> bool:
    mood = ctx.mood(bar)
    return mood in {"rally", "volatile"}


def _apply_stabs(ctx, lead, support, low, trailing: list[int]) -> None:
    last = trailing[-1] if trailing else None
    for voice, events in (("lead", lead), ("support", support), ("low", low)):
        for index, event in enumerate(events):
            if event.midi is None or ctx.kind_at.get(event.bar, "phrase") not in _PEDAL:
                continue
            stabbed = event.staccato and event.accent
            villa_stab = (
                ctx.ensemble == "villa"
                and last is not None
                and event.bar == last
                and event.accent
                and _bright(ctx, event.bar)
            )
            if stabbed or villa_stab:
                _put(events, index, _STAB[voice])


def _sync_ties(events: list[NoteEvent]) -> list[NoteEvent]:
    order = sorted(range(len(events)), key=lambda index: (events[index].bar, events[index].beat, events[index].tie_stop))
    chain: dict[int, int] = {}
    updated = list(events)
    for index in order:
        event = updated[index]
        if event.midi is None or event.velocity is None:
            continue
        if not event.tie_stop:
            if event.tie_start:
                chain[event.midi] = event.velocity
            else:
                chain.pop(event.midi, None)
            continue
        source = chain.get(event.midi)
        if source is not None and event.velocity != source:
            updated[index] = replace(event, velocity=source)
        if not event.tie_start:
            chain.pop(event.midi, None)
    return updated


def _take(events: list[NoteEvent], bars: set[int]) -> tuple[list[NoteEvent], list[NoteEvent]]:
    kept = [event for event in events if event.bar not in bars]
    moved = [event for event in events if event.bar in bars]
    return kept, moved


def _merge(kept: list[NoteEvent], moved: list[NoteEvent]) -> list[NoteEvent]:
    return kept + moved


def apply_guitar_wave(ctx, lead, support, low, patterns: list[str] | None = None, relaxed: set[int] | None = None):
    """Rebase pattern velocities onto the volume wave. Replaces `_shape_dynamics`."""
    del relaxed
    patterns = list(patterns or [])
    lead = list(lead)
    support = list(support)
    low = list(low)
    volumes = resolve_bar_volumes(ctx)
    waves = _build_waves(ctx, volumes)
    _assign_body(ctx, lead, support, low, patterns, waves)
    _order_voices(ctx, lead, support, low, patterns)
    _apply_snaps(ctx, lead, support, low, patterns, waves)
    leading, trailing = _pedal_regions(ctx)
    if leading:
        body = leading[-1] + 1
        if body < ctx.bars and body in waves:
            v_join = _hat_at(ctx, waves, patterns, body, 0.0)
        else:
            v_join = 48
        kept_l, moved_l = _take(lead, set(leading))
        kept_s, moved_s = _take(support, set(leading))
        kept_b, moved_b = _take(low, set(leading))
        moved_l, moved_s, moved_b = shape_intro_region(moved_l, moved_s, moved_b, v_join)
        lead, support, low = _merge(kept_l, moved_l), _merge(kept_s, moved_s), _merge(kept_b, moved_b)
    if trailing:
        body = trailing[0] - 1
        if body >= 0 and body in waves:
            v_close = _hat_at(ctx, waves, patterns, body, float(max(0, ctx.epb - 1)))
        else:
            v_close = 48
        kept_l, moved_l = _take(lead, set(trailing))
        kept_s, moved_s = _take(support, set(trailing))
        kept_b, moved_b = _take(low, set(trailing))
        moved_l, moved_s, moved_b = shape_outro_region(moved_l, moved_s, moved_b, v_close)
        lead, support, low = _merge(kept_l, moved_l), _merge(kept_s, moved_s), _merge(kept_b, moved_b)
    _apply_stabs(ctx, lead, support, low, trailing)
    return _sync_ties(lead), _sync_ties(support), _sync_ties(low)
