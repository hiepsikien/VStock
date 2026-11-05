"""Executable procedure specs, kept as data.

Bach's Fugue realizes exactly one procedure: imitation. The renderer answers
the subject in the bass `lag` bars later, with the subject's rhythm and one
contour direction per run (1:1), forward, and uninverted. There is no
exposition, episode, countersubject, stretto, or key plan here.

The spec is deliberately narrower than a procedure engine. `ImitationSpec`
names only the parameters the fuga renderer actually reads; `check_realized`
refuses a value the renderer does not know, so a spec edit can fail loudly
instead of silently changing nothing.

`PROCEDURES` is the id table a sentence slot may point at. It is data only:
this module does not plan spans, and `sentence_specs.plan_sentence`/`plan_run`
never emit a procedure.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTOUR_ONE_TO_ONE = "1:1"


@dataclass(frozen=True)
class ImitationSpec:
    """One imitation answer: lag in bars, contour density, direction flags."""

    lag: int
    contour: str
    retrograde: bool
    inversion: bool

    def __post_init__(self) -> None:
        self.check_realized()

    def check_realized(self) -> None:
        """Refuse a spec the current fuga renderer cannot realize."""
        if self.lag < 1:
            raise ValueError("imitation needs a lag of at least one bar")
        if self.contour != CONTOUR_ONE_TO_ONE:
            raise ValueError(
                "the fuga renderer only knows the 1:1 contour, "
                f"got {self.contour!r}"
            )
        if self.retrograde:
            raise ValueError("the fuga renderer never retrogrades the subject")
        if self.inversion:
            raise ValueError("the fuga renderer never inverts the subject")


BACH_IMITATION = ImitationSpec(
    lag=2,
    contour=CONTOUR_ONE_TO_ONE,
    retrograde=False,
    inversion=False,
)

# The ids a sentence slot may name. A procedure is not a span-fill plan: the
# owner/renderer resolves it, so `plan_sentence`/`plan_run` never emit it.
PROCEDURES: dict[str, ImitationSpec] = {"bach_imitation": BACH_IMITATION}


def validate_procedure(procedure_id: str) -> str:
    """Return `procedure_id` if it names a registered procedure.

    Raises ``ValueError`` naming the unknown id, so a registry or authoring
    caller can fail loudly instead of carrying a dead reference.
    """
    if not isinstance(procedure_id, str) or not procedure_id:
        raise ValueError("a procedure id must be a non-empty string")
    if procedure_id not in PROCEDURES:
        raise ValueError(
            f"unknown procedure {procedure_id!r}; "
            f"expected one of {sorted(PROCEDURES)}"
        )
    return procedure_id
