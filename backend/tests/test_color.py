"""The colour chain is generated from typed specs, and amount 1 is the old chain."""

from __future__ import annotations

from array import array
from pathlib import Path

from app.sonify.audio import _wav_samples, write_wav
from app.sonify.params import DEFAULT_PARAMS, compose_params
from app.sonify.preset import apply_preset, preset_chain

OLD = {
    "symphony": (
        "highshelf=f=8000:g=-2,equalizer=f=300:t=h:w=200:g=1.5,"
        "asoftclip=type=tanh:threshold=0.9:oversample=1,"
        "aecho=1:1:24|40|58:0.07|0.045|0.03"
    ),
    "guitar": (
        "highshelf=f=8000:g=-1,equalizer=f=280:t=h:w=180:g=1.2,"
        "aecho=1:1:12|20:0.05|0.03"
    ),
    "jazz": (
        "aecho=1:1:22|36|48:0.08|0.05|0.03,"
        "asoftclip=type=tanh:threshold=0.9:oversample=1"
    ),
    "minimalist": "aecho=1:1:18|32:0.07|0.04",
    "ambient": "highshelf=f=7000:g=-1.5,aecho=1:1:28|48:0.06|0.035",
}


def test_amount_one_reproduces_every_default_chain() -> None:
    for variant, chain in OLD.items():
        assert preset_chain(variant).ffmpeg == chain


def test_amount_scales_gain_decay_and_threshold() -> None:
    chain = preset_chain("symphony", amount=0.5)
    assert chain is not None
    assert "g=-1," in chain.ffmpeg
    assert "threshold=0.95" in chain.ffmpeg
    assert "0.035|0.0225|0.015" in chain.ffmpeg


def test_amount_past_one_stays_a_valid_chain() -> None:
    chain = preset_chain("symphony", amount=2.0)
    assert chain is not None
    assert "g=-4," in chain.ffmpeg
    assert "g=3," in chain.ffmpeg
    assert "threshold=0.8" in chain.ffmpeg
    assert "0.14|0.09|0.06" in chain.ffmpeg


def test_zero_amount_is_dry() -> None:
    assert preset_chain("symphony", amount=0.0) is None
    with compose_params({**DEFAULT_PARAMS, "color": 0.0, "noise": 0.0}):
        assert apply_preset(Path("dry.wav"), Path("out.wav"), "symphony") is False


def test_noise_percent_is_absolute() -> None:
    full = preset_chain("symphony", noise_percent=0.5)
    quiet = preset_chain("symphony", noise_percent=0.25)
    assert full is not None and quiet is not None
    assert full.noise == 0.005
    assert quiet.noise == 0.0025
    assert preset_chain("guitar", noise_percent=0.5).noise == 0.005
    assert preset_chain("symphony").noise == 0.001


def test_noise_lands_even_when_the_color_chain_is_off(tmp_path: Path) -> None:
    dry = tmp_path / "dry.wav"
    write_wav(dry, 1, 8000, array("f", [0.0] * 64))
    out = tmp_path / "out.wav"
    params = {**DEFAULT_PARAMS, "color": 0.0, "noise": 0.5}
    assert apply_preset(dry, out, "symphony", params=params)
    _channels, _rate, heard = _wav_samples(out)
    assert max(abs(sample) for sample in heard) > 0.001
