"""Scoring: every metric of the paper's Section VI-C, from result files and the manifest.

INVALID is the positive class. Precision, recall and F1 use answered items (verdict not
UNCERTAIN); FAR, FRR and abstention use all items, so abstaining never counts as
acceptance. UNPARSABLE answers are a protocol failure: reported, never scored as
accept or reject (they count as not answered).
"""
from __future__ import annotations

import json
import math
import pathlib
from collections import defaultdict

import numpy as np

# Localization is well defined only where the error has a place: a removed object leaves
# no pixels behind, and which of several identical parts is "the extra one" is arbitrary.
LOCALIZABLE = {"unequal_partition", "wrong_part_count", "wrong_label", "semantic_mismatch",
               "relation_reversal", "broken_symmetry"}


def load_manifest(bench: pathlib.Path) -> dict[str, dict]:
    return {r["item_id"]: r for r in (json.loads(x) for x in (bench / "manifest.jsonl").read_text().splitlines())}


def load_results(path: pathlib.Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def iou(a, b) -> float:
    if not a or not b:
        return 0.0
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def detection(results: list[dict], man: dict) -> dict:
    tp = fp = fn = tn = 0
    n_inv = n_val = acc_inv = rej_val = abst = unp = 0
    for r in results:
        y, v = man[r["item_id"]]["label"], r["verdict"]
        if v == "UNPARSABLE":
            unp += 1
        if v in ("UNCERTAIN", "UNPARSABLE"):
            abst += 1
        if y == "INVALID":
            n_inv += 1
            acc_inv += v == "VALID"
            tp += v == "INVALID"
            fn += v == "VALID"
        else:
            n_val += 1
            rej_val += v == "INVALID"
            fp += v == "INVALID"
            tn += v == "VALID"
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec + rec and not math.isnan(prec + rec) else float("nan")
    n = len(results)
    return {"n": n, "precision": prec, "recall": rec, "f1": f1,
            "far": acc_inv / n_inv if n_inv else float("nan"), "frr": rej_val / n_val if n_val else float("nan"),
            "abstention": abst / n if n else float("nan"), "unparsable": unp / n if n else float("nan"),
            "accuracy": (tp + tn) / n if n else float("nan")}


def aurc(results: list[dict], man: dict) -> float:
    """Area under the risk-coverage curve, ranking answers by confidence (min over constraints)."""
    pts = []
    for r in results:
        if r["verdict"] in ("UNPARSABLE",):
            continue
        conf = min(r.get("confidence", {}).values(), default=1.0) if r.get("confidence") else 1.0
        pred = r["verdict"] if r["verdict"] != "UNCERTAIN" else _forced(r)
        pts.append((conf, pred != man[r["item_id"]]["label"]))
    if not pts:
        return float("nan")
    pts.sort(key=lambda t: -t[0])
    errs = np.cumsum([e for _, e in pts])
    risks = errs / np.arange(1, len(pts) + 1)
    return float(risks.mean())


def _forced(r: dict) -> str:
    """Best guess when forced to answer: majority status direction of the weakest constraint."""
    st = r.get("statuses", {})
    return "INVALID" if "F" in st.values() else "VALID" if st and all(s == "T" for s in st.values()) else "INVALID"


def pairwise(results: list[dict], man: dict) -> dict:
    by_pair: dict[str, dict] = defaultdict(dict)
    for r in results:
        m = man[r["item_id"]]
        by_pair[m["pair_id"]][m["polarity"]] = r["verdict"]
    pairs = [v for v in by_pair.values() if "+" in v and "-" in v]
    ok = sum(v["+"] == "VALID" and v["-"] == "INVALID" for v in pairs)
    return {"pairs": len(pairs), "pair_accuracy": ok / len(pairs) if pairs else float("nan")}


def localization(results: list[dict], man: dict) -> dict:
    """Of violated, localizable items judged INVALID: reported violated constraint is a target,
    and its witness box overlaps a ground-truth region with IoU >= 0.5."""
    n = hit_c = hit_loc = 0
    for r in results:
        m = man[r["item_id"]]
        if m["label"] != "INVALID" or r["verdict"] != "INVALID" or not set(m["operators"]) & LOCALIZABLE:
            continue
        report = {d["cid"]: d for d in r.get("report", [])}
        viol = [cid for cid, s in r.get("statuses", {}).items() if s == "F"]
        if not viol:
            continue
        n += 1
        tgt = [cid for cid in viol if cid in m["targets"]]
        hit_c += bool(tgt) and set(viol) <= set(m["targets"])
        if tgt:
            box = report.get(tgt[0], {}).get("witness")
            regions = m["gt_regions"].get(tgt[0], [])
            hit_loc += any(iou(box, g) >= 0.5 for g in regions)
    return {"loc_n": n, "violation_type_accuracy": hit_c / n if n else float("nan"),
            "localization_accuracy": hit_loc / n if n else float("nan")}


def constraint_accuracy(results: list[dict], man: dict) -> float:
    ok = tot = 0
    for r in results:
        m = man[r["item_id"]]
        for cid, s in r.get("statuses", {}).items():
            if s == "U":
                continue
            tot += 1
            ok += (s == "F") == (cid in m["targets"])
    return ok / tot if tot else float("nan")


def style_invariance(results: list[dict], man: dict) -> dict:
    """Same scene, base style vs unseen style: does the verdict stay the same?"""
    by_key = {}
    for r in results:
        by_key[(man[r["item_id"]]["pair_id"], man[r["item_id"]]["polarity"])] = r["verdict"]
    same = tot = 0
    for r in results:
        m = man[r["item_id"]]
        if m["split"] != "test_unseen_style":
            continue
        src = by_key.get((m["source_pair"], m["polarity"]))
        if src is None:
            continue
        tot += 1
        same += src == r["verdict"]
    return {"invariance_n": tot, "style_invariance": same / tot if tot else float("nan")}


def summarize(results: list[dict], man: dict) -> dict:
    out = detection(results, man)
    out.update(pairwise(results, man))
    out.update(localization(results, man))
    out["constraint_accuracy"] = constraint_accuracy(results, man)
    out["aurc"] = aurc(results, man)
    out["calls_per_item"] = float(np.mean([r.get("calls", 1) for r in results])) if results else float("nan")
    out["tokens_in"] = float(np.mean([r["usage"]["input"] for r in results])) if results else float("nan")
    out["tokens_out"] = float(np.mean([r["usage"]["output"] for r in results])) if results else float("nan")
    out["latency"] = float(np.mean([r["usage"]["latency"] for r in results])) if results else float("nan")
    return out


def by_pass(results: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list] = defaultdict(list)
    for r in results:
        out[r["pass"]].append(r)
    return dict(out)


def mean_sd(values: list[float]) -> tuple[float, float]:
    v = [x for x in values if not math.isnan(x)]
    if not v:
        return float("nan"), float("nan")
    return float(np.mean(v)), float(np.std(v, ddof=1)) if len(v) > 1 else 0.0
