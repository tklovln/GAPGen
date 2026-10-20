"""Oracle grounding: the evidence graph a perfect VLM would return, built from the spec.

Used only to test the measurement operators and the rule engine (perception removed);
it is the upper bound reported separately from every real method, never a baseline.
"""
from __future__ import annotations

from ..domains import counting as C
from ..domains import fraction as Fr
from ..render import object_bbox


def _fig_category(shape: str) -> str:
    return "triangle" if shape.startswith("triangle") else shape


def oracle_evidence(spec: dict) -> dict:
    scene, dom = spec["scene"], spec["domain"]
    ev = {"shapes": [], "objects": [], "texts": [], "lines": [], "ok": True, "error": None}
    if dom == "fraction":
        boxes = Fr.part_boxes(scene)
        ev["shapes"].append({"shape": "circle" if scene["shape"] == "circle" else "rectangle",
                             "box": Fr.whole_box(scene),
                             "parts": [{"box": b, "colored": bool(c)} for b, c in zip(boxes, scene["colored"])]})
        if scene.get("label"):
            ev["texts"].append({"text": scene["label"]["text"], "box": Fr.label_box(scene)})
    elif dom == "counting":
        for o in scene["objects"]:
            ev["objects"].append({"category": o["category"], "box": object_bbox(o["category"], o["cx"], o["cy"], o["size"]),
                                  "direction": None})
        if scene.get("label"):
            ev["texts"].append({"text": scene["label"]["text"], "box": C.label_box(scene)})
        if scene.get("divider"):
            ev["lines"].append({"style": "solid", "orientation": "vertical", "position": scene["divider"]["x"]})
    else:
        for o in scene.get("objects", []):
            ev["objects"].append({"category": o["category"], "box": object_bbox(o["category"], o["cx"], o["cy"], o["size"]),
                                  "direction": o.get("direction") if o["category"] == "arrow" else None})
        for e in scene.get("figure", []):
            h = e["size"] / 2
            ev["objects"].append({"category": _fig_category(e["shape"]),
                                  "box": [e["cx"] - h, e["cy"] - h, e["cx"] + h, e["cy"] + h], "direction": None})
        if scene.get("axis"):
            ev["lines"].append({"style": "dashed", "orientation": "vertical", "position": scene["axis"]["x"]})
    return ev
