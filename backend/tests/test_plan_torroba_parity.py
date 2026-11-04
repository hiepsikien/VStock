"""Golden lock for the Torroba plan row: which pattern each phrase receives.

Torroba chooses a primary texture from the meter and the mood, then a separate
contrast step paints the other formal area. A framed movement (1D/1W/1M/3M)
calls `_assign_torroba` -> `_torroba_primary` / `_torroba_contrast` once per
body, slot, or session. The unframed phrase path (`_select_body`) is not
reachable from a production span -- 1W's intro/outro count as pedal sections
too -- so the matrix also renders body-only specs with no pedal frame, the same
synthetic shape the pattern tests use.

Torroba retargets meter and tempo before the plan runs: a 4/4 calm or selloff
movement becomes 3/4, and every movement is lifted to its meter/mood floor in
92-132 BPM. The fixture locks the pattern row; `test_tempo_and_meter_anchors`
also locks a small anchor set of the observed `bpm`/`kind`, because a retarget
change can leave every row unchanged.

The fixture records the raw `_patterns` row, including its `pedal` entries, so
a rule-table refactor that changes one phrase, one order, or one fallback shows
up as a diff even when the printed movement name stays the same.

The matrix is bounded and deterministic. It walks every span, every character,
both bar shapes, the whole Torroba tempo ladder (the eight floor values plus an
out-of-band clamp), all three plan meters, and both contrast flags.

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_TORROBA_PLAN=1 python3 -m pytest tests/test_plan_torroba_parity.py -q

Review the resulting JSON diff in the same commit that changes a Torroba rule.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import dataclass, replace
from functools import lru_cache

import pytest

from app.sonify import guitar_patterns as gp
from app.sonify.form import METER_34, METER_44, METER_68, FormSection, FormSpec
from app.sonify.model import Bar
from app.sonify.params import compose_params
from app.sonify.render import render
from app.sonify.span import (
    attach_frame,
    month_specs,
    quarter_specs,
    retarget_torroba_meter,
    retarget_torroba_tempo,
    week_spec,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "torroba_plan.json"
WRITE = os.environ.get("VSTOCK_WRITE_TORROBA_PLAN") == "1"

SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
TEMPOS = (None, 60, 100, 120, 140)
UNFRAMED_BARS = 32

# The eight floors `retarget_torroba_tempo` can apply, plus the 132 ceiling.
FLOORS = (92, 96, 104, 108, 112, 116, 124, 132)
TORROBA_PATTERNS = frozenset(
    {"castillo", "sonatina", "fandanguillo", "danza", "torroba_tremolo", "alcaniz", "olite"}
)
# Every id the current primary/contrast pair can actually reach. Sonatina is
# still in `_torroba_contrast`, but the mood map no longer names it.
REACHABLE = TORROBA_PATTERNS - {"sonatina"}


@dataclass(frozen=True)
class Observed:
    """The row plus the context that produced it, for coverage assertions."""

    patterns: tuple[str, ...]
    bars: int
    bpm: int
    kind: str
    framed: bool
    bands: tuple[str, ...]


# Three traded levels so the daily/weekly plans carry real `p`, `mf`, and `f`
# bands rather than a wall of one marking. 100/250/400 is wide enough for
# `marking_for_volume` to reach the low, middle, and high cells; the untraded
# bars in the quiet shape still land on `p`.
LOW_VOLUME = 100.0
MID_VOLUME = 250.0
HIGH_VOLUME = 400.0
LOW_BARS = 32
MID_BARS = 32


def _volume(index: int, *, quiet: bool = False) -> float:
    if quiet:
        return 0.0 if index < 72 else HIGH_VOLUME
    if index < LOW_BARS:
        return LOW_VOLUME
    if index < LOW_BARS + MID_BARS:
        return MID_VOLUME
    return HIGH_VOLUME


def _bars(shape: str, *, quiet: bool = False) -> list[Bar]:
    bars: list[Bar] = []
    for index in range(96):
        close = 100.0 if shape == "held" else 100.0 + (index % 7) * 2
        bars.append(Bar(close, _volume(index, quiet=quiet)))
    return bars


def _quiet_bars(shape: str) -> list[Bar]:
    """A body with untraded bars in the majority, so `p` really appears."""
    return _bars(shape, quiet=True)


def _framed_spec(span: str, character: str | None, bpm: int | None, *, sessions: int = 1, movement: int = 0):
    """The body the span planner would hand to render, after Torroba retargets.

    `prepare_week` and `_framed_torroba` retarget the meter first, then the
    tempo floor for that new meter, then attach the frame. 1D has no form here:
    `render` picks the daily spec and retargets only the meter.
    """
    if span == "1D":
        # No form is the daily path: render picks DAILY_ENSEMBLE_SPEC and its
        # GUITAR_BPM, so 1D cannot take a bpm override and does not run the
        # tempo-floor retarget.
        return None
    if span == "1W":
        spec = week_spec(sessions)
    elif span == "1M":
        spec = month_specs("guitar")[movement]
    elif span == "3M":
        spec = quarter_specs("guitar")[movement]
    else:  # pragma: no cover - guarded by SPANS
        raise ValueError(f"unknown span: {span}")
    if bpm is not None:
        spec = replace(spec, bpm=bpm)
    spec = retarget_torroba_tempo(retarget_torroba_meter(spec, character), character)
    if span in ("1M", "3M"):
        spec = attach_frame(spec, span)
    return spec


def _body_spec(bpm: int, meter, *, trio: bool = False, bridge: bool = False) -> FormSpec:
    """A body with no pedal frame, so `_patterns` keeps the per-phrase path.

    The contrast flag sits on the second phrase, not the opening one, so the
    row shows both the primary phrase and the contrast answer.
    """
    sections = tuple(
        FormSection(
            bar,
            min(bar + 8, UNFRAMED_BARS),
            "phrase",
            0,
            bridge=bridge and bar == 8,
            trio=trio and bar == 8,
        )
        for bar in range(0, UNFRAMED_BARS, 8)
    )
    return FormSpec(UNFRAMED_BARS, bpm, sections, meter=meter)


def _key(
    span: str,
    character: str | None,
    shape: str,
    bpm: int | None,
    *,
    sessions: int = 1,
    movement: int = 0,
) -> str:
    parts = [span, character or "none", shape, "auto" if bpm is None else str(bpm)]
    if span == "1W":
        parts.append(f"w{sessions}")
    if span in ("1M", "3M"):
        parts.append(f"m{movement}")
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
            ensemble="torroba",
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


def _build_cases() -> dict[str, Observed]:
    cases: dict[str, Observed] = {}

    # 1D is the daily frame: no bpm override, meter retargeted by character.
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1D", character, shape, None)
            cases[key] = _observe(_bars(shape), character, _framed_spec("1D", character, None))

    # 1W is framed by its intro/outro, so it runs the macro path. The week
    # retargets against the opening session's character.
    for character in CHARACTERS:
        for shape in SHAPES:
            key = _key("1W", character, shape, None)
            cases[key] = _observe(
                _bars(shape), character, _framed_spec("1W", character, None)
            )

    # A longer week buckets one macro choice per session. 140 is above the
    # 132 ceiling, so the clamp is in the golden.
    for sessions, bpm in ((2, None), (5, 140)):
        for character in CHARACTERS:
            key = _key("1W", character, "running", bpm, sessions=sessions)
            cases[key] = _observe(
                _bars("running"),
                character,
                _framed_spec("1W", character, bpm, sessions=sessions),
            )

    # 1M movement 0 is 4/4 before retarget: calm/selloff become 3/4.
    for character in CHARACTERS:
        for shape in SHAPES:
            key = _key("1M", character, shape, None, movement=0)
            cases[key] = _observe(
                _bars(shape),
                character,
                _framed_spec("1M", character, None, movement=0),
                movement_index=0,
            )

    # The four overrides cover below-floor lift, two mid-band values, and the
    # ceiling clamp on both meters this movement can take.
    for character in ("rally", "calm"):
        for bpm in TEMPOS[1:]:
            key = _key("1M", character, "held", bpm, movement=0)
            cases[key] = _observe(
                _bars("held"),
                character,
                _framed_spec("1M", character, bpm, movement=0),
                movement_index=0,
            )

    # 1M movement 1 carries the bridge in 3/4. Movement 2 carries the trio in
    # 6/8. Movement 3 is 4/4 with no contrast flag, so its A-B-A comes from
    # `_assign_torroba` rather than the section.
    for movement in (1, 2, 3):
        shape = "running" if movement < 3 else "held"
        for character in CHARACTERS:
            key = _key("1M", character, shape, None, movement=movement)
            cases[key] = _observe(
                _bars(shape),
                character,
                _framed_spec("1M", character, None, movement=movement),
                movement_index=movement,
            )

    # 3M movement 0 is the longest 4/4 body. Movement 1 is the 3/4 bridge.
    # Movement 2 is 4/4 with no contrast flag.
    for character in CHARACTERS:
        for shape in SHAPES:
            key = _key("3M", character, shape, None, movement=0)
            cases[key] = _observe(
                _bars(shape),
                character,
                _framed_spec("3M", character, None, movement=0),
                movement_index=0,
            )
    for movement, shape in ((1, "running"), (2, "held")):
        for character in CHARACTERS:
            key = _key("3M", character, shape, None, movement=movement)
            cases[key] = _observe(
                _bars(shape),
                character,
                _framed_spec("3M", character, None, movement=movement),
                movement_index=movement,
            )

    # Unframed: the phrase ladder at each plan meter. The base rows use one
    # bpm per meter; the tempo sweep below walks the rest.
    meters = ((METER_44, "4/4", 112), (METER_34, "3/4", 116), (METER_68, "6/8", 132))
    for meter, name, bpm in meters:
        for character in CHARACTERS:
            for shape in SHAPES:
                key = f"unframed|{name}|{character or 'none'}|{shape}|{bpm}"
                cases[key] = _observe(
                    _bars(shape),
                    character,
                    _body_spec(bpm, meter),
                    framed=False,
                )

    # The phrase ladder's tempo sweep. Torroba's primary map does not read bpm,
    # but the row must stay put across the band a span can hand it.
    for meter, name, _base in meters:
        for character in CHARACTERS:
            for bpm in (92, 104, 120):
                key = f"unframed|{name}|{character or 'none'}|running|{bpm}"
                cases[key] = _observe(
                    _bars("running"),
                    character,
                    _body_spec(bpm, meter),
                    framed=False,
                )

    # Unframed contrast: the phrase ladder answers trio/bridge on the second
    # phrase. A bridge and a trio are separate flags with the same rule.
    for meter, name, _base in meters:
        for character in CHARACTERS:
            for flag in ("trio", "bridge"):
                key = f"unframed|{name}|{character or 'none'}|held|100|{flag}"
                cases[key] = _observe(
                    _bars("held"),
                    character,
                    _body_spec(100, meter, **{flag: True}),
                    framed=False,
                )

    # Quiet-majority bodies. Torroba's chooser does not read the band, but the
    # row must not change when the tape is untraded; these also keep real `p`
    # bars in the framed golden.
    cases["1D|none|held|auto|quiet"] = _observe(
        _quiet_bars("held"), None, _framed_spec("1D", None, None)
    )
    cases["1D|rally|running|auto|quiet"] = _observe(
        _quiet_bars("running"), "rally", _framed_spec("1D", "rally", None)
    )
    for movement, character in ((0, "rally"), (2, "volatile")):
        key = f"1M|{character}|held|auto|quiet|m{movement}"
        cases[key] = _observe(
            _quiet_bars("held"),
            character,
            _framed_spec("1M", character, None, movement=movement),
            movement_index=movement,
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


def test_torroba_plan_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate torroba_plan.json in CI")
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        # One case per line: a rule change diffs a handful of rows, not 7k.
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


def test_tempo_and_meter_anchors() -> None:
    """A few keys where the retarget is visible even when the row is not."""
    anchors = {
        "1M|rally|held|60|m0": (112, "4/4"),
        "1M|calm|held|100|m0": (100, "3/4"),
        "1M|rally|held|140|m0": (132, "4/4"),
        "1W|rally|running|140|w5": (132, "4/4"),
        "1W|calm|held|auto|w1": (92, "3/4"),
        "1D|rally|running|auto": (96, "4/4"),
        "1D|calm|held|auto": (96, "3/4"),
    }
    cases = _cases()
    for key, expected in anchors.items():
        case = cases[key]
        assert (case.bpm, case.kind) == expected, (key, case.bpm, case.kind)


def test_matrix_size_is_intentional() -> None:
    assert len(_cases()) == 192, len(_cases())


def test_matrix_covers_every_span_character_shape_and_tempo() -> None:
    cases = _cases()
    for span in SPANS:
        keys = [key for key in cases if key.startswith(f"{span}|")]
        assert keys, span
        assert {key.split("|")[1] for key in keys} == {
            character or "none" for character in CHARACTERS
        }, span
        assert {key.split("|")[2] for key in keys} == set(SHAPES), span
        assert "auto" in {key.split("|")[3] for key in keys}, span

    # 1M is the span that walks the explicit override list; the others carry
    # the auto row and the week's 140 clamp.
    overrides = {
        key.split("|")[3]
        for key in cases
        if key.startswith("1M|") and "|m0" in key
    }
    assert {"auto", "60", "100", "120", "140"} <= overrides, overrides

    # The framed spans run the macro ladder; the synthetic rows run the phrase
    # ladder, and all three plan meters appear there.
    assert {key.split("|")[0] for key in cases} == set(SPANS) | {"unframed"}
    assert not any(case.framed for key, case in cases.items() if key.startswith("unframed|"))
    assert not any(
        not case.framed for key, case in cases.items() if not key.startswith("unframed|")
    )
    assert {case.kind for key, case in cases.items() if key.startswith("unframed|")} == {
        "4/4",
        "3/4",
        "6/8",
    }

    # Every tempo floor a span can apply is in the golden, and nothing leaves
    # the 92-132 band.
    observed = {case.bpm for case in cases.values()}
    assert set(FLOORS) <= observed, sorted(set(FLOORS) - observed)
    assert min(observed) >= 92 and max(observed) <= 132, (min(observed), max(observed))

    # The phrase path must really choose per phrase, not repeat one id.
    phrase_rows = [
        case.patterns for key, case in cases.items() if key.startswith("unframed|")
    ]
    assert any(
        len({pattern for pattern in row if pattern != "pedal"}) >= 2
        for row in phrase_rows
    )

    # The fixture must see real dynamic bands, not a wall of `mf`: a `p`, an
    # `mf`, and an `f` all have to fire somewhere.
    band_values = {band for case in cases.values() for band in case.bands}
    assert {"p", "mf", "f"} <= band_values, band_values

    # The unmarked id in the contrast table (Sonatina) is not reachable from
    # the current primary map; every reachable id is in the golden.
    every_row = {pattern for case in cases.values() for pattern in case.patterns}
    assert "sonatina" not in every_row
    assert REACHABLE <= every_row, sorted(REACHABLE - every_row)

    # The phrase ladder's trio/bridge branch is in the golden, not only in the
    # synthetic unit test. 4/4 primary is Olite and its contrast is Castillo;
    # 6/8 calm is Danza and its contrast is Alcaniz; a 3/4 rally is Juglar and
    # its contrast is Danza. The flag owns the phrase that starts inside bar 8,
    # so assert the opening/closing primary and that the contrast id is present
    # rather than pinning a phrase index.
    for flag in ("trio", "bridge"):
        four = [
            case.patterns
            for key, case in cases.items()
            if key.startswith("unframed|4/4|") and key.endswith(f"|{flag}")
        ]
        assert four and all(
            row[0] == "olite" and row[-1] == "olite" and "castillo" in row
            for row in four
        ), flag
        six = [
            case.patterns
            for key, case in cases.items()
            if key.startswith("unframed|6/8|calm|") and key.endswith(f"|{flag}")
        ]
        assert six and all(
            row[0] == "danza" and row[-1] == "danza" and "alcaniz" in row
            for row in six
        ), flag
        three = [
            case.patterns
            for key, case in cases.items()
            if key.startswith("unframed|3/4|rally|") and key.endswith(f"|{flag}")
        ]
        assert three and all(
            row[0] == "torroba_tremolo" and row[-1] == "torroba_tremolo" and "danza" in row
            for row in three
        ), flag

    # The daily 34-bar body is one pattern in every meter. The longer framed
    # bodies paint an A-B-A, even when the section carries no trio or bridge:
    # that is the macro path's contrast step. A 3/4 body whose mood has no
    # contrast cell (m1 with no character) collapses to the primary id, so the
    # A-B-A assertion applies whenever the contrast really differs.
    for key, case in cases.items():
        if key.startswith("1D|"):
            assert len({pattern for pattern in case.patterns if pattern != "pedal"}) == 1, key
    for movement in (0, 1, 2, 3):
        rows = [
            case.patterns
            for key, case in cases.items()
            if key.startswith("1M|") and key.endswith(f"|m{movement}")
        ]
        assert rows
        assert any(
            len({pattern for pattern in row if pattern != "pedal"}) >= 2 for row in rows
        ), movement
        for row in rows:
            body = [pattern for pattern in row if pattern != "pedal"]
            if len(set(body)) >= 2:
                assert body[0] == body[-1], (movement, row)

    # A quiet-majority daily body still keeps the same single id; the band is
    # not an input to the Torroba chooser.
    quiet_daily = [
        case.patterns
        for key, case in cases.items()
        if key.startswith("1D|") and key.endswith("|quiet")
    ]
    assert quiet_daily
    for row in quiet_daily:
        assert len({pattern for pattern in row if pattern != "pedal"}) == 1
