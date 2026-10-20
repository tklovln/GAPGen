"""Task A, fraction understanding: a whole divided into parts, some colored, maybe labeled.

Constraints (ids are stable across templates)
    parts    cardinality  part_count = n
    equal    geometric    equal_area
    colored  cardinality  colored_part_count = k
    label    semantic     label_text = "k/n"        (label templates only)

Operators change exactly one of them (asserted in eav.build):
    unequal_partition    Incorrect Proportion  two adjacent uncolored parts trade area
    wrong_colored_count  Incorrect Proportion  colored block grows or shrinks by one part
    wrong_part_count     Incorrect Proportion  n -> n +- 1 equal parts, k unchanged
    wrong_label          Incorrect Label       label shows a different fraction
Colored parts never change size, so the colored area stays k/n under unequal_partition:
the picture still "looks like" one of four parts colored, which is the misconception.
"""
from __future__ import annotations

import math

import numpy as np

from . import Item, NotApplicable, constraint

N_CHOICES = [2, 3, 4, 5, 6, 8]
GRID_CHOICES = [(2, 2), (2, 3), (2, 4), (3, 3), (2, 5)]
DELTA = (0.35, 0.60)          # relative area change of unequal_partition (>= delta_min)
SHAPE_WORD = {"circle": "a circle", "strips": "a rectangle", "grid": "a grid"}


# --------------------------------------------------------------------------- geometry

def n_parts(scene: dict) -> int:
    if scene["shape"] == "grid":
        return scene["geom"]["rows"] * scene["geom"]["cols"]
    return len(scene["sizes"])


def part_areas(scene: dict) -> list[float]:
    g = scene["geom"]
    if scene["shape"] == "circle":
        return [s * math.pi * g["r"] ** 2 for s in scene["sizes"]]
    if scene["shape"] == "strips":
        return [s * g["w"] * g["h"] for s in scene["sizes"]]
    rows = g["rows"]
    return [scene["sizes"][c] * g["w"] * g["h"] / rows for _ in range(rows) for c in range(g["cols"])]


def part_boxes(scene: dict) -> list[list[float]]:
    g = scene["geom"]
    if scene["shape"] == "circle":
        boxes, a0 = [], g["start"]
        for s in scene["sizes"]:
            a1 = a0 + 360.0 * s
            angles = np.radians(np.linspace(a0, a1, 32))
            xs = np.concatenate([[g["cx"]], g["cx"] + g["r"] * np.cos(angles)])
            ys = np.concatenate([[g["cy"]], g["cy"] + g["r"] * np.sin(angles)])
            boxes.append([float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())])
            a0 = a1
        return boxes
    if scene["shape"] == "strips":
        boxes, x = [], g["x"]
        for s in scene["sizes"]:
            boxes.append([x, g["y"], x + s * g["w"], g["y"] + g["h"]])
            x += s * g["w"]
        return boxes
    boxes, rh = [], g["h"] / g["rows"]
    xs = [g["x"]]
    for s in scene["sizes"]:
        xs.append(xs[-1] + s * g["w"])
    for r in range(g["rows"]):
        for c in range(g["cols"]):
            boxes.append([xs[c], g["y"] + r * rh, xs[c + 1], g["y"] + (r + 1) * rh])
    return boxes


def whole_box(scene: dict) -> list[float]:
    g = scene["geom"]
    if scene["shape"] == "circle":
        return [g["cx"] - g["r"], g["cy"] - g["r"], g["cx"] + g["r"], g["cy"] + g["r"]]
    return [g["x"], g["y"], g["x"] + g["w"], g["y"] + g["h"]]


def label_box(scene: dict) -> list[float]:
    lab = scene["label"]
    w = 0.62 * lab["size"] * len(lab["text"])
    return [lab["x"] - w / 2, lab["y"] - 0.6 * lab["size"], lab["x"] + w / 2, lab["y"] + 0.6 * lab["size"]]


def primitives(scene: dict) -> list[dict]:
    g, prims = scene["geom"], []
    if scene["shape"] == "circle":
        a0 = g["start"]
        for s, col in zip(scene["sizes"], scene["colored"]):
            a1 = a0 + 360.0 * s
            prims.append({"kind": "wedge", "cx": g["cx"], "cy": g["cy"], "r": g["r"],
                          "theta1": a0, "theta2": a1, "colored": col})
            a0 = a1
    else:
        for (x0, y0, x1, y1), col in zip(part_boxes(scene), scene["colored"]):
            prims.append({"kind": "rect", "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "colored": col})
    if scene.get("label"):
        lab = scene["label"]
        prims.append({"kind": "text", "x": lab["x"], "y": lab["y"], "text": lab["text"], "size": lab["size"]})
    return prims


# --------------------------------------------------------------------------- truth

def evaluate(scene: dict, constraints: list[dict]) -> dict[str, bool]:
    n = n_parts(scene)
    units = len(scene["sizes"])
    out = {}
    for c in constraints:
        if c["name"] == "part_count":
            out[c["id"]] = n == c["value"]
        elif c["name"] == "equal_area":
            out[c["id"]] = max(abs(s * units - 1.0) for s in scene["sizes"]) < 1e-9
        elif c["name"] == "colored_part_count":
            out[c["id"]] = int(sum(scene["colored"])) == c["value"]
        elif c["name"] == "label_text":
            out[c["id"]] = bool(scene.get("label")) and scene["label"]["text"] == c["value"]
        else:
            raise KeyError(c["name"])
    return out


# --------------------------------------------------------------------------- sampling

def _colored_block(n: int, k: int, start: int, wrap: bool) -> list[bool]:
    if not wrap:
        start = min(start, n - k)
    return [((i - start) % n) < k for i in range(n)]


def _sample(rng: np.random.Generator, shape: str, with_label: bool, template: str) -> Item:
    if shape == "grid":
        rows, cols = GRID_CHOICES[rng.integers(len(GRID_CHOICES))]
        n = rows * cols
    else:
        n = int(rng.choice(N_CHOICES))
    k = int(rng.integers(1, n))
    if shape == "circle":
        r = float(rng.uniform(120, 150) if with_label else rng.uniform(140, 180))
        cx = float(rng.uniform(170, 210) if with_label else rng.uniform(220, 292))
        geom = {"cx": cx, "cy": float(rng.uniform(226, 286)), "r": r, "start": float(rng.uniform(0, 360))}
        sizes = [1.0 / n] * n
        colored = _colored_block(n, k, int(rng.integers(n)), wrap=True)
        label_xy = (float(cx + r + rng.uniform(62, 78)), geom["cy"])     # clear of the circle
    elif shape == "strips":
        w, h = float(rng.uniform(300, 420)), float(rng.uniform(140, 200))
        x = float((512 - w) / 2 + rng.uniform(-20, 20))
        y = float(rng.uniform(110, 150) if with_label else (512 - h) / 2 + rng.uniform(-30, 30))
        geom = {"x": x, "y": y, "w": w, "h": h}
        sizes = [1.0 / n] * n
        colored = _colored_block(n, k, int(rng.integers(n)), wrap=False)
        label_xy = (256.0, y + h + 70)
    else:
        w, h = float(rng.uniform(280, 360)), float(rng.uniform(240, 320))
        geom = {"x": float((512 - w) / 2 + rng.uniform(-20, 20)), "y": float((512 - h) / 2 + rng.uniform(-20, 20)),
                "w": w, "h": h, "rows": rows, "cols": cols}
        sizes = [1.0 / cols] * cols
        colored = [False] * n                      # column-major from the left
        for idx in range(k):
            c, r = divmod(idx, rows)
            colored[r * cols + c] = True
        label_xy = None
    scene = {"domain": "fraction", "shape": shape, "geom": geom, "sizes": sizes, "colored": colored,
             "label": None}
    cons = [
        constraint("parts", "cardinality", "part_count", "whole", "eq", n, f"the whole is divided into {n} parts"),
        constraint("equal", "geometric", "equal_area", "parts", "true", True, "all parts have equal area"),
        constraint("colored", "cardinality", "colored_part_count", "parts", "eq", k,
                   f"exactly {k} of the parts {'is' if k == 1 else 'are'} colored"),
    ]
    noun = "cells" if shape == "grid" else "parts"
    objective = (f"Show the fraction {k}/{n}: {SHAPE_WORD[shape]} divided into {n} equal {noun} "
                 f"with {k} of them colored.")
    if with_label:
        scene["label"] = {"text": f"{k}/{n}", "x": label_xy[0], "y": label_xy[1], "size": float(rng.uniform(44, 56))}
        cons.append(constraint("label", "semantic", "label_text", "label", "eq", f"{k}/{n}",
                               f'the label reads "{k}/{n}"'))
        objective += f" Label it {k}/{n}."
    return Item("fraction", template, objective, cons, scene)


TEMPLATES = {
    "F1_circle": {"role": "dev", "sample": lambda rng: _sample(rng, "circle", False, "F1_circle")},
    "F2_strips": {"role": "dev", "sample": lambda rng: _sample(rng, "strips", False, "F2_strips")},
    "F3_circle_label": {"role": "dev", "sample": lambda rng: _sample(rng, "circle", True, "F3_circle_label")},
    "F4_grid": {"role": "heldout", "sample": lambda rng: _sample(rng, "grid", False, "F4_grid")},
    "F5_strips_label": {"role": "heldout", "sample": lambda rng: _sample(rng, "strips", True, "F5_strips_label")},
}


# --------------------------------------------------------------------------- operators

def _uncolored_adjacent_units(item: Item) -> list[tuple[int, int]]:
    """Adjacent size units (parts, or grid columns) that are entirely uncolored."""
    s = item.scene
    if s["shape"] == "grid":
        rows, cols = s["geom"]["rows"], s["geom"]["cols"]
        free = [not any(s["colored"][r * cols + c] for r in range(rows)) for c in range(cols)]
        return [(c, c + 1) for c in range(cols - 1) if free[c] and free[c + 1]]
    n = len(s["sizes"])
    pairs = [(i, i + 1) for i in range(n - 1)]
    if s["shape"] == "circle" and n > 2:
        pairs.append((n - 1, 0))
    return [(i, j) for i, j in pairs if not s["colored"][i] and not s["colored"][j]]


def _unit_boxes(item: Item, unit: int) -> list[list[float]]:
    s, boxes = item.scene, part_boxes(item.scene)
    if s["shape"] != "grid":
        return [boxes[unit]]
    cols = s["geom"]["cols"]
    return [boxes[r * cols + unit] for r in range(s["geom"]["rows"])]


def unequal_partition(item: Item, rng) -> None:
    pairs = _uncolored_adjacent_units(item)
    if not pairs:
        raise NotApplicable("needs two adjacent uncolored parts")
    i, j = pairs[rng.integers(len(pairs))]
    if rng.random() < 0.5:
        i, j = j, i
    d = float(rng.uniform(*DELTA))
    base = item.scene["sizes"][i]
    item.scene["sizes"][i] = base * (1 + d)
    item.scene["sizes"][j] = base * (1 - d)
    item.gt_regions["equal"] = _unit_boxes(item, i) + _unit_boxes(item, j)


def wrong_colored_count(item: Item, rng) -> None:
    s = item.scene
    n, k = n_parts(s), int(sum(s["colored"]))
    options = []
    if k + 1 <= n - 1:
        options.append(+1)
    if k - 1 >= 1:
        options.append(-1)
    if not options:
        raise NotApplicable("no valid colored count")
    step = options[rng.integers(len(options))]
    if s["shape"] == "grid":
        rows, cols = s["geom"]["rows"], s["geom"]["cols"]
        order = [r * cols + c for c in range(cols) for r in range(rows)]
        idx = order[k] if step > 0 else order[k - 1]
    else:
        col = s["colored"]
        starts = [i for i in range(n) if col[i] and not col[(i - 1) % n]]
        start = starts[0]
        end = (start + k - 1) % n
        if step > 0:
            cand = []
            if s["shape"] == "circle" or end + 1 < n:
                cand.append((end + 1) % n)
            if s["shape"] == "circle" or start - 1 >= 0:
                cand.append((start - 1) % n)
            idx = cand[rng.integers(len(cand))]
        else:
            idx = [start, end][rng.integers(2)]
    s["colored"][idx] = not s["colored"][idx]
    item.gt_regions["colored"] = [part_boxes(s)[idx]]


def wrong_part_count(item: Item, rng) -> None:
    s = item.scene
    k = int(sum(s["colored"]))
    if s["shape"] == "grid":
        rows, cols = s["geom"]["rows"], s["geom"]["cols"]
        opts = [c for c in (cols - 1, cols + 1) if c >= 2 and rows * c - 1 >= k and rows * c <= 12]
        if not opts:
            raise NotApplicable("no valid grid size")
        cols2 = opts[rng.integers(len(opts))]
        s["geom"]["cols"] = cols2
        s["sizes"] = [1.0 / cols2] * cols2
        colored = [False] * (rows * cols2)
        for idx in range(k):
            c, r = divmod(idx, rows)
            colored[r * cols2 + c] = True
        s["colored"] = colored
    else:
        n = len(s["sizes"])
        opts = [m for m in (n - 1, n + 1) if m >= max(2, k + 1) and m <= 9]
        if not opts:
            raise NotApplicable("no valid part count")
        m = opts[rng.integers(len(opts))]
        starts = [i for i in range(n) if s["colored"][i] and not s["colored"][(i - 1) % n]]
        start = min(starts[0], m - k) if s["shape"] == "strips" else starts[0] % m
        s["sizes"] = [1.0 / m] * m
        s["colored"] = _colored_block(m, k, start, wrap=s["shape"] == "circle")
    item.gt_regions["parts"] = [whole_box(s)]


def wrong_label(item: Item, rng) -> None:
    s = item.scene
    if not s.get("label"):
        raise NotApplicable("no label")
    n, k = n_parts(s), int(sum(s["colored"]))
    # single-digit fractions only: a wider label could run into the shape
    cand = [f"{a}/{n}" for a in range(1, min(n, 10)) if a != k] + [f"{k}/{b}" for b in range(k + 1, 10) if b != n]
    s["label"]["text"] = cand[rng.integers(len(cand))]
    item.gt_regions["label"] = [label_box(s)]


OPERATORS = {
    "unequal_partition": {"category": "Incorrect Proportion", "target": "equal", "apply": unequal_partition},
    "wrong_colored_count": {"category": "Incorrect Proportion", "target": "colored", "apply": wrong_colored_count},
    "wrong_part_count": {"category": "Incorrect Proportion", "target": "parts", "apply": wrong_part_count},
    "wrong_label": {"category": "Incorrect Label", "target": "label", "apply": wrong_label},
}
