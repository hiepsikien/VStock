"""Writer-owned guitar trace points for bass/off-grid price lines."""

from __future__ import annotations

from app.sonify import dfi as D
from app.sonify import guitar_patterns as GP
from app.sonify.model import Bar, Score
from app.sonify.render import render
from app.sonify.span import month_specs


def _bars(count: int = 48) -> list[Bar]:
    return [
        Bar(close=100 + (index % 9) * 0.4, volume=1000 + index * 10)
        for index in range(count)
    ]


def _forced_render(
    monkeypatch,
    ensemble: str,
    pattern: str,
    form_index: int,
) -> Score:
    original = GP._patterns

    def force(ctx):
        found = original(ctx)
        return [pattern if item != "pedal" else item for item in found]

    monkeypatch.setattr(GP, "_patterns", force)
    return render(  # type: ignore[arg-type]
        _bars(),
        title="Trace",
        variant="guitar",
        ensemble=ensemble,
        form=month_specs("guitar")[form_index],
    )


def _body_trace(score: Score) -> list:
    frame = frozenset(score.frame_bars)
    return [point for point in score.price_trace if point.bar not in frame]


def test_thumb_cantabile_uses_writer_owned_points(monkeypatch) -> None:
    score = _forced_render(monkeypatch, "villa", "thumb_cantabile", 0)
    body = _body_trace(score)
    assert body
    assert all(point.price_eighth is not None for point in body)
    assert all(point.bar not in score.frame_bars for point in score.price_trace)


def test_etude1_keeps_its_off_grid_origin(monkeypatch) -> None:
    score = _forced_render(monkeypatch, "villa", "etude1", 0)
    body = _body_trace(score)
    off_grid = [
        point
        for point in body
        if abs(point.beat * 2 - round(point.beat * 2)) > 0.01
    ]
    assert off_grid
    first = next(point for point in off_grid if point.beat == 1.75)
    epb = int(round(score.bar_beats * 2))
    assert first.price_eighth == first.bar * epb + 2
    assert first.price_eighth != first.bar * epb + int(round(first.beat * 2))

    result = D.compute(score, variant="guitar", ensemble="villa")
    assert result is not None
    assert result.coverage > 0.5


def test_thumb_owns_only_its_own_bars(monkeypatch) -> None:
    captured: dict = {}
    original = GP._patterns

    def force(ctx):
        found = original(ctx)
        body = 0
        patterns = []
        for item in found:
            if item == "pedal":
                patterns.append(item)
                continue
            patterns.append("thumb_cantabile" if body % 2 == 0 else "chord_melody")
            body += 1
        captured["ctx"] = ctx
        captured["patterns"] = patterns
        return patterns

    monkeypatch.setattr(GP, "_patterns", force)
    score = render(  # type: ignore[arg-type]
        _bars(),
        title="Mixed",
        variant="guitar",
        ensemble="villa",
        form=month_specs("guitar")[0],
    )
    ctx = captured["ctx"]
    patterns = captured["patterns"]
    thumb = [
        point
        for point in score.price_trace
        if GP._bar_pattern(ctx, point.bar, patterns) == "thumb_cantabile"
    ]
    chord = [
        point
        for point in score.price_trace
        if GP._bar_pattern(ctx, point.bar, patterns) == "chord_melody"
    ]
    assert thumb and chord
    assert all(point.price_eighth is not None for point in thumb)
    assert any(point.price_eighth is None for point in chord)


def test_juglar_owns_the_beat_not_the_second_sixteenth(monkeypatch) -> None:
    score = _forced_render(monkeypatch, "torroba", "torroba_tremolo", 1)
    body = _body_trace(score)
    owned = [point for point in body if point.price_eighth is not None]
    assert owned
    assert len(owned) >= len(body) * 0.9
    assert any(point.beat in {0.0, 1.0, 2.0} for point in owned)

    result = D.compute(score, variant="guitar", ensemble="torroba")
    assert result is not None
    assert result.coverage > 0.5


def test_frame_bars_do_not_enter_the_price_trace() -> None:
    score = render(  # type: ignore[arg-type]
        _bars(),
        title="Frame",
        variant="guitar",
        ensemble="villa",
    )
    assert score.frame_bars
    assert all(point.bar not in score.frame_bars for point in score.price_trace)
