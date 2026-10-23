"""Villa-Lobos harmony dialect locked by the guitar plan, test 11."""

from __future__ import annotations

import pytest

from app.sonify.chords import AF, C, CM, EF, F, FDIM7, FM, G, fifth_above_bass, same_harmonic_root
from app.sonify.form import FormSection, FormSpec, plan_markov_chords
from app.sonify.harmony import COMMON, VILLA, color_pitch_classes, dialect_for
from app.sonify.keys import D_KEY, transpose_chord
from app.sonify.quantize import bar_quantization_loss, c_major_scale, c_natural_minor_scale

_MAJOR = {
    "Csus2", "Dsus2", "Fsus2", "Gsus2", "Asus2",
    "Csus4", "Dsus4", "Esus4", "Gsus4", "Asus4",
    "Cadd9", "Fadd9", "Gadd9",
    "G7sus4", "D7sus4", "A7sus4", "E7sus4",
    "Bbsus2", "Ebsus2",
}
_MINOR = {
    "Csus2", "Ebsus2", "Fsus2", "Absus2",
    "Csus4", "Dsus4", "Ebsus4", "Fsus4", "Gsus4",
    "Cmadd9", "Fmadd9",
    "C7sus4", "D7sus4", "F7sus4", "G7sus4",
}


def _spec(count: int, *, splits: tuple[int, ...] = (), kinds: tuple[str, ...] | None = None) -> FormSpec:
    if kinds is not None:
        sections = tuple(
            FormSection(index, index + 1, kind, 0)  # type: ignore[arg-type]
            for index, kind in enumerate(kinds)
        )
        return FormSpec(bars=len(kinds), bpm=88, sections=sections, borrowed=True)
    starts = [0, *splits, count]
    sections = tuple(
        FormSection(starts[index], starts[index + 1], "phrase", 0)
        for index in range(len(starts) - 1)
    )
    return FormSpec(bars=count, bpm=88, sections=sections, borrowed=True)


def _plan(
    bars: list[list[int]],
    *,
    character="rally",
    regime="uptrend",
    kinds: tuple[str, ...] | None = None,
    splits: tuple[int, ...] = (),
    mode="major",
    dialect=VILLA,
):
    spec = _spec(len(bars), splits=splits, kinds=kinds)
    scale = c_natural_minor_scale() if mode == "minor" else c_major_scale()
    flat = [note for bar in bars for note in bar]
    return plan_markov_chords(
        (regime,) * spec.regime_slots,
        flat,
        scale,
        spec,
        character=character,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        dialect=dialect,
    )


def _bar(*notes: int) -> list[int]:
    row = [notes[-1]] * 8
    row[0] = notes[0]
    if len(notes) > 1:
        row[4] = notes[1]
    return row


def test_catalog_matches_the_scale_rules() -> None:
    major = {chord.name for chord in VILLA.extra("major")}
    minor = {chord.name for chord in VILLA.extra("minor")}
    assert major == _MAJOR
    assert minor == _MINOR
    assert "B7sus4" not in major
    assert "E7sus4" in major
    assert "A7sus4" not in minor
    assert {"C7sus4", "D7sus4", "F7sus4", "G7sus4"} <= minor
    assert "Ebadd9" not in minor and "Abadd9" not in minor
    for chord in (*VILLA.extra("major"), *VILLA.extra("minor")):
        assert (chord.pitches[2] - chord.pitches[0]) % 12 == 7
        assert fifth_above_bass(chord) % 12 == chord.pitches[2] % 12


def test_shares_root_covers_suspended_only() -> None:
    csus4 = next(chord for chord in VILLA.extra("major") if chord.name == "Csus4")
    cadd9 = next(chord for chord in VILLA.extra("major") if chord.name == "Cadd9")
    assert same_harmonic_root(C, csus4) is False
    assert VILLA.shares_root(C, csus4) is True
    assert same_harmonic_root(C, cadd9) is True
    assert VILLA.shares_root(C, cadd9) is False
    assert COMMON.shares_root(C, csus4) is False
    assert COMMON.allowed(csus4, pedal=True, phrase_downbeat=True, character=None, mode="major") is True
    assert dialect_for("classic") is COMMON
    assert dialect_for("barrios") is COMMON
    assert dialect_for("villa") is VILLA


def test_planing_ebsus2_is_heard_as_eb() -> None:
    ebsus2 = next(chord for chord in VILLA.extra("major") if chord.name == "Ebsus2")
    assert VILLA.is_parent(EF, ebsus2, "major") is True
    heard = VILLA.opening_pitch_classes(ebsus2, "major")
    assert heard == EF.pitch_classes
    assert bar_quantization_loss([67] * 8, heard, c_major_scale()) == 0.0
    stripped = ebsus2.pitch_classes - color_pitch_classes(ebsus2)
    with pytest.raises(ValueError):
        bar_quantization_loss([67] * 8, stripped, c_major_scale())


def test_planing_edges_are_major_only() -> None:
    ebsus2 = next(chord for chord in VILLA.extra("minor") if chord.name == "Ebsus2")
    fsus2 = next(chord for chord in VILLA.extra("major") if chord.name == "Fsus2")
    assert VILLA.transition(fsus2, ebsus2, "major") == 0.22
    assert VILLA.transition(ebsus2, EF, "major") == 0.0
    assert VILLA.transition(ebsus2, EF, "minor") == 0.40
    assert VILLA.transition(ebsus2, F, "major") == 0.34


def test_transpose_spells_the_fourth_as_a_fourth() -> None:
    csus4 = next(chord for chord in VILLA.extra("major") if chord.name == "Csus4")
    spelled = transpose_chord(csus4, D_KEY)
    assert spelled.degrees == (0, 3, 4)
    fourth = spelled.pitches[1] % 12
    assert all(tone[1] != "F" for tone in spelled.tones if tone[0] == fourth)


def _tonic() -> list[int]:
    """C with E on the downbeat, so a G sus4 cannot read the bar as its fourth."""
    return [64, 60, 60, 60, 60, 60, 60, 60]


def test_strong_f_becomes_csus4_only_while_c_is_held() -> None:
    held = _plan([_tonic(), [65] * 8])
    assert held[0].name in {"C", "Cmaj7"}
    assert held[1].name == "Csus4"
    longer = _plan([_tonic(), _tonic(), [65] * 8], character="calm")
    assert longer[0].name in {"C", "Cmaj7"}
    assert longer[1].name in {"C", "Cmaj7"}
    assert longer[2].name == "Csus4"
    rally_hold = _plan([_tonic(), [65] * 8, [65] * 8], character="rally")
    assert rally_hold[1].name == "Csus4"
    assert rally_hold[2].name == "Csus4"
    boundary = _plan([_tonic(), [65] * 8], splits=(1,))
    assert boundary[0].name in {"C", "Cmaj7"}
    assert boundary[1].name == "Csus4"


def test_four_weak_a_eighths_make_f_cheaper_than_the_rally_hold() -> None:
    poisoned = [65, 69, 69, 69, 65, 69, 65, 65]
    chords = _plan([_tonic(), [65] * 8, poisoned], character="rally")
    assert chords[1].name == "Csus4"
    assert chords[2].name in {"F", "Fmaj7"}


def test_root_or_fifth_does_not_paint_sus_and_a_pulls_to_f() -> None:
    only_c = _plan([_tonic(), [60] * 8])
    only_g = _plan([_tonic(), [67] * 8])
    with_a = _plan([_tonic(), _bar(65, 69, 60)])
    assert only_c[1].name != "Csus4"
    assert only_g[1].name != "Csus4"
    assert with_a[1].name in {"F", "Fmaj7"}


def test_opening_bar_depends_on_regime_and_character() -> None:
    assert _plan([[65] * 8], character="rally")[0].name in {"F", "Fmaj7"}
    assert _plan([[65] * 8], character="volatile")[0].name in {"F", "Fmaj7"}
    assert _plan([[65] * 8], character="selloff")[0].name == "Dm"
    assert _plan([[65] * 8], regime="sideway")[0].name not in {"F", "Fmaj7"}
    pedal = _plan([[65] * 8, [65] * 8], kinds=("intro", "intro"))
    assert pedal[0].name in {"C", "Cmaj7"}
    assert pedal[1].name in {"C", "Cmaj7"}


def test_add9_needs_the_ninth_and_the_same_root() -> None:
    both = _bar(64, 62, 64)
    held = _plan([_tonic(), both])
    assert held[1].name == "Cadd9"
    longer = _plan([_tonic(), _tonic(), both], character="calm")
    assert longer[2].name == "Cadd9"
    boundary = _plan([_tonic(), both], splits=(1,))
    assert boundary[1].name == "Cadd9"
    only_e = _plan([_tonic(), [64] * 8])
    assert only_e[1].name in {"C", "Cmaj7"}


def test_common_dialect_does_not_invent_sus() -> None:
    chords = _plan([[60] * 8, [65] * 8], dialect=COMMON)
    assert all(chord.kind_text not in {"sus2", "sus4", "7sus4", "add9"} for chord in chords)
    assert all(chord.quality_group != "suspended" for chord in chords)


def _extra(mode: str, name: str):
    return next(chord for chord in VILLA.extra(mode) if chord.name == name)


def test_a_root_note_does_not_open_the_sus_that_calls_it_a_fourth() -> None:
    """A second-bar same-root move is priced at 0.15, so it must not collect 0.70."""
    opened = _plan([[60] * 8, [60] * 8, [65] * 8], character="rally")
    assert opened[0].name in {"C", "Cmaj7"}
    assert opened[1].name in {"C", "Cmaj7"}
    assert opened[2].name == "Csus4"
    only_g = _plan([[67] * 8, [67] * 8], character="rally")
    assert all(chord.name != "Dsus4" for chord in only_g)
    # A bare tonic does not open a sus of another root. The G→C door and the
    # calm floor-cancel both lose to the diatonic path.
    for character in ("rally", "calm", "selloff", None):
        bare = _plan([[60] * 8, [60] * 8, [60] * 8], character=character)
        common = _plan([[60] * 8, [60] * 8, [60] * 8], character=character, dialect=COMMON)
        assert [chord.name for chord in bare] == [chord.name for chord in common]
    minor_c = _plan([[60] * 8, [60] * 8, [60] * 8], character="rally", mode="minor")
    minor_common = _plan(
        [[60] * 8, [60] * 8, [60] * 8], character="rally", mode="minor", dialect=COMMON
    )
    assert [chord.name for chord in minor_c] == [chord.name for chord in minor_common]
    only_eb = _plan([[63] * 8, [63] * 8], character="rally", mode="minor")
    assert all(chord.name != "F7sus4" for chord in only_eb)


def test_a_color_stays_silent_until_its_root_is_held() -> None:
    """A fourth or a flat seventh only counts once that root is already held."""
    for character in ("rally", "calm", "selloff", "volatile", None):
        fa = [[65] * 8, [65] * 8, [65] * 8]
        assert [chord.name for chord in _plan(fa, character=character)] == [
            chord.name for chord in _plan(fa, character=character, dialect=COMMON)
        ]
        eb = [[63] * 8, [63] * 8, [63] * 8]
        assert [chord.name for chord in _plan(eb, character=character, mode="minor")] == [
            chord.name
            for chord in _plan(eb, character=character, mode="minor", dialect=COMMON)
        ]
    split = [[60] * 8, [60] * 8, [60] * 8]
    assert [chord.name for chord in _plan(split, character="selloff", splits=(1,))] == [
        chord.name for chord in _plan(split, character="selloff", splits=(1,), dialect=COMMON)
    ]


def test_flat_roots_do_not_borrow_the_natural_letter_row() -> None:
    for name in ("Asus4", "Asus2", "A7sus4"):
        assert VILLA.transition(AF, _extra("major", name), "major") == 0.0
    for name in ("Esus4", "E7sus4"):
        assert VILLA.transition(EF, _extra("major", name), "major") == 0.0
    assert VILLA.transition(_extra("major", "Asus4"), AF, "major") == 0.0
    assert VILLA.transition(G, _extra("major", "Csus4"), "major") == 0.50
    assert VILLA.transition(FDIM7, _extra("minor", "Fsus4"), "minor") == 0.0
    assert VILLA.transition(EF, _extra("minor", "Fsus2"), "minor") == 0.22
    assert VILLA.transition(C, _extra("minor", "Ebsus4"), "minor") == 0.08
    assert VILLA.transition(_extra("minor", "Ebsus4"), FM, "minor") == 0.22
    assert VILLA.transition(AF, _extra("minor", "Absus2"), "minor") == 0.30
    flat = _plan([[63] * 8, [68] * 8], character="rally", mode="minor")
    assert all(chord.root_step == "E" and chord.alter == -1 for chord in flat)
    assert flat[1].name == "Ebsus4"


def test_minor_add9_uses_the_parent_third() -> None:
    cmadd9 = next(chord for chord in VILLA.extra("minor") if chord.name == "Cmadd9")
    fmadd9 = next(chord for chord in VILLA.extra("minor") if chord.name == "Fmadd9")
    assert cmadd9.pitches[1] % 12 == CM.pitches[1] % 12
    assert fmadd9.pitches[1] % 12 == FM.pitches[1] % 12
    assert cmadd9.quality_group == "major"
