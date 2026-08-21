"""Build the multi-theme qualitative wall (Figure 3 replacement) for the paper.

Composites the B3 packs of every available theme into one transparent-background
PNG: one row per theme, split into element / power-up / crate blocks. Crates are
ordered by depletion (intact -> destroyed) to show stage progression.

Source: generated_art/research_B3_{theme}/sprites/*.png  (256x256 RGBA, cut out)
Output: paper/figures/qual_multitheme_wall.png  (transparent background, no grid lines)

Run:  python paper/figures/make_qualitative_figures.py
Self-check: python paper/figures/make_qualitative_figures.py --check
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN = ROOT / "generated_art"
OUT = ROOT / "paper" / "figures" / "qual_multitheme_wall.png"

THEMES = ["fruit", "pet", "ocean", "steampunk"]  # missing ones are skipped
# Within a row: element block | powerup block | crate block (intact -> destroyed).
BLOCKS = [
    ["Red", "Grn", "Blu", "Yel", "Pur"],
    ["Soda0d", "Soda90", "LtBl"],
    ["Crt4", "Crt3", "Crt2", "Crt1"],
]
BLOCK_LABELS = ["elements", "power-ups", "crate (intact \u2192 destroyed)"]

CELL = 128          # rendered sprite size (px)
PAD = 10            # padding between sprites
BLOCK_GAP = 40      # gap between element/powerup/crate blocks
LABEL_W = 112      # left gutter for theme name
TOP = 30            # top strip for block labels


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("Arial.ttf", "Helvetica.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load(theme: str, name: str) -> Image.Image | None:
    p = GEN / f"research_B3_{theme}" / "sprites" / f"{name}.png"
    if not p.exists():
        return None
    return Image.open(p).convert("RGBA").resize((CELL, CELL), Image.LANCZOS)


def _available_themes() -> list[str]:
    return [t for t in THEMES if (GEN / f"research_B3_{t}" / "sprites").is_dir()]


def build_wall() -> pathlib.Path:
    themes = _available_themes()
    if not themes:
        raise SystemExit("no B3 sprite dirs found under generated_art/")

    n_cols = sum(len(b) for b in BLOCKS)
    row_w = LABEL_W + n_cols * (CELL + PAD) + len(BLOCKS) * BLOCK_GAP
    row_h = CELL + PAD
    W = row_w
    H = TOP + len(themes) * row_h + 8

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # transparent, no grid
    draw = ImageDraw.Draw(canvas)
    f_theme = _font(18)
    f_block = _font(15)

    # Block header labels (drawn once along the top, over the first row's x-positions).
    def block_x_starts() -> list[int]:
        xs, x = [], LABEL_W
        for b in BLOCKS:
            xs.append(x)
            x += len(b) * (CELL + PAD) + BLOCK_GAP
        return xs

    for lbl, x0, blk in zip(BLOCK_LABELS, block_x_starts(), BLOCKS):
        w = len(blk) * (CELL + PAD) - PAD
        bbox = draw.textbbox((0, 0), lbl, font=f_block)
        tw = bbox[2] - bbox[0]
        draw.text((x0 + (w - tw) / 2, 6), lbl, fill=(60, 60, 60, 255), font=f_block)

    for r, theme in enumerate(themes):
        y = TOP + r * row_h
        draw.text((8, y + CELL / 2 - 12), theme, fill=(20, 20, 20, 255), font=f_theme)
        x = LABEL_W
        for blk in BLOCKS:
            for name in blk:
                sp = _load(theme, name)
                if sp is not None:
                    canvas.alpha_composite(sp, (x, y))
                x += CELL + PAD
            x += BLOCK_GAP

    canvas.save(OUT)
    return OUT


def self_check() -> None:
    themes = _available_themes()
    assert themes, "no themes found"
    # every theme must have all 12 assets referenced in BLOCKS
    need = [n for b in BLOCKS for n in b]
    for t in themes:
        for n in need:
            assert _load(t, n) is not None, f"missing {t}/{n}"
    out = build_wall()
    im = Image.open(out)
    assert im.mode == "RGBA", "output not RGBA (transparent)"
    # corner pixel must be fully transparent (no grid background)
    assert im.getpixel((0, 0))[3] == 0, "background is not transparent"
    assert out.stat().st_size > 5000
    print(f"self_check OK: {out.name} ({im.size[0]}x{im.size[1]}, themes={themes})")


if __name__ == "__main__":
    if "--check" in sys.argv:
        self_check()
    else:
        print("wrote", build_wall().relative_to(ROOT))
