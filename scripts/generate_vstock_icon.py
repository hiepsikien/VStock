#!/usr/bin/env python3
"""Generate VStock app icon — Apple Stocks aesthetic + AI neural nodes."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
RADIUS = 228  # iOS-like squircle approximation via rounded rect
OUT_DIR = Path(__file__).resolve().parents[1] / "assets"


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def chart_points(size: int) -> list[tuple[float, float]]:
    """White chart line that forms a clear V then rises — reads as VStock + growth."""
    # Normalized control points (x, y) in 0..1; y lower = higher on screen? No: y increases down.
    # Keep V vertex inside Android adaptive safe zone (~center 66%).
    pts = [
        (0.10, 0.36),
        (0.20, 0.44),
        (0.30, 0.52),
        (0.40, 0.62),  # V bottom-left arm
        (0.50, 0.70),  # V vertex (AI focus)
        (0.60, 0.48),
        (0.68, 0.40),
        (0.76, 0.34),  # first peak
        (0.82, 0.42),
        (0.90, 0.26),  # higher peak
        (0.96, 0.30),
    ]
    return [(x * size, y * size) for x, y in pts]


def draw_grid(draw: ImageDraw.ImageDraw, size: int) -> None:
    color = (55, 58, 62, 255)
    step = size // 12
    for i in range(1, 12):
        x = i * step
        # dotted vertical lines
        y = int(size * 0.12)
        end = int(size * 0.88)
        while y < end:
            draw.line([(x, y), (x, min(y + 6, end))], fill=color, width=2)
            y += 14


def draw_thick_polyline(
    base: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    """Anti-aliased thick stroke via oversized draw + downsample."""
    scale = 2
    layer = Image.new("RGBA", (base.width * scale, base.height * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    scaled = [(x * scale, y * scale) for x, y in points]
    d.line(scaled, fill=color, width=width * scale, joint="curve")
    # round caps
    r = (width * scale) // 2
    for x, y in (scaled[0], scaled[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    layer = layer.resize(base.size, Image.Resampling.LANCZOS)
    base.alpha_composite(layer)


def glow_circle(
    base: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[int, int, int],
    glow: int = 28,
) -> None:
    pad = glow * 3
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # soft glow
    for i in range(glow, 0, -2):
        alpha = int(40 * (1 - i / glow))
        r = radius + i
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(*color, alpha),
        )
    # core
    d.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(*color, 255),
    )
    # inner white highlight
    ir = radius * 0.35
    d.ellipse(
        [cx - ir, cy - ir, cx + ir, cy + ir],
        fill=(255, 255, 255, 230),
    )
    soft = layer.filter(ImageFilter.GaussianBlur(radius=1.2))
    base.alpha_composite(soft)


def generate(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (10, 10, 12, 255))
    draw = ImageDraw.Draw(img)

    draw_grid(draw, size)

    pts = chart_points(size)
    # V vertex index
    v_idx = 4
    vx, vy = pts[v_idx]

    # AI neural links from V vertex to rising peaks (cyan, under white line)
    ai_targets = [6, 7, 9]  # mid rise, first peak, high peak
    cyan = (90, 200, 250)
    link_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ld = ImageDraw.Draw(link_layer)
    for ti in ai_targets:
        tx, ty = pts[ti]
        ld.line([(vx, vy), (tx, ty)], fill=(*cyan, 160), width=max(2, size // 280))
    link_layer = link_layer.filter(ImageFilter.GaussianBlur(radius=0.6))
    img.alpha_composite(link_layer)

    # vertical cyan crosshair through V
    cross = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cross)
    top = size * 0.14
    bot = size * 0.90
    cd.line([(vx, top), (vx, bot)], fill=(*cyan, 200), width=max(2, size // 320))
    # soft glow on crosshair
    glow_line = cross.filter(ImageFilter.GaussianBlur(radius=size // 180))
    img.alpha_composite(glow_line)
    img.alpha_composite(cross)

    # white chart line
    draw_thick_polyline(img, pts, (245, 245, 247, 255), width=max(8, size // 72))

    # AI nodes on targets (smaller)
    for ti in ai_targets:
        tx, ty = pts[ti]
        glow_circle(img, tx, ty, radius=size * 0.018, color=cyan, glow=max(8, size // 90))

    # main AI node at V vertex
    glow_circle(img, vx, vy, radius=size * 0.038, color=cyan, glow=max(16, size // 45))

    # apply squircle / rounded mask
    mask = rounded_mask(size, int(size * RADIUS / SIZE))
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask=mask)
    return out


def generate_android_foreground(size: int = 512) -> Image.Image:
    """Foreground for adaptive icon — chart centered with safe padding."""
    # Render at 1024 then crop center content into 512 with transparent bg
    full = generate(1024)
    # strip rounded corners — adaptive icons apply their own mask
    # Rebuild without mask for adaptive foreground
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # faint grid only in content area
    draw_grid(draw, 1024)
    pts = chart_points(1024)
    v_idx = 4
    vx, vy = pts[v_idx]
    cyan = (90, 200, 250)
    link_layer = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    ld = ImageDraw.Draw(link_layer)
    for ti in [6, 7, 9]:
        tx, ty = pts[ti]
        ld.line([(vx, vy), (tx, ty)], fill=(*cyan, 160), width=4)
    img.alpha_composite(link_layer)
    cross = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cross)
    cd.line([(vx, 140), (vx, 920)], fill=(*cyan, 200), width=3)
    img.alpha_composite(cross.filter(ImageFilter.GaussianBlur(radius=4)))
    img.alpha_composite(cross)
    draw_thick_polyline(img, pts, (245, 245, 247, 255), width=14)
    for ti in [6, 7, 9]:
        tx, ty = pts[ti]
        glow_circle(img, tx, ty, radius=18, color=cyan, glow=12)
    glow_circle(img, vx, vy, radius=38, color=cyan, glow=22)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def generate_monochrome(size: int = 432) -> Image.Image:
    """Android monochrome — white silhouette of chart + nodes on transparent."""
    img = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    pts = chart_points(1024)
    draw_thick_polyline(img, pts, (255, 255, 255, 255), width=18)
    d = ImageDraw.Draw(img)
    for i, (x, y) in enumerate(pts):
        if i in (4, 6, 7, 9):
            r = 28 if i == 4 else 16
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255))
    # crosshair thin
    vx, vy = pts[4]
    d.line([(vx, 160), (vx, 900)], fill=(255, 255, 255, 180), width=4)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    icon = generate(1024)
    # opaque RGB for Expo icon
    rgb = Image.new("RGB", icon.size, (10, 10, 12))
    rgb.paste(icon, mask=icon.split()[-1])
    rgb.save(OUT_DIR / "icon.png", "PNG", optimize=True)

    # splash — chart mark centered on black
    splash = Image.new("RGB", (1024, 1024), (10, 10, 12))
    mark = generate(640)
    splash.paste(mark, ((1024 - 640) // 2, (1024 - 640) // 2), mark)
    splash.save(OUT_DIR / "splash-icon.png", "PNG", optimize=True)

    # favicon 48
    fav = rgb.resize((48, 48), Image.Resampling.LANCZOS)
    fav.save(OUT_DIR / "favicon.png", "PNG", optimize=True)

    # Android adaptive
    bg = Image.new("RGB", (512, 512), (0, 0, 0))
    bg.save(OUT_DIR / "android-icon-background.png", "PNG", optimize=True)

    fg = generate_android_foreground(512)
    # composite on transparent — already is
    fg.save(OUT_DIR / "android-icon-foreground.png", "PNG", optimize=True)

    mono = generate_monochrome(432)
    mono.save(OUT_DIR / "android-icon-monochrome.png", "PNG", optimize=True)

    # also export concept preview without squircle for docs
    preview = generate(1024)
    preview_rgb = Image.new("RGB", preview.size, (10, 10, 12))
    preview_rgb.paste(preview, mask=preview.split()[-1])
    artifacts = Path("/opt/cursor/artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    preview_rgb.save(artifacts / "vstock-icon-final.png", "PNG", optimize=True)

    print("Generated icons in", OUT_DIR)
    for name in [
        "icon.png",
        "splash-icon.png",
        "favicon.png",
        "android-icon-background.png",
        "android-icon-foreground.png",
        "android-icon-monochrome.png",
    ]:
        p = OUT_DIR / name
        print(f"  {name}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
