"""Names the chart prints. A guitar dance is stored with the audio file."""

from __future__ import annotations

from app.sonify.guitar_patterns import _FORM, _HEADLINE, _SKIP_VOICES
from app.sonify.keys import KeySpec, MovementCharacter
from app.sonify.model import Bar
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
    "bach_fuga": "Fugue",
    "bach_bourree": "Bourree",
    "bach_gavotte": "Gavotte",
    "bach_sarabande": "Sarabande",
    "bach_gigue": "Gigue",
    "bach_chaconne": "Chaconne",
    "pedal": "Pedal",
}


def pattern_title(pattern: str, ensemble: str) -> str:
    """English dance name. Villa's thumb line is Prélude No. 1, not a chorale."""
    if pattern == "thumb_cantabile" and ensemble == "villa":
        return "Prelude"
    return _PATTERN_TITLE.get(pattern, "")


def pattern_form(ids: list[str], ensemble: str) -> str:
    """One name, or opening — first change — close.

    Adjacent repeats collapse. A longer row keeps those three names so the
    movement title stays a single A–B–A line.
    """
    names: list[str] = []
    for pattern in ids:
        title = pattern_title(pattern, ensemble)
        if not title or (names and names[-1] == title):
            continue
        names.append(title)
    if not names:
        return ""
    if len(names) > 3:
        names = [names[0], names[1], names[-1]]
        if names[-1] == names[1]:
            names = names[:2]
    if len(names) == 1:
        return names[0]
    return " — ".join(names)


def _written_dance(found: list[str], forms: list[list[str]], ensemble: str) -> str:
    titled = pattern_form(forms[0], ensemble) if forms else ""
    if titled:
        return titled
    if found:
        return pattern_title(found[0], ensemble)
    return ""


def guitar_movement_name(
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
) -> str:
    """The dance `render` will write. Tests use this; a request must not."""
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


def span_movement_name(
    movement: PreparedMovement,
    *,
    variant: str,
    span: str,
    index: int,
    stored: str = "",
) -> str:
    """Name sent on the span manifest.

    A guitar dance is the name written beside the audio file. Reading the
    manifest does not plan the score again, and a missing name stays blank.
    """
    if variant == "guitar":
        return stored
    month = _label_month(movement.label) if span == "1Y" else None
    return movement_title(variant, span, index, movement.spec, month) or ""
