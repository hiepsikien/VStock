"""Golden lock for the movement names the guitar renderer prints.

Names come from the production path `render` -> `_written_dance`, captured
through `program.guitar_movement_name`. The fixture records one name per case
so a refactor that silently renames or reorders a dance shows up as a diff.

The matrix is deterministic and sampled where a movement is long. `villa` and
`brouwer` plan their harmony per bar and cost seconds each, so they take one
character per long span, two on the day span (the characters rotate until every
one is used), and both bar shapes across those day characters. The other four
ensembles carry the full five characters on 1D/1W/1M, three on 3M, and always
both bar shapes on 1D. Every ensemble appears on every span, every character
appears on every span, and both held/running shapes and 72/120 tempos appear on
every span. 1D has no bpm knob (its tempo is `GUITAR_BPM[ensemble]`).

Regenerate the fixture on purpose with:

    VSTOCK_WRITE_NAME_PARITY=1 python3 -m pytest tests/test_name_parity.py -q

Review the resulting JSON diff in the same commit that changes a selector.
"""

from __future__ import annotations

import json
import os
import pathlib
from dataclasses import replace
from functools import lru_cache

from app.sonify.model import Bar
from app.sonify.program import guitar_movement_name
from app.sonify.span import FormSpec, attach_frame, month_specs, quarter_specs, week_spec

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "name_parity.json"
WRITE = os.environ.get("VSTOCK_WRITE_NAME_PARITY") == "1"

ENSEMBLES = ("classic", "villa", "barrios", "brouwer", "bach", "torroba")
# These two plan harmony per bar (villa's Markov transition dominates); one
# movement costs about 0.5s / 3.5s for 1D / 3M, so they are sampled hardest.
HEAVY = frozenset({"villa", "brouwer"})
SPANS = ("1D", "1W", "1M", "3M")
CHARACTERS = (None, "calm", "rally", "selloff", "volatile")
SHAPES = ("held", "running")
TEMPOS = (72, 120)


def _bars(shape: str) -> list[Bar]:
    if shape == "held":
        return [Bar(100.0)] * 96
    return [Bar(100.0 + (index % 7) * 2) for index in range(96)]


def _form(span: str, bpm: int | None, movement: int = 0) -> FormSpec | None:
    """The body the span planner would hand to render, plus an optional tempo."""
    if span == "1D":
        # No form is the daily path: render picks DAILY_ENSEMBLE_SPEC and the
        # ensemble's GUITAR_BPM, so 1D cannot take a bpm override here.
        return None
    if span == "1W":
        # A short week keeps the 1W section walk; a full five sessions costs
        # several seconds per ensemble and does not change which row is named.
        spec = week_spec(1)
    elif span == "1M":
        spec = attach_frame(month_specs("guitar")[movement], "1M")
    elif span == "3M":
        spec = attach_frame(quarter_specs("guitar")[movement], "3M")
    else:  # pragma: no cover - guarded by SPANS
        raise ValueError(f"unknown span: {span}")
    return spec if bpm is None else replace(spec, bpm=bpm)


def _characters(ensemble_index: int, span_index: int) -> tuple[str | None, ...]:
    if ENSEMBLES[ensemble_index] in HEAVY:
        if span_index == 0:
            # Two characters on the cheapest span so the four spans still walk
            # all five characters for this ensemble.
            return (
                CHARACTERS[ensemble_index % len(CHARACTERS)],
                CHARACTERS[(ensemble_index + len(CHARACTERS) - 1) % len(CHARACTERS)],
            )
        return (CHARACTERS[(ensemble_index + span_index) % len(CHARACTERS)],)
    if span_index == 0:
        return CHARACTERS
    if span_index == len(SPANS) - 1:
        # 3M is the most expensive cheap span; rotate a window of three.
        start = ensemble_index % len(CHARACTERS)
        return tuple(CHARACTERS[(start + step) % len(CHARACTERS)] for step in range(3))
    return CHARACTERS


def _shapes(span_index: int, character_index: int, heavy: bool) -> tuple[str, ...]:
    if span_index == 0 and not heavy:
        return SHAPES
    # One shape per case; the character walk above still gives a heavy
    # ensemble both shapes on 1D and every span both shapes overall.
    return (SHAPES[(span_index + character_index + len(SHAPES)) % len(SHAPES)],)


def _key(ensemble: str, span: str, character: str | None, shape: str, bpm: int | None) -> str:
    return "|".join(
        (ensemble, span, character or "none", shape, "auto" if bpm is None else str(bpm))
    )


@lru_cache(maxsize=1)
def _cases() -> dict[str, str]:
    cases: dict[str, str] = {}
    for ensemble_index, ensemble in enumerate(ENSEMBLES):
        heavy = ensemble in HEAVY
        for span_index, span in enumerate(SPANS):
            characters = _characters(ensemble_index, span_index)
            for character_index, character in enumerate(characters):
                for shape in _shapes(span_index, character_index, heavy):
                    bpm = (
                        None
                        if span == "1D"
                        else TEMPOS[(ensemble_index + span_index + character_index) % len(TEMPOS)]
                    )
                    key = _key(ensemble, span, character, shape, bpm)
                    cases[key] = guitar_movement_name(
                        _bars(shape),
                        ensemble=ensemble,
                        character=character,
                        form=_form(span, bpm),
                    )

    # A full 1W is five sessions, so its row can name three patterns. The
    # sampled 1W above uses one session and always names one row.
    for ensemble_index, ensemble in enumerate(ENSEMBLES):
        character = CHARACTERS[ensemble_index % len(CHARACTERS)]
        key = _key(ensemble, "1W5", character, "running", 120)
        cases[key] = guitar_movement_name(
            _bars("running"),
            ensemble=ensemble,
            character=character,
            form=replace(week_spec(5), bpm=120),
        )

    # A 1M movement index changes which row is named. Sample all four
    # movements for the ensembles whose rows walk.
    for ensemble in ("villa", "barrios", "torroba"):
        for movement in range(4):
            character = "rally" if movement % 2 else "calm"
            key = _key(ensemble, "1M", character, "running", 120) + f"|m{movement}"
            cases[key] = guitar_movement_name(
                _bars("running"),
                ensemble=ensemble,
                character=character,
                form=_form("1M", 120, movement),
            )
    return cases


def _load() -> dict[str, str]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {str(name): str(value) for name, value in raw.items()}


def test_names_match_the_fixture() -> None:
    cases = _cases()
    if WRITE:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    expected = _load()
    missing = sorted(set(cases) - set(expected))
    extra = sorted(set(expected) - set(cases))
    assert not missing and not extra, (missing[:5], extra[:5])

    mismatched = {
        key: (cases[key], expected[key]) for key in cases if cases[key] != expected[key]
    }
    assert not mismatched, list(mismatched.items())[:3]


def test_matrix_is_bounded() -> None:
    assert 100 <= len(_cases()) <= 300, len(_cases())


def test_matrix_covers_every_ensemble_span_and_character() -> None:
    cases = _cases()
    for ensemble in ENSEMBLES:
        for span in SPANS:
            keys = [key for key in cases if key.startswith(f"{ensemble}|{span}|")]
            assert keys, (ensemble, span)
            # The whole span, not each ensemble, carries the character/shape/
            # tempo sweep: villa and brouwer are sampled hardest.
            span_keys = [key for key in cases if key.split("|")[1] == span]
            characters = {key.split("|")[2] for key in span_keys}
            assert characters == {character or "none" for character in CHARACTERS}, (
                span,
                characters,
            )
            assert {key.split("|")[3] for key in span_keys} == set(SHAPES), span
            if span != "1D":
                assert {key.split("|")[4] for key in span_keys} == {
                    str(bpm) for bpm in TEMPOS
                }, span
