"""Names the chart prints. A guitar dance is stored with the audio file."""

from __future__ import annotations

from app.sonify.guitar_patterns import _FORM, _HEADLINE, _SKIP_VOICES
from app.sonify.keys import KeySpec, MovementCharacter
from app.sonify.model import Bar
from app.sonify.movement_titles import movement_title as guitar_movement_title
from app.sonify.pattern_registry import meta as pattern_meta
from app.sonify.render import render
from app.sonify.span import FormSpec, PreparedMovement, movement_title

_PATTERN_TITLE = {
    "study": "Etude",
    "galop": "Galop",
    "mozart_var": "Variations",
    "elegiaque": "Elegy",
    "cantabile": "Cantabile",
    "villa_pattern": "Arpeggio",
    "etude1": "Etude 1",
    "etude11": "Etude 11",
    "chord_melody": "Chord Melody",
    "thumb_cantabile": "Cantabile",
    "preludio": "Prelude",
    "tremolo": "Tremolo",
    "andante": "Andante",
    "choro": "Choro",
    "polca": "Polka",
    "hemiola": "Hemiola",
    "vals": "Waltz",
    "noviembre": "Ballade",
    "brouwer_etude": "Etude",
    "elogio_pizz": "Dance",
    "sarabande": "Sarabande",
    "castillo": "Castillo",
    "sonatina": "Sonatina",
    "fandanguillo": "Fandanguillo",
    "danza": "Danza",
    "torroba_tremolo": "Juglar",
    "alcaniz": "Alcaniz",
    "olite": "Olite",
    "bach_fuga": "Fugue",
    "bach_bourree": "Bourree",
    "bach_gavotte": "Gavotte",
    "bach_sarabande": "Sarabande",
    "bach_gigue": "Gigue",
    "bach_chaconne": "Chaconne",
    "bach_prelude": "Prelude",
    "bach_allemande": "Allemande",
    "bach_courante": "Courante",
    "pedal": "Pedal",
}


def pattern_title(pattern: str, ensemble: str) -> str:
    """English dance name, for direct/diagnostic callers.

    This is not the printed movement name: that is
    `movement_titles.movement_title`, and `pattern_form` drops every id whose
    registry `level` is `texture`. Villa's thumb line is Prélude No. 1, not a
    chorale.
    """
    if pattern == "thumb_cantabile" and ensemble == "villa":
        return "Prelude"
    return _PATTERN_TITLE.get(pattern, "")


def _topic(pattern: str) -> bool:
    """True only for an id that can stand as a printed unit.

    A texture owns no name, even while `_PATTERN_TITLE` still carries one for
    it. Unknown ids are not topics either, so a stray id cannot print.
    """
    try:
        return pattern_meta(pattern).level == "topic"
    except KeyError:
        return False


def pattern_form(ids: list[str], ensemble: str) -> str:
    """Up to three topic names. Textures are dropped before the row is built.

    Adjacent repeats collapse first. Three different names stay all three,
    so Prelude — Andante — Sarabande is not shortened. Four or more keep the
    opening, the center name, and the close: a week that hears Andante in
    the middle is not titled for the second region only. A rally week of
    four sessions plays Prelude, Andante, Andante, Prelude; adjacent Andante
    collapses and the title is Prelude — Andante — Prelude. A row that does not end on
    its opening, such as A–B–A–B, shortens to the two ends once the center
    repeats the opening.

    This is the non-printed form description now. The movement's printed name
    is `Movement.title`; a texture-only row returns "".
    """
    names: list[str] = []
    for pattern in ids:
        if not _topic(pattern):
            continue
        title = pattern_title(pattern, ensemble)
        if not title or (names and names[-1] == title):
            continue
        names.append(title)
    if len(names) > 3:
        picked = [names[0], names[len(names) // 2], names[-1]]
        names = []
        for title in picked:
            if not names or names[-1] != title:
                names.append(title)
    if len(names) <= 1:
        return names[0] if names else ""
    return " — ".join(names)


def _written_dance(found: list[str], forms: list[list[str]], ensemble: str) -> str:
    """The non-printed A–B–A row. Textures never reach either branch."""
    titled = pattern_form(forms[0], ensemble) if forms else ""
    if titled:
        return titled
    if found and _topic(found[0]):
        return pattern_title(found[0], ensemble)
    return ""


def guitar_form_description(
    bars: list[Bar],
    *,
    ensemble: str = "classic",
    key: KeySpec | None = None,
    character: MovementCharacter | None = None,
    form: FormSpec | None = None,
    source_groups: list[list[int]] | None = None,
    mode: str = "major",
    home_pedal: bool = False,
    character_at=None,
    gap_leads=None,
    outro_override=None,
    framed: bool = True,
    movement_index: int | None = None,
) -> str:
    """The non-printed form row `render` writes. Tests use this; a request must not.

    The printed name is the curated `Movement.title`, not this row.
    """
    found: list[str] = []
    forms: list[list[str]] = []
    token_headline = _HEADLINE.set(found)
    token_form = _FORM.set(forms)
    token_skip = _SKIP_VOICES.set(True)
    try:
        render(
            bars,
            variant="guitar",
            ensemble=ensemble,  # type: ignore[arg-type]
            key=key,
            character=character,
            form=form,
            source_groups=source_groups,
            mode=mode,
            home_pedal=home_pedal,
            character_at=character_at,
            gap_leads=gap_leads,
            outro_override=outro_override,
            framed=framed,
            movement_index=movement_index,
        )
    finally:
        _HEADLINE.reset(token_headline)
        _FORM.reset(token_form)
        _SKIP_VOICES.reset(token_skip)
    return _written_dance(found, forms, ensemble)


def _label_month(label: str) -> int | None:
    head = label.strip().split("/", 1)[0]
    if not head.isdigit():
        return None
    month = int(head)
    return month if 1 <= month <= 12 else None


def recap_movement_name(
    *,
    variant: str,
    ensemble: str,
    character: str | None,
    stored: str = "",
) -> str:
    """Printed daily name, recomputed on read.

    The daily recap stores a name beside its audio. Reading it from the table
    instead means a naming release does not invalidate every daily file; the
    stored value stays as a fallback for other variants.
    """
    if variant != "guitar":
        return stored
    return guitar_movement_title(ensemble, "1D", 0, character)


def span_movement_name(
    movement: PreparedMovement,
    *,
    variant: str,
    span: str,
    index: int,
) -> str:
    """Printed name sent on the span manifest.

    A guitar movement prints its curated `title`, planned before any audio is
    written, so the manifest does not read the audio's stored name. The old
    render-time name is now the non-printed form row.
    """
    if variant == "guitar":
        return movement.title
    month = _label_month(movement.label) if span == "1Y" else None
    return movement_title(variant, span, index, movement.spec, month) or ""


def span_form_description(*, variant: str, stored: str = "") -> str:
    """Non-printed A–B–A row. Guitar writes it beside the audio file.

    Other variants have no separate row, so the field stays empty. This is
    never the printed name: the frontend may show it as a tooltip or a
    secondary line, but the manifest `name` is `Movement.title`.
    """
    return stored if variant == "guitar" else ""
