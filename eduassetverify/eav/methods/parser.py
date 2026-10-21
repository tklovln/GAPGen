"""Educational constraint parser (paper Section IV-B): objective text -> constraint set.

The language model transcribes the requirements stated in the objective into the schema;
it is told to keep contradictions rather than resolve them. A deterministic consistency
check then rejects unsatisfiable sets before any image is verified.

Gold-constraint and extracted-constraint regimes are scored separately (eav.parse_eval).
"""
from __future__ import annotations

import json
from fractions import Fraction

from ..evidence import parse_json
from ..styles import COUNT_CATEGORIES, SHAPE_CATEGORIES

SCHEMA = """Constraint names (use only these):
  part_count            value: integer                 the whole is divided into this many parts
  equal_area            value: true                    all parts have equal area
  colored_part_count    value: integer                 number of colored parts
  fraction_value        value: "a/b"                   the fraction the picture is meant to show
  label_text            value: string                  exact text of a written label, e.g. "3/8"
  object_count          value: integer                 total number of objects
  all_objects_category  value: category                every object is of this category
  numeral_label         value: string                  exact number written in the picture
  category_count        subject: category, value: integer   objects of this category (others may appear)
  group_count           subject: {"group": "left" | "right", "category": category}, value: integer
                                                       objects of the category on that side of a line
  object_present        subject: category              the picture contains this object
  left_of               subject: [category A, category B]   A is to the left of B
  above                 subject: [category A, category B]   A is above B
  mirror_symmetric      value: true                    mirror-symmetric about the dashed line
  rotated_quarter_cw    value: true                    right arrow = left arrow turned a quarter turn clockwise
Categories are singular nouns: """ + ", ".join(sorted(set(COUNT_CATEGORIES) | set(SHAPE_CATEGORIES) | {"arrow"}))


def prompt(objective: str) -> str:
    return ("Transcribe the requirements of a learning objective for an educational picture into constraints.\n\n"
            f"{SCHEMA}\n\n"
            "Rules: write one constraint per stated requirement; a requirement that says where objects are also "
            "implies that each named object is present (object_present). The shape that is divided into parts "
            "(a circle, rectangle or grid) is the whole of a fraction and is described by part_count, not by "
            "object_present or all_objects_category. Copy numbers exactly as stated. If two requirements "
            "contradict each other, keep both; never resolve a conflict.\n\n"
            f'Objective: "{objective}"\n\n'
            'Return JSON {"constraints": [{"name": "...", "subject": ..., "value": ...}, ...]} '
            "(omit subject or value when a constraint has none).")


NAMES = {"part_count", "equal_area", "colored_part_count", "fraction_value", "label_text", "object_count",
         "all_objects_category", "numeral_label", "category_count", "group_count", "object_present", "left_of",
         "above", "mirror_symmetric", "rotated_quarter_cw"}
TYPE = {"part_count": "cardinality", "colored_part_count": "cardinality", "object_count": "cardinality",
        "category_count": "cardinality", "group_count": "cardinality", "equal_area": "geometric",
        "mirror_symmetric": "geometric", "fraction_value": "semantic", "label_text": "semantic",
        "all_objects_category": "semantic", "numeral_label": "semantic", "object_present": "semantic",
        "left_of": "spatial", "above": "spatial", "rotated_quarter_cw": "spatial"}


def _cat(x) -> str:
    s = str(x).strip().lower()
    for c in sorted(set(COUNT_CATEGORIES) | set(SHAPE_CATEGORIES) | {"arrow"}, key=len, reverse=True):
        if s in (c, c + "s", c + "es") or s.endswith(" " + c) or s.endswith(" " + c + "s"):
            return c
    return s


def normalize(raw: list) -> list[dict]:
    out = []
    for k, c in enumerate(raw or []):
        if not isinstance(c, dict) or c.get("name") not in NAMES:
            continue
        name, subj, val = c["name"], c.get("subject"), c.get("value")
        try:
            if name in ("part_count", "colored_part_count", "object_count", "category_count", "group_count"):
                val = int(val)
            elif name in ("equal_area", "mirror_symmetric", "rotated_quarter_cw"):
                val = True
            elif name in ("label_text", "numeral_label", "fraction_value"):
                val = str(val).replace(" ", "")
            elif name == "all_objects_category":
                val = _cat(val)
            if name == "category_count":
                subj = _cat(subj)
            elif name == "group_count":
                subj = {"group": str(subj.get("group", "")).lower(), "category": _cat(subj.get("category"))}
            elif name == "object_present":
                subj = _cat(subj if subj is not None else val)
                val = True
            elif name in ("left_of", "above"):
                subj = [_cat(subj[0]), _cat(subj[1])]
                val = True
            elif name == "rotated_quarter_cw":
                subj = ["left arrow", "right arrow"]
        except (TypeError, ValueError, KeyError, IndexError, AttributeError):
            continue
        out.append({"id": f"x{k}", "type": TYPE[name], "name": name, "subject": subj, "op": "eq", "value": val,
                    "text": f"{name} {json.dumps(subj) if subj is not None else ''} {json.dumps(val)}".strip()})
    return out


def _frac(s: str):
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def contradictions(cons: list[dict]) -> list[str]:
    """Deterministic satisfiability check of a constraint set."""
    out = []
    by = {}
    for c in cons:
        by.setdefault(c["name"], []).append(c)
    for name, cs in by.items():          # one value per single-valued constraint
        if name in ("part_count", "colored_part_count", "object_count", "label_text", "numeral_label",
                    "fraction_value", "all_objects_category") and len({json.dumps(c["value"]) for c in cs}) > 1:
            out.append(f"{name} has conflicting values")
    n = by.get("part_count", [None])[0]
    k = by.get("colored_part_count", [None])[0]
    if n and k and not 0 <= k["value"] <= n["value"]:
        out.append("more colored parts than parts")
    f = by.get("fraction_value", [None])[0]
    if f and n and k and _frac(f["value"]) is not None and n["value"] > 0 and _frac(f["value"]) != Fraction(k["value"], n["value"]):
        out.append("fraction value differs from colored/parts")
    lab = by.get("label_text", [None])[0]
    if lab and f and _frac(lab["value"]) is not None and lab["value"] != f["value"]:
        out.append("label differs from the fraction")
    if lab and n and k and "/" in lab["value"] and lab["value"] != f"{k['value']}/{n['value']}" and not f:
        out.append("label differs from colored/parts")
    # the number of objects, however it is stated
    cnt = by.get("object_count", [None])[0]
    cc = by.get("category_count", [])
    allcat = by.get("all_objects_category", [None])[0]
    total = cnt["value"] if cnt else (cc[0]["value"] if len(cc) == 1 else None)
    num = by.get("numeral_label", [None])[0]
    if num and total is not None and num["value"] != str(total):
        out.append("numeral differs from the object count")
    if cnt and allcat and any(c["subject"] == allcat["value"] and c["value"] != cnt["value"] for c in cc):
        out.append("all objects are one category, but the counts differ")
    if allcat and any(c["subject"] != allcat["value"] and c["value"] > 0 for c in cc):
        out.append("objects of another category required although all objects must be one category")
    for rel in ("left_of", "above"):     # a relation and its reverse, or a cycle
        edges = {tuple(c["subject"]) for c in by.get(rel, [])}
        nodes = {x for e in edges for x in e}
        reach = {a: {b for x, b in edges if x == a} for a in nodes}
        for _ in nodes:
            for a in nodes:
                reach[a] |= {c for b in list(reach[a]) for c in reach.get(b, ())}
        if any(a in reach[a] for a in nodes):
            out.append(f"{rel} relations form a cycle")
    return out


def parse(objective: str, vlm, sample: str) -> dict:
    resp = vlm.ask(prompt(objective), [], sample=sample)
    js = parse_json(resp["text"]) or {}
    cons = normalize(js.get("constraints"))
    return {"constraints": cons, "contradictions": contradictions(cons), "ok": bool(cons),
            "usage": resp.get("usage", {}), "error": resp.get("error")}
