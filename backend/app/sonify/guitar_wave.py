"""Affine volume wave for classical guitar.

The smoothed tide is one center C per bar. Every sounding note keeps the
velocity it was written with, shifted by round(C) - 64. Lead, bass, and
inner voices in the same bar share that center, so a swell, an accent, or a
tremolo step survives as the MIDI difference that was already on the note.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from app.sonify.dynamics import percentile
from app.sonify.guitar import _PEDAL, _TREMOLO_QUARTER_OFFSETS
from app.sonify.model import NoteEvent

BAND_VOLUME = {"p": 1.0, "mp": 2.0, "mf": 4.0, "f": 8.0}
BAND_LEVEL = {"p": 0.15, "mp": 0.40, "mf": 0.65, "f": 0.90}
WRITTEN_CENTER = 64
D_LO = -16
D_HI = 8
DEVIATION = D_HI - D_LO
STEP = 4.0
C_WHISPER = 27.0
OUTRO_END = 23.0
PEDAL_FLOOR = 20
SPEECH = 22
WARM_LIMIT = 63
_STAB = {"lead": 70, "low": 66, "support": 62}


@dataclass(frozen=True)
class PatternWaveProfile:
    floor_calm: int
    floor_wide: int
    ceil_calm: int
    ceil_wide: int
    snap_calm: int | None
    snap_wide: int | None
    max_units_per_phrase: int
    max_units_per_sec: int
    snap_targets: str
    d_lo: int = D_LO
    d_hi: int = D_HI


def _profile(
    floor_calm: int,
    floor_wide: int,
    ceil_calm: int,
    ceil_wide: int,
    snap_calm: int | None,
    snap_wide: int | None,
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
        per_phrase,
        per_sec,
        targets,
    )


# Exactly the 28 (ensemble, pattern) rows. Pedal is a frame path, not a 29th row.
PROFILES: dict[tuple[str, str], PatternWaveProfile] = {
    ("bach", "bach_sarabande"): _profile(26, 30, 56, 62, None, None, 0, 0, "none"),
    ("bach", "bach_gavotte"): _profile(28, 32, 58, 62, 66, 68, 1, 2, "gavotte"),
    ("bach", "bach_bourree"): _profile(28, 32, 58, 63, 66, 68, 1, 3, "bourree"),
    ("bach", "bach_fuga"): _profile(28, 32, 58, 63, 66, 68, 1, 2, "fuga"),
    ("bach", "bach_gigue"): _profile(28, 32, 58, 63, 68, 70, 1, 3, "gigue"),
    ("bach", "bach_chaconne"): _profile(26, 30, 58, 63, 68, 70, 1, 3, "chaconne"),
    ("classic", "cantabile"): _profile(24, 28, 54, 58, None, None, 0, 0, "none"),
    ("classic", "elegiaque"): _profile(24, 28, 56, 62, 66, 68, 1, 2, "appoggiatura"),
    ("classic", "study"): _profile(26, 30, 56, 63, 68, 70, 1, 2, "study"),
    ("classic", "mozart_var"): _profile(26, 30, 56, 62, 66, 68, 1, 2, "apex_rise"),
    ("classic", "galop"): _profile(28, 32, 58, 63, 68, 70, 1, 3, "galop"),
    ("barrios", "preludio"): _profile(26, 30, 56, 62, 66, 68, 1, 2, "canto"),
    ("barrios", "andante"): _profile(24, 28, 54, 60, None, None, 0, 0, "none"),
    ("barrios", "thumb_cantabile"): _profile(26, 30, 56, 62, 66, 68, 1, 2, "thumb"),
    ("barrios", "tremolo"): _profile(28, 32, 58, 63, 68, 72, 1, 2, "tremolo"),
    ("barrios", "choro"): _profile(28, 32, 58, 63, 70, 74, 1, 4, "offbeat"),
    ("barrios", "polca"): _profile(28, 32, 58, 63, 70, 72, 1, 3, "offbeat"),
    ("barrios", "hemiola"): _profile(28, 32, 58, 63, 70, 74, 1, 4, "hemiola"),
    ("barrios", "vals"): _profile(26, 30, 58, 62, 68, 72, 1, 3, "vals"),
    ("villa", "chord_melody"): _profile(24, 28, 54, 60, None, None, 0, 0, "none"),
    ("villa", "thumb_cantabile"): _profile(28, 32, 58, 63, 68, 70, 1, 2, "thumb"),
    ("villa", "villa_pattern"): _profile(26, 30, 58, 63, 68, 72, 1, 3, "tresillo"),
    ("villa", "etude1"): _profile(28, 32, 58, 63, 68, 70, 1, 2, "etude1"),
    ("villa", "etude11"): _profile(28, 32, 58, 63, 70, 74, 1, 3, "etude11"),
    ("brouwer", "noviembre"): _profile(22, 26, 52, 58, None, None, 0, 0, "none"),
    ("brouwer", "sarabande"): _profile(24, 28, 56, 62, 68, 72, 1, 2, "sarabande"),
    ("brouwer", "brouwer_etude"): _profile(24, 28, 58, 63, 68, 72, 1, 3, "tumbao"),
    ("brouwer", "elogio_pizz"): _profile(24, 28, 56, 62, 72, 76, 1, 4, "slap"),
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


def _reflect_index(index: int, length: int) -> int:
    """Reflect across the first and last samples so a window always has 5 taps."""
    if length <= 1:
        return 0
    guard = 0
    while index < 0 or index >= length:
        if index < 0:
            index = -index
        else:
            last = length - 1
            index = last - (index - last)
        guard += 1
        if guard > 8:
            return min(length - 1, max(0, index))
    return index


def smooth_ell(volumes: list[float], start: int, end: int) -> list[float]:
    """Equal-weight 5-point mean of ln(1 + v) on [start, end)."""
    if end <= start:
        return []
    raw = [math.log1p(max(0.0, float(volumes[bar]))) for bar in range(start, end)]
    smoothed: list[float] = []
    length = len(raw)
    for index in range(length):
        total = 0.0
        for offset in range(-2, 3):
            total += raw[_reflect_index(index + offset, length)]
        smoothed.append(total / 5.0)
    return smoothed


def u_raw_from(smoothed: list[float], bands: list[str]) -> list[float]:
    """Min–max the smoothed tide, or the printed band when the section is flat."""
    if not smoothed:
        return []
    low = min(smoothed)
    high = max(smoothed)
    if high - low <= 1e-6:
        return [BAND_LEVEL.get(band, 0.65) for band in bands]
    span = high - low
    return [(value - low) / span for value in smoothed]


def lipschitz(levels: list[float], delta: float) -> list[float]:
    """Smallest envelope above `levels` whose adjacent bars differ by at most `delta`."""
    if not levels:
        return []
    if delta <= 0:
        peak = max(levels)
        return [min(1.0, max(0.0, peak)) for _ in levels]
    shaped: list[float] = []
    last = len(levels) - 1
    for index in range(len(levels)):
        lifted = max(levels[other] - delta * abs(index - other) for other in range(last + 1))
        shaped.append(min(1.0, max(0.0, lifted)))
    return shaped


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
    ceiling = min(WARM_LIMIT, ceiling)
    if ceiling < floor:
        ceiling = floor
    return floor, ceiling


def gain(v_floor: int, v_ceil: int) -> float:
    """M = 1 on every locked window, because each one is at least 30 wide."""
    span = v_ceil - v_floor
    if span <= 0:
        return 0.0
    return min(1.0, span / float(DEVIATION))


def tide_bounds(v_floor: int, v_ceil: int, profile: PatternWaveProfile) -> tuple[float, float, float]:
    opened = gain(v_floor, v_ceil)
    c_lo = v_floor - opened * profile.d_lo
    c_hi = v_ceil - opened * profile.d_hi
    return opened, c_lo, c_hi


def shape_u(raw: list[float], c_lo: float, c_hi: float) -> list[float]:
    tide = c_hi - c_lo
    if tide <= 1e-9:
        return [0.0 for _ in raw]
    return lipschitz(raw, STEP / tide)


def centers_from(c_lo: float, c_hi: float, levels: list[float]) -> list[float]:
    tide = c_hi - c_lo
    return [c_lo + level * tide for level in levels]


def round_center(center: float) -> int:
    """Python 3 half-to-even, once per bar, before the written offset is added."""
    return int(round(center))


def affine_raw(center: float, written: int) -> int:
    """round(C) + (V_written - 64). Not round(C + d)."""
    return round_center(center) + (int(written) - WRITTEN_CENTER)


def intro_centers(count: int, body: float) -> list[float]:
    """Leading pedal bars. One bar joins the body; a longer ramp steps by at most 4."""
    if count <= 0:
        return []
    if count == 1:
        return [float(body)]
    raw = [C_WHISPER + (body - C_WHISPER) * index / (count - 1) for index in range(count)]
    raw[-1] = float(body)
    for index in range(count - 2, -1, -1):
        low = raw[index + 1] - STEP
        high = raw[index + 1] + STEP
        raw[index] = min(high, max(low, raw[index]))
    return raw


def outro_centers(count: int, body: float) -> list[float]:
    """The seam stays on the last body center. Later bars fall by at most 4, down to 23."""
    if count <= 0:
        return []
    values = [float(body)]
    for index in range(1, count):
        decayed = max(OUTRO_END, body - STEP * index)
        previous = values[-1]
        values.append(min(previous, max(decayed, previous - STEP)))
    return values


def _line(start: float, end: float, count: int) -> list[float]:
    if count <= 1:
        return [end] if count == 1 else []
    return [start + (end - start) * index / (count - 1) for index in range(count)]


def _speech_center(written: int) -> float:
    """Lowest center that stores the softest note at SPEECH, before humanize."""
    return float(SPEECH - (int(written) - WRITTEN_CENTER))


def _clears(centers: list[float], floors: list[float | None]) -> bool:
    return all(floor is None or center + 1e-6 >= floor for center, floor in zip(centers, floors))


def fit_intro(centers: list[float], floors: list[float | None]) -> list[float]:
    """Keep the seam. Raise a straight ramp so earlier bars still speak.

    A per-bar lift cancels round(C) wherever the softest note is under SPEECH,
    so several intro bars share one chord. The line spreads that rise instead.
    The last bar stays on the body center. If the body itself is below the
    speech line, every bar stays on that center. The old whisper ramp would
    keep falling through notes that no longer speak.
    """
    count = len(centers)
    if count <= 1 or _clears(centers, floors):
        return list(centers)
    end = centers[-1]
    start = centers[0]
    span = count - 1
    for index, floor in enumerate(floors[:-1]):
        if floor is None:
            continue
        if index == 0:
            start = max(start, floor)
            continue
        start = max(start, (floor * span - end * index) / (span - index))
    start = max(start, end - STEP * span)
    if start > end + 1e-6:
        return [end] * count
    line = _line(start, end, count)
    if _clears(line, [*floors[:-1], None]):
        return line
    if any(floor is not None and floor > end + 1e-6 for floor in floors):
        return [end] * count
    return list(centers)


def fit_outro(centers: list[float], floors: list[float | None]) -> list[float]:
    """Keep the seam. Ease the fall so later bars still speak.

    Written 64 still reaches 23. A softer note raises the ending just enough
    that the straight fall stays on its speech line, never steeper than 4.
    If the body itself is below that line, every bar stays on the body center
    instead of decaying toward 23.
    """
    count = len(centers)
    if count <= 1 or _clears(centers, floors):
        return list(centers)
    body = centers[0]
    end = min(centers[-1], body)
    span = count - 1
    for index, floor in enumerate(floors):
        if floor is None or index == 0:
            continue
        end = max(end, body + (floor - body) * span / index)
    end = min(body, max(end, body - STEP * span))
    line = _line(body, end, count)
    if _clears(line, floors):
        return line
    if any(floor is not None and floor > body + 1e-6 for floor in floors):
        return [body] * count
    return list(centers)


def _flat_phrase(phrase) -> bool:
    if phrase is None or not phrase.runs:
        return True
    return phrase.rise <= 0 or len({run.midi for run in phrase.runs}) <= 1


def phrase_curve(phrase, t: float) -> float:
    """Cosine breath: 0 at the edges, 1 at the apex. Ranking only; it is not added to V."""
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


@dataclass
class _Wave:
    start: int
    end: int
    pattern: str
    levels: list[float]
    smoothed: list[float]
    alpha_price: float
    alpha_vol: float
    alpha_warm: float
    v_floor: int
    v_ceil: int
    gain: float
    c_lo: float
    c_hi: float
    centers: list[float]


@dataclass
class _Placed:
    center: float
    rounded: int
    pedal: bool
    v_floor: int
    v_ceil: int
    wave: _Wave | None


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


def _contiguous(bars: list[int]) -> list[tuple[int, int]]:
    if not bars:
        return []
    spans: list[tuple[int, int]] = []
    start = bars[0]
    previous = bars[0]
    for bar in bars[1:]:
        if bar == previous + 1:
            previous = bar
            continue
        spans.append((start, previous + 1))
        start = bar
        previous = bar
    spans.append((start, previous + 1))
    return spans


def _body_spans(ctx, pedal: set[int]) -> list[tuple[object, int, int]]:
    spans: list[tuple[object, int, int]] = []
    covered: set[int] = set()
    for section in ctx.sections:
        if getattr(section, "kind", None) in _PEDAL:
            continue
        if section.end <= section.start:
            continue
        bars = [bar for bar in range(section.start, min(ctx.bars, section.end)) if bar not in pedal]
        for start, end in _contiguous(bars):
            spans.append((section, start, end))
            covered.update(range(start, end))
    leftover = [bar for bar in range(ctx.bars) if bar not in pedal and bar not in covered]
    for start, end in _contiguous(leftover):
        spans.append((None, start, end))
    return spans


def _section_pattern(ctx, patterns: list[str], start: int, end: int) -> str:
    for bar in range(start, end):
        pattern = _pattern_at(ctx, bar, patterns)
        if profile_for(ctx.ensemble, pattern) is not None:
            return pattern
    return _pattern_at(ctx, start, patterns)


def _build_waves(ctx, volumes: list[float], patterns: list[str], pedal: set[int]) -> dict[int, _Wave]:
    found: dict[int, _Wave] = {}
    for section, start, end in _body_spans(ctx, pedal):
        if end <= start:
            continue
        pattern = _section_pattern(ctx, patterns, start, end)
        profile = profile_for(ctx.ensemble, pattern)
        if profile is None:
            continue
        smoothed = smooth_ell(volumes, start, end)
        bands = [ctx.band(bar) for bar in range(start, end)]
        raw = u_raw_from(smoothed, bands)
        price = alpha_price(_rel_span(ctx, section))
        volume = alpha_volume(smoothed, price)
        inward = bool(section is not None and (getattr(section, "trio", False) or getattr(section, "bridge", False)))
        opened = warm_alpha(price, volume, inward=inward)
        v_floor, v_ceil = window_for(profile, opened)
        opened_gain, c_lo, c_hi = tide_bounds(v_floor, v_ceil, profile)
        levels = shape_u(raw, c_lo, c_hi)
        centers = centers_from(c_lo, c_hi, levels)
        wave = _Wave(
            start,
            end,
            pattern,
            levels,
            smoothed,
            price,
            volume,
            opened,
            v_floor,
            v_ceil,
            opened_gain,
            c_lo,
            c_hi,
            centers,
        )
        for bar in range(start, end):
            found[bar] = wave
    return found


def _place_centers(ctx, patterns: list[str], volumes: list[float]) -> tuple[dict[int, _Placed], dict[int, _Wave], list[int], list[int]]:
    leading, trailing = _pedal_regions(ctx)
    pedal = {bar for bar in range(ctx.bars) if ctx.kind_at.get(bar, "phrase") in _PEDAL}
    waves = _build_waves(ctx, volumes, patterns, pedal)
    placed: dict[int, _Placed] = {}
    for bar, wave in waves.items():
        index = bar - wave.start
        center = wave.centers[index]
        placed[bar] = _Placed(center, round_center(center), False, wave.v_floor, wave.v_ceil, wave)

    def body_center(bar: int, fallback: float) -> float:
        found = placed.get(bar)
        if found is not None:
            return found.center
        return fallback

    if leading:
        join = leading[-1] + 1
        body = body_center(join, C_WHISPER) if join < ctx.bars else C_WHISPER
        for bar, center in zip(leading, intro_centers(len(leading), body)):
            placed[bar] = _Placed(center, round_center(center), True, PEDAL_FLOOR, WARM_LIMIT, None)
    if trailing:
        join = trailing[0] - 1
        body = body_center(join, OUTRO_END) if join >= 0 else OUTRO_END
        for bar, center in zip(trailing, outro_centers(len(trailing), body)):
            placed[bar] = _Placed(center, round_center(center), True, PEDAL_FLOOR, WARM_LIMIT, None)
    for bar in range(ctx.bars):
        if bar in placed:
            continue
        if bar in pedal:
            placed[bar] = _Placed(C_WHISPER, round_center(C_WHISPER), True, PEDAL_FLOOR, WARM_LIMIT, None)
        else:
            placed[bar] = _Placed(float(WRITTEN_CENTER), WRITTEN_CENTER, False, PEDAL_FLOOR, WARM_LIMIT, None)
    return placed, waves, leading, trailing


def _sounding(events: list[NoteEvent], bar: int) -> list[int]:
    return [
        index
        for index, event in enumerate(events)
        if event.bar == bar and event.midi is not None and event.velocity is not None and not event.tie_stop
    ]


def _put(events: list[NoteEvent], index: int, velocity: int) -> None:
    events[index] = replace(events[index], velocity=int(velocity))


def _apply_affine(ctx, voices: dict[str, list[NoteEvent]], placed: dict[int, _Placed]) -> None:
    for bar in range(ctx.bars):
        spot = placed[bar]
        raws: dict[tuple[str, int], int] = {}
        for voice, events in voices.items():
            for index in _sounding(events, bar):
                raws[(voice, index)] = spot.rounded + (int(events[index].velocity or 0) - WRITTEN_CENTER)
        if spot.pedal:
            for (voice, index), raw in raws.items():
                _put(voices[voice], index, min(WARM_LIMIT, raw))
            continue
        for (voice, index), raw in raws.items():
            _put(voices[voice], index, max(spot.v_floor, min(spot.v_ceil, raw)))


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


def _u_at(wave: _Wave, bar: int) -> float:
    index = min(len(wave.levels) - 1, max(0, bar - wave.start))
    return wave.levels[index]


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
            if wave.alpha_price < 0.25 and pattern != "elogio_pizz":
                continue
            onset = _onset(event, ctx.epb)
            phrase = _phrase_at(ctx, onset)
            level = _u_at(wave, event.bar)
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
            units.append(_Unit(score, pattern, event.bar, _phrase_key(phrase), voice, [index], ceiling))
    units.extend(tresillo.values())
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
        count = len(
            {
                int(math.floor(event.beat + 1e-9))
                for event in events
                if start <= event.bar < end and event.midi is not None and not event.tie_stop and event.duration_beats >= 0.75
            }
        )
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


def _apply_snaps(ctx, voices, patterns, waves) -> None:
    """Overwrite only the chosen attacks. Companions stay on the clamped affine value."""
    units = _collect_units(ctx, voices, patterns, waves)
    for unit in _select_units(ctx, units, waves, voices):
        velocity = _snapped_velocity(unit.score, unit.ceiling)
        velocity = max(66, min(unit.ceiling, velocity))
        events = voices[unit.voice]
        for index in unit.indexes:
            _put(events, index, velocity)


def _bright(ctx, bar: int) -> bool:
    mood = ctx.mood(bar)
    return mood in {"rally", "volatile"}


def _apply_stabs(ctx, voices, trailing: list[int]) -> None:
    last = trailing[-1] if trailing else None
    for voice, events in voices.items():
        for index, event in enumerate(events):
            if event.midi is None or event.velocity is None:
                continue
            if ctx.kind_at.get(event.bar, "phrase") not in _PEDAL:
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


def _bar_floors(voices: dict[str, list[NoteEvent]], bars: list[int]) -> list[float | None]:
    floors: list[float | None] = []
    for bar in bars:
        written = [
            int(event.velocity or 0)
            for events in voices.values()
            for event in events
            if event.bar == bar and event.midi is not None and event.velocity is not None and not event.tie_stop
        ]
        floors.append(_speech_center(min(written)) if written else None)
    return floors


def _retarget(placed: dict[int, _Placed], bars: list[int], centers: list[float]) -> None:
    for bar, center in zip(bars, centers):
        spot = placed[bar]
        placed[bar] = _Placed(float(center), round_center(center), True, spot.v_floor, spot.v_ceil, None)


def _fit_pedal_speech(
    voices: dict[str, list[NoteEvent]],
    placed: dict[int, _Placed],
    leading: list[int],
    trailing: list[int],
) -> None:
    """One line per pedal region, so speech does not erase the tide or the seam."""
    if len(leading) > 1:
        _retarget(placed, leading, fit_intro([placed[bar].center for bar in leading], _bar_floors(voices, leading)))
    if len(trailing) > 1:
        _retarget(placed, trailing, fit_outro([placed[bar].center for bar in trailing], _bar_floors(voices, trailing)))
    region = set(leading) | set(trailing)
    for bar, spot in list(placed.items()):
        if not spot.pedal or bar in region:
            continue
        floor = _bar_floors(voices, [bar])[0]
        if floor is not None and spot.center < floor:
            _retarget(placed, [bar], [floor])


def apply_guitar_wave(ctx, lead, support, low, patterns: list[str] | None = None, relaxed: set[int] | None = None):
    """Shift written velocities by one rounded center per bar.

    Body notes that are not snapped land in [V_floor, V_ceil] with V_ceil <= 63.
    Pedal bars skip that floor. Their centers are raised onto one line so the
    softest note is stored at 22 when the seam still has room, then capped at 63.
    Snap and frame stabs run after that clamp and overwrite only their own attacks.
    """
    del relaxed
    patterns = list(patterns or [])
    voices = {"lead": list(lead), "support": list(support), "low": list(low)}
    volumes = resolve_bar_volumes(ctx)
    placed, waves, leading, trailing = _place_centers(ctx, patterns, volumes)
    _fit_pedal_speech(voices, placed, leading, trailing)
    _apply_affine(ctx, voices, placed)
    _apply_snaps(ctx, voices, patterns, waves)
    _apply_stabs(ctx, voices, trailing)
    return _sync_ties(voices["lead"]), _sync_ties(voices["support"]), _sync_ties(voices["low"])
