"""Stub for the guitar scale engine.

A later change replaces this module wholesale. Keep the surface to the
constant and the detector signature; do not grow helpers here.
"""

SCALE_SIXTEENTH_MIN_BPM = 88


def detect_price_impulses(
    raw_pitches,
    section_starts,
    *,
    epb,
    strong_eighths,
    pedal_bars=frozenset(),
):
    return ()
