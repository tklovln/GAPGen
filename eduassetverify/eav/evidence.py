"""Evidence graphs: the normalized form of what a grounding reading reports about an image.

    {"shapes":  [{"shape", "box", "parts": [{"box", "colored"}]}],      fraction schema
     "objects": [{"category", "box", "direction"}],                     object schema
     "texts":   [{"text", "box"}],
     "lines":   [{"style", "orientation", "position"}],
     "ok": parsed?, "error": str | None}

Boxes are [x0, y0, x1, y1] in pixels of the 512x512 image. VLMs answer with explicit
left/top/right/bottom keys (no xy/yx ambiguity) in their native frame (eav.vlm.prompts).
"""
from __future__ import annotations

import json
import re

SIZE = 512.0
FRACTION_NAMES = {"part_count", "equal_area", "colored_part_count", "label_text"}
COUNTING_NAMES = {"object_count", "all_objects_category", "numeral_label", "category_count", "group_count"}
SPATIAL_NAMES = {"object_present", "left_of", "above", "mirror_symmetric", "rotated_quarter_cw"}
COUNT_VOCAB = ["apple", "fish", "flower", "heart", "star", "tree", "other"]
SHAPE_VOCAB = ["arrow", "circle", "diamond", "heart", "square", "star", "triangle", "other"]
SEMANTIC_TEXT = {"label_text", "numeral_label"}
SEMANTIC_CATEGORY = {"all_objects_category", "object_present"}


def schema_for(constraints: list[dict]) -> str:
    names = {c["name"] for c in constraints}
    if names & FRACTION_NAMES:
        return "partition"
    if names & COUNTING_NAMES:
        return "counting"
    return "spatial"


def parse_json(text: str, allow_list: bool = False, repair: bool = True):
    """Parse a model's JSON answer. Small syntax slips (a stray brace, trailing prose) are
    repaired; `parse_json(..., repair=False)` is the strict check of protocol compliance."""
    if text is None:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    starts = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    if starts:
        t = t[min(starts):]
    for _ in range(8 if repair else 1):
        try:
            val = json.loads(t)
            break
        except json.JSONDecodeError as e:
            if not repair:
                return None
            if e.msg == "Extra data":
                t = t[:e.pos]
            elif e.pos < len(t) and t[e.pos] in "}]" and e.msg.startswith("Expecting"):
                t = t[:e.pos] + t[e.pos + 1:]
            else:
                return None
    else:
        return None
    if isinstance(val, dict) or (allow_list and isinstance(val, list)):
        return val
    return None


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def box_px(b, unit: float = 1000.0) -> list[float] | None:
    """{"left","top","right","bottom"} or [x0, y0, x1, y1] in `unit` units -> pixels."""
    if isinstance(b, dict):
        vals = [_num(b.get(k)) for k in ("left", "top", "right", "bottom")]
    elif isinstance(b, (list, tuple)) and len(b) == 4:
        vals = [_num(v) for v in b]
    else:
        return None
    if any(v is None for v in vals):
        return None
    x0, y0, x1, y1 = (min(unit, max(0.0, v)) * SIZE / unit for v in vals)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    return [x0, y0, x1, y1]


def norm_text(s) -> str:
    s = "" if s is None else str(s)
    s = s.replace("\u2044", "/").replace("\u2215", "/").replace("\uff0f", "/")
    return re.sub(r"\s+", "", s)


def evidence(raw: dict | None, unit: float = 1000.0) -> dict:
    ev = {"shapes": [], "objects": [], "texts": [], "lines": [], "ok": raw is not None, "error": None}
    if raw is None:
        ev["error"] = "unparsable"
        return ev
    for s in raw.get("shapes") or []:
        if not isinstance(s, dict):
            continue
        box = box_px(s.get("box"), unit)
        parts = []
        for p in s.get("parts") or []:
            if isinstance(p, dict):
                parts.append({"box": box_px(p.get("box"), unit), "colored": bool(p.get("colored"))})
        if box or parts:
            ev["shapes"].append({"shape": str(s.get("shape", "other")).lower(), "box": box, "parts": parts})
    for o in raw.get("objects") or []:
        if not isinstance(o, dict):
            continue
        box = box_px(o.get("box"), unit)
        if box:
            d = str(o.get("direction") or "none").lower()
            ev["objects"].append({"category": str(o.get("category", "other")).lower().strip(), "box": box,
                                  "direction": d if d in ("up", "down", "left", "right") else None})
    for t in raw.get("texts") or []:
        if isinstance(t, dict) and str(t.get("text", "")).strip():
            ev["texts"].append({"text": norm_text(t.get("text")), "box": box_px(t.get("box"), unit)})
    for ln in raw.get("lines") or []:
        if isinstance(ln, dict):
            pos = _num(ln.get("position"))
            ev["lines"].append({"style": str(ln.get("style", "solid")).lower(),
                                "orientation": str(ln.get("orientation", "vertical")).lower(),
                                "position": None if pos is None else min(unit, max(0.0, pos)) * SIZE / unit})
    return ev
