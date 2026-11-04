"""Golden lock for the Bach plan rows: which dance each phrase receives.

Bach uses two plan scopes. A framed movement (1D/1W/1M/3M) selects through
`_assign_macro` -> `_dominant_pattern_auto`; a movement longer than 40 bars
walks the suite row in `_bach_region_patterns` instead of one locked dance.
The unframed phrase path (`_select_body`) is not reachable from a production
span -- even 1W's intro/outro count as pedal sections -- so the matrix also
renders body-only specs with no pedal frame. That is the same synthetic shape
the pattern tests use.

The fixture records the raw `_patterns` row, including its `pedal` entries, so
a rule-table refactor that changes one phrase, one order, or one fallback shows
up as a diff even when the printed movement name stays the same.

The matrix is bounded and deterministic. It walks every span, every character,
both bar shapes, and six tempos a span can override. The unframed cases walk
all three Bach meters (4/4, 3/4, 6/8), the slow tempo split, and the trio and
bridge contrast flags.

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_BACH_PLAN=1 python3 -m pytest tests/test_plan_bach_parity.py -q

Review the resulting JSON diff in the same commit that changes a Bach rule.
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
from app.sonify.span import attach_frame, month_specs, quarter_specs, week_spec

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "bach_plan.json"
WRITE = os.environ.get("VSTOCK_WRITE_BACH_PLAN") == "1"

SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
# Every span BPM in the Bach table, plus the two overrides the suite uses.
TEMPOS = (60, 72, 90, 96, 100, 108, 120)
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


# Three traded levels, so `marking_for_volume` returns p, mf, and f instead of
# collapsing every bar to one band. Bach's plan does not read the band, but the
# matrix should still exercise the real dynamic path.
VOLUMES = (100.0, 250.0, 400.0)


def _volume(index: int) -> float:
    return VOLUMES[min(len(VOLUMES) - 1, index * len(VOLUMES) // 96)]


def _bars(shape: str) -> list[Bar]:
    bars: list[Bar] = []
    for index in range(96):
        close = 100.0 if shape == "held" else 100.0 + (index % 7) * 2
        bars.append(Bar(close, _volume(index)))
    return bars


def _form(span: str, bpm: int | None, *, sessions: int = 1, movement: int = 0):
    """The body the span planner would hand to render, plus an optional tempo."""
    if span == "1D":
        # No form is the daily path: render picks DAILY_ENSEMBLE_SPEC and Bach's
        # GUITAR_BPM (96), so 1D cannot take a bpm override here.
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

    The contrast flag sits on the second phrase, not the opening one, so the
    matrix really walks the trio/bridge branch of `_select_body`.
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
            ensemble="bach",
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

    # 1D is the daily frame: the 34-bar/96 BPM/4/4 fingerprint, no bpm override.
    for shape in SHAPES:
        for character in CHARACTERS:
            key = _key("1D", character, shape, None)
            cases[key] = _observe(_bars(shape), character, _form("1D", None))

    # 1W is framed by its intro/outro, so it runs the macro path. Rotate the
    # tempo across characters and shapes so every tempo appears on the span.
    for character_index, character in enumerate(CHARACTERS):
        for shape_index, shape in enumerate(SHAPES):
            bpm = TEMPOS[(character_index * len(SHAPES) + shape_index) % len(TEMPOS)]
            key = _key("1W", character, shape, bpm)
            cases[key] = _observe(_bars(shape), character, _form("1W", bpm))

    # A longer week buckets one region per session. From the second session on
    # the body passes 40 bars, so the suite row replaces the single lock.
    for sessions in (2, 3, 4, 5):
        for character in CHARACTERS:
            key = _key("1W", character, "running", 90, sessions=sessions)
            cases[key] = _observe(
                _bars("running"), character, _form("1W", 90, sessions=sessions)
            )

    # 1M is framed: macro path, and every movement is longer than 40 bars, so
    # each walks its suite row. Movement 1 is 3/4 with a bridge, movement 2 is
    # 6/8 with a trio, and movement 3 is the 4/4 finale.
    for movement in range(4):
        for character_index, character in enumerate(CHARACTERS):
            bpm = TEMPOS[(movement + character_index) % len(TEMPOS)]
            for shape in SHAPES:
                key = _key("1M", character, shape, bpm, movement=movement)
                cases[key] = _observe(
                    _bars(shape),
                    character,
                    _form("1M", bpm, movement=movement),
                    movement_index=movement,
                )

    # 3M is framed as well; all three movements walk the suite row at the
    # longest bodies.
    for movement in range(3):
        for character_index, character in enumerate(CHARACTERS):
            bpm = TEMPOS[(movement + character_index + 1) % len(TEMPOS)]
            for shape in SHAPES:
                key = _key("3M", character, shape, bpm, movement=movement)
                cases[key] = _observe(
                    _bars(shape),
                    character,
                    _form("3M", bpm, movement=movement),
                    movement_index=movement,
                )

    # The explicit tempo override on every framed span: one character/shape
    # pair per tempo, so a span cannot silently ignore its bpm input.
    for span, movement in (("1W", 0), ("1M", 0), ("3M", 0)):
        for index, bpm in enumerate(TEMPOS):
            character = CHARACTERS[index % len(CHARACTERS)]
            key = _key(span, character, "running", bpm, movement=movement)
            cases[key] = _observe(
                _bars("running"),
                character,
                _form(span, bpm, movement=movement),
                movement_index=movement,
            )

    # Unframed: the daily body at Bach's ensemble tempo (96).
    for shape in SHAPES:
        for character in CHARACTERS:
            key = f"unframed|daily|{character or 'none'}|{shape}|auto"
            cases[key] = _observe(_bars(shape), character, None, framed=False)

    # Unframed 4/4: the slow floor and the fast band, both shapes.
    for character in CHARACTERS:
        for shape in SHAPES:
            for bpm in (72, 120):
                key = f"unframed|4/4|{character or 'none'}|{shape}|{bpm}"
                cases[key] = _observe(
                    _bars(shape), character, _body_spec(bpm, METER_44), framed=False
                )

    # Unframed 3/4 and 6/8: the meter gates and the slow 3/4 row.
    for meter, name in ((METER_34, "3/4"), (METER_68, "6/8")):
        for character in CHARACTERS:
            for bpm in (60, 72, 120):
                key = f"unframed|{name}|{character or 'none'}|running|{bpm}"
                cases[key] = _observe(
                    _bars("running"), character, _body_spec(bpm, meter), framed=False
                )
            key = f"unframed|{name}|{character or 'none'}|held|120"
            cases[key] = _observe(
                _bars("held"), character, _body_spec(120, meter), framed=False
            )

    # Unframed contrast: trio and bridge answer through `_bach_contrast`, and
    # the second phrase carries the flag so the opening phrase stays primary.
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


def test_bach_plan_matches_the_fixture() -> None:
    rows = _rows()
    if WRITE:
        if os.environ.get("CI"):
            pytest.fail("refusing to regenerate bach_plan.json in CI")
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
    assert len(_cases()) == 200, len(_cases())


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

    # 1D is always the daily fingerprint: 34 bars, 96 BPM, 4/4.
    assert all(
        (case.bars, case.bpm, case.kind) == (34, 96, "4/4")
        for key, case in cases.items()
        if key.startswith("1D|")
    )

    # The framed spans run the macro path; the synthetic rows run the phrase
    # path, and all three Bach meters appear there.
    assert {key.split("|")[0] for key in cases} == set(SPANS) | {"unframed"}
    assert not any(case.framed for key, case in cases.items() if key.startswith("unframed|"))
    assert not any(
        not case.framed for key, case in cases.items() if not key.startswith("unframed|")
    )
    assert {case.kind for key, case in cases.items() if key.startswith("unframed|")} == {
        "3/4",
        "4/4",
        "6/8",
    }

    # A long framed movement really walks the suite row: at least two distinct
    # body dances, not one locked id.
    region_rows = [
        case.patterns
        for key, case in cases.items()
        if key.startswith(("1W|", "1M|", "3M|"))
        and len({pattern for pattern in case.patterns if pattern != "pedal"}) >= 2
    ]
    assert region_rows

    # Prelude never closes a suite row that already heard another dance.
    for row in region_rows:
        body = [pattern for pattern in row if pattern != "pedal"]
        if len(body) >= 3 and "bach_prelude" in body[:-1]:
            assert body[-1] != "bach_prelude", row

    # The unframed contrast flag reaches `_bach_contrast` and not the opening
    # phrase. At 120 a 4/4 Bourrée answers with the Fugue; at 72 the slow row
    # answers with the Chaconne instead.
    for flag in ("trio", "bridge"):
        rows = {
            key: case.patterns
            for key, case in cases.items()
            if key.endswith(f"|{flag}")
        }
        assert rows, flag
        assert all(
            len({pattern for pattern in row if pattern != "pedal"}) >= 2
            for row in rows.values()
        ), flag
        assert any(
            "bach_fuga" in row
            for key, row in rows.items()
            if key.endswith("|120|" + flag)
        ), flag
        assert any(
            "bach_chaconne" in row
            for key, row in rows.items()
            if key.endswith("|72|" + flag)
        ), flag

    # The fixture must see real dynamic bands, not a wall of `mf`.
    band_values = {band for case in cases.values() for band in case.bands}
    assert {"p", "mf", "f"} <= band_values, band_values

    # The default matrix reaches the dance ids below the quiet rows, so the
    # golden locks the whole menu rather than one branch.
    all_ids = {pattern for case in cases.values() for pattern in case.patterns}
    assert {
        "bach_bourree",
        "bach_gavotte",
        "bach_courante",
        "bach_gigue",
        "bach_sarabande",
        "bach_chaconne",
        "bach_fuga",
        "bach_prelude",
        "bach_allemande",
    } <= all_ids
