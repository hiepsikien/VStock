"""The cache keeps Default and legacy files, and bounds profile hashes."""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

import pytest

from app.sonify import audio
from app.sonify.audio import RECAP_REVISION, SPAN_REVISION, RecapStore, _STORED_NAME
from app.sonify.params import DEFAULT_PARAMS, params_from_flags


def _touch(path: Path, stamp: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    os.utime(path, (stamp, stamp))


def test_stored_name_accepts_a_profile_mark() -> None:
    assert _STORED_NAME.match("FPT_2026-10-14_symphony_77_1_p0123456789ab.m4a")
    assert _STORED_NAME.match("FPT_2026-10-14_symphony-wood_77_1_p0123456789ab.json")
    assert not _STORED_NAME.match("FPT_2026-10-14_symphony_77_1_pXYZ.m4a")


def test_prune_keeps_default_legacy_and_profile_files(tmp_path: Path, monkeypatch) -> None:
    store = RecapStore(tmp_path)
    day = date(2026, 10, 14)
    default = store._stem("FPT", day, "symphony", 1)
    legacy = store._stem("FPT", day, "symphony", 1, params=params_from_flags(False, True))
    profile = store._stem(
        "FPT", day, "symphony", 1, params={**DEFAULT_PARAMS, "tempo": 0.96}
    )
    old = f"FPT_2026-10-14_symphony_old_{1}"
    now = time.time()
    for stem in (default, legacy, profile, old):
        _touch(tmp_path / f"{stem}.m4a", now)

    store.prune()

    assert (tmp_path / f"{default}.m4a").is_file()
    assert (tmp_path / f"{legacy}.m4a").is_file()
    assert (tmp_path / f"{profile}.m4a").is_file()
    assert not (tmp_path / f"{old}.m4a").exists()


def test_lru_bounds_profile_hashes_and_pins_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(audio, "PARAMS_CACHE_MAX", 2)
    store = RecapStore(tmp_path)
    day = date(2026, 10, 14)
    now = time.time()
    default = store._stem("FPT", day, "symphony", 1)
    _touch(tmp_path / f"{default}.m4a", now)

    stems = [
        store._stem(
            "FPT", day, "symphony", 1, params={**DEFAULT_PARAMS, "tempo": factor}
        )
        for factor in (0.90, 0.95, 1.05)
    ]
    for index, stem in enumerate(stems):
        _touch(tmp_path / f"{stem}.m4a", now + index)
        _touch(tmp_path / f"{stem}.json", now + index)

    store.prune()

    assert (tmp_path / f"{default}.m4a").is_file()
    assert not (tmp_path / f"{stems[0]}.m4a").exists()
    assert not (tmp_path / f"{stems[0]}.json").exists()
    assert (tmp_path / f"{stems[1]}.m4a").is_file()
    assert (tmp_path / f"{stems[2]}.m4a").is_file()


def test_span_prune_keeps_a_profile_movement(tmp_path: Path, monkeypatch) -> None:
    store = RecapStore(tmp_path)
    spans = tmp_path / "spans"
    plain = store._span_stem("FPT", "1W", 0, "symphony", 5, "1.0")
    profile = store._span_stem(
        "FPT", "1W", 0, "symphony", 5, "1.0", params={**DEFAULT_PARAMS, "tempo": 0.96}
    )
    old = store._span_stem("FPT", "1W", 0, "symphony", 5, "1.0").replace(
        f"_{SPAN_REVISION}_", "_old_"
    )
    now = time.time()
    for stem in (plain, profile, old):
        _touch(spans / f"{stem}.m4a", now)

    store.prune()

    assert f"_{RECAP_REVISION}_" not in plain
    assert (spans / f"{plain}.m4a").is_file()
    assert (spans / f"{profile}.m4a").is_file()
    assert not (spans / f"{old}.m4a").exists()


@pytest.mark.parametrize("factor", [0.75, 1.0, 1.25])
def test_cache_identity_is_a_pure_function_of_params(factor: float) -> None:
    left = {**DEFAULT_PARAMS, "tempo": factor}
    right = {**DEFAULT_PARAMS, "tempo": round(factor, 2)}
    assert audio.cache_mark(left) == audio.cache_mark(right)
