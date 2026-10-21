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
    N["max_sd_main_table"] = main_max_sd(N)
    N["max_sd_ablation_table"] = ablation_max_sd(N)

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
