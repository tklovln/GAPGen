"""Task B, object counting and classification.

Constraints
    count     cardinality  object_count = N            (C1-C3)
    category  semantic     all_objects_category = X    (C1-C3)
    numeral   semantic     numeral_label = "N"         (C3)
    count_x   cardinality  category_count(X) = N       (C4, distractors allowed)
    left      cardinality  group_count(left, X) = N1   (C5)
    right     cardinality  group_count(right, X) = N2  (C5)

Operators
    missing_object     Missing Object     one target object removed
    extra_object       Extra Object       one target object added
    semantic_mismatch  Semantic Mismatch  one object replaced by another category (C1-C3)
    wrong_label        Incorrect Label    numeral shows N +- 1 (C3)
"""
from __future__ import annotations

import math

import numpy as np

from ..render import object_bbox
from ..styles import COUNT_CATEGORIES
from . import Item, NotApplicable, constraint

PLURAL = {"apple": "apples", "star": "stars", "fish": "fish", "heart": "hearts",
          "flower": "flowers", "ball": "balls"}
ARTICLE = {"apple": "an apple"}


def _article(cat: str) -> str:
    return ARTICLE.get(cat, f"a {cat}")


# --------------------------------------------------------------------------- layout

def _grid_slots(n_slots: int, top: float, bottom: float, rng) -> tuple[list[tuple[float, float]], float]:
    cols = math.ceil(math.sqrt(n_slots))
    rows = math.ceil(n_slots / cols)
    size = min(88.0, 380.0 / cols, (bottom - top) / (rows * 1.3))
    step = size * 1.32
    x0 = 256 - step * (cols - 1) / 2 + rng.uniform(-10, 10)
    y0 = (top + bottom) / 2 - step * (rows - 1) / 2
    slots = [(x0 + c * step, y0 + r * step) for r in range(rows) for c in range(cols)][:n_slots]
    return slots, float(size)


def _free_spot(objs: list[dict], size: float, box: tuple[float, float, float, float], rng, tries=400):
    x0, y0, x1, y1 = box
    for _ in range(tries):
        x = rng.uniform(x0 + size / 2, x1 - size / 2)
        y = rng.uniform(y0 + size / 2, y1 - size / 2)
        if all(math.hypot(x - o["cx"], y - o["cy"]) > 0.62 * (size + o["size"]) + 6 for o in objs):
            return float(x), float(y)
    raise NotApplicable("no free spot")


def _scatter(objs: list[dict], cats: list[str], box, size_rng, rng) -> None:
    for cat in cats:
        size = float(rng.uniform(*size_rng))
        x, y = _free_spot(objs, size, box, rng)
        objs.append({"id": len(objs), "category": cat, "cx": x, "cy": y, "size": size})


def primitives(scene: dict) -> list[dict]:
    prims = []
    if scene.get("divider"):
        x = scene["divider"]["x"]
        prims.append({"kind": "line", "x0": x, "y0": 50, "x1": x, "y1": 462, "dashed": False})
    for o in scene["objects"]:
        prims.append({"kind": "object", "category": o["category"], "cx": o["cx"], "cy": o["cy"], "size": o["size"]})
    if scene.get("label"):
        lab = scene["label"]
        prims.append({"kind": "text", "x": lab["x"], "y": lab["y"], "text": lab["text"], "size": lab["size"]})
    return prims


def label_box(scene: dict) -> list[float]:
    lab = scene["label"]
    w = 0.62 * lab["size"] * len(lab["text"])
    return [lab["x"] - w / 2, lab["y"] - 0.6 * lab["size"], lab["x"] + w / 2, lab["y"] + 0.6 * lab["size"]]


def _bbox(o: dict) -> list[float]:
    return object_bbox(o["category"], o["cx"], o["cy"], o["size"])


# --------------------------------------------------------------------------- truth

def evaluate(scene: dict, constraints: list[dict]) -> dict[str, bool]:
    objs, out = scene["objects"], {}
    for c in constraints:
        name = c["name"]
        if name == "object_count":
            out[c["id"]] = len(objs) == c["value"]
        elif name == "all_objects_category":
            out[c["id"]] = all(o["category"] == c["value"] for o in objs)
        elif name == "numeral_label":
            out[c["id"]] = bool(scene.get("label")) and scene["label"]["text"] == c["value"]
        elif name == "category_count":
            out[c["id"]] = sum(o["category"] == c["subject"] for o in objs) == c["value"]
        elif name == "group_count":
            x = scene["divider"]["x"]
            side = c["subject"]["group"]
            n = sum(o["category"] == c["subject"]["category"] and ((o["cx"] < x) == (side == "left")) for o in objs)
            out[c["id"]] = n == c["value"]
        else:
            raise KeyError(name)
    return out


# --------------------------------------------------------------------------- sampling

def _sample_grid(rng, numeral: bool, template: str) -> Item:
    cat = COUNT_CATEGORIES[rng.integers(len(COUNT_CATEGORIES))]
    n = int(rng.integers(3, 13))
    bottom = 390.0 if numeral else 470.0
    slots, size = _grid_slots(n + 1, 50.0, bottom, rng)   # one spare slot for extra_object
    objs = [{"id": i, "category": cat, "cx": float(x), "cy": float(y), "size": size}
            for i, (x, y) in enumerate(slots[:n])]
    scene = {"domain": "counting", "layout": "grid", "objects": objs, "slots": [list(s) for s in slots],
             "label": None, "divider": None}
    cons = [constraint("count", "cardinality", "object_count", "objects", "eq", n,
                       f"the picture shows exactly {n} objects"),
            constraint("category", "semantic", "all_objects_category", "objects", "eq", cat,
                       f"every object is {_article(cat)}")]
    objective = f"Show exactly {n} {PLURAL[cat]} and nothing else."
    if numeral:
        scene["label"] = {"text": str(n), "x": 256.0, "y": 448.0, "size": float(rng.uniform(46, 56))}
        cons.append(constraint("numeral", "semantic", "numeral_label", "label", "eq", str(n),
                               f'the number written below is "{n}"'))
        objective = f"Show exactly {n} {PLURAL[cat]} and write the number {n} below them."
    return Item("counting", template, objective, cons, scene)


def _sample_scatter(rng, template: str) -> Item:
    cat = COUNT_CATEGORIES[rng.integers(len(COUNT_CATEGORIES))]
    n = int(rng.integers(3, 11))
    objs: list[dict] = []
    _scatter(objs, [cat] * n, (30, 30, 482, 482), (58, 78), rng)
    scene = {"domain": "counting", "layout": "scatter", "objects": objs, "label": None, "divider": None}
    cons = [constraint("count", "cardinality", "object_count", "objects", "eq", n,
                       f"the picture shows exactly {n} objects"),
            constraint("category", "semantic", "all_objects_category", "objects", "eq", cat,
                       f"every object is {_article(cat)}")]
    return Item("counting", template, f"Show exactly {n} {PLURAL[cat]} and nothing else.", cons, scene)


def _sample_distractors(rng, template: str) -> Item:
    cats = list(rng.permutation(COUNT_CATEGORIES))
    cat, others = cats[0], cats[1:3]
    n, m = int(rng.integers(3, 9)), int(rng.integers(2, 5))
    objs: list[dict] = []
    _scatter(objs, [cat] * n + [others[i % len(others)] for i in range(m)], (30, 30, 482, 482), (54, 72), rng)
    order = rng.permutation(len(objs))            # do not leave targets first in the list
    objs = [dict(objs[i], id=j) for j, i in enumerate(order)]
    scene = {"domain": "counting", "layout": "scatter", "objects": objs, "label": None, "divider": None}
    cons = [constraint("count_x", "cardinality", "category_count", cat, "eq", n,
                       f"the picture shows exactly {n} {PLURAL[cat]} (other objects may appear)")]
    objective = f"Show exactly {n} {PLURAL[cat]}; other objects may also appear."
    return Item("counting", template, objective, cons, scene)


def _sample_groups(rng, template: str) -> Item:
    cat = COUNT_CATEGORIES[rng.integers(len(COUNT_CATEGORIES))]
    n1, n2 = int(rng.integers(2, 7)), int(rng.integers(2, 7))
    objs: list[dict] = []
    _scatter(objs, [cat] * n1, (24, 40, 236, 472), (52, 66), rng)
    _scatter(objs, [cat] * n2, (276, 40, 488, 472), (52, 66), rng)
    scene = {"domain": "counting", "layout": "groups", "objects": objs, "label": None, "divider": {"x": 256.0}}
    cons = [constraint("left", "cardinality", "group_count", {"group": "left", "category": cat}, "eq", n1,
                       f"exactly {n1} {PLURAL[cat]} are left of the line"),
            constraint("right", "cardinality", "group_count", {"group": "right", "category": cat}, "eq", n2,
                       f"exactly {n2} {PLURAL[cat]} are right of the line")]
    objective = f"Show {n1} {PLURAL[cat]} on the left of the line and {n2} {PLURAL[cat]} on the right."
    return Item("counting", template, objective, cons, scene)


TEMPLATES = {
    "C1_grid": {"role": "dev", "sample": lambda rng: _sample_grid(rng, False, "C1_grid")},
    "C2_scatter": {"role": "dev", "sample": lambda rng: _sample_scatter(rng, "C2_scatter")},
    "C3_grid_numeral": {"role": "dev", "sample": lambda rng: _sample_grid(rng, True, "C3_grid_numeral")},
    "C4_distractors": {"role": "heldout", "sample": lambda rng: _sample_distractors(rng, "C4_distractors")},
    "C5_two_groups": {"role": "heldout", "sample": lambda rng: _sample_groups(rng, "C5_two_groups")},
}


# --------------------------------------------------------------------------- operators

def _target_info(item: Item, rng):
    """(constraint id, category, object filter) that missing/extra operate on."""
    cons = {c["id"]: c for c in item.constraints}
    if "count" in cons:
        return "count", cons["category"]["value"], lambda o: True
    if "count_x" in cons:
        cat = cons["count_x"]["subject"]
        return "count_x", cat, lambda o: o["category"] == cat
    side = ["left", "right"][rng.integers(2)]
    cat, x = cons[side]["subject"]["category"], item.scene["divider"]["x"]
    return side, cat, lambda o: o["category"] == cat and ((o["cx"] < x) == (side == "left"))


def missing_object(item: Item, rng) -> None:
    cid, _, keep = _target_info(item, rng)
    s = item.scene
    pool = [i for i, o in enumerate(s["objects"]) if keep(o)]
    if len(pool) < 2:
        raise NotApplicable("too few objects to remove one")
    idx = pool[-1] if s["layout"] == "grid" else pool[rng.integers(len(pool))]
    removed = s["objects"].pop(idx)
    item.gt_regions[cid] = [_bbox(removed)]


def extra_object(item: Item, rng) -> None:
    cid, cat, _ = _target_info(item, rng)
    s = item.scene
    if s["layout"] == "grid":
        n = len(s["objects"])
        if n >= len(s["slots"]):
            raise NotApplicable("no spare grid slot")
        x, y = s["slots"][n]
        size = s["objects"][0]["size"]
    else:
        size = float(np.median([o["size"] for o in s["objects"]]))
        if cid == "left":
            box = (24, 40, 236, 472)
        elif cid == "right":
            box = (276, 40, 488, 472)
        else:
            box = (30, 30, 482, 482)
        x, y = _free_spot(s["objects"], size, box, rng)
    new = {"id": max(o["id"] for o in s["objects"]) + 1, "category": cat, "cx": float(x), "cy": float(y),
           "size": size}
    s["objects"].append(new)
    item.gt_regions[cid] = [_bbox(new)]


def semantic_mismatch(item: Item, rng) -> None:
    cons = {c["id"]: c for c in item.constraints}
    if "category" not in cons:
        raise NotApplicable("no category constraint")
    cat = cons["category"]["value"]
    s = item.scene
    idx = int(rng.integers(len(s["objects"])))
    others = [c for c in COUNT_CATEGORIES if c != cat]
    s["objects"][idx]["category"] = others[rng.integers(len(others))]
    item.gt_regions["category"] = [_bbox(s["objects"][idx])]


def wrong_label(item: Item, rng) -> None:
    s = item.scene
    if not s.get("label"):
        raise NotApplicable("no numeral")
    n = int(s["label"]["text"])
    cand = [m for m in (n - 1, n + 1) if m >= 1]
    s["label"]["text"] = str(cand[rng.integers(len(cand))])
    item.gt_regions["numeral"] = [label_box(s)]


OPERATORS = {
    "missing_object": {"category": "Missing Object", "target": None, "apply": missing_object},
    "extra_object": {"category": "Extra Object", "target": None, "apply": extra_object},
    "semantic_mismatch": {"category": "Semantic Mismatch", "target": "category", "apply": semantic_mismatch},
    "wrong_label": {"category": "Incorrect Label", "target": "numeral", "apply": wrong_label},
}
