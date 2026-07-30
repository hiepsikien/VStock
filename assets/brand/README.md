# VStock brand kit (FINAL)

## Tokens
| Token | Hex | Use |
|-------|-----|-----|
| lime | `#C8F000` | Squircle fill |
| ink | `#0A0A0A` | Chart arrow |
| paper | `#F4F4F0` | Wordmark on dark |
| void | `#0A0A0A` | Dark backgrounds |

## Master SVGs (`assets/brand/`)
| File | Use |
|------|-----|
| `vstock-mark.svg` | Flat master mark |
| `vstock-icon-app.svg` | App icon 1024 source |
| `vstock-mark-inverted.svg` | Ink squircle + lime chart |
| `vstock-mark-mono-black.svg` | Black bg / white chart |
| `vstock-mark-mono-white.svg` | White bg / black chart |
| `vstock-lockup.svg` | Horizontal on dark |
| `vstock-lockup-transparent.svg` | Horizontal, no bg |
| `vstock-lockup-on-light.svg` | Horizontal for light UI |
| `vstock-lockup-stacked.svg` | Mark above wordmark |
| `vstock-wordmark.svg` | Wordmark only (paper) |
| `vstock-wordmark-on-light.svg` | Wordmark only (ink) |

## Raster exports (`assets/brand/exports/`)
- `mark-{32..1024}.png` — mark sizes
- `mark-inverted-*`, `mark-mono-*` — mono / inverted
- `lockup-dark-1800.png`, `lockup-transparent-1800.png`, `lockup-on-light-1800.png`
- `lockup-stacked-800.png`
- `wordmark-*.png`, `splash-1024.png`

## App wiring
- `assets/icon.png`, `favicon.png`, `splash-icon.png`
- Android adaptive: lime background + chart foreground
- `app.json` adaptive `backgroundColor`: `#C8F000`

## Rules
- Master is **flat** (no outer glow).
- Final mark: original tip weight, slightly longer climb.
