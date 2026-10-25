"""Names the chart prints. The dance is the pattern the guitar writer chose."""

from __future__ import annotations

import logging

from app.sonify.guitar_patterns import _HEADLINE, _SKIP_VOICES
from app.sonify.keys import KeySpec, MovementCharacter
from app.sonify.model import Bar
from app.sonify.render import render
from app.sonify.span import FormSpec, PreparedMovement, movement_title

logger = logging.getLogger(__name__)

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
    return _PATTERN_TITLE.get(pattern, "Etude")


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
    """The dance `render` will write for these bars. Voice rendering is skipped."""
    found: list[str] = []
    token_headline = _HEADLINE.set(found)
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
        _SKIP_VOICES.reset(token_skip)
    return pattern_title(found[0] if found else "study", ensemble)


def _label_month(label: str) -> int | None:
    head = label.strip().split("/", 1)[0]
    if not head.isdigit():
        return None
    month = int(head)
    return month if 1 <= month <= 12 else None


def span_movement_names(
    movements: tuple[PreparedMovement, ...] | list[PreparedMovement],
    *,
    variant: str,
    ensemble: str,
    span: str,
) -> list[str]:
    return [
        span_movement_name(movement, variant=variant, ensemble=ensemble, span=span, index=index)
        for index, movement in enumerate(movements)
    ]


def span_movement_name(
    movement: PreparedMovement,
    *,
    variant: str,
    ensemble: str,
    span: str,
    index: int,
) -> str:
    """Name sent on the span manifest. Guitar asks the pattern picker."""
    if variant == "guitar":
        try:
            return guitar_movement_name(
                movement.bars,
                ensemble=ensemble,
                key=movement.key,
                character=movement.character,
                form=movement.spec,
                source_groups=movement.groups,
                mode=movement.mode,
                home_pedal=movement.home_pedal,
                character_at=movement.bar_characters,
                gap_leads=movement.gap_leads,
                outro_override=movement.outro_override,
                framed=False,
            )
        except Exception:
            logger.warning("guitar movement name failed for %s %s", span, movement.label, exc_info=True)
            return "Etude"
    month = _label_month(movement.label) if span == "1Y" else None
    return movement_title(variant, span, index, movement.spec, month) or ""
