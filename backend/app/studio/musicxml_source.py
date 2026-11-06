"""Resolve the MusicXML import implementation used by the Studio API.

The API router is written against one small contract (``parse_musicxml``,
``slice_score``, ``score_summary``, ``ImportedScore``). A dedicated parser is
being built as ``app.studio.musicxml_import``; this seam prefers it as soon as
it exists and otherwise falls back to the bounded stdlib reader in
``musicxml_import_fallback``.

Using ``find_spec`` instead of ``try: import`` keeps a broken real parser
visible: if the module exists but fails to import, the error is raised instead
of silently degrading to the fallback.
"""

from __future__ import annotations

import importlib
import importlib.util

_REAL_MODULE = "app.studio.musicxml_import"
_FALLBACK_MODULE = "app.studio.musicxml_import_fallback"


def _resolve() -> tuple[object, str]:
    if importlib.util.find_spec(_REAL_MODULE) is not None:
        return importlib.import_module(_REAL_MODULE), _REAL_MODULE
    return importlib.import_module(_FALLBACK_MODULE), _FALLBACK_MODULE


_module, PARSER_MODULE = _resolve()

ImportedScore = _module.ImportedScore
parse_musicxml = _module.parse_musicxml
score_summary = _module.score_summary
slice_score = _module.slice_score

__all__ = [
    "ImportedScore",
    "PARSER_MODULE",
    "parse_musicxml",
    "score_summary",
    "slice_score",
]
