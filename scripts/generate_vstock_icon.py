#!/usr/bin/env python3
"""Generate VStock app icon — Version A (yellow AI nodes, right crop, no grid/crosshair)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
RADIUS = 228
YELLOW = (245, 166, 35)  # #F5A623
YELLOW_BRIGHT = (255, 196, 64)
WHITE = (255, 255, 255)
BG = (0, 0, 0)
OUT_DIR = Path(__file__).resolve().parents[1] / "assets"
BRAND_DIR = OUT_DIR / "brand"


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    return mask


def thick_line(
    base: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    scale = 3
    layer = Image.new("RGBA", (base.width * scale, base.height * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    scaled = [(x * scale, y * scale) for x, y in points]
    d.line(scaled, fill=color, width=width * scale, joint="curve")
    r = (width * scale) // 2
    for x, y in (scaled[0], scaled[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    base.alpha_composite(layer.resize(base.size, Image.Resampling.LANCZOS))


def glow_circle(base: Image.Image, cx: float, cy: float, radius: float, glow: int = 20) -> None:
    pad = int(glow * 3 + radius + 4)
    box = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    cx_l = cy_l = pad
    for i in range(glow, 0, -1):
        alpha = int(50 * (1 - i / glow) ** 1.4)
        r = radius + i
        d.ellipse([cx_l - r, cy_l - r, cx_l + r, cy_l + r], fill=(*YELLOW, alpha))
    d.ellipse(
        [cx_l - radius, cy_l - radius, cx_l + radius, cy_l + radius],
        fill=(*YELLOW_BRIGHT, 255),
    )
    ir = max(2, radius * 0.30)
    d.ellipse([cx_l - ir, cy_l - ir, cx_l + ir, cy_l + ir], fill=(255, 255, 255, 240))
    box = box.filter(ImageFilter.GaussianBlur(radius=1.0))
    base.alpha_composite(box, dest=(int(cx) - pad, int(cy) - pad))


def chart_points(size: int) -> tuple[list[tuple[float, float]], int, list[int]]:
    """Right ~65% focus: V near left edge, rise to the right."""
    norm = [
        (0.06, 0.62),
        (0.14, 0.70),
        (0.22, 0.78),  # V vertex
        (0.34, 0.52),
        (0.44, 0.40),
        (0.54, 0.36),
        (0.62, 0.46),
        (0.72, 0.30),
        (0.82, 0.38),
        (0.92, 0.24),
    ]
    pts = [(x * size, y * size) for x, y in norm]
    return pts, 2, [5, 7, 9]


def purge_faint_grey(img: Image.Image) -> Image.Image:
    """Remove residual grey/dashed-grid pixels; keep yellow + bright white only."""
    arr = np.array(img).astype(np.int16)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    L = (r.astype(np.float32) + g + b) / 3.0
    is_yellow = (r >= 100) & (r > b + 35) & (g >= 50)
    is_white = (L >= 150) & (np.abs(r - g) <= 25) & (np.abs(g - b) <= 25)
    keep = is_yellow | is_white | (a < 8)
    kill = ~keep
    arr[kill, 0] = 0
    arr[kill, 1] = 0
    arr[kill, 2] = 0
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def purge_rgb(img: Image.Image) -> Image.Image:
    arr = np.array(img.convert("RGB")).astype(np.int16)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    L = (r.astype(np.float32) + g + b) / 3.0
    is_yellow = (r >= 100) & (r > b + 35) & (g >= 50)
    is_white = (L >= 150) & (np.abs(r - g) <= 25) & (np.abs(g - b) <= 25)
    arr[~(is_yellow | is_white)] = 0
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def generate(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = rounded_mask(size, int(size * RADIUS / SIZE))
    img.paste(Image.new("RGBA", (size, size), (*BG, 255)), mask=mask)

    pts, v_idx, targets = chart_points(size)
    vx, vy = pts[v_idx]

    link = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ld = ImageDraw.Draw(link)
    for ti in targets:
        tx, ty = pts[ti]
        ld.line([(vx, vy), (tx, ty)], fill=(*YELLOW, 200), width=max(3, size // 220))
    img.alpha_composite(link)

    thick_line(img, pts, (*WHITE, 255), width=max(10, size // 64))

    for ti in targets:
        tx, ty = pts[ti]
        glow_circle(img, tx, ty, radius=size * 0.017, glow=14)
    glow_circle(img, vx, vy, radius=size * 0.038, glow=20)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, mask=mask)
    out = purge_faint_grey(out)
    arr = np.array(out)
    m = np.array(mask)
    arr[m == 0, 3] = 0
    return Image.fromarray(arr, "RGBA")


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def to_rgb(mark: Image.Image) -> Image.Image:
    rgb = Image.new("RGB", mark.size, BG)
    rgb.paste(mark, mask=mark.split()[-1])
    return purge_rgb(rgb)


def make_lockup(mark: Image.Image, *, transparent: bool = False) -> Image.Image:
    mark_s = 360
    m = purge_faint_grey(mark.resize((mark_s, mark_s), Image.Resampling.LANCZOS))
    pad, gap = (24, 40) if transparent else (56, 48)
    font = find_font(132)
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bbox = tmp.textbbox((0, 0), "VStock", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    w = pad + mark_s + gap + tw + pad
    h = pad + mark_s + pad
    canvas = (
        Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if transparent
        else Image.new("RGB", (w, h), BG)
    )
    canvas.paste(m, (pad, pad), m)
    d = ImageDraw.Draw(canvas)
    text_x = pad + mark_s + gap
    text_y = pad + (mark_s - th) // 2 - bbox[1]
    vb = d.textbbox((0, 0), "V", font=font)
    fv = (*YELLOW, 255) if transparent else YELLOW
    fs = (255, 255, 255, 255) if transparent else (255, 255, 255)
    d.text((text_x, text_y), "V", font=font, fill=fv)
    d.text((text_x + (vb[2] - vb[0]), text_y), "Stock", font=font, fill=fs)
    return purge_faint_grey(canvas) if transparent else purge_rgb(canvas)


def make_splash(mark: Image.Image) -> Image.Image:
    sq = Image.new("RGB", (1024, 1024), BG)
    m = purge_faint_grey(mark.resize((400, 400), Image.Resampling.LANCZOS))
    top = (1024 - 400) // 2 - 50
    sq.paste(m, ((1024 - 400) // 2, top), m)
    d = ImageDraw.Draw(sq)
    font = find_font(78)
    bbox = d.textbbox((0, 0), "VStock", font=font)
    tw = bbox[2] - bbox[0]
    x = (1024 - tw) // 2
    y = top + 400 + 40 - bbox[1]
    vb = d.textbbox((0, 0), "V", font=font)
    d.text((x, y), "V", font=font, fill=YELLOW)
    d.text((x + (vb[2] - vb[0]), y), "Stock", font=font, fill=(255, 255, 255))
    return purge_rgb(sq)


def generate_monochrome(size: int = 432) -> Image.Image:
    mark = generate(1024)
    arr = np.array(mark)
    L = arr[:, :, :3].mean(axis=2)
    r, b = arr[:, :, 0], arr[:, :, 2]
    content = (L > 20) | ((r > 80) & (r > b + 20))
    out = np.zeros_like(arr)
    out[content, :3] = 255
    out[content, 3] = 255
    out[arr[:, :, 3] < 10, 3] = 0
    return Image.fromarray(out, "RGBA").resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BRAND_DIR.mkdir(parents=True, exist_ok=True)

    mark = generate(1024)
    icon = to_rgb(mark)
    icon.save(OUT_DIR / "icon.png", "PNG", optimize=True)
    purge_rgb(icon.resize((48, 48), Image.Resampling.LANCZOS)).save(
        OUT_DIR / "favicon.png", "PNG"
    )

    splash_mark = Image.new("RGB", (1024, 1024), BG)
    mm = purge_faint_grey(mark.resize((520, 520), Image.Resampling.LANCZOS))
    splash_mark.paste(mm, ((1024 - 520) // 2, (1024 - 520) // 2), mm)
    purge_rgb(splash_mark).save(OUT_DIR / "splash-icon.png", "PNG", optimize=True)

    Image.new("RGB", (512, 512), (0, 0, 0)).save(
        OUT_DIR / "android-icon-background.png", "PNG", optimize=True
    )
    purge_faint_grey(mark.resize((512, 512), Image.Resampling.LANCZOS)).save(
        OUT_DIR / "android-icon-foreground.png", "PNG", optimize=True
    )
    generate_monochrome(432).save(
        OUT_DIR / "android-icon-monochrome.png", "PNG", optimize=True
    )

    mark.save(BRAND_DIR / "mark.png", "PNG", optimize=True)
    make_splash(mark).save(BRAND_DIR / "splash-logo.png", "PNG", optimize=True)
    make_lockup(mark, transparent=False).save(
        BRAND_DIR / "logo-with-name.png", "PNG", optimize=True
    )
    make_lockup(mark, transparent=True).save(
        BRAND_DIR / "logo-with-name-transparent.png", "PNG", optimize=True
    )

    print("Generated icons in", OUT_DIR)
    print("Brand lockups in", BRAND_DIR)


if __name__ == "__main__":
    main()
