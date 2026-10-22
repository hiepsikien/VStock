"""Instrument rows beside the four genres. Classic stays the row already shipping."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.sonify.audio import RECAP_REVISION, SPAN_REVISION, RecapAsset, RecapStore, _STORED_NAME
from app.sonify.ensemble import ensemble_for, fit_ensemble
from app.sonify.keys import A_KEY
from app.sonify.model import Bar, NoteEvent
from app.sonify.musicxml import score_to_musicxml
from app.sonify.render import render


def _note(midi: int) -> NoteEvent:
    return NoteEvent(bar=0, beat=0.0, midi=midi, duration_beats=1.0, voice=1)


def _score():
    return render(
        [Bar(100.0, 100.0, 100.0)] * 30,
        framed=False,
        regimes=("sideway",) * 3,
    )


def test_classic_score_keeps_the_current_bass_writing() -> None:
    xml = score_to_musicxml(_score())
    assert "<instrument-name>Electric Bass (finger)</instrument-name>" in xml
    assert "<octave-change>-1</octave-change>" in xml
    assert "ensemble=" not in RecapAsset(
        symbol="VNM",
        day=date(2026, 10, 22),
        variant="symphony",
        audio_path=Path("x.m4a"),
        duration_sec=1,
        map_duration_sec=1,
        peaks=[],
        bar_count=30,
        media_type="audio/mp4",
    ).audio_url


def test_wood_names_and_pitch_floors() -> None:
    base = _score()
    planted = replace(base, ensemble="wood", lead=(_note(50),), support=(_note(48),))
    fitted = fit_ensemble(planted)
    assert fitted.lead[0].midi == 62
    assert fitted.support[0].midi == 60
    xml = score_to_musicxml(planted)
    assert "<part-name>Oboe</part-name>" in xml
    assert "<part-name>Clarinet in Bb</part-name>" in xml
    assert "<instrument-name>Clarinet</instrument-name>" in xml
    assert "<octave-change>-1</octave-change>" in xml


def test_a_major_wood_fold_uses_the_sounding_pitch() -> None:
    fitted = fit_ensemble(replace(_score(), ensemble="wood", key=A_KEY, lead=(_note(60),)))
    assert fitted.lead[0].midi == 72


def test_brass_caps_the_trumpet_and_the_horn_fill() -> None:
    fitted = fit_ensemble(
        replace(_score(), ensemble="brass", lead=(_note(84),), comp=(_note(79),))
    )
    assert fitted.lead[0].midi == 72
    assert fitted.comp[0].midi == 67
    xml = score_to_musicxml(replace(_score(), ensemble="brass"))
    assert "<part-name>French Horns a6</part-name>" in xml
    assert "<instrument-name>Horn in F</instrument-name>" in xml


def test_organ_hands_a_low_lead_to_the_baritone() -> None:
    fitted = fit_ensemble(
        replace(_score(), ensemble="organ", variant="jazz", lead=(_note(55), _note(56)))
    )
    assert [note.midi for note in fitted.lead] == [56]
    assert fitted.support[-1].midi == 55


def test_choir_sings_at_pitch_and_clamps_viola_and_bass() -> None:
    base = replace(_score(), ensemble="choir", variant="ambient", comp=(_note(45),), low=(_note(35), _note(36)))
    fitted = fit_ensemble(base)
    assert fitted.comp[0].midi == 57
    assert [note.midi for note in fitted.low] == [47, 36]
    xml = score_to_musicxml(base)
    assert "<part-name>Basses</part-name>" in xml
    assert "<octave-change>" not in xml


def test_breath_keeps_the_english_horn_top() -> None:
    fitted = fit_ensemble(replace(_score(), ensemble="breath", variant="ambient", lead=(_note(84),)))
    assert fitted.lead[0].midi == 84


def test_ensemble_must_belong_to_the_variant() -> None:
    assert ensemble_for("jazz", "classic") == "classic"
    assert ensemble_for("jazz", "soul") == "soul"
    with pytest.raises(ValueError):
        ensemble_for("jazz", "wood")


def test_cache_names_keep_the_classic_stem(tmp_path: Path) -> None:
    store = RecapStore(tmp_path)
    day = date(2026, 10, 22)
    classic = store._stem("VNM", day, "symphony", 30)
    assert classic == f"VNM_2026-10-22_symphony_{RECAP_REVISION}_30"
    wood = store._stem("VNM", day, "symphony", 30, "wood")
    assert wood == f"VNM_2026-10-22_symphony-wood_{RECAP_REVISION}_30"
    assert _STORED_NAME.match(f"{classic}.m4a")
    assert _STORED_NAME.match(f"{wood}.json")
    span = store._span_stem("VNM", "1W", 0, "symphony", 5, "1.0")
    assert f"_symphony_{SPAN_REVISION}_" in span
    band = store._span_stem("VNM", "1W", 0, "symphony", 5, "1.0", "wood")
    assert f"_symphony_wood_{SPAN_REVISION}_" in band
    assert f"_symphony_{SPAN_REVISION}_" not in band
