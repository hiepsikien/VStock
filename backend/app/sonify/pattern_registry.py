"""Pattern `level` and `name_source`, as data.

`level` answers one question: can this id stand as a printed unit (`topic`), or
is it a technique that only fills a cell (`texture`)? `name_source` records
where the printed name comes from, so a label can be judged later without
re-reading every renderer. It is metadata about the name, not the mechanism.

`None` is only for texture: a texture owns no name, even when `_PATTERN_TITLE`
still prints one today (that is the section 8 violation, fixed elsewhere).

This module changes no behaviour. `_FAMILY`, `_PATTERN_TITLE`, `PROFILES`, and
the renderers stay as they are; `validate()` is the only code that reads them,
and it only reports.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

# `topic` = names itself; `texture` = an idiom that fills a cell.
LEVELS = frozenset({"topic", "texture"})
# Where a printed topic name comes from. Same axes as the model doc section 2,
# plus `tempo` (Andante) and `device` (Hemiola), which the six did not cover.
NAME_SOURCES = frozenset(
    {"dance", "work", "genre", "form", "function", "character", "tempo", "device"}
)


@dataclass(frozen=True)
class PatternMeta:
    """One id's taxonomy. `name_source` is None exactly when `level` is texture."""

    id: str
    level: str
    name_source: str | None


# Grouped by the ensemble that renders the id, matching the inventory in the
# model doc section 12. `thumb_cantabile` is one id shared by Barrios and Villa.
PATTERN_META: Mapping[str, PatternMeta] = MappingProxyType({
    # Bach: suite movements are dances; the fugue and chaconne are forms (model doc section 4.2), the prelude a function.
    "bach_allemande": PatternMeta("bach_allemande", "topic", "dance"),
    "bach_bourree": PatternMeta("bach_bourree", "topic", "dance"),
    "bach_chaconne": PatternMeta("bach_chaconne", "topic", "form"),
    "bach_courante": PatternMeta("bach_courante", "topic", "dance"),
    "bach_fuga": PatternMeta("bach_fuga", "topic", "form"),
    "bach_gavotte": PatternMeta("bach_gavotte", "topic", "dance"),
    "bach_gigue": PatternMeta("bach_gigue", "topic", "dance"),
    "bach_prelude": PatternMeta("bach_prelude", "topic", "function"),
    "bach_sarabande": PatternMeta("bach_sarabande", "topic", "dance"),
    # Barrios: three dances, a tempo marking, a genre, and one rhythmic device.
    "andante": PatternMeta("andante", "topic", "tempo"),
    "choro": PatternMeta("choro", "topic", "genre"),
    "hemiola": PatternMeta("hemiola", "topic", "device"),
    "polca": PatternMeta("polca", "topic", "dance"),
    "preludio": PatternMeta("preludio", "topic", "function"),
    "thumb_cantabile": PatternMeta("thumb_cantabile", "texture", None),
    "tremolo": PatternMeta("tremolo", "texture", None),
    "vals": PatternMeta("vals", "topic", "dance"),
    # Brouwer: two dances, an etude, and a ballade.
    "brouwer_etude": PatternMeta("brouwer_etude", "topic", "genre"),
    "elogio_pizz": PatternMeta("elogio_pizz", "topic", "dance"),
    "noviembre": PatternMeta("noviembre", "topic", "genre"),
    "sarabande": PatternMeta("sarabande", "topic", "dance"),
    # Classic: three character pieces, one dance, one form, one genre.
    "cantabile": PatternMeta("cantabile", "topic", "character"),
    "elegiaque": PatternMeta("elegiaque", "topic", "genre"),
    "galop": PatternMeta("galop", "topic", "dance"),
    "mozart_var": PatternMeta("mozart_var", "topic", "form"),
    "study": PatternMeta("study", "topic", "genre"),
    # Torroba: four borrowed work names, two dances, one form.
    "alcaniz": PatternMeta("alcaniz", "topic", "work"),
    "castillo": PatternMeta("castillo", "topic", "work"),
    "danza": PatternMeta("danza", "topic", "dance"),
    "fandanguillo": PatternMeta("fandanguillo", "topic", "dance"),
    "olite": PatternMeta("olite", "topic", "work"),
    "sonatina": PatternMeta("sonatina", "topic", "form"),
    "torroba_tremolo": PatternMeta("torroba_tremolo", "topic", "work"),
    # Villa: two etudes and two textures. `thumb_cantabile` lives with Barrios.
    "chord_melody": PatternMeta("chord_melody", "texture", None),
    "etude1": PatternMeta("etude1", "topic", "genre"),
    "etude11": PatternMeta("etude11", "topic", "genre"),
    "villa_pattern": PatternMeta("villa_pattern", "texture", None),
    # Pedal is a frame path, not a printed unit: no wave profile, never a headline.
    "pedal": PatternMeta("pedal", "texture", None),
})


def meta(pattern_id: str) -> PatternMeta:
    """One id's metadata. An unknown id raises `KeyError`."""
    return PATTERN_META[pattern_id]


def validate() -> None:
    """Check the table against the modules it describes. Raises `ValueError`.

    Explicit raises, not asserts: `python -O` strips asserts, and this is the
    guard that keeps `level` from becoming a claim. Imports stay lazy so the
    module is importable on its own and stays off the `program` -> `span` path.
    """
    from app.sonify.guitar_patterns import _FAMILY
    from app.sonify.guitar_wave import PROFILES
    from app.sonify.program import pattern_title

    missing = sorted(set(_FAMILY) - set(PATTERN_META))
    extra = sorted(set(PATTERN_META) - set(_FAMILY))
    if missing or extra:
        raise ValueError(
            f"registry drifted from _FAMILY: missing={missing} extra={extra}"
        )
    for pattern, found in PATTERN_META.items():
        if found.id != pattern:
            raise ValueError(f"{pattern}: id is {found.id!r}")
        if found.level not in LEVELS:
            raise ValueError(f"{pattern}: bad level {found.level!r}")
        if found.level == "texture":
            if found.name_source is not None:
                raise ValueError(f"{pattern}: texture must not claim a name_source")
            continue
        if found.name_source not in NAME_SOURCES:
            raise ValueError(f"{pattern}: bad name_source {found.name_source!r}")

    # Check the printed title per PROFILES row, not once per id: a topic whose
    # title depends on the ensemble must resolve for every ensemble it ships in.
    for ensemble, pattern in PROFILES:
        if PATTERN_META[pattern].level != "topic":
            continue
        if not pattern_title(pattern, ensemble):
            raise ValueError(f"({ensemble}, {pattern}): topic has no printed title")
