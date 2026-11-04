"""Golden lock for the Villa plan row: which pattern each phrase receives.

Villa has two documented plan scopes. A framed movement (1D/1W/1M/3M) calls
`_assign_macro` -> `_dominant_pattern_auto` once per body, slot, or session.
The unframed phrase path (`_select_body`) is not reachable from a production
span -- even 1W's intro/outro count as pedal sections -- so the matrix also
renders body-only specs with no pedal frame. That is the same synthetic shape
the pattern tests use.

The fixture records the raw `_patterns` row, including its `pedal` entries, so
a rule-table refactor that changes one phrase, one order, or one fallback shows
up as a diff even when the printed movement name stays the same.

The matrix is bounded and deterministic. It walks every span, every character,
both bar shapes, and every tempo a span can override. The unframed cases walk
both ladder meters (4/4 and 6/8) and the slow/regular tempo split.

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_VILLA_PLAN=1 python3 -m pytest tests/test_plan_villa_parity.py -q

Review the resulting JSON diff in the same commit that changes a Villa rule.
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

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "villa_plan.json"
WRITE = os.environ.get("VSTOCK_WRITE_VILLA_PLAN") == "1"

SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
TEMPOS = (72, 100, 120)
UNFRAMED_BARS = 32


@dataclass(frozen=True)
class Observed:
    """The row plus the context that produced it, for coverage assertions."""

    patterns: tuple[str, ...]
    bars: int
    bpm: int
    kind: str
    framed: bool
    bands: tuple[str, ...]


# Two traded levels 4x apart, so `marking_for_volume` returns `p` and `f`
# instead of collapsing every slot to `mf`. The quiet block is a minority of
# the body, so the default matrix still reaches the etude and 6/8 macro rules;
# `_quiet_bars` is the dedicated quiet-majority shape below.
LOW_BARS = 38
LOW_VOLUME = 100.0
HIGH_VOLUME = 400.0


def _volume(index: int, *, quiet: bool = False) -> float:
    if quiet:
        return 0.0 if index < 72 else HIGH_VOLUME
    return LOW_VOLUME if index < LOW_BARS else HIGH_VOLUME


def _bars(shape: str, *, quiet: bool = False) -> list[Bar]:
    bars: list[Bar] = []
    for index in range(96):
        close = 100.0 if shape == "held" else 100.0 + (index % 7) * 2
        bars.append(Bar(close, _volume(index, quiet=quiet)))
    return bars


def _quiet_bars(shape: str) -> list[Bar]:
    """A body with untraded bars in the majority, to fire the macro quiet rule."""
    return _bars(shape, quiet=True)


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


def _body_spec(bpm: int, meter, *, trio: bool = False, bridge: bool = False) -> FormSpec:
    """A body with no pedal frame, so `_patterns` keeps the per-phrase path.

    The contrast flag sits on the second phrase, not the opening one: the
    opening-body rule would otherwise shadow the thumb rule and hide the
    phrase ladder's trio/bridge branch.
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
            ensemble="villa",
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

    # 1D is the daily frame: macro path, no bpm override.
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1D", character, shape, None)
            cases[key] = _observe(_bars(shape), character, _form("1D", None))

    # 1W is framed by its intro/outro, so it runs the macro path. Rotate the
    # tempo across characters and shapes so all three appear on the span.
    for character_index, character in enumerate(CHARACTERS):
        for shape_index, shape in enumerate(SHAPES):
            bpm = TEMPOS[(character_index + shape_index) % len(TEMPOS)]
            key = _key("1W", character, shape, bpm)
            cases[key] = _observe(_bars(shape), character, _form("1W", bpm))

    # A longer week buckets one macro choice per session.
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1W", character, shape, 100, sessions=2)
            cases[key] = _observe(
                _bars(shape), character, _form("1W", 100, sessions=2)
            )
    for character in CHARACTERS:
        key = _key("1W", character, "running", 120, sessions=5)
        cases[key] = _observe(
            _bars("running"), character, _form("1W", 120, sessions=5)
        )

    # 1M is framed: macro path. Movement 0 walks every character and both
    # shapes, rotating the tempo so all three are present.
    for character_index, character in enumerate(CHARACTERS):
        bpm = TEMPOS[character_index % len(TEMPOS)]
        for shape in SHAPES:
            key = _key("1M", character, shape, bpm)
            cases[key] = _observe(
                _bars(shape), character, _form("1M", bpm), movement_index=0
            )

    # Movement 1/2 carry the trio, which the macro path answers through
    # `_contrast_pattern` rather than the primary chooser.
    for movement in (1, 2, 3):
        character = CHARACTERS[movement % len(CHARACTERS)]
        bpm = TEMPOS[movement % len(TEMPOS)]
        key = _key("1M", character, "running", bpm, movement=movement)
        cases[key] = _observe(
            _bars("running"),
            character,
            _form("1M", bpm, movement=movement),
            movement_index=movement,
        )

    # 3M is framed as well; one movement is enough to lock the macro ladder at
    # the longest body. Tempo rotates across the characters.
    for character_index, character in enumerate(CHARACTERS):
        bpm = TEMPOS[(character_index + 1) % len(TEMPOS)]
        for shape in SHAPES:
            key = _key("3M", character, shape, bpm)
            cases[key] = _observe(
                _bars(shape), character, _form("3M", bpm), movement_index=0
            )

    # Quiet-majority macro bodies. These use the partially untraded shape so
    # the macro rule really fires and pre-empts the etude rows it sits above.
    for shape, character in (("held", None), ("running", "rally")):
        key = f"1D|{character or 'none'}|{shape}|auto|quiet"
        cases[key] = _observe(_quiet_bars(shape), character, _form("1D", None))
    for movement, character, bpm in ((0, "rally", 120), (2, "volatile", 120)):
        key = f"1M|{character}|held|{bpm}|quiet|m{movement}"
        cases[key] = _observe(
            _quiet_bars("held"),
            character,
            _form("1M", bpm, movement=movement),
            movement_index=movement,
        )

    # Unframed: the daily body at the ensemble tempo (100 for Villa).
    for shape in SHAPES:
        for character in CHARACTERS:
            key = f"unframed|daily|{character or 'none'}|{shape}|auto"
            cases[key] = _observe(
                _bars(shape), character, None, framed=False
            )

    # Unframed 4/4: the slow floor and the etude band, both shapes.
    for character in CHARACTERS:
        key = f"unframed|4/4|{character or 'none'}|held|72"
        cases[key] = _observe(
            _bars("held"), character, _body_spec(72, METER_44), framed=False
        )
        key = f"unframed|4/4|{character or 'none'}|running|72"
        cases[key] = _observe(
            _bars("running"), character, _body_spec(72, METER_44), framed=False
        )
        key = f"unframed|4/4|{character or 'none'}|running|120"
        cases[key] = _observe(
            _bars("running"), character, _body_spec(120, METER_44), framed=False
        )
        key = f"unframed|4/4|{character or 'none'}|held|120"
        cases[key] = _observe(
            _bars("held"), character, _body_spec(120, METER_44), framed=False
        )

    # Unframed 6/8: the phrase ladder's meter gate, slow and fast.
    for character in CHARACTERS:
        for bpm in (72, 120):
            key = f"unframed|6/8|{character or 'none'}|running|{bpm}"
            cases[key] = _observe(
                _bars("running"), character, _body_spec(bpm, METER_68), framed=False
            )
        key = f"unframed|6/8|{character or 'none'}|held|120"
        cases[key] = _observe(
            _bars("held"), character, _body_spec(120, METER_68), framed=False
        )

    # Unframed contrast: the phrase ladder answers trio/bridge on the thumb,
    # while the macro ladder never reads either flag. The second phrase carries
    # the flag, so the opening-body rule does not shadow it.
    for flag in ("trio", "bridge"):
        for bpm in (72, 120):
            key = f"unframed|4/4|none|held|{bpm}|{flag}"
            cases[key] = _observe(
                _bars("held"),
                None,
                _body_spec(bpm, METER_44, **{flag: True}),
                framed=False,
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


def test_villa_plan_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate villa_plan.json in CI")
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
    assert len(_cases()) == 111, len(_cases())


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

    # The phrase path must really choose per phrase, not repeat one id.
    phrase_rows = [
        case.patterns for key, case in cases.items() if key.startswith("unframed|")
    ]
    assert any(
        len({pattern for pattern in row if pattern != "pedal"}) >= 2
        for row in phrase_rows
    )

    # 1M m1/m2 exercise the trio contrast, which is a different id than primary.
    assert any(
        "thumb_cantabile" in case.patterns and "chord_melody" in case.patterns
        for key, case in cases.items()
        if key.startswith("1M|") and key.endswith("|m1")
    )

    # The fixture must see the real dynamic bands, not a wall of `mf`: a `p`
    # phrase and the macro quiet-majority rule only fire when bands vary.
    band_values = {band for case in cases.values() for band in case.bands}
    assert {"p", "f"} <= band_values, band_values
    assert any(
        "p" in case.bands for key, case in cases.items() if not key.startswith("unframed|")
    )
    assert any(
        "p" in case.bands for key, case in cases.items() if key.startswith("unframed|")
    )

    # The phrase ladder's trio/bridge branch is in the golden, not only in the
    # synthetic unit test.
    for flag in ("trio", "bridge"):
        rows = [
            case.patterns for key, case in cases.items() if key.endswith(f"|{flag}")
        ]
        assert rows and all("thumb_cantabile" in row for row in rows), flag

    # The default matrix still reaches the macro rows below quiet-majority, so
    # adding the quiet cases did not collapse the ladder into one branch.
    macro_rows = [
        case.patterns
        for key, case in cases.items()
        if not key.startswith("unframed|")
    ]
    for pattern in ("villa_pattern", "chord_melody", "etude1", "etude11", "thumb_cantabile"):
        assert any(pattern in row for row in macro_rows), pattern

    # A quiet-majority daily body is all block chords, even at rally tempo.
    quiet_daily = [
        case.patterns
        for key, case in cases.items()
        if key.startswith("1D|") and key.endswith("|quiet")
    ]
    assert quiet_daily
    for row in quiet_daily:
        assert {pattern for pattern in row if pattern != "pedal"} == {"chord_melody"}
