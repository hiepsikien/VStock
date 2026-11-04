"""Golden lock for the classic plan row: which pattern each phrase receives.

Classic has two plan scopes, exactly like Villa. A framed movement (1D/1W/1M/3M)
calls `_assign_macro` -> `_dominant_pattern_auto` -> `_classic_macro` once per
body, slot, or session. The unframed phrase path (`_select_body`) is not
reachable from a production span -- even 1W's intro/outro count as pedal
sections -- so the matrix also renders body-only specs with no pedal frame.
That is the same synthetic shape the pattern tests use.

The fixture records the raw `_patterns` row, including its `pedal` entries, so
a rule-table refactor that changes one phrase, one order, or one fallback shows
up as a diff even when the printed movement name stays the same.

The matrix is bounded and deterministic. It walks every span, every character,
both bar shapes, and the tempos a span can carry, including the split points
that matter here: 72 (the slow floor) and 90 (the shared opening-body tremolo
floor). It also covers the macro path's `rally` galop: character set, a
character-less body marked as rally at the bar level, and the minor mode that
keeps the study instead of the dance.

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_CLASSIC_PLAN=1 python3 -m pytest tests/test_plan_classic_parity.py -q

Review the resulting JSON diff in the same commit that changes a classic rule.
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

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "classic_plan.json"
WRITE = os.environ.get("VSTOCK_WRITE_CLASSIC_PLAN") == "1"

SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
# 72 is the slow floor, 90 the shared opening-body floor, and 101/120 sample
# the fast band. Classic has no 100 BPM threshold; 101 is not a boundary.
TEMPOS = (72, 90, 101, 120)
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
    mode: str
    rel_span: float
    character: str | None
    marked: bool


# Two traded levels 4x apart, so `marking_for_volume` returns `p` and `f`
# instead of collapsing every slot to `mf`. The quiet block is a minority of
# the body, so the default matrix still reaches the lively macro rules.
LOW_BARS = 38
LOW_VOLUME = 100.0
HIGH_VOLUME = 400.0


def _volume(index: int) -> float:
    return LOW_VOLUME if index < LOW_BARS else HIGH_VOLUME


def _bars(shape: str) -> list[Bar]:
    bars: list[Bar] = []
    for index in range(96):
        close = 100.0 if shape == "held" else 100.0 + (index % 7) * 2
        bars.append(Bar(close, _volume(index)))
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


def _body_spec(bpm: int, meter, *, trio: bool = False, bridge: bool = False) -> FormSpec:
    """A body with no pedal frame, so `_patterns` keeps the per-phrase path.

    The contrast flag sits on the second phrase, not the opening one: the
    shared opening-body branch would otherwise shadow the phrase ladder.
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
    suffix: str = "",
) -> str:
    parts = [span, character or "none", shape, "auto" if bpm is None else str(bpm)]
    if span == "1W":
        parts.append(f"w{sessions}")
    if span in ("1M", "3M"):
        parts.append(f"m{movement}")
    if suffix:
        parts.append(suffix)
    return "|".join(parts)


def _observe(
    bars: list[Bar],
    character: str | None,
    form,
    *,
    framed: bool = True,
    movement_index: int = 0,
    mode: str = "major",
    character_at=None,
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
            ensemble="classic",
            character=character,
            character_at=character_at,
            form=form,
            framed=framed,
            movement_index=movement_index,
            mode=mode,
        )
    finally:
        gp._patterns = original
        gp._HEADLINE.reset(tokens[0])
        gp._FORM.reset(tokens[1])
        gp._SKIP_VOICES.reset(tokens[2])
    assert len(captured) == 1, len(captured)
    ctx, row = captured[0]
    assert found and forms, (found, forms)
    marked = bool(
        ctx.character_at is not None
        and any(item is not None for item in ctx.character_at)
    )
    return Observed(
        patterns=tuple(row),
        bars=ctx.bars,
        bpm=ctx.bpm,
        kind=ctx.kind,
        framed=gp._framed(ctx),
        bands=tuple(sorted(set(ctx.band_at.values()))),
        mode=ctx.mode,
        rel_span=ctx.rel_span,
        character=ctx.character,
        marked=marked,
    )


def _rally_at(bars: int = 256) -> tuple[str | None, ...]:
    return tuple("rally" for _ in range(bars))


def _build_cases() -> dict[str, Observed]:
    cases: dict[str, Observed] = {}

    # 1D is the daily frame: macro path, no bpm override (88 for classic).
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1D", character, shape, None)
            cases[key] = _observe(_bars(shape), character, _form("1D", None))

    # 1W is framed by its intro/outro, so it runs the macro path at 90. Rotate
    # the characters across both shapes; the bpm is the week's own.
    for character in CHARACTERS:
        for shape in SHAPES:
            key = _key("1W", character, shape, 90)
            cases[key] = _observe(_bars(shape), character, _form("1W", 90))

    # A longer week buckets one macro choice per session.
    for character in CHARACTERS:
        key = _key("1W", character, "running", 90, sessions=2)
        cases[key] = _observe(
            _bars("running"), character, _form("1W", 90, sessions=2)
        )
    for character in CHARACTERS:
        key = _key("1W", character, "running", 90, sessions=5)
        cases[key] = _observe(
            _bars("running"), character, _form("1W", 90, sessions=5)
        )

    # 1M movement 0 is 4/4 at 96: walk every character and both shapes,
    # rotating the tempo so every split point appears on the span.
    for character_index, character in enumerate(CHARACTERS):
        bpm = TEMPOS[character_index % len(TEMPOS)]
        for shape in SHAPES:
            key = _key("1M", character, shape, bpm)
            cases[key] = _observe(
                _bars(shape), character, _form("1M", bpm), movement_index=0
            )

    # Movement 1 is 3/4 at 72 with a bridge; movement 2 is 6/8 at 120 with a
    # trio. The macro path answers contrast through `_contrast_pattern`, not
    # through the primary chooser. Movement 3 is a plain 4/4 body.
    for movement, bpm in ((1, 72), (2, 120), (3, 96)):
        for character in CHARACTERS:
            key = _key("1M", character, "running", bpm, movement=movement)
            cases[key] = _observe(
                _bars("running"),
                character,
                _form("1M", bpm, movement=movement),
                movement_index=movement,
            )

    # 3M walks the short (60), middling (96), and fast (108) movements.
    for movement, bpm in ((0, 96), (1, 60), (2, 108)):
        for character_index, character in enumerate(CHARACTERS):
            shape = SHAPES[character_index % len(SHAPES)]
            key = _key("3M", character, shape, bpm, movement=movement)
            cases[key] = _observe(
                _bars(shape),
                character,
                _form("3M", bpm, movement=movement),
                movement_index=movement,
            )

    # The bpm split points of the macro ladder on a real 1M body: 73 and 89
    # are just above the slow floor, 90 is the opening-body floor, and 100 is
    # the moderato bar. Held bars keep rel_span low, so rally cannot dance.
    for bpm in (73, 89, 90, 100):
        for character in CHARACTERS:
            key = _key("1M", character, "held", bpm, suffix="split")
            cases[key] = _observe(
                _bars("held"), character, _form("1M", bpm), movement_index=0
            )

    # The macro galop: a rally body with a wide span and a known character
    # dances; the same body in minor stays a study. A character-less body
    # marked as rally at the bar level also dances; unmarked it stays a study.
    key = _key("1M", "rally", "running", 96, suffix="galop")
    cases[key] = _observe(
        _bars("running"), "rally", _form("1M", 96), movement_index=0
    )
    key = _key("1M", "rally", "running", 96, suffix="minor")
    cases[key] = _observe(
        _bars("running"), "rally", _form("1M", 96), movement_index=0, mode="minor"
    )
    key = _key("1M", None, "running", 96, suffix="marked")
    cases[key] = _observe(
        _bars("running"),
        None,
        _form("1M", 96),
        movement_index=0,
        character_at=_rally_at(),
    )
    key = _key("1M", None, "running", 96, suffix="unmarked")
    cases[key] = _observe(
        _bars("running"), None, _form("1M", 96), movement_index=0
    )
    key = _key("1M", "rally", "held", 96, suffix="narrow")
    cases[key] = _observe(
        _bars("held"), "rally", _form("1M", 96), movement_index=0
    )

    # Unframed: the daily body at the ensemble tempo (88 for classic), 4/4.
    for character in CHARACTERS:
        for bpm in TEMPOS:
            key = f"unframed|4/4|{character or 'none'}|held|{bpm}"
            cases[key] = _observe(
                _bars("held"), character, _body_spec(bpm, METER_44), framed=False
            )

    # Running bars give a real melodic shape for the phrase ladder. 89 and 90
    # straddle the shared opening-body floor: the opening phrase is a study at
    # 90 but an elegy at 89.
    for character in CHARACTERS:
        for bpm in (89, 90, 120):
            key = f"unframed|4/4|{character or 'none'}|running|{bpm}"
            cases[key] = _observe(
                _bars("running"), character, _body_spec(bpm, METER_44), framed=False
            )

    # Unframed 6/8: the phrase ladder is meter-blind, so this is the cross-check
    # that the meter really does not change the classic block.
    for character in CHARACTERS:
        for bpm in (72, 101):
            key = f"unframed|6/8|{character or 'none'}|held|{bpm}"
            cases[key] = _observe(
                _bars("held"), character, _body_spec(bpm, METER_68), framed=False
            )

    # Unframed contrast: the phrase ladder reads trio only together with the
    # minor mode (elegiaque). A bridge is not read at all. The second phrase
    # carries the flag, so the opening-body rule does not shadow it.
    for flag in ("trio", "bridge"):
        for bpm in (72, 89, 120):
            for mode in ("major", "minor"):
                key = f"unframed|4/4|none|held|{bpm}|{flag}|{mode}"
                cases[key] = _observe(
                    _bars("held"),
                    None,
                    _body_spec(bpm, METER_44, **{flag: True}),
                    framed=False,
                    mode=mode,
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


def test_classic_plan_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate classic_plan.json in CI")
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
    assert len(_cases()) == 152, len(_cases())


def test_matrix_covers_every_span_character_shape_and_tempo() -> None:
    cases = _cases()
    for span in SPANS:
        keys = [key for key in cases if key.startswith(f"{span}|")]
        assert keys, span
        assert {key.split("|")[1] for key in keys} == {
            character or "none" for character in CHARACTERS
        }, span
        assert {key.split("|")[2] for key in keys} == set(SHAPES), span
        tempos = {key.split("|")[3] for key in keys}
        expected_tempos = {
            "1D": {"auto"},
            "1W": {"90"},
            "1M": {"72", "90", "96", "101", "120"} | {"73", "89", "100"},
            "3M": {"60", "96", "108"},
        }[span]
        assert tempos == expected_tempos, (span, tempos)

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

    # Both ladders appear, and every classic id is in the golden.
    macro_rows = [
        case.patterns
        for key, case in cases.items()
        if not key.startswith("unframed|")
    ]
    for pattern in ("elegiaque", "cantabile", "mozart_var", "study", "galop"):
        assert any(pattern in row for row in macro_rows), pattern
    for pattern in ("elegiaque", "cantabile", "mozart_var", "study"):
        assert any(pattern in row for row in phrase_rows), pattern

    # The macro galop needs a wide, major rally body; minor keeps the study,
    # and a narrow body is not a dance either.
    galop = cases["1M|rally|running|96|m0|galop"]
    assert "galop" in galop.patterns and galop.rel_span >= 0.012
    assert galop.mode == "major"
    minor = cases["1M|rally|running|96|m0|minor"]
    assert "galop" not in minor.patterns and minor.mode == "minor"
    assert "galop" not in cases["1M|rally|held|96|m0|narrow"].patterns
    assert "galop" in cases["1M|none|running|96|m0|marked"].patterns
    assert "galop" not in cases["1M|none|running|96|m0|unmarked"].patterns

    # The opening body is the shared study above the tremolo floor: the same
    # calm shape sings Cantabile at 89 and drops to the study at 90.
    assert cases["unframed|4/4|calm|running|90"].patterns[0] == "study"
    assert cases["unframed|4/4|calm|running|89"].patterns[0] == "cantabile"

    # Trio eases into the elegy only in minor; bridge is not read.
    assert "elegiaque" in cases["unframed|4/4|none|held|120|trio|minor"].patterns
    assert "elegiaque" not in cases["unframed|4/4|none|held|120|trio|major"].patterns
    assert "elegiaque" not in cases["unframed|4/4|none|held|120|bridge|major"].patterns

    # The fixture must see the real dynamic bands, not a wall of `mf`.
    band_values = {band for case in cases.values() for band in case.bands}
    assert {"p", "f"} <= band_values, band_values
