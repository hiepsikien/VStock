"""Report the telemetry that gates the B2/B3 parameter waves.

Run from `backend/`:

  .venv/bin/python scripts/sonify_events_report.py --since 2026-11-01
  .venv/bin/python scripts/sonify_events_report.py --json --db /data/events.sqlite3

Use `--db` more than once when several instances kept separate SQLite files.
The gate in `docs/sonify-params-tier-bc-roadmap.md` needs the denominator
(`ReplayRoom` sessions with a play), A/B usage, and saved profiles with at
least one B/C knob.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, time as clock_time, timedelta, timezone
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]

from app.sonify.events import EventStore


def _timestamp(value: str, *, end: bool) -> float:
    text = value.strip()
    if len(text) == 10:
        day = date.fromisoformat(text)
        moment = datetime.combine(day, clock_time.min, tzinfo=timezone.utc)
        if end:
            moment += timedelta(days=1)
        return moment.timestamp()
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _merge(summaries: list[dict]) -> dict:
    total = 0
    by_name: dict[str, int] = {}
    by_day: dict[str, int] = {}
    replay = 0
    ab = 0
    saved = 0
    with_bc = 0
    for summary in summaries:
        total += summary["total"]
        for key, value in summary["byName"].items():
            by_name[key] = by_name.get(key, 0) + value
        for key, value in summary["byDay"].items():
            by_day[key] = by_day.get(key, 0) + value
        replay += summary["sessions"]["replay"]
        ab += summary["sessions"]["ab"]
        saved += summary["profiles"]["saved"]
        with_bc += summary["profiles"]["withBc"]
    return {
        "total": total,
        "byName": dict(sorted(by_name.items())),
        "byDay": dict(sorted(by_day.items())),
        "sessions": {
            "replay": replay,
            "ab": ab,
            "abRatio": (ab / replay) if replay else 0.0,
        },
        "profiles": {
            "saved": saved,
            "withBc": with_bc,
            "withBcRatio": (with_bc / saved) if saved else 0.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        action="append",
        default=[],
        help="SQLite file; repeat to merge several instances",
    )
    parser.add_argument("--since", help="ISO date or datetime (UTC)")
    parser.add_argument("--until", help="ISO date or datetime (UTC); date is exclusive")
    parser.add_argument(
        "--prune-days",
        type=int,
        help="delete events older than N days before reporting (use with care)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON only")
    args = parser.parse_args()

    since = _timestamp(args.since, end=False) if args.since else None
    until = _timestamp(args.until, end=True) if args.until else None
    paths = [Path(item) for item in args.db] or [None]
    for path in paths:
        if path is not None and not path.is_file():
            parser.error(f"database not found: {path}")
    if args.prune_days is not None:
        cutoff = time.time() - max(0, args.prune_days) * 86_400
        deleted = sum(EventStore(path).prune(cutoff) for path in paths)
        print(f"pruned:     {deleted}", file=sys.stderr)
    summaries = [EventStore(path).summary(since=since, until=until) for path in paths]
    result = _merge(summaries)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"events:      {result['total']}")
    print(f"by day:      {result['byDay']}")
    print(f"by name:     {result['byName']}")
    print(
        "sessions:    "
        f"{result['sessions']['replay']} replay, "
        f"{result['sessions']['ab']} A/B "
        f"({result['sessions']['abRatio']:.0%})"
    )
    print(
        "profiles:    "
        f"{result['profiles']['saved']} saved, "
        f"{result['profiles']['withBc']} with B/C "
        f"({result['profiles']['withBcRatio']:.0%})"
    )


if __name__ == "__main__":
    main()
