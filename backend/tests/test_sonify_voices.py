"""Symphony, jazz, and minimalist voices on the open 250 ms tape."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.sonify import router
from app.sonify.chords import AM9, CMAJ9, DM9, EM7, FMAJ9, G9
from app.sonify.model import STREAM_VARIANTS, VARIANTS
from app.sonify.stream import BAR_NOTES, BEAT_NOTES, BUCKET_MS, Trade, render_stream
from app.sonify.voices import approach_note

_JAZZ = {chord.name: chord for chord in (CMAJ9, FMAJ9, DM9, G9, AM9, EM7)}


def _tape(volumes: list[float], price: float = 100.0) -> list[Trade]:
    return [Trade(index * BUCKET_MS, price, volume) for index, volume in enumerate(volumes)]


def _roles(variant: str) -> set[str]:
    notes = render_stream(_tape([1.0] * 32), variant=variant)  # type: ignore[arg-type]
    return {voice.role for note in notes for voice in note.voices}


def test_three_variants_orchestrate_differently() -> None:
    roles = {variant: _roles(variant) for variant in STREAM_VARIANTS}
    assert "violin" in roles["symphony"] and "piano" in roles["symphony"]
    assert "sax" in roles["jazz"] and "rhodes" in roles["jazz"]
    assert "arp" in roles["minimalist"] and "pad" in roles["minimalist"]
    assert "glass" in roles["ambient"] and "halo" in roles["ambient"] and "drone" in roles["ambient"]
    assert roles["symphony"].isdisjoint({"sax", "arp", "glass"})
    assert roles["jazz"].isdisjoint({"violin", "arp", "glass"})
    assert roles["minimalist"].isdisjoint({"violin", "sax", "glass"})
    assert roles["ambient"].isdisjoint({"violin", "sax", "arp"})


def test_each_variant_locks_notes_when_the_tape_grows() -> None:
    early_trades = _tape([1.0, 5.0] * 20)
    later = early_trades + _tape([2.0] * 16)
    later = [Trade(index * BUCKET_MS, trade.price, trade.qty) for index, trade in enumerate(later)]
    for variant in STREAM_VARIANTS:
        early = render_stream(early_trades, seed=2, variant=variant)  # type: ignore[arg-type]
        full = render_stream(later, seed=2, variant=variant)  # type: ignore[arg-type]
        assert early == full[: len(early)]


def test_quiet_symphony_holds_one_bass_for_the_bar() -> None:
    # Bar 0 spreads the volume scale, bar 1 is silent, bar 2 reads that silence.
    volumes = [1.0] * 8 + [8.0] * 8 + [0.0] * 16 + [0.0] * 16
    notes = render_stream(_tape(volumes), variant="symphony")
    quiet = [note for note in notes if note.seq >= 32]
    assert quiet[0].band == "p"
    bass = [note.seq for note in quiet if any(voice.role == "bass" for voice in note.voices)]
    assert bass == [32]


def test_approach_note_steps_off_the_next_root() -> None:
    landed = approach_note(43, 38, 43)
    assert landed in (36, 40)
    assert landed != 38


def test_jazz_walks_into_the_chord_already_chosen_for_the_next_bar() -> None:
    notes = render_stream(_tape([1.0, 3.0, 1.0, 4.0] * 16), seed=1, variant="jazz")
    assert notes[0].chord == "Cmaj9"
    assert notes[0].swing is True
    approaches = [
        note
        for note in notes
        if note.seq % BAR_NOTES == 12 and note.seq + BEAT_NOTES < len(notes)
    ]
    assert approaches
    checked = 0
    for note in approaches:
        basses = [voice for voice in note.voices if voice.role == "bass"]
        if not basses:
            continue
        chord = _JAZZ[note.chord]
        nxt = _JAZZ[notes[note.seq + BEAT_NOTES].chord]
        fifth = chord.bass_midi + 7
        beat3 = chord.bass_midi + 12 if note.band == "f" else fifth
        assert basses[0].midi == approach_note(beat3, nxt.bass_midi, fifth)
        checked += 1
    assert checked > 0


def test_loud_minimalist_pulses_four_times_a_second() -> None:
    volumes = [1.0] * 8 + [8.0] * 8 + [40.0] * 32
    notes = render_stream(_tape(volumes), variant="minimalist")
    loud = [note for note in notes if 32 <= note.seq < 48]
    assert loud[0].band == "f"
    for note in loud:
        assert sum(voice.role == "pulse" for voice in note.voices) == 1
        if note.seq % BEAT_NOTES == 0 and (note.seq // BEAT_NOTES) % 4 in (1, 3):
            assert any(voice.role == "stab" for voice in note.voices)


def test_climb_from_g5_to_c7_returns_for_every_variant() -> None:
    """G, A, B and F do not exist inside a fifth. Arranging them must return."""
    from app.sonify.chords import CMAJ7
    from app.sonify.voices import arrange

    for variant in STREAM_VARIANTS:
        for midi in range(79, 97):
            voices, _sax = arrange(
                variant,  # type: ignore[arg-type]
                seq=midi,
                midi=midi,
                velocity=80,
                chord=CMAJ7,
                next_chord=CMAJ7,
                band="mf",
                prev_sax=None,
                allow_high=True,
                price_held=False,
            )
            assert voices
            for voice in voices:
                if voice.role == "flute":
                    assert 79 <= voice.midi <= 88
                if voice.role == "vibe":
                    assert 84 <= voice.midi <= 89
                if voice.role in ("bell", "shimmer"):
                    assert 84 <= voice.midi <= 96
        notes = render_stream(
            [Trade(index * BUCKET_MS, 80_000 + index * 80, 1.0) for index in range(64)],
            variant=variant,  # type: ignore[arg-type]
        )
        assert notes
        assert max(note.midi for note in notes) >= 79


def test_ambient_strikes_sparse_long_notes_on_steady_price_and_blooms_with_volume() -> None:
    # Steady price across 32 buckets (2 bars): ambient glass melody only rings once per bar.
    steady = render_stream(_tape([1.0] * 32, price=81_500.0), variant="ambient")
    glass_strikes = [
        voice
        for note in steady
        for voice in note.voices
        if voice.role == "glass"
    ]
    assert len(glass_strikes) == 2
    assert all(voice.dur_ms >= 2500 for voice in glass_strikes)

    # Low liquidity vs high liquidity in ambient mode: high volume blooms swell & sub voices.
    volumes = [1.0] * 8 + [8.0] * 8 + [0.0] * 32 + [50.0] * 32
    dynamic = render_stream(_tape(volumes, price=81_500.0), variant="ambient")
    quiet_bar = [note for note in dynamic if 32 <= note.seq < 48]
    loud_bar = [note for note in dynamic if 64 <= note.seq < 80]
    assert quiet_bar[0].band == "p"
    assert loud_bar[0].band == "f"
    quiet_swells = sum(voice.role in ("swell", "sub") for note in quiet_bar for voice in note.voices)
    loud_swells = sum(voice.role in ("swell", "sub") for note in loud_bar for voice in note.voices)
    assert quiet_swells == 0
    assert loud_swells >= 6
    assert any(voice.role == "sub" for note in loud_bar for voice in note.voices)


def test_websocket_selects_the_jazz_variant() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/sonify/ws?variant=jazz&speed=500") as socket:
            hello = socket.receive_json()
            assert hello["variant"] == "jazz"
            first = socket.receive_json()
            assert first["swing"] is True
            assert any(voice["role"] == "sax" for voice in first["voices"])
            assert first["chord"] == "Cmaj9"
