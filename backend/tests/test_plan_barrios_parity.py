"""Golden lock for the Barrios plan rows: which pattern each phrase receives.

Barrios chooses at three scopes. A framed movement (1D/1W/1M/3M) calls
`_assign_macro`, which for a long body (>40 bars) walks the region rows of
`_barrios_palette` / `_barrios_region_patterns`, and otherwise asks
`_dominant_pattern_auto` once for the whole body or session. The 34-bar 1D body
is the one short framed body that chooses per phrase through `_select_body`.
The unframed phrase path is not reachable from a production span -- even 1W's
intro/outro count as pedal sections -- so the matrix also renders body-only
specs with no pedal frame, the same synthetic shape the pattern tests use.

The fixture records the raw `_patterns` row, including its `pedal` entries, so
a rule-table refactor that changes one phrase, one order, or one fallback shows
up as a diff even when the printed movement name stays the same.

The matrix is bounded and deterministic. It walks every span, every character,
both melody shapes (a held body and a running body), the real dynamic bands,
every tempo a span can override (the tremolo floor, its 140 ceiling, the 100
dance gate, and the 1D 120), the 34-bar 1D special, trio/bridge contrast, and
both the 4/4 and 6/8 region rows.

A running phrase needs at least four source bars per musical bar: `resample`
picks one close per eighth, so a one- or two-bar group plateaus into a hold.
The helper therefore gives every movement four source bars per musical bar.

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_BARRIOS_PLAN=1 python3 -m pytest tests/test_plan_barrios_parity.py -q

Review the resulting JSON diff in the same commit that changes a Barrios rule.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, replace
from functools import lru_cache

import pytest

from app.sonify import guitar_patterns as gp
from app.sonify.form import METER_44, METER_68, FormSection, FormSpec
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.span import attach_frame, month_specs, quarter_specs, week_spec

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "barrios_plan.json"
WRITE = os.environ.get("VSTOCK_WRITE_BARRIOS_PLAN") == "1"

SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
# Every tempo a Barrios rule reads: the tremolo floor and its ceiling, the
# dance gate above 100, the daily 120, and the values just outside each edge.
TEMPOS = (72, 89, 90, 100, 101, 120, 140, 141)
UNFRAMED_BARS = 32
LONG_BARS = 64

# Source bars per musical bar. Four keeps a running shape running; fewer
# collapse each group's resampled closes into a hold.
BARS_PER_MUSICAL_BAR = 4


@dataclass(frozen=True)
class Observed:
    """The row plus the context that produced it, for coverage assertions."""

    patterns: tuple[str, ...]
    bars: int
    bpm: int
    kind: str
    framed: bool
    bands: tuple[str, ...]


def _volume(index: int, count: int, level: str) -> float:
    """Real dynamic bands: a quiet minority, a loud majority, or half and half.

    A uniform series collapses p10 and p90 onto one value and marks every
    window `mf`, so the levels always trade two volumes. A 15% quiet lead-in is
    the smallest margin that still keeps the traded percentiles apart while
    leaving a long body loud enough for the forte-majority row.
    """
    if level == "mixed":
        return 100.0 if index < count // 2 else 400.0
    if level == "loud":
        return 100.0 if index < max(1, count * 15 // 100) else 400.0
    if level == "quiet":
        return 100.0 if index < count - max(1, count // 10) else 400.0
    raise ValueError(f"unknown level: {level}")


def _bars(shape: str, count: int, level: str = "mixed") -> list[Bar]:
    bars: list[Bar] = []
    for index in range(count):
        close = 100.0 if shape == "held" else 100.0 + (index % 4) * 40
        bars.append(Bar(close, _volume(index, count, level)))
    return bars


def _form(span: str, bpm: int | None, *, sessions: int = 1, movement: int = 0):
    """The body the span planner would hand to render, plus an optional tempo."""
    if span == "1D":
        # No form is the daily path: render picks DAILY_ENSEMBLE_SPEC and the
        # ensemble's GUITAR_BPM, so 1D cannot take a bpm override here.
        return None
    if span == "1W":
        spec = week_spec(sessions)
    elif span == "1M":
        spec = attach_frame(month_specs("guitar")[movement], "1M")
    elif span == "3M":
        spec = attach_frame(quarter_specs("guitar")[movement], "3M")
    else:  # pragma: no cover - guarded by SPANS
        raise ValueError(f"unknown span: {span}")
    return spec if bpm is None else replace(spec, bpm=bpm)


def _body_spec(
    bpm: int,
    meter,
    *,
    trio: bool = False,
    bridge: bool = False,
    bars: int = UNFRAMED_BARS,
    contrast_bar: int = 8,
) -> FormSpec:
    """A body with no pedal frame, so `_patterns` keeps the per-phrase path.

    The contrast flag sits below the opening phrase: the opening-body rule
    would otherwise shadow the thumb rules and hide the phrase ladder's
    trio/bridge branch.
    """
    sections = tuple(
        FormSection(
            bar,
            min(bar + 8, bars),
            "phrase",
            0,
            bridge=bridge and bar == contrast_bar,
            trio=trio and bar == contrast_bar,
        )
        for bar in range(0, bars, 8)
    )
    return FormSpec(bars, bpm, sections, meter=meter)


def _key(
    span: str,
    character: str | None,
    shape: str,
    bpm: int | None,
    *,
    sessions: int = 1,
    movement: int = 0,
    level: str = "mixed",
) -> str:
    parts = [span, character or "none", shape, "auto" if bpm is None else str(bpm)]
    if span == "1W":
        parts.append(f"w{sessions}")
    if span in ("1M", "3M"):
        parts.append(f"m{movement}")
    if level != "mixed":
        parts.append(level)
    return "|".join(parts)


def _observe(
    bars: list[Bar],
    character: str | None,
    form,
    *,
    framed: bool = True,
    movement_index: int = 0,
) -> Observed:
    """Run the production render with voices skipped and capture the raw row."""
    captured: list[tuple] = []
    original = gp._patterns

    def spy(ctx):
        row = original(ctx)
        captured.append((ctx, list(row)))
        return row

    found: list[str] = []
    forms: list[list[str]] = []
    tokens = (
        gp._HEADLINE.set(found),
        gp._FORM.set(forms),
        gp._SKIP_VOICES.set(True),
    )
    gp._patterns = spy
    try:
        render(
            bars,
            variant="guitar",
            ensemble="barrios",
            character=character,
            form=form,
            framed=framed,
            movement_index=movement_index,
        )
    finally:
        gp._patterns = original
        gp._HEADLINE.reset(tokens[0])
        gp._FORM.reset(tokens[1])
        gp._SKIP_VOICES.reset(tokens[2])
    assert len(captured) == 1, len(captured)
    ctx, row = captured[0]
    assert found and forms, (found, forms)
    return Observed(
        patterns=tuple(row),
        bars=ctx.bars,
        bpm=ctx.bpm,
        kind=ctx.kind,
        framed=gp._framed(ctx),
        bands=tuple(sorted(set(ctx.band_at.values()))),
    )


def _framed_case(
    span: str,
    character: str | None,
    shape: str,
    bpm: int | None,
    *,
    sessions: int = 1,
    movement: int = 0,
    level: str = "mixed",
) -> Observed:
    """Render this span at this tempo, with four source bars per musical bar."""
    form = _form(span, bpm, sessions=sessions, movement=movement)
    musical_bars = 34 if form is None else form.bars
    bars = _bars(shape, musical_bars * BARS_PER_MUSICAL_BAR, level)
    return _observe(bars, character, form, movement_index=movement)


def _unframed_case(
    character: str | None,
    shape: str,
    bpm: int,
    *,
    kind: str = "4/4",
    trio: bool = False,
    bridge: bool = False,
    bars: int = UNFRAMED_BARS,
    contrast_bar: int = 8,
) -> Observed:
    meter = METER_68 if kind == "6/8" else METER_44
    spec = _body_spec(
        bpm, meter, trio=trio, bridge=bridge, bars=bars, contrast_bar=contrast_bar
    )
    return _observe(_bars(shape, bars * BARS_PER_MUSICAL_BAR), character, spec, framed=False)


def _build_cases() -> dict[str, Observed]:
    cases: dict[str, Observed] = {}

    # 1D is the daily frame: the 34-bar special. It runs `_select_body` per
    # phrase and, for the whole body, `_daily_barrios_pattern`.
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1D", character, shape, None)
            cases[key] = _framed_case("1D", character, shape, None)

    # 1W is framed by its intro/outro, so it runs the macro path as one
    # session. Walk every tempo with the two characters that read the ladder.
    for tempo_index, bpm in enumerate(TEMPOS):
        for character_index, character in enumerate((None, "rally")):
            shape = SHAPES[(tempo_index + character_index) % len(SHAPES)]
            key = _key("1W", character, shape, bpm)
            cases[key] = _framed_case("1W", character, shape, bpm)
    for bpm in (72, 120):
        for character in ("calm", "selloff", "volatile"):
            for shape in SHAPES:
                key = _key("1W", character, shape, bpm)
                cases[key] = _framed_case("1W", character, shape, bpm)

    # A longer week buckets one macro choice per session, and its >40-bar body
    # walks the region row instead of locking one id.
    for character in (None, "rally", "calm", "volatile"):
        for shape in SHAPES:
            key = _key("1W", character, shape, 120, sessions=2)
            cases[key] = _framed_case("1W", character, shape, 120, sessions=2)

    # 1M is framed. Movement 0 is 4/4, movement 1 is 3/4, movement 2 is 6/8,
    # and movement 3 is the 4/4 finale with its long pedal close.
    for movement in range(4):
        for character_index, character in enumerate(CHARACTERS):
            shape = SHAPES[(movement + character_index) % len(SHAPES)]
            bpm = TEMPOS[(movement * len(CHARACTERS) + character_index) % len(TEMPOS)]
            key = _key("1M", character, shape, bpm, movement=movement)
            cases[key] = _framed_case(
                "1M", character, shape, bpm, movement=movement
            )

    # The moderato 4/4 opening rule: the finale pedal and a selloff/volatile
    # session sing Ultimo Tremolo, every other 90-100 body opens Preludio.
    for movement in (0, 3):
        for bpm in (90, 100):
            for character in ("calm", "rally"):
                key = _key("1M", character, "held", bpm, movement=movement)
                cases[key] = _framed_case(
                    "1M", character, "held", bpm, movement=movement
                )

    # The long 6/8 row reads a forte majority, not the phrase's apex band.
    for character in (None, "calm", "rally"):
        for level in ("loud", "quiet"):
            key = _key("1M", character, "held", 120, movement=2, level=level)
            cases[key] = _framed_case(
                "1M", character, "held", 120, movement=2, level=level
            )

    # The 4/4 region row at >100: a tremolo, preludio, or dance opening each
    # seat a different guest row.
    for character, shape in (("rally", "held"), (None, "running"), ("rally", "running")):
        key = _key("1M", character, shape, 120, movement=0)
        cases[key] = _framed_case("1M", character, shape, 120, movement=0)

    # 3M repeats the framed 4/4/3/4/6/8 bodies at the longest length, so the
    # region row sees many slots.
    for movement in range(3):
        for character_index, character in enumerate(CHARACTERS):
            shape = SHAPES[(movement + character_index + 1) % len(SHAPES)]
            bpm = TEMPOS[(movement * len(CHARACTERS) + character_index + 3) % len(TEMPOS)]
            key = _key("3M", character, shape, bpm, movement=movement)
            cases[key] = _framed_case(
                "3M", character, shape, bpm, movement=movement
            )

    # Unframed 4/4: the phrase ladder at every tempo it reads, both shapes.
    for bpm in TEMPOS:
        for character in (None, "rally"):
            for shape in SHAPES:
                key = _key("unframed", character, shape, bpm)
                cases[key] = _unframed_case(character, shape, bpm)
    for bpm in (72, 90, 120):
        for shape in SHAPES:
            key = _key("unframed", "calm", shape, bpm)
            cases[key] = _unframed_case("calm", shape, bpm)
    for bpm in (90, 101):
        for shape in SHAPES:
            key = _key("unframed", "selloff", shape, bpm)
            cases[key] = _unframed_case("selloff", shape, bpm)

    # Unframed 6/8: the running dance row. The apex band decides hemiola vs
    # polca, and a trio takes the vals first.
    for bpm in (72, 100, 101, 120, 141):
        for character in (None, "rally"):
            for shape in SHAPES:
                key = _key("unframed", character, shape, bpm, level="mixed") + "|6/8"
                cases[key] = _unframed_case(character, shape, bpm, kind="6/8")
    for bpm in (90, 120):
        key = f"unframed|calm|running|{bpm}|6/8"
        cases[key] = _unframed_case("calm", "running", bpm, kind="6/8")
    for bpm in (101, 140):
        key = f"unframed|rally|running|{bpm}|6/8|trio"
        cases[key] = _unframed_case(
            "rally", "running", bpm, kind="6/8", trio=True, contrast_bar=16
        )

    # Unframed long bodies: the held phrase after two tremolo phrases falls
    # back to the andante, and a held trio or bridge after that run sings on
    # the thumb. The contrast flag sits on phrase three.
    for flag in ("trio", "bridge"):
        for bpm in (72, 120):
            for shape in SHAPES:
                key = f"unframed|none|{shape}|{bpm}|{flag}"
                cases[key] = _unframed_case(
                    None,
                    shape,
                    bpm,
                    bars=LONG_BARS,
                    contrast_bar=24,
                    **{flag: True},
                )
    return cases


@lru_cache(maxsize=1)
def _cases() -> dict[str, Observed]:
    with compose_params({}):
        return _build_cases()


def _rows() -> dict[str, list[str]]:
    return {key: list(case.patterns) for key, case in _cases().items()}


def _load() -> dict[str, list[str]]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {str(key): [str(item) for item in row] for key, row in raw.items()}


def test_barrios_plan_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate barrios_plan.json in CI")
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        # One case per line: a rule change diffs a handful of rows, not 3.5k.
        lines = ["{"]
        items = sorted(rows.items())
        for index, (key, row) in enumerate(items):
            comma = "," if index < len(items) - 1 else ""
            lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(row)}{comma}")
        lines.append("}")
        FIXTURE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    expected = _load()
    missing = sorted(set(rows) - set(expected))
    extra = sorted(set(expected) - set(rows))
    assert not missing and not extra, (missing[:5], extra[:5])

    mismatched = {key: (rows[key], expected[key]) for key in rows if rows[key] != expected[key]}
    assert not mismatched, list(mismatched.items())[:2]


def test_matrix_size_is_intentional() -> None:
    assert len(_cases()) == 171, len(_cases())


def test_matrix_covers_every_span_character_shape_and_tempo() -> None:
    cases = _cases()
    for span in SPANS:
        keys = [key for key in cases if key.startswith(f"{span}|")]
        assert keys, span
        assert {key.split("|")[1] for key in keys} == {
            character or "none" for character in CHARACTERS
        }, span
        assert {key.split("|")[2] for key in keys} == set(SHAPES), span
        if span != "1D":
            assert {key.split("|")[3] for key in keys} == {
                str(bpm) for bpm in TEMPOS
            }, span

    # The framed spans run the macro ladder; the synthetic rows run the phrase
    # ladder, and both meters appear there.
    assert {key.split("|")[0] for key in cases} == set(SPANS) | {"unframed"}
    assert not any(case.framed for key, case in cases.items() if key.startswith("unframed|"))
    assert not any(
        not case.framed for key, case in cases.items() if not key.startswith("unframed|")
    )
    assert {case.kind for key, case in cases.items() if key.startswith("unframed|")} == {
        "4/4",
        "6/8",
    }

    # The phrase path must really choose per phrase, not repeat one id, and a
    # running body must really run: the dance row is only reachable there.
    phrase_rows = [
        case.patterns for key, case in cases.items() if key.startswith("unframed|")
    ]
    assert any(
        len({pattern for pattern in row if pattern != "pedal"}) >= 2
        for row in phrase_rows
    )
    for pattern in ("choro", "vals", "hemiola", "polca"):
        assert any(pattern in row for row in phrase_rows), pattern

    # The fixture must see the real dynamic bands, not a wall of `mf`: the
    # phrase hemiola, the `p` polca, and the macro forte majority need them.
    band_values = {band for case in cases.values() for band in case.bands}
    assert {"p", "mf", "f"} <= band_values, band_values

    # The phrase ladder's trio/bridge branch is in the golden: a held contrast
    # phrase after two tremolo phrases sings on the thumb. Below the tremolo
    # floor only the bridge does; the slow trio keeps the andante. A running
    # contrast phrase never sings on the thumb: the branch is hold-only.
    for flag in ("trio", "bridge"):
        fast = [
            case.patterns
            for key, case in cases.items()
            if key.startswith("unframed|none|held|120|") and key.endswith(f"|{flag}")
        ]
        assert fast and all("thumb_cantabile" in row for row in fast), flag
        running = [
            case.patterns
            for key, case in cases.items()
            if key.startswith(f"unframed|none|running|120|")
            and key.endswith(f"|{flag}")
        ]
        assert running and not any("thumb_cantabile" in row for row in running), flag
    assert "thumb_cantabile" in cases["unframed|none|held|72|bridge"].patterns
    assert "thumb_cantabile" in cases["unframed|none|running|72|bridge"].patterns
    assert "thumb_cantabile" not in cases["unframed|none|held|72|trio"].patterns

    # 1D is the 34-bar special: the row mixes the per-phrase ladder with the
    # held/andante fallback, so it is not one locked pattern.
    daily = [case.patterns for key, case in cases.items() if key.startswith("1D|")]
    body = [{pattern for pattern in row if pattern != "pedal"} for row in daily]
    assert any(len(ids) >= 2 for ids in body), body
    assert any("preludio" in ids for ids in body)
    assert any("tremolo" in ids for ids in body)
    assert any("andante" in ids for ids in body)
    assert any("choro" in ids for ids in body), body

    # The long 6/8 row reads the forte majority: the loud body opens and closes
    # on hemiola, the quiet body on polca, at the same tempo and mood. Both
    # rows hand the trio region the same vals.
    loud = [pattern for pattern in cases["1M|none|held|120|m2|loud"].patterns if pattern != "pedal"]
    quiet = [pattern for pattern in cases["1M|none|held|120|m2|quiet"].patterns if pattern != "pedal"]
    assert loud[0] == loud[-1] == "hemiola", loud
    assert quiet[0] == quiet[-1] == "polca", quiet
    assert "vals" in loud and "vals" in quiet

    # The finale pedal decides the moderato 4/4 opening: movement 3 opens and
    # closes on tremolo where movement 0 opens Preludio at the same tempo and
    # calm, and both hand the middle region the chorale.
    finale = [pattern for pattern in cases["1M|calm|held|90|m3"].patterns if pattern != "pedal"]
    opening = [pattern for pattern in cases["1M|calm|held|90|m0"].patterns if pattern != "pedal"]
    assert finale[0] == finale[-1] == "tremolo", finale
    assert opening[0] == opening[-1] == "preludio", opening
    assert "andante" in finale

    # The region row paints opening, guest, and reprise: the first and last
    # body ids match, the middle id does not.
    region = [pattern for pattern in cases["1M|rally|held|120|m0"].patterns if pattern != "pedal"]
    assert len(region) >= 3
    assert region[0] == region[-1]
    assert any(pattern != region[0] for pattern in region)

    # Every macro id is in the golden, so the ladder did not collapse.
    framed_rows = [
        case.patterns for key, case in cases.items() if not key.startswith("unframed|")
    ]
    for pattern in ("andante", "preludio", "tremolo", "choro", "polca", "hemiola", "vals", "thumb_cantabile"):
        assert any(pattern in row for row in framed_rows), pattern
