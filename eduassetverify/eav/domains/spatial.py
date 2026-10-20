"""Task C, spatial reasoning: relative position, symmetry, and rotation.

Constraints
    has_a, has_b, has_c   semantic   object_present(category)
    rel                   spatial    left_of(A, B)  (S1)  |  above(A, B)  (S2)
    rel_ab, rel_bc        spatial    left_of(A, B), left_of(B, C)       (S4)
    sym                   geometric  mirror_symmetric about the dashed line (S3)
    rot                   spatial    right arrow = left arrow turned a quarter turn clockwise (S5)

Operators
    relation_reversal  Spatial Relation Reversal  swap two objects / rotate the wrong way
    broken_symmetry    Broken Symmetry            move one element off its mirror position
"""
from __future__ import annotations

import math

from ..render import object_bbox
from ..styles import SHAPE_CATEGORIES
from . import Item, NotApplicable, constraint

AXIS_X = 256.0
CW = {"up": "right", "right": "down", "down": "left", "left": "up"}
CCW = {v: k for k, v in CW.items()}
MIRROR_KIND = {"triangle_left": "triangle_right", "triangle_right": "triangle_left"}
FIG_KINDS = ["circle", "square", "diamond", "triangle_up", "triangle_left"]
AXIS_KINDS = ["circle", "square", "diamond", "triangle_up", "triangle_down"]


def _a(cat: str) -> str:
    return f"a {cat}"


def _bbox(o: dict) -> list[float]:
    return object_bbox(o["category"], o["cx"], o["cy"], o["size"])


def _fig_bbox(e: dict) -> list[float]:
    h = 0.5 * e["size"]
    return [e["cx"] - h, e["cy"] - h, e["cx"] + h, e["cy"] + h]


def primitives(scene: dict) -> list[dict]:
    prims = []
    if scene.get("axis"):
        prims.append({"kind": "line", "x0": AXIS_X, "y0": 30, "x1": AXIS_X, "y1": 482, "dashed": True})
    for e in scene.get("figure", []):
        prims.append({"kind": "fig_shape", "shape": e["shape"], "cx": e["cx"], "cy": e["cy"],
                      "size": e["size"], "color": e["color"]})
    for o in scene.get("objects", []):
        prims.append({"kind": "object", "category": o["category"], "cx": o["cx"], "cy": o["cy"],
                      "size": o["size"], "direction": o.get("direction", "up")})
    return prims


# --------------------------------------------------------------------------- truth

def _find(scene: dict, cat: str) -> dict | None:
    for o in scene.get("objects", []):
        if o["category"] == cat:
            return o
    return None


def _symmetric(figure: list[dict]) -> bool:
    for e in figure:
        mx = 2 * AXIS_X - e["cx"]
        kind = MIRROR_KIND.get(e["shape"], e["shape"])
        if not any(abs(f["cx"] - mx) < 0.5 and abs(f["cy"] - e["cy"]) < 0.5 and f["shape"] == kind
                   and abs(f["size"] - e["size"]) < 0.5 and f["color"] == e["color"] for f in figure):
            return False
    return True


def evaluate(scene: dict, constraints: list[dict]) -> dict[str, bool]:
    out = {}
    for c in constraints:
        name = c["name"]
        if name == "object_present":
            out[c["id"]] = _find(scene, c["subject"]) is not None
        elif name in ("left_of", "above"):
            a, b = (_find(scene, s) for s in c["subject"])
            if a is None or b is None:
                out[c["id"]] = False
            elif name == "left_of":
                out[c["id"]] = a["cx"] < b["cx"]
            else:
                out[c["id"]] = a["cy"] < b["cy"]
        elif name == "mirror_symmetric":
            out[c["id"]] = _symmetric(scene["figure"])
        elif name == "rotated_quarter_cw":
            left, right = sorted(scene["objects"], key=lambda o: o["cx"])
            out[c["id"]] = right["direction"] == CW[left["direction"]]
        else:
            raise KeyError(name)
    return out


# --------------------------------------------------------------------------- sampling

def _pick(rng, k: int) -> list[str]:
    return [str(c) for c in rng.permutation(SHAPE_CATEGORIES)[:k]]


def _sample_pair(rng, horizontal: bool, template: str) -> Item:
    a, b = _pick(rng, 2)
    sa, sb = float(rng.uniform(80, 110)), float(rng.uniform(80, 110))
    if horizontal:
        pa = (float(rng.uniform(100, 190)), float(rng.uniform(180, 332)))
        pb = (float(rng.uniform(322, 412)), float(rng.uniform(180, 332)))
    else:
        pa = (float(rng.uniform(180, 332)), float(rng.uniform(100, 190)))
        pb = (float(rng.uniform(180, 332)), float(rng.uniform(322, 412)))
    objs = [{"id": "A", "category": a, "cx": pa[0], "cy": pa[1], "size": sa},
            {"id": "B", "category": b, "cx": pb[0], "cy": pb[1], "size": sb}]
    rel = "left_of" if horizontal else "above"
    phrase = "to the left of" if horizontal else "above"
    cons = [constraint("has_a", "semantic", "object_present", a, "true", True, f"the picture contains {_a(a)}"),
            constraint("has_b", "semantic", "object_present", b, "true", True, f"the picture contains {_a(b)}"),
            constraint("rel", "spatial", rel, [a, b], "true", True, f"the {a} is {phrase} the {b}")]
    scene = {"domain": "spatial", "layout": "pair", "objects": objs, "axis": None, "figure": []}
    return Item("spatial", template, f"The {a} is {phrase} the {b}.", cons, scene)


def _sample_row(rng, template: str) -> Item:
    cats = _pick(rng, 3)
    objs = []
    for i, (cat, x) in enumerate(zip(cats, (110.0, 256.0, 402.0))):
        objs.append({"id": "ABC"[i], "category": cat, "cx": float(x + rng.uniform(-15, 15)),
                     "cy": float(rng.uniform(210, 302)), "size": float(rng.uniform(70, 95))})
    a, b, c = cats
    cons = [constraint(f"has_{t}", "semantic", "object_present", cat, "true", True, f"the picture contains {_a(cat)}")
            for t, cat in zip("abc", cats)]
    cons += [constraint("rel_ab", "spatial", "left_of", [a, b], "true", True, f"the {a} is to the left of the {b}"),
             constraint("rel_bc", "spatial", "left_of", [b, c], "true", True, f"the {b} is to the left of the {c}")]
    scene = {"domain": "spatial", "layout": "row", "objects": objs, "axis": None, "figure": []}
    return Item("spatial", template, f"From left to right, the picture shows {_a(a)}, {_a(b)}, and {_a(c)}.",
                cons, scene)


def _overlaps(e: dict, figure: list[dict], pad: float = 10.0) -> bool:
    for f in figure:
        if f is e:
            continue
        if abs(f["cx"] - e["cx"]) < (f["size"] + e["size"]) / 2 + pad and \
           abs(f["cy"] - e["cy"]) < (f["size"] + e["size"]) / 2 + pad:
            return True
    return False


def _sample_symmetry(rng, template: str) -> Item:
    for _ in range(200):
        figure: list[dict] = []
        if rng.random() < 0.6:
            e = {"shape": AXIS_KINDS[rng.integers(len(AXIS_KINDS))], "cx": AXIS_X,
                 "cy": float(rng.uniform(90, 420)), "size": float(rng.uniform(60, 90)),
                 "color": int(rng.integers(4))}
            figure.append(e)
        n_pairs, ok = int(rng.integers(3, 5)), True
        for _p in range(n_pairs):
            placed = False
            for _t in range(100):
                size = float(rng.uniform(55, 85))
                dx = float(rng.uniform(size / 2 + 25, 215 - size / 2))
                left = {"shape": FIG_KINDS[rng.integers(len(FIG_KINDS))], "cx": AXIS_X - dx,
                        "cy": float(rng.uniform(70, 442)), "size": size, "color": int(rng.integers(4))}
                right = dict(left, cx=AXIS_X + dx, shape=MIRROR_KIND.get(left["shape"], left["shape"]))
                if not _overlaps(left, figure) and not _overlaps(right, figure):
                    figure += [left, right]
                    placed = True
                    break
            ok = ok and placed
        if ok:
            break
    scene = {"domain": "spatial", "layout": "symmetry", "objects": [], "axis": {"x": AXIS_X}, "figure": figure}
    cons = [constraint("sym", "geometric", "mirror_symmetric", "figure", "true", True,
                       "the picture is mirror-symmetric about the dashed line")]
    return Item("spatial", template, "Draw a picture that is mirror-symmetric about the dashed line.", cons, scene)


def _sample_rotation(rng, template: str) -> Item:
    d = ["up", "right", "down", "left"][rng.integers(4)]
    size = float(rng.uniform(110, 140))
    objs = [{"id": "L", "category": "arrow", "cx": float(rng.uniform(130, 170)), "cy": float(rng.uniform(236, 276)),
             "size": size, "direction": d},
            {"id": "R", "category": "arrow", "cx": float(rng.uniform(342, 382)), "cy": float(rng.uniform(236, 276)),
             "size": size, "direction": CW[d]}]
    cons = [constraint("rot", "spatial", "rotated_quarter_cw", ["left arrow", "right arrow"], "true", True,
                       "the right arrow is the left arrow turned a quarter turn clockwise")]
    scene = {"domain": "spatial", "layout": "rotation", "objects": objs, "axis": None, "figure": []}
    return Item("spatial", template,
                "The arrow on the right is the arrow on the left turned a quarter turn clockwise.", cons, scene)


TEMPLATES = {
    "S1_left_right": {"role": "dev", "sample": lambda rng: _sample_pair(rng, True, "S1_left_right")},
    "S2_above_below": {"role": "dev", "sample": lambda rng: _sample_pair(rng, False, "S2_above_below")},
    "S3_symmetry": {"role": "dev", "sample": lambda rng: _sample_symmetry(rng, "S3_symmetry")},
    "S4_three_row": {"role": "heldout", "sample": lambda rng: _sample_row(rng, "S4_three_row")},
    "S5_rotation": {"role": "heldout", "sample": lambda rng: _sample_rotation(rng, "S5_rotation")},
}


# --------------------------------------------------------------------------- operators

def relation_reversal(item: Item, rng) -> None:
    s = item.scene
    if s["layout"] == "rotation":
        left, right = sorted(s["objects"], key=lambda o: o["cx"])
        right["direction"] = CCW[left["direction"]]
        item.gt_regions["rot"] = [_bbox(right)]
        return
    if s["layout"] == "pair":
        a, b = s["objects"]
        cid = "rel"
    elif s["layout"] == "row":
        if rng.random() < 0.5:
            a, b, cid = s["objects"][0], s["objects"][1], "rel_ab"
        else:
            a, b, cid = s["objects"][1], s["objects"][2], "rel_bc"
    else:
        raise NotApplicable("no relation to reverse")
    a["cx"], b["cx"] = b["cx"], a["cx"]
    a["cy"], b["cy"] = b["cy"], a["cy"]
    item.gt_regions[cid] = [_bbox(a), _bbox(b)]


def broken_symmetry(item: Item, rng) -> None:
    s = item.scene
    fig = s.get("figure") or []
    total = sum(e["size"] ** 2 for e in fig)
    pool = [e for e in fig if abs(e["cx"] - AXIS_X) > 1 and e["size"] ** 2 >= 0.09 * total]
    if not pool:
        raise NotApplicable("no element large enough to break symmetry visibly")
    for _ in range(200):
        e = pool[rng.integers(len(pool))]
        dist = e["size"] + float(rng.uniform(12, 40))          # never overlaps its old place
        ang = float(rng.uniform(0, 2 * math.pi))
        moved = dict(e, cx=e["cx"] + dist * math.cos(ang), cy=e["cy"] + dist * math.sin(ang))
        half = moved["size"] / 2
        inside = 20 + half < moved["cx"] < 492 - half and 20 + half < moved["cy"] < 492 - half
        same_side = (moved["cx"] - AXIS_X) * (e["cx"] - AXIS_X) > 0 and abs(moved["cx"] - AXIS_X) > half + 12
        if inside and same_side and not _overlaps(moved, [f for f in fig if f is not e]):
            e.update(moved)
            item.gt_regions["sym"] = [_fig_bbox(e)]
            return
    raise NotApplicable("could not move an element to a free spot")


OPERATORS = {
    "relation_reversal": {"category": "Spatial Relation Reversal", "target": None, "apply": relation_reversal},
    "broken_symmetry": {"category": "Broken Symmetry", "target": "sym", "apply": broken_symmetry},
}
