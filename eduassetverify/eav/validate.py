"""Independent ground-truth check: recompute every constraint from the rendered pixels.

The answer key of the benchmark comes from the scene specification (domain `evaluate`).
Before an item may enter the benchmark, this module recomputes each constraint from the
PNG alone, knowing only the style's color palette, the constraint targets, and the fixed
layout conventions of the templates (labels below or right of the shape, dashed axis,
solid divider). It never reads the scene. An item whose two answers disagree, or whose
pixels are ambiguous, is discarded: the answer key is checked before any verifier sees it.

Returns {constraint id: True | False | None}; None means "ambiguous from pixels".
"""
from __future__ import annotations

import functools
import itertools

import cv2
import numpy as np
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont

from .styles import COUNT_CATEGORIES, Style, hex_rgb

CW = {"up": "right", "right": "down", "down": "left", "left": "up"}


# --------------------------------------------------------------------------- pixels

def _dist(rgb: np.ndarray, color: str) -> np.ndarray:
    return np.sqrt(((rgb.astype(np.int32) - np.array(hex_rgb(color))) ** 2).sum(-1))


def _near(rgb, color, tol) -> np.ndarray:
    return _dist(rgb, color) < tol


def _bg_tol(style: Style) -> float:
    return 48.0 if style.texture else 30.0


def _components(mask: np.ndarray, min_area: int, connectivity: int = 8):
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=connectivity)
    out = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            x, y, w, h = stats[i, :4]
            out.append({"label": i, "area": int(stats[i, cv2.CC_STAT_AREA]), "bbox": (x, y, x + w, y + h),
                        "cx": float(cents[i][0]), "cy": float(cents[i][1]), "mask": lab == i})
    return out


def _color_tol(colors: list[str]) -> float:
    """Half the smallest distance between colors that may co-occur, capped at 45."""
    rgbs = [np.array(hex_rgb(c)) for c in colors]
    dmin = min((float(np.linalg.norm(a - b)) for a, b in itertools.combinations(rgbs, 2)), default=90.0)
    return min(45.0, 0.5 * dmin)


def _blobs(rgb, color, tol, min_area=200, merge_px=3):
    """Solid regions of one color. Opening drops the thin anti-aliased rings that a dark
    outline leaves around objects of other colors; dilation then re-joins one object's
    pieces that its own outline separates (a fish's tail and body)."""
    mask = _near(rgb, color, tol).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    if merge_px:
        mask = cv2.dilate(mask.astype(np.uint8), np.ones((2 * merge_px + 1,) * 2, np.uint8)).astype(bool)
    return _components(mask, min_area)


# --------------------------------------------------------------------------- text

GLYPHS = "0123456789/"


@functools.lru_cache(maxsize=1)
def _glyph_templates() -> dict[str, np.ndarray]:
    font = ImageFont.truetype(font_manager.findfont("DejaVu Sans"), 64)
    out = {}
    for ch in GLYPHS:
        img = Image.new("L", (110, 110), 0)
        ImageDraw.Draw(img).text((20, 10), ch, fill=255, font=font)
        out[ch] = _norm_glyph(np.asarray(img) > 127)
    return out


def _norm_glyph(mask: np.ndarray, size: int = 32, inner: int = 28) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    h, w = crop.shape
    k = inner / max(h, w)
    crop = np.asarray(Image.fromarray(crop).resize((max(1, round(w * k)), max(1, round(h * k))), Image.BILINEAR)) > 127
    out = np.zeros((size, size), bool)
    y0, x0 = (size - crop.shape[0]) // 2, (size - crop.shape[1]) // 2
    out[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    return out


def read_text(mask: np.ndarray, candidates: list[str]) -> tuple[str | None, float]:
    """Read digits and '/' glyph by glyph (template match per connected component)."""
    comps = sorted(_components(mask, min_area=12), key=lambda c: c["bbox"][0])
    if not comps:
        return None, 0.0
    tallest = max(c["bbox"][3] - c["bbox"][1] for c in comps)      # drop specks and line fragments
    comps = [c for c in comps if c["bbox"][3] - c["bbox"][1] >= 0.45 * tallest]
    tmpl = _glyph_templates()
    chars, scores = [], []
    for c in comps:
        x0, y0, x1, y1 = c["bbox"]
        g = _norm_glyph(c["mask"][y0:y1, x0:x1])
        best, best_iou = None, -1.0
        for ch, t in tmpl.items():
            iou = (g & t).sum() / max(1, (g | t).sum())
            if iou > best_iou:
                best, best_iou = ch, float(iou)
        chars.append(best)
        scores.append(best_iou)
    text = "".join(chars)
    score = min(scores)
    return (text, score) if text in candidates and score >= 0.5 else (None, score)


FRACTIONS = [f"{a}/{b}" for b in range(2, 13) for a in range(1, 13)]
NUMBERS = [str(i) for i in range(1, 21)]


# --------------------------------------------------------------------------- fraction

def measure_fraction(rgb: np.ndarray, style: Style) -> dict:
    """Parts of the (single) whole: count, colored count, area deviation, label text."""
    fills = [style.colored_fill, style.plain_fill]
    tol = 45.0
    is_fill = _near(rgb, fills[0], tol) | _near(rgb, fills[1], tol)
    is_bg = _near(rgb, style.background, _bg_tol(style))
    line = ~(is_fill | is_bg)
    regions = _components(~line, min_area=300, connectivity=4)
    h, w = line.shape
    parts = []
    for r in regions:
        x0, y0, x1, y1 = r["bbox"]
        if x0 == 0 or y0 == 0 or x1 >= w or y1 >= h:           # touches the border: background
            continue
        mean = rgb[r["mask"]].mean(0)
        d = [float(np.linalg.norm(mean - np.array(hex_rgb(f)))) for f in fills]
        if min(d) > tol:
            continue
        parts.append(dict(r, colored=d[0] < d[1]))
    out = {"parts": parts, "n": len(parts), "colored": sum(p["colored"] for p in parts), "deviation": None,
           "label": None}
    if parts:
        union = np.zeros_like(line)
        for p in parts:
            union |= p["mask"]
        k = int(2 * style.line_width + 3)
        whole = cv2.morphologyEx(union.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)).astype(bool)
        # Raw fill areas: every part loses half an outline width along each of its edges,
        # which is the same loss for equal parts, so no area has to be reassigned.
        areas = np.array([p["area"] for p in parts], float)
        out["deviation"] = float(np.max(np.abs(areas / areas.mean() - 1.0)))
        pad = int(2 * style.line_width + 15)
        text = _near(rgb, style.text_color, 70) & ~cv2.dilate(whole.astype(np.uint8), np.ones((pad, pad), np.uint8)).astype(bool)
        if text.sum() > 40:
            out["label"] = read_text(text, FRACTIONS)[0]
    return out


def validate_fraction(rgb, style, constraints) -> dict:
    m = measure_fraction(rgb, style)
    res = {}
    for c in constraints:
        if c["name"] == "part_count":
            res[c["id"]] = m["n"] == c["value"]
        elif c["name"] == "colored_part_count":
            res[c["id"]] = m["colored"] == c["value"]
        elif c["name"] == "equal_area":
            d = m["deviation"]
            res[c["id"]] = None if d is None else (True if d < 0.10 else False if d > 0.25 else None)
        elif c["name"] == "label_text":
            res[c["id"]] = None if m["label"] is None else m["label"] == c["value"]
    return res


# --------------------------------------------------------------------------- counting

def _divider_x(rgb, style) -> float | None:
    line = _near(rgb, style.outline, 60)
    cols = line.sum(0)
    x = int(np.argmax(cols))
    return float(x) if cols[x] > 0.5 * line.shape[0] else None


def measure_counting(rgb: np.ndarray, style: Style) -> dict:
    colors = [style.object_color(c) for c in COUNT_CATEGORIES]
    tol = _color_tol(colors)
    merge = max(3, int(np.ceil(0.8 * style.line_width)) + 1)
    blobs = {c: _blobs(rgb, style.object_color(c), tol, merge_px=merge) for c in COUNT_CATEGORIES}
    band = _near(rgb, style.text_color, 70)
    band[:400] = False
    numeral = read_text(band, NUMBERS)[0] if band.sum() > 40 else None
    return {"blobs": blobs, "numeral": numeral, "divider": _divider_x(rgb, style)}


def validate_counting(rgb, style, constraints) -> dict:
    m = measure_counting(rgb, style)
    counts = {c: len(b) for c, b in m["blobs"].items()}
    res = {}
    for c in constraints:
        name = c["name"]
        if name == "object_count":
            res[c["id"]] = sum(counts.values()) == c["value"]
        elif name == "all_objects_category":
            res[c["id"]] = all(n == 0 for cat, n in counts.items() if cat != c["value"])
        elif name == "numeral_label":
            res[c["id"]] = None if m["numeral"] is None else m["numeral"] == c["value"]
        elif name == "category_count":
            res[c["id"]] = counts[c["subject"]] == c["value"]
        elif name == "group_count":
            x = m["divider"]
            if x is None:
                res[c["id"]] = None
                continue
            left = c["subject"]["group"] == "left"
            n = sum((b["cx"] < x) == left for b in m["blobs"][c["subject"]["category"]])
            res[c["id"]] = n == c["value"]
    return res


# --------------------------------------------------------------------------- spatial

def _arrow_direction(mask: np.ndarray) -> str:
    ys, xs = np.nonzero(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh, ww = crop.shape
    if hh >= ww:
        top, bottom = crop[: hh // 2].sum(), crop[hh - hh // 2:].sum()
        return "up" if top > bottom else "down"
    left, right = crop[:, : ww // 2].sum(), crop[:, ww - ww // 2:].sum()
    return "left" if left > right else "right"


def _symmetry_iou(rgb, style) -> float:
    """IoU of the figure with its mirror image about the dashed axis.

    The axis position is the outline-weighted mean column around the strongest column,
    so a line centered between two pixel columns mirrors pixel i onto 2*axis - i exactly.
    """
    fg = ~_near(rgb, style.background, _bg_tol(style))
    line = _near(rgb, style.outline, 60)
    cols = line[:, 160:352].sum(0).astype(float)
    peak = int(np.argmax(cols))
    run_lo, run_hi = peak, peak
    while run_lo > 0 and cols[run_lo - 1] >= 0.5 * cols[peak]:
        run_lo -= 1
    while run_hi < len(cols) - 1 and cols[run_hi + 1] >= 0.5 * cols[peak]:
        run_hi += 1
    axis = 160 + (run_lo + run_hi + 1) / 2.0          # pixel-boundary coordinate of the line center
    band = style.line_width + 3
    fg[:, int(np.floor(axis - band)):int(np.ceil(axis + band))] = False      # symmetric about the axis
    w = fg.shape[1]
    xs = np.arange(w)
    mx = np.round(2 * axis - (xs + 0.5) - 0.5).astype(int)    # pixel centers at i + 0.5
    valid = (mx >= 0) & (mx < w)
    mirror = np.zeros_like(fg)
    mirror[:, xs[valid]] = fg[:, mx[valid]]
    fg[:, ~valid] = False
    return float((fg & mirror).sum() / max(1, (fg | mirror).sum()))


def validate_spatial(rgb, style, constraints) -> dict:
    res = {}
    shape_colors = [style.object_color(c) for c in ("star", "square", "circle", "triangle", "heart")]
    tol = _color_tol(shape_colors)
    cache: dict[str, list] = {}

    def blobs(cat):
        if cat not in cache:
            cache[cat] = _blobs(rgb, style.object_color(cat), tol, min_area=400)
        return cache[cat]

    for c in constraints:
        name = c["name"]
        if name == "object_present":
            res[c["id"]] = len(blobs(c["subject"])) > 0
        elif name in ("left_of", "above"):
            a, b = (blobs(s) for s in c["subject"])
            if len(a) != 1 or len(b) != 1:
                res[c["id"]] = None
                continue
            key = "cx" if name == "left_of" else "cy"
            gap = b[0][key] - a[0][key]
            res[c["id"]] = True if gap > 15 else False if gap < -15 else None
        elif name == "mirror_symmetric":
            iou = _symmetry_iou(rgb, style)
            hi, lo = (0.80, 0.72) if style.sketch else (0.90, 0.85)   # sketch wobble is not mirror-exact
            res[c["id"]] = True if iou >= hi else False if iou <= lo else None
        elif name == "rotated_quarter_cw":
            arrows = sorted(_blobs(rgb, style.object_color("arrow"), 45.0, min_area=800), key=lambda b: -b["area"])[:2]
            if len(arrows) != 2:
                res[c["id"]] = None
                continue
            left, right = sorted(arrows, key=lambda b: b["cx"])
            res[c["id"]] = _arrow_direction(right["mask"]) == CW[_arrow_direction(left["mask"])]
    return res


VALIDATORS = {"fraction": validate_fraction, "counting": validate_counting, "spatial": validate_spatial}


def validate(domain: str, rgb: np.ndarray, style: Style, constraints: list[dict]) -> dict:
    return VALIDATORS[domain](rgb, style, constraints)
