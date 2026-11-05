"""Phase 0 schema tests for ``app.studio.texture_spec``.

These are bounded schema/validator tests. They never render, register, or
import ``guitar_patterns``; the registry test proves the import stays inert.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.sonify.form import METER_34, METER_44, METER_68, METER_128, Meter
from app.studio.texture_spec import (
    AuthoredEvent,
    MeterSpec,
    MeterVariant,
    PitchRef,
    TextureError,
    TextureSpec,
    TextureSpecError,
    check_texture_spec,
    parse_meter_spec,
    parse_texture_spec,
    publishable,
    texture_spec_to_mapping,
    validate_authored,
    validate_pitch_ref,
    validate_texture_spec,
)

ALL_METERS = (METER_44, METER_34, METER_68, METER_128)


def _variant(meter=METER_34, **overrides) -> MeterVariant:
    data = {
        "meter": MeterSpec.from_form_meter(meter),
        "materializer": "grid_3_4",
        "transform": "none",
        "unsupported": False,
        "reason": None,
        "sentences": (),
    }
    data.update(overrides)
    return MeterVariant(**data)


def _spec(**overrides) -> TextureSpec:
    data = {
        "id": "suite_mazurka",
        "composer": "villa",
        "kind": "pattern",
        "level": "topic",
        "parent": None,
        "runtime": "code",
        "status": "draft",
        "meter_variants": (_variant(),),
        "authored": (),
    }
    data.update(overrides)
    return TextureSpec(**data)


def _event(voice: int, beat: float, duration: float, **overrides) -> AuthoredEvent:
    data = {
        "bar": 0,
        "beat": beat,
        "duration_beats": duration,
        "voice": voice,
        "pitch": PitchRef.chord_root(),
    }
    data.update(overrides)
    return AuthoredEvent(**data)


def _paths(errors: tuple[TextureError, ...]) -> list[str]:
    return [error.path for error in errors]


# ---------------------------------------------------------------------------
# MeterSpec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("meter", ALL_METERS, ids=lambda meter: f"{meter.beats}/{meter.beat_type}")
def test_meter_spec_round_trips_every_form_meter(meter: Meter) -> None:
    spec = MeterSpec.from_form_meter(meter)
    mapping = spec.to_mapping()
    assert mapping["extra_weights"] == [[e, w] for e, w in meter.extra_weights]
    again = parse_meter_spec(json.loads(json.dumps(mapping)))
    assert again == spec
    assert again.key() == spec.key()
    assert again.to_form_meter() == meter


def test_meter_34_extra_weights_survive_round_trip() -> None:
    spec = MeterSpec.from_form_meter(METER_34)
    assert spec.extra_weights == ((4, 0.8),)
    assert parse_meter_spec(spec.to_mapping()).extra_weights == ((4, 0.8),)
    assert spec.to_form_meter() == METER_34
    assert MeterSpec.from_form_meter(METER_34).to_form_meter().extra_weights == ((4, 0.8),)


def test_meter_key_ignores_id() -> None:
    one = MeterSpec.from_form_meter(METER_34, id="valsa")
    two = MeterSpec.from_form_meter(METER_34, id="3/4")
    assert one.id != two.id
    assert one.key() == two.key()
    assert one != two
    assert one.to_mapping()["id"] == "valsa"


def test_meter_spec_rejects_inconsistent_eighths() -> None:
    with pytest.raises(TextureSpecError) as excinfo:
        parse_meter_spec(
            {
                "id": "3/4",
                "beats": 3,
                "beat_type": 4,
                "eighths_per_bar": 8,
                "strong_eighths": [0],
                "subbar_breaks": [4],
                "extra_weights": [],
            }
        )
    assert excinfo.value.path == "meter"
    assert "eighths_per_bar" in excinfo.value.message


# ---------------------------------------------------------------------------
# PitchRef
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ref",
    [
        PitchRef.melody_eighth(0),
        PitchRef.melody_eighth(2, 1),
        PitchRef.chord_degree(1),
        PitchRef.chord_degree(5),
        PitchRef.chord_root(),
        PitchRef.scale_step(-1),
        PitchRef.scale_step(3),
        PitchRef.literal_midi(0),
        PitchRef.literal_midi(127),
    ],
)
def test_every_pitch_kind_is_accepted(ref: PitchRef) -> None:
    assert validate_pitch_ref(ref) == ()
    assert PitchRef.from_mapping(ref.to_mapping()) == ref


def test_pitch_mapping_is_declarative_only() -> None:
    assert PitchRef.chord_root().to_mapping() == {"kind": "chord_root"}
    assert PitchRef.melody_eighth(0, 2).to_mapping() == {
        "kind": "melody_eighth",
        "eighth": 0,
        "offset": 2,
    }
    assert PitchRef.literal_midi(57).to_mapping() == {"kind": "literal_midi", "value": 57}


def test_unknown_pitch_kind_is_rejected() -> None:
    assert _paths(validate_pitch_ref(PitchRef(kind="price"))) == ["pitch.kind"]
    with pytest.raises(TextureSpecError) as excinfo:
        PitchRef.from_mapping({"kind": "price"})
    assert excinfo.value.path == "pitch.kind"


def test_unknown_or_invalid_pitch_field_is_rejected() -> None:
    # A field that belongs to another kind.
    assert "pitch.degree" in _paths(
        validate_pitch_ref(PitchRef(kind="chord_root", degree=1))
    )
    assert "pitch.eighth" in _paths(
        validate_pitch_ref(PitchRef(kind="literal_midi", value=57, eighth=0))
    )
    # A field that exists for no kind.
    with pytest.raises(TextureSpecError):
        PitchRef.from_mapping({"kind": "chord_root", "degree": 1})
    with pytest.raises(TextureSpecError):
        PitchRef.from_mapping({"kind": "chord_root", "midi": 60})


def test_melody_eighth_out_of_range_is_an_error_not_a_clamp() -> None:
    assert validate_pitch_ref(PitchRef.melody_eighth(3), melody_length=4) == ()
    assert _paths(validate_pitch_ref(PitchRef.melody_eighth(4), melody_length=4)) == [
        "pitch.eighth"
    ]
    assert _paths(
        validate_pitch_ref(PitchRef.melody_eighth(3, 1), melody_length=4)
    ) == ["pitch.offset"]
    assert _paths(validate_pitch_ref(PitchRef.melody_eighth(-1))) == ["pitch.eighth"]
    assert _paths(validate_pitch_ref(PitchRef.melody_eighth(0, -1))) == ["pitch.offset"]


def test_bad_degree_and_midi_are_rejected() -> None:
    assert _paths(validate_pitch_ref(PitchRef.chord_degree(0))) == ["pitch.degree"]
    assert _paths(validate_pitch_ref(PitchRef.chord_degree("1"))) == ["pitch.degree"]
    assert _paths(validate_pitch_ref(PitchRef.literal_midi(-1))) == ["pitch.value"]
    assert _paths(validate_pitch_ref(PitchRef.literal_midi(128))) == ["pitch.value"]
    assert _paths(validate_pitch_ref(PitchRef.literal_midi(60.0))) == ["pitch.value"]


def test_scale_step_accepts_negative_but_requires_an_integer() -> None:
    assert validate_pitch_ref(PitchRef.scale_step(-3)) == ()
    assert _paths(validate_pitch_ref(PitchRef.scale_step(1.5))) == ["pitch.steps"]


# ---------------------------------------------------------------------------
# AuthoredEvent and per-voice duration
# ---------------------------------------------------------------------------


def _three_voice_full_bar() -> tuple[AuthoredEvent, ...]:
    return (
        *(_event(1, beat, 1.0) for beat in range(4)),
        _event(2, 0.0, 2.0),
        _event(2, 2.0, 2.0),
        _event(3, 0.0, 4.0),
    )


def test_three_voices_each_fill_the_bar_at_once() -> None:
    events = _three_voice_full_bar()
    # All voices sound together: the raw duration sum is 12 beats, not 4.
    assert sum(event.duration_beats for event in events) == 12.0
    assert validate_authored(events, METER_44, require_full_bars=True) == ()


def test_require_full_bars_catches_a_short_voice() -> None:
    events = (_event(1, 0.0, 3.0),)
    errors = validate_authored(events, METER_44, require_full_bars=True)
    assert _paths(errors) == ["authored.events.voice[1].bar[0]"]
    assert "duration sum 3.0" in errors[0].message
    # Without the flag a short voice is a rest, not an error.
    assert validate_authored(events, METER_44) == ()


def test_overlap_in_one_voice_fails() -> None:
    events = (_event(1, 0.0, 2.0), _event(1, 1.0, 1.0))
    errors = validate_authored(events, METER_44)
    assert _paths(errors) == ["authored.events[1].beat"]
    assert "overlaps" in errors[0].message


def test_overlap_across_voices_is_allowed() -> None:
    events = (_event(1, 0.0, 4.0), _event(3, 0.0, 4.0), _event(2, 0.0, 4.0))
    assert validate_authored(events, METER_44, require_full_bars=True) == ()


def test_overflow_past_the_bar_fails() -> None:
    errors = validate_authored((_event(1, 3.0, 2.0),), METER_44)
    assert _paths(errors) == ["authored.events[0].duration_beats"]
    assert "overflows" in errors[0].message


def test_back_to_back_notes_and_bar_lengths_are_meter_aware() -> None:
    events = (_event(1, 0.0, 2.5, bar=0), _event(1, 2.5, 0.5, bar=0))
    assert validate_authored(events, METER_34) == ()
    # 2.5 beats is inside 3/4's 3 quarter beats but also inside 4/4.
    assert validate_authored(events, METER_44) == ()
    # 3.25 overflows 3/4.
    assert validate_authored((_event(1, 2.75, 0.5),), METER_34)


def test_event_voice_and_notational_metadata_ranges() -> None:
    assert _paths(validate_authored((_event(0, 0.0, 1.0),), METER_44)) == [
        "authored.events[0].voice"
    ]
    assert _paths(validate_authored((_event(1, 0.0, 0.0),), METER_44)) == [
        "authored.events[0].duration_beats"
    ]
    assert _paths(validate_authored((_event(1, 0.0, 1.0, staff=3),), METER_44)) == [
        "authored.events[0].staff"
    ]
    assert _paths(validate_authored((_event(1, 0.0, 1.0, string=7),), METER_44)) == [
        "authored.events[0].string"
    ]
    assert _paths(validate_authored((_event(1, 0.0, 1.0, fret=5),), METER_44)) == [
        "authored.events[0].fret"
    ]
    assert _paths(validate_authored((_event(1, 0.0, 1.0, review="maybe"),), METER_44)) == [
        "authored.events[0].review"
    ]
    assert _paths(
        validate_authored((_event(1, 0.0, 1.0, confidence=1.5),), METER_44)
    ) == ["authored.events[0].confidence"]


def test_accepts_tab_metadata() -> None:
    event = _event(
        1,
        0.0,
        1.0,
        string=1,
        fret=5,
        written_pitch="E4",
        sounding_pitch="E3",
        confidence=0.91,
        conflict=False,
        review="edited",
    )
    assert validate_authored((event,), METER_44) == ()
    mapping = event.to_mapping()
    assert mapping["string"] == 1
    assert mapping["fret"] == 5
    assert AuthoredEvent.from_mapping(mapping) == event


def test_tie_and_slur_endpoints_are_paired_per_voice() -> None:
    tie_events = (
        _event(1, 3.0, 1.0, bar=0, tie="start"),
        _event(1, 0.0, 1.0, bar=1, tie="stop"),
    )
    assert validate_authored(tie_events, METER_44) == ()

    lone_start = validate_authored((_event(1, 0.0, 1.0, tie="start"),), METER_44)
    assert _paths(lone_start) == ["authored.events[0].tie"]
    assert "without a stop" in lone_start[0].message

    lone_stop = validate_authored((_event(1, 0.0, 1.0, tie="stop"),), METER_44)
    assert _paths(lone_stop) == ["authored.events[0].tie"]
    assert "without a start" in lone_stop[0].message

    slur_events = (
        _event(2, 0.0, 1.0, slur="start"),
        _event(2, 1.0, 1.0, slur="stop"),
    )
    assert validate_authored(slur_events, METER_44) == ()
    assert _paths(
        validate_authored((_event(2, 0.0, 1.0, slur="start"),), METER_44)
    ) == ["authored.events[0].slur"]


def test_next_bar_tie_requires_a_stop_in_the_next_bar() -> None:
    events = (
        _event(1, 3.0, 1.0, bar=0, tie="next_bar"),
        _event(1, 0.0, 1.0, bar=1, tie="stop"),
    )
    assert validate_authored(events, METER_44) == ()
    errors = validate_authored((_event(1, 3.0, 1.0, bar=0, tie="next_bar"),), METER_44)
    assert _paths(errors) == ["authored.events[0].tie"]
    assert "next bar" in errors[0].message


# ---------------------------------------------------------------------------
# TextureSpec
# ---------------------------------------------------------------------------


def _full_spec() -> TextureSpec:
    return _spec(
        source={"piece": "Suite Popular Brasileira — Mazurka-Choro", "bars": [1, 8]},
        authored=(
            _event(1, 0.0, 1.5, pitch=PitchRef.melody_eighth(0)),
            _event(1, 1.5, 1.5, pitch=PitchRef.melody_eighth(3)),
            _event(3, 0.0, 3.0, pitch=PitchRef.chord_root()),
        ),
        derived={"resolved_midi": "from_render_context"},
        routing={"bass": {"voice": 3, "mode": "chord_root"}},
        traits={"family": "arpeggio", "kinetic": True},
        selection={"priority": 10, "mood": ["calm", "selloff"]},
        provenance={"model": "gemini-3.5-flash", "confidence": 0.82},
    )


def test_texture_spec_json_round_trip() -> None:
    spec = _full_spec()
    mapping = texture_spec_to_mapping(spec)
    payload = json.loads(json.dumps(mapping))
    assert parse_texture_spec(payload) == spec
    assert texture_spec_to_mapping(parse_texture_spec(payload)) == mapping
    assert validate_texture_spec(spec, meter=METER_34, require_full_bars=True) == ()


def test_authored_mapping_shape_matches_the_doc() -> None:
    mapping = texture_spec_to_mapping(_full_spec())
    events = mapping["authored"]["events"]
    assert events[0]["pitch"] == {"kind": "melody_eighth", "eighth": 0}
    assert "resolved_midi" not in events[0]
    assert mapping["meter_variants"][0]["meter"]["extra_weights"] == [[4, 0.8]]


def test_missing_required_fields_are_rejected() -> None:
    mapping = texture_spec_to_mapping(_spec())
    for key in ("id", "composer", "kind", "level", "runtime", "status", "meter_variants"):
        broken = dict(mapping)
        del broken[key]
        with pytest.raises(TextureSpecError) as excinfo:
            parse_texture_spec(broken)
        assert excinfo.value.path == "spec"
        assert key in excinfo.value.message


def test_check_texture_spec_reports_missing_fields_as_records() -> None:
    mapping = texture_spec_to_mapping(_spec())
    del mapping["composer"]
    errors = check_texture_spec(mapping)
    assert len(errors) == 1
    assert errors[0].path == "spec"
    assert "composer" in errors[0].message


def test_empty_meter_variants_are_rejected() -> None:
    errors = validate_texture_spec(_spec(meter_variants=()))
    assert _paths(errors) == ["meter_variants"]


def test_duplicate_meter_variant_keys_are_rejected() -> None:
    one = _variant(METER_34, materializer="grid_3_4")
    two = MeterVariant(
        meter=MeterSpec.from_form_meter(METER_34, id="another label"),
        materializer="grid_3_4",
    )
    errors = validate_texture_spec(_spec(meter_variants=(one, two)))
    assert _paths(errors) == ["meter_variants[1].meter"]
    assert "duplicate" in errors[0].message


def test_meter_variant_id_must_be_non_empty() -> None:
    variant = _variant()
    empty_id = MeterVariant(meter=MeterSpec(
        id="",
        beats=3,
        beat_type=4,
        eighths_per_bar=6,
        strong_eighths=(0,),
        subbar_breaks=(4,),
        extra_weights=((4, 0.8),),
    ), materializer="grid_3_4")
    errors = validate_texture_spec(_spec(meter_variants=(variant, empty_id)))
    # The empty-id meter has the same canonical key as METER_34, so both the
    # duplicate and the empty label are reported.
    assert "meter_variants[1].meter.id" in _paths(errors)
    assert "meter_variants[1].meter" in _paths(errors)


def test_unsupported_variant_requires_reason() -> None:
    unsupported = _variant(METER_128, materializer=None, unsupported=True, reason=None)
    errors = validate_texture_spec(_spec(meter_variants=(unsupported,)))
    assert _paths(errors) == ["meter_variants[0].reason"]

    declared = _variant(
        METER_128,
        materializer=None,
        unsupported=True,
        reason="No 12/8 materializer in Phase 0",
    )
    assert validate_texture_spec(_spec(meter_variants=(declared,))) == ()


def test_supported_variant_needs_a_materializer() -> None:
    errors = validate_texture_spec(_spec(meter_variants=(_variant(materializer=None),)))
    assert _paths(errors) == ["meter_variants[0].materializer"]


def test_unsupported_transform_is_rejected() -> None:
    errors = validate_texture_spec(_spec(meter_variants=(_variant(transform="auto"),)))
    assert _paths(errors) == ["meter_variants[0].transform"]


def test_sentence_kind_requires_a_parent() -> None:
    errors = validate_texture_spec(_spec(kind="sentence", parent=None))
    assert _paths(errors) == ["parent"]
    assert validate_texture_spec(_spec(kind="sentence", parent="villa_pattern")) == ()


def test_runtime_kind_level_and_status_values_are_bounded() -> None:
    errors = validate_texture_spec(
        _spec(kind="movement", level="bar", runtime="python", status="live")
    )
    assert _paths(errors) == ["kind", "level", "runtime", "status"]


def test_unknown_top_level_key_is_rejected_unless_allowed() -> None:
    mapping = texture_spec_to_mapping(_spec())
    mapping["suite"] = {"name": "Suite Popular Brasileira", "movement": 1}
    with pytest.raises(TextureSpecError) as excinfo:
        parse_texture_spec(mapping)
    assert excinfo.value.path == "spec"
    assert "suite" in excinfo.value.message

    spec = parse_texture_spec(mapping, allow_extra=True)
    assert spec.extra == {"suite": {"name": "Suite Popular Brasileira", "movement": 1}}
    assert texture_spec_to_mapping(spec)["suite"] == spec.extra["suite"]
    assert validate_texture_spec(spec, allow_extra=True) == ()
    assert _paths(validate_texture_spec(spec)) == ["suite"]


def test_publish_gate_rejects_pending_and_low_confidence() -> None:
    accepted = _event(1, 0.0, 4.0, confidence=0.6, review="accepted")
    assert publishable(_spec(authored=(accepted,))) is True

    pending = _event(1, 0.0, 4.0, confidence=0.9, review="pending")
    assert publishable(_spec(authored=(pending,))) is False

    low = _event(1, 0.0, 4.0, confidence=0.59, review="edited")
    assert publishable(_spec(authored=(low,))) is False

    no_confidence = _event(1, 0.0, 4.0, confidence=None, review="edited")
    assert publishable(_spec(authored=(no_confidence,))) is True

    unknown_review = _event(1, 0.0, 4.0, confidence=0.9, review="maybe")
    assert publishable(_spec(authored=(unknown_review,))) is False


def test_authored_validation_is_opt_in_for_meter_geometry() -> None:
    short = _event(1, 0.0, 3.0)
    spec = _spec(authored=(short,))
    assert validate_texture_spec(spec) == ()
    errors = validate_texture_spec(spec, meter=METER_44, require_full_bars=True)
    assert _paths(errors) == ["authored.events.voice[1].bar[0]"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_import_does_not_register_or_load_the_pattern_module() -> None:
    backend = Path(__file__).resolve().parents[1]
    code = (
        "import sys\n"
        "from app.sonify.sentence_specs import SENTENCE_SPECS\n"
        "before = len(SENTENCE_SPECS)\n"
        "import app.studio.texture_spec\n"
        "print(before, len(SENTENCE_SPECS), "
        "'app.sonify.guitar_patterns' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    before, after, loaded = completed.stdout.split()
    assert before == after
    assert loaded == "False"
