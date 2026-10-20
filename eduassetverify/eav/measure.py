"""Palette-free measurement operators: what the verifier measures inside VLM-localized boxes.

Unlike eav.validate (the benchmark's own answer-key check), these operators know nothing
about the style: they estimate the background from the image border and separate regions
by color edges. VLMs misjudge precise geometry, so areas, symmetry and arrow orientation
come from here; the VLM only says where to look.

Every operator returns {"ok": bool, ...}; ok=False means its preconditions failed (the
rule engine then falls back to the VLM reading or returns undetermined).
"""
from __future__ import annotations

import cv2
import numpy as np

H = W = 512


def background(rgb: np.ndarray) -> tuple[np.ndarray, float]:
    border = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3),
                             rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)]).astype(float)
    color = np.median(border, 0)
    noise = float(np.percentile(np.linalg.norm(border - color, axis=1), 95))
    return color, max(30.0, 2.5 * noise)


def foreground(rgb: np.ndarray) -> np.ndarray:
    bg, tol = background(rgb)
    return np.linalg.norm(rgb.astype(float) - bg, axis=2) > tol


def _pad(box, frac=0.08, px=6) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * frac + px, (y1 - y0) * frac + px
    return (max(0, int(x0 - dx)), max(0, int(y0 - dy)), min(W, int(np.ceil(x1 + dx))), min(H, int(np.ceil(y1 + dy))))


def _components(mask, min_area, connectivity=4):
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=connectivity)
    out = []
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            x, y, w, h = stats[i, :4]
            out.append({"area": int(stats[i, cv2.CC_STAT_AREA]), "bbox": [int(x), int(y), int(x + w), int(y + h)],
                        "cx": float(cents[i][0]), "cy": float(cents[i][1]), "mask": lab == i})
    return out


def _edges(rgb: np.ndarray, thresh: float = 120.0) -> np.ndarray:
    f = rgb.astype(np.float32)
    g = np.zeros(rgb.shape[:2], np.float32)
    for ch in range(3):
        gx = cv2.Sobel(f[:, :, ch], cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(f[:, :, ch], cv2.CV_32F, 0, 1, ksize=3)
        g = np.maximum(g, np.hypot(gx, gy))
    return cv2.dilate((g > thresh).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)


# --------------------------------------------------------------------------- partition

def partition(rgb: np.ndarray, box) -> dict:
    """Parts of a divided shape inside `box`: regions bounded by edges, not touching the crop border."""
    x0, y0, x1, y1 = _pad(box)
    crop = rgb[y0:y1, x0:x1]
    if crop.shape[0] < 20 or crop.shape[1] < 20:
        return {"ok": False, "why": "box too small"}
    edges = _edges(crop)
    regions = _components(~edges, min_area=max(80, int(0.012 * crop.shape[0] * crop.shape[1])))
    h, w = edges.shape
    parts = [r for r in regions if r["bbox"][0] > 0 and r["bbox"][1] > 0 and r["bbox"][2] < w and r["bbox"][3] < h]
    # A thick outline has a flat interior of its own: a network of thin "regions" along the
    # lines (with a hub where they meet). Mean inscribed distance separates it from parts.
    def _thickness(p):
        dt = cv2.distanceTransform(np.pad(p["mask"], 1).astype(np.uint8), cv2.DIST_L2, 3)
        return float(dt[dt > 0].mean())

    parts = [p for p in parts if _thickness(p) >= 3.0]
    if len(parts) < 1:
        return {"ok": False, "why": "no enclosed regions"}
    bg, _ = background(rgb)
    means = np.array([crop[p["mask"]].mean(0) for p in parts])
    dist_bg = np.linalg.norm(means - bg, axis=1)
    if len(parts) >= 2 and np.ptp(dist_bg) > 40:
        # two fill colors: the one farther from the background is "colored"
        lo, hi = dist_bg.min(), dist_bg.max()
        colored = dist_bg > (lo + hi) / 2
    else:
        colored = dist_bg > 60
    areas = np.array([p["area"] for p in parts], float)
    covered = areas.sum() / max(1.0, float((x1 - x0) * (y1 - y0)))
    out_parts = [{"bbox": [p["bbox"][0] + x0, p["bbox"][1] + y0, p["bbox"][2] + x0, p["bbox"][3] + y0],
                  "area": int(a), "colored": bool(c)} for p, a, c in zip(parts, areas, colored)]
    dev = np.abs(areas / areas.mean() - 1.0)
    return {"ok": len(parts) >= 2 and covered >= 0.3, "n": len(parts), "colored": int(colored.sum()),
            "deviation": float(dev.max()), "worst": out_parts[int(np.argmax(dev))]["bbox"], "parts": out_parts,
            "coverage": float(covered)}


# --------------------------------------------------------------------------- objects

def blob(rgb: np.ndarray, box, fg: np.ndarray | None = None) -> dict:
    """The largest foreground blob inside `box`: centroid, area, and arrow direction."""
    fg = foreground(rgb) if fg is None else fg
    x0, y0, x1, y1 = _pad(box, 0.05, 3)
    comps = _components(fg[y0:y1, x0:x1], min_area=60, connectivity=8)
    if not comps:
        return {"ok": False}
    b = max(comps, key=lambda c: c["area"])
    return {"ok": True, "cx": b["cx"] + x0, "cy": b["cy"] + y0, "area": b["area"],
            "bbox": [b["bbox"][0] + x0, b["bbox"][1] + y0, b["bbox"][2] + x0, b["bbox"][3] + y0],
            "direction": arrow_direction(b["mask"])}


def arrow_direction(mask: np.ndarray) -> str:
    ys, xs = np.nonzero(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    hh, ww = crop.shape
    if hh >= ww:
        return "up" if crop[: hh // 2].sum() > crop[hh - hh // 2:].sum() else "down"
    return "left" if crop[:, : ww // 2].sum() > crop[:, ww - ww // 2:].sum() else "right"


def thin_vertical_lines(fg: np.ndarray, max_width: int = 9) -> np.ndarray:
    """Per column: foreground pixels that belong to thin vertical strokes."""
    k = max_width // 2 + 2
    left = np.zeros_like(fg)
    right = np.zeros_like(fg)
    left[:, k:] = fg[:, :-k]
    right[:, :-k] = fg[:, k:]
    thin = fg & ~left & ~right
    return thin.sum(0)


def vertical_line(rgb: np.ndarray, x_range=(96, 416), min_frac=0.35) -> dict:
    """A (dashed or solid) vertical line: its x position at pixel-boundary precision."""
    fg = foreground(rgb)
    cols = thin_vertical_lines(fg).astype(float)
    a, b = x_range
    seg = cols[a:b]
    peak = int(np.argmax(seg))
    if seg[peak] < min_frac * H:
        return {"ok": False}
    lo = hi = peak
    while lo > 0 and seg[lo - 1] >= 0.5 * seg[peak]:
        lo -= 1
    while hi < len(seg) - 1 and seg[hi + 1] >= 0.5 * seg[peak]:
        hi += 1
    return {"ok": True, "x": a + (lo + hi + 1) / 2.0, "width": hi - lo + 1, "coverage": float(seg[peak] / H)}


def count_blobs(rgb: np.ndarray, exclude_x: float | None = None) -> dict:
    """Palette-free object count: solid foreground blobs, minus thin lines and text-sized specks."""
    fg = foreground(rgb).astype(np.uint8)
    if exclude_x is not None:
        x = int(round(exclude_x))
        fg[:, max(0, x - 8):x + 8] = 0
    solid = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    merged = cv2.dilate(solid, np.ones((7, 7), np.uint8))
    comps = _components(merged.astype(bool), min_area=150, connectivity=8)
    if not comps:
        return {"ok": False, "n": 0, "blobs": []}
    med = float(np.median([c["area"] for c in comps]))
    keep = [c for c in comps if c["area"] >= 0.3 * med]
    return {"ok": True, "n": len(keep), "blobs": [{"cx": c["cx"], "cy": c["cy"], "bbox": c["bbox"]} for c in keep]}


def symmetry(rgb: np.ndarray, axis_x: float | None = None) -> dict:
    """IoU between the foreground and its mirror image about a vertical axis."""
    fg = foreground(rgb)
    line = vertical_line(rgb)
    if line["ok"]:
        axis_x, band = line["x"], line["width"] / 2 + 3
    elif axis_x is None:
        return {"ok": False}
    else:
        band = 6.0
    fg[:, int(np.floor(axis_x - band)):int(np.ceil(axis_x + band))] = False
    xs = np.arange(W)
    mx = np.round(2 * axis_x - (xs + 0.5) - 0.5).astype(int)
    valid = (mx >= 0) & (mx < W)
    mirror = np.zeros_like(fg)
    mirror[:, xs[valid]] = fg[:, mx[valid]]
    fg[:, ~valid] = False
    union = (fg | mirror).sum()
    if union < 500:
        return {"ok": False}
    diff = fg ^ mirror
    comps = _components(diff, min_area=40, connectivity=8)
    worst = max(comps, key=lambda c: c["area"])["bbox"] if comps else None
    return {"ok": True, "iou": float((fg & mirror).sum() / union), "axis": float(axis_x), "worst": worst}
