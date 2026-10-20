"""Three-valued rule engine (paper Sections IV-D to IV-F).

For each constraint and each of the m readings, a checker returns a Reading: status
T / F / U, the value it decided on, whether the VLM reading and the measurement
conflicted, a witness box, and an agreement weight in [0, 1] (below 1 near a decision
threshold). `aggregate` turns the m readings into one status with confidence q:
the majority status is kept if q >= tau, else U. The verdict is the strong Kleene
conjunction: INVALID if any status is F, VALID if all are T, UNCERTAIN otherwise.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

import numpy as np

from . import measure as M
from .evidence import SEMANTIC_CATEGORY, SEMANTIC_TEXT

T, F, U = "T", "F", "U"
ORDER = {F: 0, U: 1, T: 2}
CW = {"up": "right", "right": "down", "down": "left", "left": "up"}


@dataclass
class Config:
    equal_area: tuple = (0.10, 0.20)     # deviation <= eps_T -> T, >= eps_F -> F
    symmetry: tuple = (0.92, 0.82)       # IoU >= hi -> T, <= lo -> F
    rel_margin: float = 0.25             # relation margin, fraction of mean object width
    area_margin: float = 0.03            # weight ramps to 1 this far from a threshold
    iou_margin: float = 0.03
    tau: float = 0.6                     # 2 of 3 agreeing readings pass; set on the dev split
    use_measure: bool = True             # ablation: geometry from VLM boxes only
    use_semantic: bool = True            # ablation: semantic constraints from grounding only
    abstain: bool = True                 # ablation: U counts as a rejection


@dataclass
class Reading:
    status: str
    value: object = None
    conflict: bool = False
    witness: list | None = None
    weight: float = 1.0
    source: str = "vlm"


@dataclass
class Decision:
    cid: str
    name: str
    status: str
    q: float
    witness: list | None
    readings: list = field(default_factory=list)


def _zone(x: float, hi_good: float, lo_bad: float, margin: float, larger_is_good: bool) -> tuple[str, float]:
    if larger_is_good:
        if x >= hi_good:
            return T, min(1.0, (x - hi_good) / margin + 0.5)
        if x <= lo_bad:
            return F, min(1.0, (lo_bad - x) / margin + 0.5)
        return U, 0.0
    if x <= hi_good:
        return T, min(1.0, (hi_good - x) / margin + 0.5)
    if x >= lo_bad:
        return F, min(1.0, (x - lo_bad) / margin + 0.5)
    return U, 0.0


def _main_shape(ev: dict) -> dict | None:
    shapes = [s for s in ev["shapes"] if s.get("box")]
    if not shapes:
        return None
    return max(shapes, key=lambda s: (s["box"][2] - s["box"][0]) * (s["box"][3] - s["box"][1]))


def _union_box(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    a = np.array(boxes)
    return [float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 2].max()), float(a[:, 3].max())]


def _text_value(c: dict, ev: dict, sem: dict | None, cfg: Config) -> tuple[str | None, list | None]:
    if cfg.use_semantic and sem and sem.get("text") is not None:
        return sem["text"], sem.get("box")
    shape = _main_shape(ev)
    texts = [t for t in ev["texts"] if any(ch.isdigit() for ch in t["text"])]
    if shape and shape.get("box"):           # labels sit outside the shape
        sx0, sy0, sx1, sy1 = shape["box"]
        out = [t for t in texts if not t["box"] or not (sx0 < (t["box"][0] + t["box"][2]) / 2 < sx1
                                                        and sy0 < (t["box"][1] + t["box"][3]) / 2 < sy1)]
        texts = out or texts
    if not texts:
        return None, None
    t = max(texts, key=lambda t: len(t["text"]))
    return t["text"], t["box"]


def _categories(ev: dict, sem: dict | None, cfg: Config) -> list[tuple[str, list | None]]:
    if cfg.use_semantic and sem and sem.get("categories") is not None:
        return list(zip(sem["categories"], [o["box"] for o in ev["objects"]]))
    return [(o["category"], o["box"]) for o in ev["objects"]]


def _find(ev: dict, cat: str) -> dict | None:
    cands = [o for o in ev["objects"] if o["category"] == cat]
    if not cands:
        return None
    return max(cands, key=lambda o: (o["box"][2] - o["box"][0]) * (o["box"][3] - o["box"][1]))


def check(c: dict, ev: dict, rgb: np.ndarray, ctx: dict, sem: dict | None, cfg: Config) -> Reading:
    """One constraint under one reading. `ctx` caches image-level measurements."""
    name = c["name"]
    if not ev["ok"]:
        return Reading(U, source="unparsable")
    # ---------------------------------------------------------------- fraction
    if name in ("part_count", "colored_part_count", "equal_area"):
        shape = _main_shape(ev)
        if shape is None:
            return Reading(U, source="no shape")
        key = ("partition", tuple(round(v) for v in shape["box"]))
        if cfg.use_measure and key not in ctx:
            ctx[key] = M.partition(rgb, shape["box"])
        meas = ctx.get(key) if cfg.use_measure else None
        parts = shape["parts"]
        if name == "part_count":
            vlm = len(parts)
            val = meas["n"] if meas and meas["ok"] else vlm
            conflict = bool(meas and meas["ok"] and meas["n"] != vlm)
            return Reading(T if val == c["value"] else F, val, conflict, shape["box"],
                           source="measured" if meas and meas["ok"] else "vlm")
        if name == "colored_part_count":
            vlm = sum(p["colored"] for p in parts)
            val = meas["colored"] if meas and meas["ok"] else vlm
            conflict = bool(meas and meas["ok"] and meas["colored"] != vlm)
            return Reading(T if val == c["value"] else F, val, conflict, shape["box"],
                           source="measured" if meas and meas["ok"] else "vlm")
        if meas and meas["ok"]:
            st, w = _zone(meas["deviation"], *cfg.equal_area, cfg.area_margin, larger_is_good=False)
            return Reading(st, meas["deviation"], False, meas["worst"], w, "measured")
        boxes = [p["box"] for p in parts if p["box"]]          # VLM-only proxy: part box areas
        if len(boxes) < 2:
            return Reading(U, source="vlm")
        areas = np.array([(b[2] - b[0]) * (b[3] - b[1]) for b in boxes])
        dev = float(np.max(np.abs(areas / areas.mean() - 1)))
        st, w = _zone(dev, *cfg.equal_area, cfg.area_margin, larger_is_good=False)
        return Reading(st, dev, False, boxes[int(np.argmax(np.abs(areas / areas.mean() - 1)))], w, "vlm")
    # ---------------------------------------------------------------- text
    if name in SEMANTIC_TEXT:
        val, box = _text_value(c, ev, sem, cfg)
        return Reading(T if val == c["value"] else F, val, False, box,
                       source="semantic" if cfg.use_semantic and sem and sem.get("text") is not None else "vlm")
    # ---------------------------------------------------------------- counting
    if name == "object_count":
        vlm = len(ev["objects"])
        meas = None
        if cfg.use_measure:
            if "blobs" not in ctx:
                line = M.vertical_line(ctx["rgb"])
                ctx["blobs"] = M.count_blobs(ctx["rgb"], line["x"] if line["ok"] else None)
            meas = ctx["blobs"]
        val = meas["n"] if meas and meas["ok"] else vlm
        conflict = bool(meas and meas["ok"] and meas["n"] != vlm)
        return Reading(T if val == c["value"] else F, val, conflict, _union_box([o["box"] for o in ev["objects"]]),
                       source="measured" if meas and meas["ok"] else "vlm")
    if name in SEMANTIC_CATEGORY:
        cats = _categories(ev, sem, cfg)
        src = "semantic" if cfg.use_semantic and sem and sem.get("categories") is not None else "vlm"
        if name == "all_objects_category":
            bad = [(cat, box) for cat, box in cats if cat != c["value"]]
            return Reading(F if bad or not cats else T, [cat for cat, _ in cats], False,
                           bad[0][1] if bad else None, source=src)
        present = [box for cat, box in cats if cat == c["subject"]]
        return Reading(T if present else F, len(present), False, present[0] if present else None, source=src)
    if name == "category_count":
        objs = [o for o in ev["objects"] if o["category"] == c["subject"]]
        return Reading(T if len(objs) == c["value"] else F, len(objs), False, _union_box([o["box"] for o in objs]))
    if name == "group_count":
        x = None
        if cfg.use_measure:
            if "line" not in ctx:
                ctx["line"] = M.vertical_line(ctx["rgb"])
            if ctx["line"]["ok"]:
                x = ctx["line"]["x"]
        if x is None:
            vert = [ln for ln in ev["lines"] if ln["orientation"] == "vertical" and ln["position"] is not None]
            x = vert[0]["position"] if vert else None
        if x is None:
            return Reading(U, source="no divider")
        left = c["subject"]["group"] == "left"
        objs = [o for o in ev["objects"] if o["category"] == c["subject"]["category"]
                and (((o["box"][0] + o["box"][2]) / 2 < x) == left)]
        return Reading(T if len(objs) == c["value"] else F, len(objs), False, _union_box([o["box"] for o in objs]))
    # ---------------------------------------------------------------- spatial
    if name in ("left_of", "above"):
        a, b = (_find(ev, s) for s in c["subject"])
        if a is None or b is None:
            return Reading(U, source="object missing")
        pts = []
        for o in (a, b):
            m = M.blob(rgb, o["box"], ctx.get("fg")) if cfg.use_measure else {"ok": False}
            pts.append((m["cx"], m["cy"]) if m["ok"] else ((o["box"][0] + o["box"][2]) / 2, (o["box"][1] + o["box"][3]) / 2))
        k = 0 if name == "left_of" else 1
        size = np.mean([(o["box"][2] - o["box"][0]) if k == 0 else (o["box"][3] - o["box"][1]) for o in (a, b)])
        margin = cfg.rel_margin * size
        diff = pts[1][k] - pts[0][k]
        st = T if diff > margin else F if diff < -margin else U
        w = min(1.0, max(0.0, abs(diff) / margin - 1.0)) if st != U else 0.0
        return Reading(st, float(diff), False, _union_box([a["box"], b["box"]]), max(w, 0.5 if st != U else 0.0),
                       "measured" if cfg.use_measure else "vlm")
    if name == "mirror_symmetric":
        if cfg.use_measure:
            if "sym" not in ctx:
                dashed = [ln for ln in ev["lines"] if ln["orientation"] == "vertical" and ln["position"] is not None]
                ctx["sym"] = M.symmetry(rgb, dashed[0]["position"] if dashed else None)
            meas = ctx["sym"]
            if meas["ok"]:
                st, w = _zone(meas["iou"], *cfg.symmetry, cfg.iou_margin, larger_is_good=True)
                return Reading(st, meas["iou"], False, meas["worst"], w, "measured")
        # VLM-only rule: every object needs a same-category partner mirrored about the axis
        dashed = [ln for ln in ev["lines"] if ln["orientation"] == "vertical" and ln["position"] is not None]
        if not dashed or not ev["objects"]:
            return Reading(U)
        ax = dashed[0]["position"]
        for o in ev["objects"]:
            cx, cy = (o["box"][0] + o["box"][2]) / 2, (o["box"][1] + o["box"][3]) / 2
            tol = 0.35 * (o["box"][2] - o["box"][0])
            if not any(p["category"] == o["category"] and abs((p["box"][0] + p["box"][2]) / 2 - (2 * ax - cx)) < tol
                       and abs((p["box"][1] + p["box"][3]) / 2 - cy) < tol for p in ev["objects"]):
                return Reading(F, False, False, o["box"])
        return Reading(T, True)
    if name == "rotated_quarter_cw":
        arrows = sorted([o for o in ev["objects"] if o["category"] == "arrow"], key=lambda o: o["box"][0])
        if len(arrows) < 2:
            return Reading(U, source="arrows missing")
        left, right = arrows[0], arrows[-1]
        dirs, conflict = [], False
        for o in (left, right):
            d = o["direction"]
            if cfg.use_measure:
                m = M.blob(rgb, o["box"], ctx.get("fg"))
                if m["ok"]:
                    conflict |= d is not None and d != m["direction"]
                    d = m["direction"]
            dirs.append(d)
        if None in dirs:
            return Reading(U, source="direction unknown")
        return Reading(T if dirs[1] == CW[dirs[0]] else F, dirs, conflict, right["box"],
                       source="measured" if cfg.use_measure else "vlm")
    raise KeyError(name)


def aggregate(cid: str, name: str, readings: list[Reading], cfg: Config) -> Decision:
    votes = Counter(r.status for r in readings if r.status != U)
    if not votes or (votes[T] == votes[F]):
        return Decision(cid, name, U, 0.0, None, [asdict(r) for r in readings])
    maj = T if votes[T] > votes[F] else F
    q = float(np.mean([r.weight if (r.status == maj and not r.conflict) else 0.0 for r in readings]))
    status = maj if q >= cfg.tau else U
    witness = next((r.witness for r in readings if r.status == maj and r.witness), None)
    return Decision(cid, name, status, q, witness, [asdict(r) for r in readings])


def verdict(decisions: list[Decision], cfg: Config) -> str:
    statuses = [d.status for d in decisions]
    if not cfg.abstain:
        statuses = [F if s == U else s for s in statuses]
    low = min(statuses, key=lambda s: ORDER[s]) if statuses else U
    return {T: "VALID", F: "INVALID", U: "UNCERTAIN"}[low]


def decide(constraints: list[dict], readings: list[dict], sem_readings: list[dict | None], rgb: np.ndarray,
           cfg: Config) -> dict:
    """Full rule pass: m evidence graphs (+ m semantic readings) -> statuses, verdict, report."""
    ctx = {"rgb": rgb, "fg": M.foreground(rgb)}
    decisions = []
    for c in constraints:
        rs = [check(c, ev, rgb, ctx, sem_readings[i] if i < len(sem_readings) else None, cfg)
              for i, ev in enumerate(readings)]
        decisions.append(aggregate(c["id"], c["name"], rs, cfg))
    return {"verdict": verdict(decisions, cfg),
            "statuses": {d.cid: d.status for d in decisions},
            "confidence": {d.cid: d.q for d in decisions},
            "report": [asdict(d) for d in decisions]}
