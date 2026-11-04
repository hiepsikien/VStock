"""Printed name of a guitar movement, keyed `(ensemble, span, index)`.

A pattern names a *unit* inside a movement (`level: topic`). A movement is the
printed chapter, and its name is an identity of its own: it does not follow the
pattern the macro chooser happens to pick for this market, and a texture never
lends it a name. The table is total for every span the guitar renders as a
movement: `1D`/`1W` hold one, `1M` four, `3M` three.

The names draft the suite a listener already hears: the topic each ensemble
prints for that slot where one is stable, and the work behind the texture
(`Arpeggio`, `Tremolo`, `Chord Melody`) where the current label is a technique.
Entries marked `# TODO review` are drafts that need an editorial pass; every
other row is a topic name the ensemble already prints today.

`1Y` has no row. A year is twelve calendar movements; `span.py` reuses the
`1M` programme by month instead of inventing a second table here.
"""

from __future__ import annotations

TITLES: dict[tuple[str, str, int], str] = {
    # Sor: Etude, Cantabile, Elegy, Galop, Variations are all printed today.
    ("classic", "1D", 0): "Etude",
    ("classic", "1W", 0): "Etude",
    ("classic", "1M", 0): "Etude",
    ("classic", "1M", 1): "Cantabile",
    ("classic", "1M", 2): "Elegy",
    ("classic", "1M", 3): "Galop",
    ("classic", "3M", 0): "Etude",
    ("classic", "3M", 1): "Cantabile",
    ("classic", "3M", 2): "Galop",
    # Villa-Lobos. The arpeggio and block-chord textures borrow the suite
    # movement they are drawn from; `Etude 1`/`Etude 11` stay as printed.
    ("villa", "1D", 0): "Choros No. 1",  # TODO review: villa_pattern (Arpeggio)
    ("villa", "1W", 0): "Choros No. 1",  # TODO review: villa_pattern (Arpeggio)
    ("villa", "1M", 0): "Choros No. 1",  # TODO review: villa_pattern (Arpeggio)
    ("villa", "1M", 1): "Prelude",  # TODO review: thumb_cantabile (Prélude No. 1)
    ("villa", "1M", 2): "Mazurka-Choro",  # TODO review: chord_melody (Chord Melody)
    ("villa", "1M", 3): "Etude 11",
    ("villa", "3M", 0): "Choros No. 1",  # TODO review: villa_pattern (Arpeggio)
    ("villa", "3M", 1): "Prelude",  # TODO review: thumb_cantabile (Prélude No. 1)
    ("villa", "3M", 2): "Etude 1",
    # Barrios. `Cathedral` is the printed name of `preludio`; the tremolo rows
    # take the work that drives the texture.
    ("barrios", "1D", 0): "Ultimo Tremolo",  # TODO review: tremolo (Tremolo)
    ("barrios", "1W", 0): "Ultimo Tremolo",  # TODO review: tremolo (Tremolo)
    ("barrios", "1M", 0): "Cathedral",
    ("barrios", "1M", 1): "Andante",
    ("barrios", "1M", 2): "Polka",
    ("barrios", "1M", 3): "Ultimo Tremolo",  # TODO review: tremolo (Tremolo)
    ("barrios", "3M", 0): "Cathedral",
    ("barrios", "3M", 1): "Andante",
    ("barrios", "3M", 2): "Ultimo Tremolo",  # TODO review: tremolo (Tremolo)
    # Brouwer: four topics, one per movement.
    ("brouwer", "1D", 0): "Etude",
    ("brouwer", "1W", 0): "Etude",
    ("brouwer", "1M", 0): "Etude",
    ("brouwer", "1M", 1): "Ballade",
    ("brouwer", "1M", 2): "Sarabande",
    ("brouwer", "1M", 3): "Dance",
    ("brouwer", "3M", 0): "Etude",
    ("brouwer", "3M", 1): "Ballade",
    ("brouwer", "3M", 2): "Dance",
    # Bach: the suite order is the identity, not the region row.
    ("bach", "1D", 0): "Courante",
    ("bach", "1W", 0): "Bourree",
    ("bach", "1M", 0): "Allemande",
    ("bach", "1M", 1): "Courante",
    ("bach", "1M", 2): "Sarabande",
    ("bach", "1M", 3): "Gigue",
    ("bach", "3M", 0): "Allemande",
    ("bach", "3M", 1): "Courante",
    ("bach", "3M", 2): "Gigue",
    # Torroba: the castles open, the suite closes on its dance.
    ("torroba", "1D", 0): "Olite",
    ("torroba", "1W", 0): "Olite",
    ("torroba", "1M", 0): "Olite",
    ("torroba", "1M", 1): "Castillo",
    ("torroba", "1M", 2): "Alcaniz",
    ("torroba", "1M", 3): "Danza",
    ("torroba", "3M", 0): "Olite",
    ("torroba", "3M", 1): "Castillo",
    ("torroba", "3M", 2): "Danza",
}


def movement_title(ensemble: str, span: str, index: int) -> str:
    """One movement's printed name. A missing key raises `KeyError`."""
    return TITLES[(ensemble, span, index)]
