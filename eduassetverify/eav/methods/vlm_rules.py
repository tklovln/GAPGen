"""Ablation "w/o rule engine": the VLM decides each constraint from the same evidence graph.

The evidence (VLM reading plus measured geometry) is serialized as text; the VLM gets it
together with the requirements, but no image, and answers satisfied true/false per
requirement. Statuses from the m readings are aggregated exactly as in the full method,
so the only difference to EduAssetVerify is who applies the rule.
"""
from __future__ import annotations

import json

import numpy as np

from .. import measure as M
from ..evidence import parse_json
from ..rules import Config, Reading, _main_shape, aggregate, verdict


def _r(v):
    return int(round(v))


def serialize(ev: dict, rgb: np.ndarray, cache: dict) -> dict:
    """Compact, image-free description: what was read, and what was measured."""
    out = {}
    shape = _main_shape(ev)
    if shape:
        key = tuple(_r(v) for v in shape["box"])
        if key not in cache:
            cache[key] = M.partition(rgb, shape["box"])
        meas = cache[key]
        out["shape"] = {"kind": shape["shape"], "parts_read": len(shape["parts"]),
                        "colored_parts_read": sum(p["colored"] for p in shape["parts"])}
        if meas["ok"]:
            areas = [p["area"] for p in meas["parts"]]
            out["shape"]["measured"] = {"parts": meas["n"], "colored_parts": meas["colored"],
                                        "part_areas_px": areas}
    if ev["objects"]:
        objs = []
        for o in ev["objects"]:
            d = {"category": o["category"], "center": [_r((o["box"][0] + o["box"][2]) / 2), _r((o["box"][1] + o["box"][3]) / 2)],
                 "size": [_r(o["box"][2] - o["box"][0]), _r(o["box"][3] - o["box"][1])]}
            if o["category"] == "arrow":
                b = M.blob(rgb, o["box"], cache.setdefault("fg", M.foreground(rgb)))
                if b["ok"]:
                    d["measured_direction"] = b["direction"]
            objs.append(d)
        out["objects"] = objs
        if "blobs" not in cache:
            line = M.vertical_line(rgb)
            cache["blobs"] = M.count_blobs(rgb, line["x"] if line["ok"] else None)
        if cache["blobs"]["ok"]:
            out["measured_object_count"] = cache["blobs"]["n"]
    if ev["texts"]:
        out["texts"] = [t["text"] for t in ev["texts"]]
    lines = [ln for ln in ev["lines"] if ln["position"] is not None]
    if lines:
        out["lines"] = [{"style": ln["style"], "orientation": ln["orientation"], "position": _r(ln["position"])}
                        for ln in lines]
        if "sym" not in cache:
            cache["sym"] = M.symmetry(rgb, lines[0]["position"])
        if cache["sym"]["ok"]:
            out["measured_mirror_overlap_iou"] = round(cache["sym"]["iou"], 3)
    return out


def prompt(objective: str, constraints: list[dict], desc: dict) -> str:
    reqs = "\n".join(f"{i + 1}. {c['text']}" for i, c in enumerate(constraints))
    return ("A picture for an educational game was analyzed. You cannot see the picture; you only get the "
            "description below, produced by an image reader and by pixel measurements (coordinates in pixels of "
            "a 512x512 image, x to the right, y downward).\n\n"
            f"Description:\n{json.dumps(desc)}\n\n"
            f'Learning objective: "{objective}"\nRequirements:\n{reqs}\n\n'
            "Using only the description, decide for each requirement whether it is satisfied. "
            'Return JSON {"requirements": [{"number": 1, "satisfied": true | false}, ...]}.')


def run_vlm_rules(item: dict, eav_rec: dict, rgb: np.ndarray, vlm, pass_idx: int, cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    cons = item["constraints"]
    cache: dict = {}
    per_c = {c["id"]: [] for c in cons}
    calls = []
    for r, ev in enumerate(eav_rec["readings"]):
        if not ev["ok"]:
            for c in cons:
                per_c[c["id"]].append(Reading("U", source="unparsable"))
            continue
        desc = serialize(ev, rgb, cache)
        resp = vlm.ask(prompt(item["objective"], cons, desc), [], sample=f"p{pass_idx}-r{r}")
        calls.append(resp)
        js = parse_json(resp["text"]) or {}
        got = {}
        for k, e in enumerate(js.get("requirements") or []):
            if not isinstance(e, dict):
                continue
            try:
                num = int(e.get("number", k + 1)) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= num < len(cons) and isinstance(e.get("satisfied"), bool):
                got[cons[num]["id"]] = "T" if e["satisfied"] else "F"
        for c in cons:
            per_c[c["id"]].append(Reading(got.get(c["id"], "U"), source="vlm-rules"))
    decisions = [aggregate(c["id"], c["name"], per_c[c["id"]], cfg) for c in cons]
    return {"verdict": verdict(decisions, cfg), "statuses": {d.cid: d.status for d in decisions},
            "confidence": {d.cid: d.q for d in decisions}, "report": [{"cid": d.cid, "status": d.status, "q": d.q,
                                                                       "witness": None} for d in decisions],
            "calls": len(calls), "errors": [c["error"] for c in calls if c.get("error")],
            "usage": {"input": sum(c["usage"].get("input", 0) for c in calls),
                      "output": sum(c["usage"].get("output", 0) for c in calls),
                      "latency": sum(c.get("latency", 0.0) for c in calls),
                      "cached": sum(bool(c.get("cached")) for c in calls)},
            "unparsable": sum(parse_json(c["text"]) is None for c in calls)}
