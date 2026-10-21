"""Paper artifacts from result files: numbers.json, LaTeX tables, figures.

    python -m eav.paper --bench data/bench_v1 --out results/paper

Every number in Section VII of the paper comes from here; tables are written as LaTeX
files and copied verbatim into the paper branch (tables/), never retyped.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

from . import metrics as MX
from .report import CONFIGS, rescore
from .vlm.client import cost

TEST = ["test_indomain", "test_unseen_template", "test_error_combo", "test_unseen_style"]
BACKBONES = {"gemini-3.5-flash": "Gemini 3.5 Flash", "global.anthropic.claude-sonnet-5": "Claude Sonnet 5"}
SHORT = {"gemini-3.5-flash": "G", "global.anthropic.claude-sonnet-5": "C"}
METHODS = [("direct", "VLM direct judge"), ("cot", "VLM CoT judge"), ("structured", "VLM structured judge"),
           ("rule_only", "Rule-only validator"), ("eav", "EduAssetVerify")]
DOMAINS = ["fraction", "counting", "spatial"]
SPLIT_NAMES = [("test_indomain", "In-domain"), ("test_unseen_template", "Unseen template"),
               ("test_error_combo", "Unseen error combination"), ("test_unseen_style", "Unseen visual style")]


def pct(ms, d=1, sd=True):
    m, s = ms if isinstance(ms, tuple) else (ms, None)
    if m is None or (isinstance(m, float) and math.isnan(m)):
        return "--"
    if sd and s is not None:
        return f"{100 * m:.{d}f}$\\pm${100 * s:.{d}f}"
    return f"{100 * m:.{d}f}"


def stats(recs, man, splits, fn=MX.summarize):
    recs = [r for r in recs if man[r["item_id"]]["split"] in splits]
    per = [fn(rs, man) for _, rs in sorted(MX.by_pass(recs).items())]
    return {k: MX.mean_sd([p[k] for p in per]) for k in per[0]} if per else {}


def load(bench, res_dir, parse_dir):
    man = MX.load_manifest(bench)
    R = {}
    for b in BACKBONES:
        for m in ("direct", "cot", "structured", "vlmrules", "eav"):
            R[(m, b)] = MX.load_results(res_dir / f"{m}__{b}.jsonl")
        eav = [r for r in R[("eav", b)] if man[r["item_id"]]["split"] in TEST]
        for name, cfg in CONFIGS.items():
            R[(name, b)] = rescore(eav, man, bench, cfg)
        R[("extracted", b)] = MX.load_results(parse_dir / f"eav_extracted_test__{b}.jsonl")
    R[("clip", "-")] = MX.load_results(res_dir / "clip__ViT-B-32.jsonl")
    return man, R


def domain_rows(recs, man, dom):
    return [r for r in recs if man[r["item_id"]]["domain"] == dom]


def far_counts(recs, man):
    c = Counter()
    for r in recs:
        m = man[r["item_id"]]
        if m["split"] in TEST and m["label"] == "INVALID" and r["verdict"] == "VALID":
            c["+".join(m["operator_categories"])] += 1
    return c


def latency_cost(recs, man, backbone):
    recs = [r for r in recs if man[r["item_id"]]["split"] in TEST]
    calls = np.mean([r.get("calls", 1) for r in recs])
    tin = np.mean([r["usage"]["input"] for r in recs])
    tout = np.mean([r["usage"]["output"] for r in recs])
    lat = np.mean([r["usage"]["latency"] for r in recs])
    usd = cost(backbone, {"input": tin * 1000, "output": tout * 1000}) if backbone != "-" else 0.0
    return {"calls": float(calls), "tin": float(tin), "tout": float(tout), "latency": float(lat), "usd_1k": usd}


def grounding_cost(recs, man, bench, backbone, thinking_budget):
    """Usage of the 3 grounding calls only (what the rule-only validator needs), from the cache."""
    from .evidence import schema_for
    from .vlm import prompts as P
    from .vlm.client import make
    vlm = make(backbone, temperature=0.7, thinking_budget=thinking_budget)
    tin = tout = lat = 0.0
    n = 0
    for r in recs:
        m = man[r["item_id"]]
        if m["split"] not in TEST:
            continue
        png = (bench / m["image"]).read_bytes()
        prompt = P.grounding(schema_for(m["constraints"]), None, P.frame_for(backbone))
        for g in range(3):
            resp = vlm.ask(prompt, [png], sample=f"p{r['pass']}-g{g}", allow_network=False)
            tin += resp["usage"].get("input", 0)
            tout += resp["usage"].get("output", 0)
            lat += resp.get("latency", 0.0)
        n += 1
    return {"calls": 3.0, "tin": tin / n, "tout": tout / n, "latency": lat / n,
            "usd_1k": cost(backbone, {"input": tin / n * 1000, "output": tout / n * 1000})}


def extras(man, R):
    """Numbers quoted in the text."""
    out = {}
    nviol = Counter()
    for r in man.values():
        if r["split"] in TEST and r["label"] == "INVALID":
            nviol["+".join(r["operators"])] += 3          # three passes
    out["violated_evals_by_operator"] = dict(nviol)
    for b in BACKBONES:
        for key in ("direct", "cot", "structured", "eav", "rule_only", "vlmrules", "extracted"):
            fa = Counter()
            for r in R[(key, b)]:
                m = man[r["item_id"]]
                if m["split"] in TEST and m["label"] == "INVALID" and r["verdict"] == "VALID":
                    fa["+".join(m["operators"])] += 1
            out[f"fa_by_operator__{key}__{b}"] = dict(fa)
            out[f"fa_total__{key}__{b}"] = sum(fa.values())
        eav = [r for r in R[("eav", b)] if man[r["item_id"]]["split"] in TEST]
        unc = [r for r in eav if r["verdict"] == "UNCERTAIN"]
        out[f"uncertain__{b}"] = {"n": len(unc), "of": len(eav),
                                  "valid": sum(man[r["item_id"]]["label"] == "VALID" for r in unc),
                                  "with_unparsable_reading": sum(r["unparsable"] > 0 for r in unc),
                                  "by_template": dict(Counter(man[r["item_id"]]["template"] for r in unc).most_common(6))}
        readings = sum(len(r["readings"]) for r in eav)
        out[f"unparsable_readings__{b}"] = {"n": sum(r["unparsable"] for r in eav), "of": readings,
                                            "by_template": dict(Counter(man[r["item_id"]]["template"] for r in eav
                                                                        for _ in range(r["unparsable"])).most_common(4))}
        # localization misses: which constraint types
        miss = Counter()
        for r in eav:
            m = man[r["item_id"]]
            if m["label"] != "INVALID" or r["verdict"] != "INVALID" or not set(m["operators"]) & MX.LOCALIZABLE:
                continue
            rep = {d["cid"]: d for d in r["report"]}
            loc_t = [t for t, op in zip(m["targets"], m["operators"]) if op in MX.LOCALIZABLE and r["statuses"].get(t) == "F"]
            if loc_t and not any(MX.iou(rep[t]["witness"], g) >= 0.5 for t in loc_t for g in m["gt_regions"].get(t, [])):
                miss[_cname(m, loc_t[0])] += 1
        out[f"loc_misses__{b}"] = dict(miss)
        for key in ("eav", "direct", "cot"):
            out[f"far_by_split__{key}__{b}"] = {s: stats(R[(key, b)], man, [s])["far"][0] for s, _ in SPLIT_NAMES}
    return out


# --------------------------------------------------------------------------- tables

MAIN_ROWS = [("clip", "CLIPScore$^{\\ast}$"), ("direct", "Direct judge"), ("cot", "CoT judge"),
             ("structured", "Structured judge"), ("rule_only", "Rule-only"), ("eav", "EduAssetVerify"),
             ("extracted", "\\quad extracted $C$")]
MAIN_COLS = ["accuracy", "far", "frr", "abstention"]


def table_main(N):
    """Compact main table: mean over passes (sd reported once, in the caption)."""
    out = []
    for key, name in MAIN_ROWS:
        cells = []
        for b in BACKBONES:
            s = N["main"]["clip"] if key == "clip" else N["main"][f"{key}__{b}"]
            cells += [pct(s[c], sd=False) for c in MAIN_COLS]
        if key == "extracted":
            out.append("\\midrule")
        out.append(f"{name} & " + " & ".join(cells) + " \\\\")
    return "\n".join(out) + "\n"


def main_max_sd(N) -> float:
    vals = []
    for key, _ in MAIN_ROWS:
        for b in BACKBONES:
            s = N["main"]["clip"] if key == "clip" else N["main"][f"{key}__{b}"]
            vals += [s[c][1] for c in MAIN_COLS]
    return float(max(vals))


def table_data(man):
    names = [("dev", "Dev"), ("test_indomain", "In-dom."), ("test_unseen_template", "Templ."),
             ("test_error_combo", "Combo"), ("test_unseen_style", "Style")]
    out = []
    tot = Counter()
    for d, dname in [("fraction", "Fraction"), ("counting", "Counting"), ("spatial", "Spatial")]:
        cnt = Counter(r["split"] for r in man.values() if r["domain"] == d)
        test = sum(cnt[s] for s in TEST)
        tot.update(cnt)
        out.append(f"{dname} & " + " & ".join(str(cnt[s]) for s, _ in names) + f" & {test} \\\\")
    out.append("\\midrule")
    out.append("Total & " + " & ".join(str(tot[s]) for s, _ in names) + f" & {sum(tot[s] for s in TEST)} \\\\")
    return "\n".join(out) + "\n"


def table_domain(N):
    out = []
    for key, name in [("direct", "Direct judge"), ("cot", "CoT judge"), ("structured", "Structured judge"),
                      ("rule_only", "Rule-only"), ("eav", "EduAssetVerify")]:
        cells = []
        for d in DOMAINS:
            for b in BACKBONES:
                cells.append(pct(N["domain"][f"{key}__{b}"][d]["far"], sd=False))
        out.append(f"{name} & " + " & ".join(cells) + " \\\\")
    return "\n".join(out) + "\n"


def table_split(N):
    out = []
    for split, name in SPLIT_NAMES:
        cells = []
        for key in ("direct", "cot", "eav"):
            for b in BACKBONES:
                cells.append(pct(N["split"][f"{key}__{b}"][split]["pair_accuracy"], sd=False))
        out.append(f"{name} & " + " & ".join(cells) + " \\\\")
    out.append("\\midrule")
    cells = []
    for key in ("direct", "cot", "eav"):
        for b in BACKBONES:
            cells.append(pct(N["invariance"][f"{key}__{b}"], sd=False))
    out.append("Style invariance & " + " & ".join(cells) + " \\\\")
    return "\n".join(out) + "\n"


def table_ablation(N):
    out = []
    for key, name in [("eav", "Full EduAssetVerify"), ("vlmrules", "w/o rule engine"),
                      ("abl_no_measure", "w/o measurement"), ("abl_no_semantic", "w/o semantic verif."),
                      ("abl_no_abstain", "w/o abstention")]:
        cells = []
        for b in BACKBONES:
            s = N["main"][f"{key}__{b}"]
            cells += [pct(s["far"], sd=False), pct(s["frr"], sd=False), pct(s["abstention"], sd=False)]
        out.append(f"{name} & " + " & ".join(cells) + " \\\\")
    return "\n".join(out) + "\n"


def ablation_max_sd(N) -> float:
    vals = [N["main"][f"{k}__{b}"][c][1] for k in ("eav", "vlmrules", "abl_no_measure", "abl_no_semantic", "abl_no_abstain")
            for b in BACKBONES for c in ("far", "frr", "abstention")]
    return float(max(vals))


def table_cost(N):
    """Rows: methods; per backbone: time (s), calls, USD per 1k assets."""
    out = []
    for key, name in [("direct", "Direct judge"), ("cot", "CoT judge"), ("structured", "Structured judge"),
                      ("rule_only", "Rule-only validator"), ("eav", "EduAssetVerify")]:
        cells = []
        for b in BACKBONES:
            c = N["cost"][f"{key}__{b}"]
            cells += [f"{c['latency']:.1f}", f"{c['calls']:.1f}", f"{c['usd_1k']:.2f}"]
        out.append(f"{name} & " + " & ".join(cells) + " \\\\")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- figure

def fig_qual(N, man, R, bench, out_path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42      # embedded TrueType, not Type 3 (IEEE PDF eXpress)
    import matplotlib.pyplot as plt
    from matplotlib import patches

    def rec(method, b, iid, p=0):
        return next(r for r in R[(method, b)] if r["item_id"] == iid and r["pass"] == p)

    b = "global.anthropic.claude-sonnet-5"
    ex = N["examples"]
    fig, axes = plt.subplots(1, 5, figsize=(7.16, 2.05))
    for ax, case in zip(axes, ex):
        m = man[case["item_id"]]
        img = np.asarray(Image.open(bench / m["image"]).convert("RGB"))
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#9e9e9e")
        if case.get("witness"):
            x0, y0, x1, y1 = case["witness"]
            ax.add_patch(patches.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#d50000", linewidth=1.6))
        ax.set_title(case["title"], fontsize=7.2, pad=2.5)
        ax.text(0.5, -0.035, case["text"], transform=ax.transAxes, ha="center", va="top", fontsize=6.3, linespacing=1.2)
    fig.subplots_adjust(left=0.005, right=0.995, top=0.91, bottom=0.235, wspace=0.07)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def pick_examples(man, R):
    """Five cases from pass 0: accepted, rejected+localized, judge false accept, false reject, uncertain."""
    b = "global.anthropic.claude-sonnet-5"
    eav = {r["item_id"]: r for r in R[("eav", b)] if r["pass"] == 0}
    direct = {r["item_id"]: r for r in R[("direct", b)] if r["pass"] == 0}
    cot = {r["item_id"]: r for r in R[("cot", b)] if r["pass"] == 0}
    test = [i for i in eav if man[i]["split"] in TEST]

    def first(pred):
        for i in sorted(test):
            if pred(i):
                return i
        return None

    def wit(i):
        rep = eav[i].get("report", [])
        f = [d for d in rep if d["status"] == "F" and d.get("witness")]
        return f[0]["witness"] if f else None

    def short_obj(i):
        o = man[i]["objective"]
        return o if len(o) < 46 else o[:44].rsplit(" ", 1)[0] + "..."

    cases = []
    i = first(lambda i: man[i]["label"] == "VALID" and man[i]["template"] == "F3_circle_label"
              and eav[i]["verdict"] == "VALID" and direct[i]["verdict"] == "VALID")
    cases.append({"item_id": i, "title": "Correctly accepted", "witness": None,
                  "text": f"{brief(man[i])}\ntruth valid, ours valid\nall 4 constraints T"})
    i = first(lambda i: man[i]["label"] == "INVALID" and man[i]["operators"] == ["semantic_mismatch"]
              and eav[i]["verdict"] == "INVALID" and wit(i) is not None
              and MX.iou(wit(i), man[i]["gt_regions"]["category"][0]) >= 0.5)
    cases.append({"item_id": i, "title": "Correctly rejected", "witness": wit(i),
                  "text": f"{brief(man[i])}\ntruth: wrong object\nall_objects_category = F"})
    i = first(lambda i: man[i]["label"] == "INVALID" and man[i]["operators"] == ["unequal_partition"]
              and direct[i]["verdict"] == "VALID" and cot[i]["verdict"] == "VALID" and eav[i]["verdict"] == "INVALID")
    dev = next((d["readings"][0]["value"] for d in eav[i]["report"] if d["cid"] == "equal"), None)
    cases.append({"item_id": i, "title": "Judges accept, ours rejects", "witness": wit(i),
                  "text": f"{brief(man[i])}\ntruth: unequal parts\nequal_area = F, deviation {dev:.2f}"})
    bg = "gemini-3.5-flash"
    eg = {r["item_id"]: r for r in R[("eav", bg)] if r["pass"] == 0}
    i = next(j for j in sorted(test) if man[j]["label"] == "VALID" and eg[j]["verdict"] == "INVALID")
    f = [d for d in eg[i]["report"] if d["status"] == "F"]
    cases.append({"item_id": i, "title": "False rejection (Gemini)", "witness": f[0].get("witness") if f else None,
                  "text": f"{brief(man[i])}\ntruth valid, ours invalid\nlabel read as \"{_val(f[0])}\""})
    i = first(lambda i: man[i]["template"] == "S3_symmetry" and man[i]["style"] == "sketch" and eav[i]["verdict"] == "UNCERTAIN")
    iou = next((d["readings"][0]["value"] for d in eav[i]["report"] if d["cid"] == "sym"), None)
    cases.append({"item_id": i, "title": "Uncertain, sent to review", "witness": None,
                  "text": f"{brief(man[i])}\ntruth {man[i]['label'].lower()}, ours uncertain\nmirror IoU {iou:.2f}, between zones"})
    return cases


def brief(m) -> str:
    c = {x["name"]: x for x in m["constraints"]}
    if "part_count" in c:
        shape = "circle" if "circle" in m["objective"] else "grid" if "grid" in m["objective"] else "rectangle"
        lab = f", labeled {c['label_text']['value']}" if "label_text" in c else ""
        return f"{c['colored_part_count']['value']}/{c['part_count']['value']} of a {shape}{lab}"
    if "object_count" in c:
        return f"exactly {c['object_count']['value']} {m['objective'].split()[3].rstrip('.,;')}, nothing else"
    if "mirror_symmetric" in c:
        return "mirror-symmetric about the axis"
    return m["objective"]


def _cname(m, cid):
    return next(c["name"] for c in m["constraints"] if c["id"] == cid)


def _val(d):
    v = d["readings"][0]["value"]
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def _wrap(s, width=34):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return "\n".join(lines[:3]) + ("..." if len(lines) > 3 else "")


def fig_rc(man, R, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3.4, 1.9))
    colors = {"gemini-3.5-flash": "#1e88e5", "global.anthropic.claude-sonnet-5": "#e53935"}
    for b, name in BACKBONES.items():
        recs = [r for r in R[("eav", b)] if man[r["item_id"]]["split"] in TEST and r["pass"] == 0]
        curve = MX.risk_coverage(recs, man)
        xs, ys = [0.0], [curve[0][1]]
        for cov, risk in curve:
            xs += [cov, cov]
            ys += [ys[-1], risk]
        ax.plot(xs[1:], ys[1:], color=colors[b], linewidth=1.4, label=f"EduAssetVerify, {name}")
        for key, mk in (("direct", "o"), ("cot", "s"), ("structured", "^")):
            jr = [r for r in R[(key, b)] if man[r["item_id"]]["split"] in TEST and r["pass"] == 0]
            d = MX.detection(jr, man)
            ax.plot([1.0], [1 - d["accuracy"]], mk, color=colors[b], markersize=4, markerfacecolor="none")
    ax.plot([], [], "o", color="gray", markerfacecolor="none", markersize=4, label="judges (direct, CoT, structured)")
    ax.set_xlabel("Coverage", fontsize=8)
    ax.set_ylabel("Risk (error rate)", fontsize=8)
    ax.set_xlim(0.9, 1.005)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6, frameon=False, loc="upper left")
    fig.tight_layout(pad=0.3)
    fig.savefig(out_path)
    plt.close(fig)


PALETTE = {"purple": "#7F55B1", "lilac": "#9B7EBD", "pink": "#F49BAB", "blush": "#FFE1E0",
           "cream": "#EEECE1", "rose": "#E16981"}


def circle_crop(spec, pad: int = 10) -> tuple[int, int, int, int]:
    """Pixel window around a circle asset, shared by Figs. 1 and 2."""
    g = spec["scene"]["geom"]
    return (int(g["cx"] - g["r"] - pad), int(g["cy"] - g["r"] - pad),
            int(np.ceil(g["cx"] + g["r"] + pad)), int(np.ceil(g["cy"] + g["r"] + pad)))


def teaser(man, R, bench, out_dir) -> dict:
    """First-page example, chosen by rule: among test unequal partitions of a circle (a pie, the
    most familiar fraction model) that all three Claude judges accepted in pass 0 and
    EduAssetVerify rejected in every pass, the one with the fewest parts. Ties: fewest
    constraints (no label), then most passes in which all three judges accepted.
    Exports the cropped image and the witness box that EduAssetVerify reported."""
    from . import measure as M
    b = "global.anthropic.claude-sonnet-5"
    V = defaultdict(dict)
    for k in ("direct", "cot", "structured", "eav"):
        for r in R[(k, b)]:
            V[(r["item_id"], r["pass"])][k] = r["verdict"]
    cands = []
    for iid, m in man.items():
        if m["split"] not in TEST or m["operators"] != ["unequal_partition"]:
            continue
        spec = json.loads((bench / "specs" / f"{iid}.json").read_text())
        if spec["scene"]["shape"] != "circle":
            continue
        if not all(V[(iid, 0)].get(j) == "VALID" for j in ("direct", "cot", "structured")):
            continue
        if not all(V[(iid, p)].get("eav") == "INVALID" for p in range(3)):
            continue
        all3 = sum(all(V[(iid, p)].get(j) == "VALID" for j in ("direct", "cot", "structured")) for p in range(3))
        cands.append((len(spec["scene"]["sizes"]), len(m["constraints"]), -all3, iid, spec))
    n, _, _, iid, spec = sorted(cands, key=lambda t: t[:4])[0]
    m = man[iid]
    x0, y0, x1, y1 = circle_crop(spec)
    Image.open(bench / m["image"]).convert("RGB").crop((x0, y0, x1, y1)).save(out_dir / "teaser_asset.png")
    W, H = x1 - x0, y1 - y0
    recs = sorted((r for r in R[("eav", b)] if r["item_id"] == iid), key=lambda r: r["pass"])
    witnesses = [next(d for d in r["report"] if d["cid"] == "equal")["witness"] for r in recs]
    wx0, wy0, wx1, wy1 = witnesses[0]
    # measured area of the witness part relative to an equal share, as the verifier saw it in pass 0
    rgb = np.asarray(Image.open(bench / m["image"]).convert("RGB"))
    shape = max(recs[0]["readings"][0]["shapes"], key=lambda sh: (sh["box"][2] - sh["box"][0]) * (sh["box"][3] - sh["box"][1]))
    part = M.partition(rgb, shape["box"])
    mean = float(np.mean([q["area"] for q in part["parts"]]))
    worst = next(q for q in part["parts"] if q["bbox"] == part["worst"])
    sizes = spec["scene"]["sizes"]
    judges = {j: {bb: [r["verdict"] for r in sorted((r for r in R[(j, bb)] if r["item_id"] == iid), key=lambda r: r["pass"])]
                  for bb in BACKBONES} for j in ("direct", "cot", "structured", "eav")}
    return {"item_id": iid, "objective": m["objective"], "split": m["split"], "style": m["style"], "parts": n,
            "crop_px": [W, H], "witness_norm": [(wx0 - x0) / W, (wy0 - y0) / H, (wx1 - x0) / W, (wy1 - y0) / H],
            "witness_same_every_pass": all(w == witnesses[0] for w in witnesses),
            "witness_area_ratio_measured": worst["area"] / mean,
            "part_sizes_spec": sizes, "largest_part_ratio_spec": max(sizes) * n, "smallest_part_ratio_spec": min(sizes) * n,
            "verdicts": judges}


def _tex(s) -> str:
    return (str(s).replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("%", "\\%")
            .replace("&", "\\&").replace("#", "\\#").replace("$", "\\$"))


def overview(man, R, bench, parse_dir, out_dir, iid: str) -> dict:
    """Fig. 2: what every module produced on the Fig. 1 asset (Claude Sonnet 5, pass 0).

    Parser answers are read from the response cache (no network; a missing entry is an
    error), grounding readings from the main-run record, and the rule pass is recomputed on
    the extracted constraints; it must reproduce the logged verdicts of the extracted and the
    gold regime. Writes the measured regions as a PNG and every value the figure prints as
    LaTeX macros (overview_values.tex), so the TikZ figure types no number by hand."""
    from . import measure as M
    from .evidence import SEMANTIC_CATEGORY, SEMANTIC_TEXT, parse_json
    from .methods import parser as PA
    from .rules import Config, decide
    from .vlm.client import make
    b = "global.anthropic.claude-sonnet-5"
    m = man[iid]
    spec = json.loads((bench / "specs" / f"{iid}.json").read_text())

    def parsed(model, p):
        vlm = make(model, temperature=0.7, thinking_budget=1024 if model.startswith("gemini") else None)
        r = vlm.ask(PA.prompt(m["objective"]), [], sample=f"parse-p{p}", allow_network=False)
        if r.get("error"):
            raise RuntimeError(f"parser answer for {iid} ({model}, pass {p}) is not in the response cache")
        return PA.normalize((parse_json(r["text"]) or {}).get("constraints"))

    def keyset(cs):
        return sorted(json.dumps([c["name"], c.get("subject"), c["value"]]) for c in cs)

    cons = parsed(b, 0)
    same_parse = all(keyset(parsed(bb, p)) == keyset(cons) for bb in BACKBONES for p in range(3))
    conflicts = PA.contradictions(cons)
    if conflicts:
        raise RuntimeError(f"overview item {iid}: parsed constraints are inconsistent: {conflicts}")
    val = {c["name"]: c["value"] for c in cons}
    n, k, frac = val["part_count"], val["colored_part_count"], val["fraction_value"]

    rec = next(r for r in R[("eav", b)] if r["item_id"] == iid and r["pass"] == 0)
    rgb = np.asarray(Image.open(bench / m["image"]).convert("RGB"))
    read0 = rec["readings"][0]
    shape = max(read0["shapes"], key=lambda sh: (sh["box"][2] - sh["box"][0]) * (sh["box"][3] - sh["box"][1]))
    sem_names = {c["name"] for c in cons} & (SEMANTIC_TEXT | SEMANTIC_CATEGORY)
    if sem_names or any(x is not None for x in rec["semantic"]):
        raise RuntimeError("overview item triggers the semantic verifier; the figure draws it as not triggered")

    res = decide(cons, rec["readings"], rec["semantic"], rgb, Config())
    ext = next(json.loads(line) for line in open(parse_dir / f"eav_extracted_test__{b}.jsonl")
               if json.loads(line)["item_id"] == iid and json.loads(line)["pass"] == 0)
    if not (res["verdict"] == ext["verdict"] == rec["verdict"] and res["confidence"] == ext["confidence"]):
        raise RuntimeError("recomputed rule pass does not reproduce the logged verdicts")
    gem = {r["item_id"]: r["verdict"] for r in R[("eav", "gemini-3.5-flash")] if r["pass"] == 0}
    gem_ext = next(json.loads(line)["verdict"] for line in open(parse_dir / "eav_extracted_test__gemini-3.5-flash.jsonl")
                   if json.loads(line)["item_id"] == iid and json.loads(line)["pass"] == 0)
    same_verdict = gem[iid] == gem_ext == res["verdict"]

    # measured regions, drawn in the same pixel window as Fig. 1
    part = M.partition(rgb, shape["box"], masks=True)
    x0, y0, x1, y1 = circle_crop(spec)
    W, H = x1 - x0, y1 - y0
    areas = np.array([q["area"] for q in part["parts"]], float)
    ratios = areas / areas.mean()
    big, small = int(np.argmax(ratios)), int(np.argmin(ratios))
    eps_t, eps_f = Config().equal_area
    canvas = np.full((H, W, 4), 0, np.uint8)
    ox, oy = part["origin"]
    def tint(hex_color, pct):          # xcolor's  name!pct  (mixed with white), so the TikZ swatches match
        rgb = np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], float)
        return tuple(int(round(v)) for v in pct / 100 * rgb + (1 - pct / 100) * 255)
    red = "#D50000"                    # eavRed in main.tex, the witness color of Figs. 1 and 3
    for i, q in enumerate(part["parts"]):
        if i == big:
            color = tint(red, 30)        # oversized part (the witness)
        elif i == small:
            color = tint(red, 15)        # undersized part
        elif q["colored"]:
            color = tint(PALETTE["lilac"], 100)
        else:
            color = tint(PALETTE["lilac"], 25)
        ys, xs = np.nonzero(q["mask"])
        ys, xs = ys + oy - y0, xs + ox - x0
        keep = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
        canvas[ys[keep], xs[keep]] = (*color, 255)
    Image.fromarray(canvas, "RGBA").save(out_dir / "overview_regions.png")

    report = {d["name"]: d for d in res["report"]}
    agree = min(sum(r["status"] == d["status"] for r in d["readings"]) for d in res["report"])
    q_min = min(d["q"] for d in res["report"])
    fails = [d for d in res["report"] if d["status"] == "F"]
    wx0, wy0, wx1, wy1 = fails[0]["witness"]

    def shown(d):
        v = d["readings"][0]["value"]
        return f"d = {v:.2f}" if isinstance(v, float) else str(v)

    parse_lines = [_tex(c["name"]) + ("" if c["value"] is True else f" = {_tex(c['value'])}") for c in cons]
    rows = [f"\\ovRow{{{i + 1}}}{{{_tex(d['name'])}}}{{{_tex(shown(d))}}}{{{d['status']}}}" for i, d in enumerate(res["report"])]
    texts = ", ".join(t["text"] for t in read0["texts"]) or "none"
    mac = {
        "ovObjective": _tex(m["objective"]),
        "ovParse": "\\\\".join(parse_lines),
        "ovConsColored": str(k), "ovConsParts": str(n), "ovConsFraction": _tex(frac), "ovConsRatio": f"{k}/{n}",
        "ovShape": _tex(shape["shape"]), "ovBox": "[" + ",".join(str(round(v)) for v in shape["box"]) + "]",
        "ovGParts": str(len(shape["parts"])), "ovGColored": str(sum(p["colored"] for p in shape["parts"])),
        "ovGTexts": _tex(texts), "ovReadings": str(len(rec["readings"])),
        "ovRegions": str(part["n"]), "ovMColored": str(part["colored"]), "ovDev": f"{part['deviation']:.2f}",
        "ovBig": f"{ratios[big]:.2f}", "ovSmall": f"{ratios[small]:.2f}",
        "ovRuleRows": "".join(rows),
        "ovEpsT": f"{eps_t:.2f}", "ovEpsF": f"{eps_f:.2f}", "ovTau": f"{Config().tau:g}",
        "ovAgree": f"{agree} of {len(rec['readings'])}", "ovQ": f"{q_min:.1f}",
        "ovMin": ", ".join(d["status"] for d in res["report"]),
        "ovMinResult": min((d["status"] for d in res["report"]), key={"F": 0, "U": 1, "T": 2}.get),
        "ovVerdict": res["verdict"], "ovFailed": _tex(fails[0]["name"]),
        # witness box in the Fig. 1 crop, normalized, y up (lower-left a, upper-right b)
        "ovWitnessXa": f"{(wx0 - x0) / W:.3f}", "ovWitnessYa": f"{1 - (wy1 - y0) / H:.3f}",
        "ovWitnessXb": f"{(wx1 - x0) / W:.3f}", "ovWitnessYb": f"{1 - (wy0 - y0) / H:.3f}",
    }
    pills = {v: ("pillon" if v == res["verdict"] else "pilloff") for v in ("VALID", "INVALID", "UNCERTAIN")}
    lines = ["% Generated by eduassetverify/eav/paper.py (overview) from the experiment records and the",
             f"% response cache: item {iid}, Claude Sonnet 5, pass 0; do not edit by hand."]
    lines += [f"\\newcommand{{\\{name}}}{{{v}}}" for name, v in mac.items()]
    lines.append("\\tikzset{" + ", ".join(f"pill{v}/.style={{{st}}}" for v, st in pills.items()) + "}")
    (out_dir / "overview_values.tex").write_text("\n".join(lines) + "\n")
    return {"item_id": iid, "backbone": b, "pass": 0, "constraints": [[c["name"], c["value"]] for c in cons],
            "consistency_conflicts": conflicts, "same_constraints_every_backbone_and_pass": same_parse,
            "grounding_reading0": {"shape": shape["shape"], "box": [round(v) for v in shape["box"]],
                                   "parts": len(shape["parts"]), "colored": sum(p["colored"] for p in shape["parts"]),
                                   "texts": [t["text"] for t in read0["texts"]]},
            "semantic_triggered": False,
            "measurement": {"regions": part["n"], "colored": part["colored"], "deviation": part["deviation"],
                            "ratios": [float(x) for x in ratios], "worst": part["worst"]},
            "rules": [{"name": d["name"], "value": d["readings"][0]["value"], "status": d["status"], "q": d["q"]}
                      for d in res["report"]],
            "readings_agree": f"{agree}/{len(rec['readings'])}", "verdict": res["verdict"],
            "witness": fails[0]["witness"], "same_verdict_under_gemini": same_verdict}


def fig_domain(N, out_path, backbone: str = "global.anthropic.claude-sonnet-5"):
    """Grouped bars: false acceptance by domain under one backbone (replaces the domain table).
    Only Claude is drawn: under Gemini every judge stays below 2% in every domain, which a panel
    on the same axis cannot show and the caption states in numbers (gemini_judge_max below).
    Judges in the pink family, EduAssetVerify in purple (its value is 0 in every cell)."""
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    import matplotlib.pyplot as plt
    judges = [("direct", "Direct judge", PALETTE["blush"]), ("cot", "CoT judge", PALETTE["pink"]),
              ("structured", "Structured judge", PALETTE["rose"])]
    doms = [("fraction", "Fraction"), ("counting", "Counting"), ("spatial", "Spatial")]
    fig, ax = plt.subplots(figsize=(3.45, 1.2))
    w = 0.2
    for i, (d, _) in enumerate(doms):
        for j, (key, label, color) in enumerate(judges):
            v = 100 * N["domain"][f"{key}__{backbone}"][d]["far"][0]
            x = i + (j - 1.5) * w
            ax.bar(x, v, w * 0.9, color=color, edgecolor=PALETTE["rose"], linewidth=0.5,
                   label=label if i == 0 else None, zorder=2)
            if v >= 2.0:                                  # label only the bars that matter
                ax.text(x, v + 0.2, f"{v:.1f}", ha="center", va="bottom", fontsize=5.8, color="#555555")
        x = i + 1.5 * w
        v = 100 * N["domain"][f"eav__{backbone}"][d]["far"][0]
        ax.scatter([x], [v], s=14, color=PALETTE["purple"], marker="D", zorder=3, clip_on=False,
                   label="EduAssetVerify" if i == 0 else None)
        ax.text(x, v + 0.4, f"{v:.0f}", ha="center", va="bottom", fontsize=6, color=PALETTE["purple"],
                fontweight="bold")
    ax.set_xticks(range(len(doms)))
    ax.set_xticklabels([n for _, n in doms], fontsize=7)
    ax.tick_params(axis="y", labelsize=6.5, length=2)
    ax.tick_params(axis="x", length=0, pad=2)
    ax.grid(axis="y", color="#e9e9e9", linewidth=0.5, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_ylim(0, 12)
    ax.set_yticks([0, 4, 8, 12])
    ax.set_xlim(-0.55, 2.55)
    ax.set_ylabel("False acceptance (%)", fontsize=6.5)
    # the legend sits above the counting and spatial groups, which stay below 3%
    h, l = ax.get_legend_handles_labels()
    order = [l.index(x) for x in ("Direct judge", "CoT judge", "Structured judge", "EduAssetVerify")]
    ax.legend([h[k] for k in order], [l[k] for k in order], loc="upper right", fontsize=6.2, ncol=2,
              frameon=True, fancybox=False, edgecolor="none", facecolor="white", framealpha=1.0,
              handlelength=1.1, columnspacing=1.0, borderaxespad=0.1, labelspacing=0.3)
    fig.subplots_adjust(left=0.11, right=0.995, top=0.965, bottom=0.15)
    fig.savefig(out_path)
    plt.close(fig)
    other = [b for b in BACKBONES if b != backbone]
    return {"backbone": backbone,
            "other_backbones_judge_max": {b: max(N["domain"][f"{k}__{b}"][d]["far"][0] for k, _, _ in judges
                                                 for d, _ in doms) for b in other},
            "other_backbones_judge_counting_max": {b: max(N["domain"][f"{k}__{b}"]["counting"]["far"][0]
                                                          for k, _, _ in judges) for b in other},
            "eav_rule_only_max_all": max(N["domain"][f"{k}__{b}"][d]["far"][0] for k in ("eav", "rule_only")
                                         for b in BACKBONES for d, _ in doms)}


# --------------------------------------------------------------------------- appendix

SEEN_STYLES = ("flat_blue", "flat_green", "flat_orange")
UNSEEN_STYLES = [("dark", "dark"), ("paper", "paper"), ("pastel_thick", "pastel, thick"), ("sketch", "sketch")]
OPERATOR_ROWS = [             # wrong_label edits a fraction label or a counting numeral: both tasks
    ("Fraction", [("wrong_part_count", "Wrong part count"), ("wrong_colored_count", "Wrong colored count"),
                  ("unequal_partition", "Unequal partition")]),
    ("Fraction, counting", [("wrong_label", "Wrong label")]),
    ("Counting", [("extra_object", "Extra object"), ("missing_object", "Missing object"),
                  ("semantic_mismatch", "Semantic mismatch")]),
    ("Spatial", [("relation_reversal", "Relation reversal"), ("broken_symmetry", "Broken symmetry")]),
]
TEMPLATE_NAMES = {"F1_circle": "circle", "F2_strips": "strips", "F3_circle_label": "circle, label",
                  "F4_grid": "grid", "F5_strips_label": "strips, label", "C1_grid": "grid",
                  "C2_scatter": "scatter", "C3_grid_numeral": "grid, numeral", "C4_distractors": "distractors",
                  "C5_two_groups": "two groups", "S1_left_right": "left-right", "S2_above_below": "above-below",
                  "S3_symmetry": "symmetry", "S4_three_row": "three in a row", "S5_rotation": "quarter turn"}
MEASURED_OPERATORS = {"wrong_part_count", "wrong_colored_count", "unequal_partition", "broken_symmetry"}


def _thumb(bench, m, px=300, box=None):
    im = Image.open(bench / m["image"]).convert("RGB")
    return np.asarray((im.crop(box) if box else im).resize((px, px), Image.LANCZOS))


def _content_box(bench, ms, pad=0.1):
    """One square window around the drawn content of several images (a counterfactual pair keeps
    the same framing, so the two images stay comparable)."""
    from . import measure as M
    boxes = []
    for m in ms:
        rgb = np.asarray(Image.open(bench / m["image"]).convert("RGB"))
        ys, xs = np.nonzero(M.foreground(rgb))
        if len(xs):
            boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    H, W = rgb.shape[:2]
    if not boxes:
        return (0, 0, W, H)
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    half = min(max(x1 - x0, y1 - y0) / 2 * (1 + pad) + 6, W / 2, H / 2)
    cx = min(max((x0 + x1) / 2, half), W - half)
    cy = min(max((y0 + y1) / 2, half), H - half)
    return (int(cx - half), int(cy - half), int(cx + half), int(cy + half))


def _figure(w_in, h_in):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["pdf.fonttype"] = 42
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(w_in, h_in))

    def at(x, y, w, h):                     # an image axis placed in inches from the lower left
        ax = fig.add_axes([x / w_in, y / h_in, w / w_in, h / h_in])
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c8")
            sp.set_linewidth(0.5)
        return ax
    return plt, fig, at


def fig_pairs(man, bench, out_path) -> dict:
    """Appendix: one counterfactual pair per operator, chosen by rule: single-operator pairs of the
    in-domain test split in a base style; fewest constraints, then smallest item id."""
    import textwrap
    pairs = defaultdict(dict)
    for m in man.values():
        pairs[m["pair_id"]][m["polarity"]] = m
    cols, picked = [], {}
    for task, ops in OPERATOR_ROWS:
        for op, name in ops:
            cands = [p for p in pairs.values() if p["-"]["operators"] == [op] and p["-"]["split"] == "test_indomain"
                     and p["-"]["style"] in SEEN_STYLES]
            p = min(cands, key=lambda p: (len(p["-"]["constraints"]), p["-"]["item_id"]))
            cols.append((task, name, p))
            picked[op] = {"correct": p["+"]["item_id"], "violated": p["-"]["item_id"], "targets": p["-"]["targets"]}
    W, H = 7.16, 1.9
    plt, fig, at = _figure(W, H)
    x0, side, pitch, y_lab = 0.46, 0.62, 0.74, 0.3
    ys = (y_lab + side + 0.05, y_lab)
    for i, (task, name, p) in enumerate(cols):
        x = x0 + i * pitch
        box = _content_box(bench, [p["+"], p["-"]])
        for y, pol in zip(ys, "+-"):
            at(x, y, side, side).imshow(_thumb(bench, p[pol], box=box))
        fig.text((x + side / 2) / W, (y_lab - 0.05) / H, textwrap.fill(name, 13), ha="center", va="top", fontsize=6.5)
    for label, y in zip(("Correct", "Violated"), ys):
        fig.text((x0 - 0.14) / W, (y + side / 2) / H, label, rotation=90, ha="center", va="center", fontsize=6.5)
    start = 0
    for task, ops in OPERATOR_ROWS:
        a, b = x0 + start * pitch, x0 + (start + len(ops) - 1) * pitch + side
        top = ys[0] + side + 0.06
        fig.add_artist(plt.Line2D([a / W, b / W], [top / H, top / H], color="#9e9e9e", linewidth=0.6))
        fig.text((a + b) / 2 / W, (top + 0.03) / H, task.replace(", ", ",\n"), ha="center", va="bottom", fontsize=7,
                 fontweight="bold", linespacing=1.05)
        start += len(ops)
    fig.savefig(out_path)
    plt.close(fig)
    return picked


def fig_bench(man, bench, out_path) -> dict:
    """Appendix: (a) the fifteen templates, one correct test asset each in a base style (smallest item
    id); (b) one scene in its base style and re-rendered in each unseen style (template F1_circle,
    smallest item id per style)."""
    heldout = {t for t in TEMPLATE_NAMES if all(m["split"] == "test_unseen_template" for m in man.values()
                                                if m["template"] == t)}
    by_key = {(m["pair_id"], m["polarity"]): m for m in man.values()}
    W, H = 7.16, 1.86
    plt, fig, at = _figure(W, H)
    side, pitch, row = 0.42, 0.56, 0.55
    x0, y_top = 0.4, H - 0.2
    picked = {"templates": {}, "styles": {}}
    for r, (task, letter) in enumerate((("Fraction", "F"), ("Counting", "C"), ("Spatial", "S"))):
        y = y_top - side - r * row
        fig.text((x0 - 0.13) / W, (y + side / 2) / H, task, rotation=90, ha="center", va="center", fontsize=6.5)
        for c in range(5):
            t = next(t for t in TEMPLATE_NAMES if t.startswith(f"{letter}{c + 1}_"))
            m = min((m for m in man.values() if m["template"] == t and m["polarity"] == "+" and m["split"] in TEST
                     and m["style"] in SEEN_STYLES), key=lambda m: m["item_id"])
            picked["templates"][t] = m["item_id"]
            x = x0 + c * pitch + (0.12 if c >= 3 else 0.0)
            ax = at(x, y, side, side)
            ax.imshow(_thumb(bench, m))
            if t in heldout:
                for sp in ax.spines.values():
                    sp.set_edgecolor(PALETTE["purple"])
                    sp.set_linestyle((0, (2, 1.2)))
                    sp.set_linewidth(0.9)
            fig.text((x + side / 2) / W, (y - 0.02) / H, TEMPLATE_NAMES[t], ha="center", va="top", fontsize=5.8)
    fig.text((x0 + 1.5 * pitch - 0.05) / W, (y_top + 0.06) / H, "Development and test", ha="center", va="bottom",
             fontsize=6.5, fontweight="bold")
    fig.text((x0 + 3.5 * pitch + 0.12 + side / 2 - 0.05) / W, (y_top + 0.06) / H, "Held out (test only)",
             ha="center", va="bottom", fontsize=6.5, fontweight="bold", color=PALETTE["purple"])
    # (b) unseen styles: the same scene in its base style (top) and in the unseen style (bottom)
    xb, side_b, pitch_b = 4.25, 0.66, 0.73
    ys = (y_top - side_b, y_top - 2 * side_b - 0.06)
    for c, (style, label) in enumerate(UNSEEN_STYLES):
        m = min((m for m in man.values() if m["split"] == "test_unseen_style" and m["polarity"] == "+"
                 and m["template"] == "F1_circle" and m["style"] == style), key=lambda m: m["item_id"])
        base = by_key[(m["source_pair"], "+")]
        picked["styles"][style] = {"unseen": m["item_id"], "base": base["item_id"]}
        x = xb + c * pitch_b
        at(x, ys[0], side_b, side_b).imshow(_thumb(bench, base))
        at(x, ys[1], side_b, side_b).imshow(_thumb(bench, m))
        fig.text((x + side_b / 2) / W, (ys[1] - 0.02) / H, label, ha="center", va="top", fontsize=6.5)
    for label, y in zip(("Base style", "Unseen style"), ys):
        fig.text((xb - 0.12) / W, (y + side_b / 2) / H, label, rotation=90, ha="center", va="center", fontsize=6.5)
    fig.savefig(out_path)
    plt.close(fig)
    picked["heldout"] = sorted(heldout)
    return picked


def fig_errors(N, out_path, backbone: str = "global.anthropic.claude-sonnet-5") -> dict:
    """Appendix: false acceptance of the three judges by operator (test set, three passes), and the
    counts the appendix text quotes (all judges, both backbones)."""
    ex = N["extras"]
    den = ex["violated_evals_by_operator"]
    judges = [("direct", "Direct judge", PALETTE["blush"]), ("cot", "CoT judge", PALETTE["pink"]),
              ("structured", "Structured judge", PALETTE["rose"])]
    rows = [(task, op, name) for task, ops in OPERATOR_ROWS for op, name in ops] + [("Combined", "+", "Two operators")]

    def far(key, b, op):
        fa = ex[f"fa_by_operator__{key}__{b}"]
        if op == "+":
            return sum(v for k, v in fa.items() if "+" in k) / sum(v for k, v in den.items() if "+" in k)
        return fa.get(op, 0) / den[op]
    vals = {key: [100 * far(key, backbone, op) for _, op, _ in rows] for key, _, _ in judges}
    plt, fig, _ = _figure(3.45, 2.0)
    ax = fig.add_axes([0.315, 0.16, 0.665, 0.73])
    hgt = 0.26
    for j, (key, label, color) in enumerate(judges):
        for i, v in enumerate(vals[key]):
            y = i + (j - 1) * hgt
            ax.barh(y, v, hgt * 0.92, color=color, edgecolor=PALETTE["rose"], linewidth=0.5,
                    label=label if i == 0 else None, zorder=2)
    for i in range(len(rows)):                 # one label per row: the range over the three judges
        lo, hi = min(vals[k][i] for k, _, _ in judges), max(vals[k][i] for k, _, _ in judges)
        if hi >= 5:
            ax.text(hi + 0.5, i, f"{lo:.1f}\u2013{hi:.1f}", va="center", ha="left", fontsize=5.8, color="#555555")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([name for _, _, name in rows], fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 37)
    ax.set_xticks([0, 10, 20, 30])
    ax.tick_params(axis="x", labelsize=6.5, length=2)
    ax.tick_params(axis="y", length=0, pad=3)
    ax.set_xlabel(f"False acceptance under {BACKBONES[backbone]} (%)", fontsize=6.5, labelpad=2)
    ax.grid(axis="x", color="#e9e9e9", linewidth=0.5, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    edge = 0
    for task, ops in OPERATOR_ROWS + [("Combined", [None])]:
        if edge:
            ax.axhline(edge - 0.5, color="#bdbdbd", linewidth=0.5, zorder=1)
        ax.text(36.8, edge - 0.42, task, ha="right", va="top", fontsize=5.8, color="#8a8a8a", style="italic")
        edge += len(ops)
    ax.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=3, fontsize=6, frameon=False,
              handlelength=1.1, columnspacing=1.0, borderaxespad=0.3)
    fig.savefig(out_path)
    plt.close(fig)
    total = measured = 0
    other = Counter()
    per_backbone = {}
    for b in BACKBONES:
        cnt = Counter()
        for key, _, _ in judges:
            for k, v in ex[f"fa_by_operator__{key}__{b}"].items():
                total += v
                cnt[k] += v
                if set(k.split("+")) <= MEASURED_OPERATORS:
                    measured += v
                else:
                    other[k] += v
        per_backbone[b] = dict(cnt)
    combined = {b: sum(v for k, v in per_backbone[b].items() if "+" in k) for b in BACKBONES}
    return {"backbone": backbone, "far_percent": {key: dict(zip([op for _, op, _ in rows], v)) for key, v in vals.items()},
            "fa_judges_both_backbones": total, "fa_measured_operators_only": measured, "fa_other": dict(other),
            "fa_judges_by_operator": per_backbone, "fa_judges_combined": combined,
            "fa_eav_both_backbones": sum(ex[f"fa_total__eav__{b}"] for b in BACKBONES)}


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--results", default="results/main")
    ap.add_argument("--parse", default="results/parse")
    ap.add_argument("--out", default="results/paper")
    args = ap.parse_args()
    bench, out = pathlib.Path(args.bench), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    man, R = load(bench, pathlib.Path(args.results), pathlib.Path(args.parse))

    N = {"main": {}, "domain": {}, "split": {}, "invariance": {}, "cost": {}, "far_counts": {}, "constraint_acc": {}}
    N["main"]["clip"] = stats(R[("clip", "-")], man, TEST)
    N["cost"]["clip"] = latency_cost(R[("clip", "-")], man, "-")
    for b in BACKBONES:
        for key in ("direct", "cot", "structured", "vlmrules", "extracted", *CONFIGS):
            recs = R[(key, b)]
            N["main"][f"{key}__{b}"] = stats(recs, man, TEST)
            N["domain"][f"{key}__{b}"] = {d: stats(domain_rows(recs, man, d), man, TEST) for d in DOMAINS}
            N["split"][f"{key}__{b}"] = {s: stats(recs, man, [s]) for s, _ in SPLIT_NAMES}
            inv = [MX.style_invariance(rs, man)["style_invariance"]
                   for _, rs in sorted(MX.by_pass([r for r in recs if man[r["item_id"]]["split"] in TEST]).items())]
            N["invariance"][f"{key}__{b}"] = MX.mean_sd(inv)
            N["far_counts"][f"{key}__{b}"] = dict(far_counts(recs, man))
        for key in ("direct", "cot", "structured", "vlmrules", "eav"):
            N["cost"][f"{key}__{b}"] = latency_cost(R[(key, b)], man, b)
        N["cost"][f"rule_only__{b}"] = grounding_cost(R[("eav", b)], man, bench, b,
                                                      1024 if b.startswith("gemini") else None)
        for key in ("structured", "eav"):
            recs = [r for r in R[(key, b)] if man[r["item_id"]]["split"] in TEST]
            N["constraint_acc"][f"{key}__{b}"] = MX.mean_sd([MX.constraint_accuracy(rs, man) for _, rs in sorted(MX.by_pass(recs).items())])
    N["n_violated_test"] = sum(1 for r in man.values() if r["split"] in TEST and r["label"] == "INVALID")
    N["n_test"] = sum(1 for r in man.values() if r["split"] in TEST)
    N["parse"] = {b: json.loads((pathlib.Path(args.parse) / f"summary_test__{b}.json").read_text()) for b in BACKBONES}
    N["battery"] = {b: json.loads((pathlib.Path("results/battery") / f"{b}.json").read_text()) for b in BACKBONES}
    N["examples"] = pick_examples(man, R)
    N["extras"] = extras(man, R)
    N["teaser"] = teaser(man, R, bench, out)
    N["overview"] = overview(man, R, bench, pathlib.Path(args.parse), out, N["teaser"]["item_id"])
    N["max_sd_main_table"] = main_max_sd(N)
    N["max_sd_ablation_table"] = ablation_max_sd(N)
    N["fig_domain"] = fig_domain(N, out / "fig_domain_far.pdf")
    N["appendix"] = {"pairs": fig_pairs(man, bench, out / "fig_pairs.pdf"),
                     "bench": fig_bench(man, bench, out / "fig_bench.pdf"),
                     "errors": fig_errors(N, out / "fig_errors.pdf")}

    (out / "numbers.json").write_text(json.dumps(N, indent=1, default=float))
    (out / "tab_main.tex").write_text(table_main(N))
    (out / "tab_domain.tex").write_text(table_domain(N))
    (out / "tab_data.tex").write_text(table_data(man))
    (out / "tab_split.tex").write_text(table_split(N))
    (out / "tab_ablation.tex").write_text(table_ablation(N))
    (out / "tab_cost.tex").write_text(table_cost(N))
    fig_qual(N, man, R, bench, out / "fig_examples.pdf")
    fig_rc(man, R, out / "fig_risk_coverage.pdf")
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
