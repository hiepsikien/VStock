"""Printed name of a guitar movement, keyed `(ensemble, span, index)`.

A pattern names a *unit* inside a movement (`level: topic`). A movement is the
printed chapter, and its name is an identity of its own: it does not follow the
pattern the macro chooser happens to pick for this market, and a texture never
lends it a name. The table is total for every span the guitar renders as a
movement: `1D`/`1W` hold one, `1M` four, `3M` three.

The names draft the suite a listener already hears: the topic each ensemble
prints for that slot where one is stable, and the work behind the texture
(`Arpeggio`, `Tremolo`, `Chord Melody`) where the current label is a technique.
The texture-derived names were reviewed: `Choros No. 1`, `Cathedral`,
`Mazurka-Choro`, and `Ultimo Tremolo`. Every other row is a topic name the
ensemble already prints today.

`1D` and `1W` also read the character: `CHARACTER_TITLES` overrides the
default row so a calm day does not print the same name as a rally day. `1Y`
has no row; a year is twelve calendar movements, and `span.py` reuses the `1M`
programme by month instead of inventing a second table here.
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
    ("villa", "1D", 0): "Choros No. 1",  # villa_pattern (Arpeggio)
    ("villa", "1W", 0): "Choros No. 1",  # villa_pattern (Arpeggio)
    ("villa", "1M", 0): "Choros No. 1",  # villa_pattern (Arpeggio)
    ("villa", "1M", 1): "Cathedral",  # thumb_cantabile (Prélude No. 1)
    ("villa", "1M", 2): "Mazurka-Choro",  # chord_melody (Chord Melody)
    ("villa", "1M", 3): "Etude 11",
    ("villa", "3M", 0): "Choros No. 1",  # villa_pattern (Arpeggio)
    ("villa", "3M", 1): "Cathedral",  # thumb_cantabile (Prélude No. 1)
    ("villa", "3M", 2): "Etude 1",
    # Barrios. `Cathedral` is the printed name of `preludio`; the tremolo rows
    # take the work that drives the texture.
    ("barrios", "1D", 0): "Ultimo Tremolo",  # tremolo (Tremolo)
    ("barrios", "1W", 0): "Ultimo Tremolo",  # tremolo (Tremolo)
    ("barrios", "1M", 0): "Cathedral",
    ("barrios", "1M", 1): "Andante",
    ("barrios", "1M", 2): "Polka",
    ("barrios", "1M", 3): "Ultimo Tremolo",  # tremolo (Tremolo)
    ("barrios", "3M", 0): "Cathedral",
    ("barrios", "3M", 1): "Andante",
    ("barrios", "3M", 2): "Ultimo Tremolo",  # tremolo (Tremolo)
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


# `1D` and `1W` are one movement whose character changes what the writer picks,
# so their printed name turns with the character too. The index-keyed `TITLES`
# row above is the `character is None` default; these override it.
CHARACTER_TITLES: dict[tuple[str, str, str], str] = {
    # Sor
    ("classic", "1D", "calm"): "Cantabile",
    ("classic", "1D", "rally"): "Galop",
    ("classic", "1D", "selloff"): "Elegy",
    ("classic", "1D", "volatile"): "Variations",
    ("classic", "1W", "calm"): "Cantabile",
    ("classic", "1W", "rally"): "Etude",
    ("classic", "1W", "selloff"): "Elegy",
    ("classic", "1W", "volatile"): "Variations",
    # Villa-Lobos: the old texture names map to the work they are drawn from.
    ("villa", "1D", "calm"): "Mazurka-Choro",
    ("villa", "1D", "rally"): "Etude 1",
    ("villa", "1D", "selloff"): "Cathedral",
    ("villa", "1D", "volatile"): "Etude 11",
    ("villa", "1W", "calm"): "Mazurka-Choro",
    ("villa", "1W", "rally"): "Etude 1",
    ("villa", "1W", "selloff"): "Cathedral",
    ("villa", "1W", "volatile"): "Etude 11",
    # Barrios: a day is the tremolo; a week opens on the prelude until the
    # character turns to selloff/volatile.
    ("barrios", "1D", "calm"): "Ultimo Tremolo",
    ("barrios", "1D", "rally"): "Ultimo Tremolo",
    ("barrios", "1D", "selloff"): "Ultimo Tremolo",
    ("barrios", "1D", "volatile"): "Ultimo Tremolo",
    ("barrios", "1W", "calm"): "Cathedral",
    ("barrios", "1W", "rally"): "Cathedral",
    ("barrios", "1W", "selloff"): "Ultimo Tremolo",
    ("barrios", "1W", "volatile"): "Ultimo Tremolo",
    # Brouwer
    ("brouwer", "1D", "calm"): "Ballade",
    ("brouwer", "1D", "rally"): "Etude",
    ("brouwer", "1D", "selloff"): "Sarabande",
    ("brouwer", "1D", "volatile"): "Dance",
    ("brouwer", "1W", "calm"): "Ballade",
    ("brouwer", "1W", "rally"): "Etude",
    ("brouwer", "1W", "selloff"): "Sarabande",
    ("brouwer", "1W", "volatile"): "Dance",
    # Bach: a day keeps the suite order; the turn names the movement it picks.
    ("bach", "1D", "calm"): "Prelude",
    ("bach", "1D", "rally"): "Courante",
    ("bach", "1D", "selloff"): "Chaconne",
    ("bach", "1D", "volatile"): "Fugue",
    ("bach", "1W", "calm"): "Prelude",
    ("bach", "1W", "rally"): "Bourree",
    ("bach", "1W", "selloff"): "Chaconne",
    ("bach", "1W", "volatile"): "Fugue",
    # Torroba: the day opens on a castle; the week keeps its opening.
    ("torroba", "1D", "calm"): "Castillo",
    ("torroba", "1D", "rally"): "Olite",
    ("torroba", "1D", "selloff"): "Castillo",
    ("torroba", "1D", "volatile"): "Olite",
    ("torroba", "1W", "calm"): "Olite",
    ("torroba", "1W", "rally"): "Olite",
    ("torroba", "1W", "selloff"): "Olite",
    ("torroba", "1W", "volatile"): "Olite",
}


def movement_title(
    ensemble: str, span: str, index: int, character: str | None = None
) -> str:
    """One movement's printed name. A missing key raises `KeyError`.

    `1D`/`1W` also read `character`; the index-keyed row is the default when
    the caller has no character. `1M`/`3M` are identities of the slot order.
    """
    if span in ("1D", "1W") and character is not None:
        return CHARACTER_TITLES[(ensemble, span, character)]
    return TITLES[(ensemble, span, index)]
