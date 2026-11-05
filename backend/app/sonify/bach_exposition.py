"""Bach fugue exposition as data — preview only.

The production Fugue realizes one imitation answer in the bass. An exposition
needs a *plan* of entries: which voice states the subject or answer, in which
bar, and for how long. This module describes that plan without becoming a
counterpoint engine or a runtime registry.

What the prototype can say
--------------------------
An `ExpositionSpec` is a bounded, contiguous entry plan:

* 2–4 entries, each exactly `subject_bars` long;
* entry ``i`` starts at ``i * subject_bars`` (ordered, non-overlapping, no
  episode gap);
* roles alternate ``subject``, ``answer``, ``subject``, ...;
* only the bass may state the answer, because the existing fuga renderer only
  answers in voice 3;
* the imitation lag must equal `subject_bars`, so a bass answer quotes the
  preceding subject;
* the whole exposition is capped at `MAX_EXPOSITION_BARS`.

The `countersubject` flag is part of the entry data so an authoring UI can show
it, but no candidate may realize it yet: a countersubject is a second
independent line, and the preview validator rejects the plan with a clear
error rather than silently dropping the request. Building one needs a real
counterpoint engine (or a second procedure), which is deliberately out of
scope.

`EXPOSITIONS` is a preview id table. It is **not** `PROCEDURES`: the
production `bach_imitation` registry and the sentence-slot validator are
untouched, so this module cannot change a rendered note.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sonify.procedure_specs import BACH_IMITATION, ImitationSpec

VOICES = ("soprano", "alto", "bass")
ROLES = ("subject", "answer")
MAX_ENTRIES = 4
MAX_SUBJECT_BARS = 4
MAX_EXPOSITION_BARS = 16


@dataclass(frozen=True)
class Entry:
    """One voice stating the subject or the answer for `bars` bars.

    `countersubject` is declarative data only. The preview refuses it, because
    a countersubject is a second independent line, not a flag the imitation
    renderer can read.
    """

    voice: str
    start_bar: int
    bars: int
    role: str = "subject"
    countersubject: bool = False

    def __post_init__(self) -> None:
        if self.voice not in VOICES:
            raise ValueError(
                f"unknown exposition voice {self.voice!r}; "
                f"expected one of {list(VOICES)}"
            )
        if self.role not in ROLES:
            raise ValueError(
                f"unknown exposition role {self.role!r}; "
                f"expected one of {list(ROLES)}"
            )
        if isinstance(self.start_bar, bool) or not isinstance(self.start_bar, int):
            raise ValueError("an entry start_bar must be an integer")
        if self.start_bar < 0:
            raise ValueError("an entry start_bar must be >= 0")
        if isinstance(self.bars, bool) or not isinstance(self.bars, int):
            raise ValueError("an entry bars must be an integer")
        if self.bars < 1:
            raise ValueError("an entry needs at least one bar")
        if self.role == "answer" and self.voice != "bass":
            raise ValueError(
                "the fuga renderer only answers in the bass, "
                f"got an answer in {self.voice!r}"
            )


@dataclass(frozen=True)
class ExpositionSpec:
    """A bounded entry plan. `check_realized` is the whole validator."""

    id: str
    pattern: str
    meter: str
    subject_bars: int
    entries: tuple[Entry, ...]
    imitation: ImitationSpec = BACH_IMITATION

    def __post_init__(self) -> None:
        self.check_realized()

    @property
    def length(self) -> int:
        """Total bars, from bar 0 to the last entry's end."""
        return sum(entry.bars for entry in self.entries)

    def check_realized(self) -> None:
        """Refuse a plan the preview renderer cannot realize."""
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("an exposition id must be a non-empty string")
        if not isinstance(self.pattern, str) or not self.pattern:
            raise ValueError("an exposition pattern must be a non-empty string")
        if not isinstance(self.meter, str) or not self.meter:
            raise ValueError("an exposition meter must be a non-empty string")
        if (
            isinstance(self.subject_bars, bool)
            or not isinstance(self.subject_bars, int)
            or not 1 <= self.subject_bars <= MAX_SUBJECT_BARS
        ):
            raise ValueError(
                f"subject_bars must be an integer in 1..{MAX_SUBJECT_BARS}"
            )
        if not isinstance(self.imitation, ImitationSpec):
            raise ValueError("imitation must be an ImitationSpec")
        self.imitation.check_realized()
        if self.imitation.lag != self.subject_bars:
            raise ValueError(
                "the imitation lag must equal subject_bars, so the answer "
                "quotes the preceding subject"
            )
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple of Entry objects")
        if not 2 <= len(self.entries) <= MAX_ENTRIES:
            raise ValueError(
                f"an exposition needs 2..{MAX_ENTRIES} entries, "
                f"got {len(self.entries)}"
            )
        if not all(isinstance(entry, Entry) for entry in self.entries):
            raise ValueError("entries must be a tuple of Entry objects")
        if self.entries[0].start_bar != 0:
            raise ValueError("entries[0].start_bar must be 0")

        previous_end = 0
        for index, entry in enumerate(self.entries):
            if entry.bars != self.subject_bars:
                raise ValueError(
                    f"entries[{index}].bars must equal subject_bars "
                    f"({self.subject_bars})"
                )
            if entry.start_bar < previous_end:
                raise ValueError(
                    f"entries[{index}].start_bar overlaps or is out of order"
                )
            if entry.start_bar != previous_end:
                raise ValueError(
                    f"entries[{index}].start_bar must be {previous_end}; "
                    "preview entries are contiguous"
                )
            expected_role = "subject" if index % 2 == 0 else "answer"
            if entry.role != expected_role:
                raise ValueError(
                    f"entries[{index}].role must be {expected_role!r}; "
                    "roles alternate from the subject"
                )
            previous_end = entry.start_bar + entry.bars
        if previous_end > MAX_EXPOSITION_BARS:
            raise ValueError(
                f"an exposition is capped at {MAX_EXPOSITION_BARS} bars, "
                f"got {previous_end}"
            )


BACH_EXPOSITION = ExpositionSpec(
    id="bach_exposition",
    pattern="bach_fuga",
    meter="4/4",
    subject_bars=2,
    entries=(
        Entry(voice="soprano", start_bar=0, bars=2, role="subject"),
        Entry(voice="bass", start_bar=2, bars=2, role="answer"),
        Entry(voice="alto", start_bar=4, bars=2, role="subject"),
    ),
)

# Preview-only id table. It is deliberately separate from
# `procedure_specs.PROCEDURES`, so a candidate cannot change production.
EXPOSITIONS: dict[str, ExpositionSpec] = {BACH_EXPOSITION.id: BACH_EXPOSITION}


def resolve_exposition(procedure_id: str) -> ExpositionSpec:
    """Return the named exposition, or raise a message naming the unknown id."""
    if not isinstance(procedure_id, str) or not procedure_id:
        raise ValueError("an exposition procedure id must be a non-empty string")
    try:
        return EXPOSITIONS[procedure_id]
    except KeyError:
        raise ValueError(
            f"unknown exposition procedure {procedure_id!r}; "
            f"expected one of {sorted(EXPOSITIONS)}"
        ) from None
