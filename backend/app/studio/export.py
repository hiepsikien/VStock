"""Deterministic JSON export for the Studio pilot sentence specs.

Layout: one file per `(pattern, meter)` pair, named
`<pattern>-<meter>.json`, where the wildcard meter `"*"` becomes `any` and
`/` becomes `-` (for example `castillo-3-4.json`, `galop-any.json`). Every file
is a v1 wrapper with its specs sorted by `(select.length_min, id)`, JSON keys
sorted, two-space indent, and a trailing newline.

Run from `backend/`::

    python3 -m app.studio.export           # write app/studio/specs/
    python3 -m app.studio.export --check   # fail if the files are stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.sonify.sentence_specs import METER_ANY, SENTENCE_SPECS, SentenceSpec
from app.studio.sentence_spec import specs_to_payload

# Torroba's four pilot patterns, then Sor's galop. Order fixes the file list.
PILOT_PATTERNS = ("castillo", "sonatina", "fandanguillo", "danza", "galop")

SPECS_DIR = Path(__file__).with_name("specs")


def spec_filename(pattern: str, meter: str) -> str:
    """The stable filename for one registry key."""
    suffix = "any" if meter == METER_ANY else meter.replace("/", "-")
    return f"{pattern}-{suffix}.json"


def _pilot_rows() -> dict[tuple[str, str], tuple[SentenceSpec, ...]]:
    # Import both owners so their module-level register() calls have run.
    import app.sonify.guitar_sor  # noqa: F401
    import app.sonify.guitar_torroba  # noqa: F401

    rows = {
        key: specs
        for key, specs in SENTENCE_SPECS.items()
        if key[0] in PILOT_PATTERNS
    }
    return dict(sorted(rows.items(), key=lambda item: _key_order(item[0])))


def _key_order(key: tuple[str, str]) -> tuple[int, str]:
    pattern, meter = key
    return PILOT_PATTERNS.index(pattern), meter


def _rendered_files() -> dict[str, str]:
    rendered: dict[str, str] = {}
    for (pattern, meter), specs in _pilot_rows().items():
        ordered = tuple(
            sorted(specs, key=lambda spec: (spec.select.length_min, spec.id))
        )
        payload = specs_to_payload(ordered)
        rendered[spec_filename(pattern, meter)] = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )
    return rendered


def export_specs(directory: str | Path = SPECS_DIR) -> list[Path]:
    """Write every pilot row and return the written paths."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, text in _rendered_files().items():
        path = target / name
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def stale_specs(directory: str | Path = SPECS_DIR) -> list[Path]:
    """Return expected files that are missing or differ from disk."""
    target = Path(directory)
    stale: list[Path] = []
    for name, text in _rendered_files().items():
        path = target / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            stale.append(path)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale files and exit non-zero instead of writing",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=SPECS_DIR,
        help=f"output directory (default: {SPECS_DIR})",
    )
    args = parser.parse_args(argv)

    if args.check:
        stale = stale_specs(args.directory)
        for path in stale:
            print(f"stale: {path}", file=sys.stderr)
        return 1 if stale else 0

    for path in export_specs(args.directory):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
