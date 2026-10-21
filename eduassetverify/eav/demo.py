"""Demo page of the paper (its project page) from the benchmark and the experiment records.

    python -m eav.demo --bench data/bench_v1 --out results/demo

Writes a static site: the templates in demo_site/ (index.html, style.css, app.js); data.js with
every test asset, its verdicts (three passes, both backbones), EduAssetVerify's first-pass report,
the first-pass answers of the judges, and the walkthrough of the Fig. 1 asset with the raw model
answers, all read from the experiment records and the response cache (no network; a missing entry
is an error, and so is a cached answer whose verdict differs from the recorded one); and the test
images, one script per template (thumbs/<template>.js). Summary numbers come from
results/paper/numbers.json, and the claims of the page's text are asserted against them, so the
page and the paper cannot disagree.

The page must also run as the page view of an Anonymous GitHub mirror (/w/), which serves documents
in a CSP sandbox with an opaque origin, may rewrite absolute URLs, and allows an anonymous visitor
175 requests per 15 minutes. Hence data and images come in <script> files, not through fetch; the
900 images take 15 requests, the walkthrough and pair images none (they are inside data.js);
nothing is stored; and no file of the site contains an absolute URL.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import pathlib
import re
import shutil
from collections import Counter

from PIL import Image

from . import metrics as MX
from . import paper as PP
from .evidence import parse_json
from .methods import parser as PA
from .rules import Config
from .vlm import prompts as P
from .vlm.client import make

SITE = pathlib.Path(__file__).resolve().parents[1] / "demo_site"
TEST = PP.TEST
BACKBONES = {"global.anthropic.claude-sonnet-5": ("C", "Claude Sonnet 5"), "gemini-3.5-flash": ("G", "Gemini 3.5 Flash")}
METHODS = [("direct", "d"), ("cot", "c"), ("structured", "s"), ("eav", "e")]
VERDICT = {"VALID": "V", "INVALID": "I", "UNCERTAIN": "U", "UNPARSABLE": "X"}
IMG_PX = 320
FORBIDDEN = re.compile(r"(?i)tklovln|xdblazer|yuehpo|tk wang|ting-kang|gamania|/home/|github\.(com|io)|https?://")


def _flat(o) -> bool:
    """True if a JSON value reads well on one line: scalars, or containers of scalars and of flat dicts."""
    def scalar(v):
        return not isinstance(v, (dict, list))
    if isinstance(o, dict):
        return all(scalar(v) or (isinstance(v, dict) and all(scalar(x) for x in v.values())) for v in o.values())
    if isinstance(o, list):
        return all(scalar(v) for v in o)
    return True


def _pretty(o, ind: int = 0) -> str:
    """A model answer, pretty-printed with one line per part or constraint."""
    pad = "  " * ind
    if _flat(o):
        return json.dumps(o, separators=(", ", ": "), ensure_ascii=False)
    if isinstance(o, dict):
        rows = [f"{pad}  {json.dumps(k)}: {_pretty(v, ind + 1)}" for k, v in o.items()]
        return "{\n" + ",\n".join(rows) + "\n" + pad + "}"
    rows = [pad + "  " + _pretty(v, ind + 1) for v in o]
    return "[\n" + ",\n".join(rows) + "\n" + pad + "]"


def _vlm(model):
    return make(model, temperature=0.7, thinking_budget=1024 if model.startswith("gemini") else None)


def _cached(vlm, prompt, images, sample):
    r = vlm.ask(prompt, images, sample=sample, allow_network=False)
    if r.get("error"):
        raise RuntimeError(f"not in the response cache: {vlm.model} {sample}")
    return r["text"]


def _norm(box, size=512.0):
    return None if not box else [round(max(0.0, min(1.0, v / size)), 4) for v in box]


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, (list, tuple)):
        if v and all(isinstance(x, str) for x in v):
            return ", ".join(f"{k} \u00d7{n}" if n > 1 else k for k, n in Counter(v).most_common())
        return ", ".join(_fmt(x) for x in v)
    return str(v)


def _uri(im: Image.Image) -> str:
    """A PNG data URI; re-encoding drops any metadata of the source file."""
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _thumb(bench, m) -> str:
    im = Image.open(bench / m["image"]).convert("RGB").resize((IMG_PX, IMG_PX), Image.LANCZOS)
    return _uri(im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))


def _verdict(js) -> str:
    """The verdict of a judge's answer, parsed as eav.methods.judges.run_judge does."""
    v = str(js.get("verdict", "")).strip().upper() if js else ""
    return v if v in ("VALID", "INVALID") else "UNPARSABLE"


def _check(js, by, kind, b, iid):
    rec = by[(kind, b)][iid][0]["verdict"]
    if _verdict(js) != rec:
        raise RuntimeError(f"cached {kind} answer of {b} on {iid} says {_verdict(js)}, the record says {rec}")


def index(recs):
    by = {(k, b): {} for k, _ in METHODS for b in BACKBONES}
    for (k, b), rs in recs.items():
        for r in rs:
            by[(k, b)].setdefault(r["item_id"], {})[r["pass"]] = r
    return by


def items(man, by, bench):
    """One record per test asset; verdicts as strings of three passes (V, I, U, or X = no answer).
    Returns the records and the test images by template."""
    thumbs = {}
    partner = {}
    for m in man.values():
        partner.setdefault(m["pair_id"], {})[m["polarity"]] = m["item_id"]
    judges = {b: _vlm(b) for b in BACKBONES}
    out = []
    order = sorted((m for m in man.values() if m["split"] in TEST),
                   key=lambda m: (["fraction", "counting", "spatial"].index(m["domain"]), m["template"], m["pair_id"],
                                  m["polarity"] == "-"))
    for m in order:
        iid = m["item_id"]
        png = (bench / m["image"]).read_bytes()
        thumbs.setdefault(m["template"], {})[iid] = _thumb(bench, m)
        it = {"i": iid, "dm": m["domain"], "t": m["template"],
              "tn": PP.TEMPLATE_NAMES[m["template"]], "st": m["style"], "sp": m["split"], "o": m["objective"],
              "y": "V" if m["label"] == "VALID" else "I", "op": m["operators"],
              "p": partner[m["pair_id"]]["+" if m["polarity"] == "-" else "-"],
              "c": [[c["id"], c["name"], c["text"]] for c in m["constraints"]], "tg": m["targets"],
              "g": {cid: [_norm(b) for b in boxes] for cid, boxes in m["gt_regions"].items()},
              "v": {}, "r": {}, "j": {}}
        for b, (bk, _) in BACKBONES.items():
            it["v"][bk] = {short: "".join(VERDICT[by[(k, b)][iid][p]["verdict"]] for p in range(3)) for k, short in METHODS}
            e0 = by[("eav", b)][iid][0]
            it["r"][bk] = [[d["name"], d["status"], _fmt(d["readings"][0]["value"]) if d["readings"] else "", round(d["q"], 2),
                            _norm(d["witness"]) if d["status"] == "F" else None,
                            d["readings"][0].get("source", "") if d["readings"] else ""] for d in e0["report"]]
            # first-pass answers of the judges, from the response cache
            ans = {}
            for kind, fn in (("cot", P.judge_cot), ("structured", P.judge_structured)):
                js = parse_json(_cached(judges[b], fn(m["objective"], m["constraints"]), [png], "p0")) or {}
                _check(js, by, kind, b, iid)
                if kind == "cot":
                    ans["c"] = str(js.get("reasoning", ""))[:600]
                else:
                    ans["s"] = ["T" if q.get("satisfied") is True else "F" if q.get("satisfied") is False else "?"
                                for q in (js.get("requirements") or []) if isinstance(q, dict)]
            it["j"][bk] = ans
        out.append(it)
    return out, thumbs


def walkthrough(N, man, by, bench, paper_dir):
    """The Fig. 1 asset through every module: the raw answers of the models (response cache) and
    the values of Fig. 2 (numbers.json, overview)."""
    ov, te = N["overview"], N["teaser"]
    iid = ov["item_id"]
    m = man[iid]
    b = ov["backbone"]
    png = (bench / m["image"]).read_bytes()
    claude = _vlm(b)
    parse_raw = parse_json(_cached(claude, PA.prompt(m["objective"]), [], "parse-p0"))
    frame = P.frame_for(b)
    g_prompt = P.grounding("partition", None, frame)
    g_raw = parse_json(_cached(claude, g_prompt, [png], "p0-g0"))
    judges = {}
    for bb, (bk, _) in BACKBONES.items():
        v = _vlm(bb)
        judges[bk] = {kind: parse_json(_cached(v, fn(m["objective"], m["constraints"]), [png], "p0"))
                      for kind, fn in (("direct", P.judge_direct), ("cot", P.judge_cot), ("structured", P.judge_structured))}
        for kind, js in judges[bk].items():
            _check(js, by, kind, bb, iid)
    cfg = Config()
    meas = ov["measurement"]
    return {"item": iid, "objective": m["objective"], "backbone": BACKBONES[b][1],
            "asset": _uri(Image.open(paper_dir / "teaser_asset.png").convert("RGB")),
            "regions": _uri(Image.open(paper_dir / "overview_regions.png").convert("RGB")),
            "witness": [round(v, 4) for v in te["witness_norm"]],
            "parser_answer": _pretty(parse_raw),
            "parser_same_everywhere": ov["same_constraints_every_backbone_and_pass"],
            "constraints": ov["constraints"],
            "grounding_prompt": g_prompt, "grounding_answer": _pretty(g_raw),
            "readings": int(ov["readings_agree"].split("/")[1]),
            "measurement": {"regions": meas["regions"], "colored": meas["colored"], "deviation": round(meas["deviation"], 2),
                            "largest": round(max(meas["ratios"]), 2), "smallest": round(min(meas["ratios"]), 2)},
            "rules": [[r["name"], _fmt(r["value"]), r["status"], round(r["q"], 2)] for r in ov["rules"]],
            "zones": {"equal_area": list(cfg.equal_area), "tau": cfg.tau}, "agree": ov["readings_agree"],
            "verdict": ov["verdict"], "same_verdict_gemini": ov["same_verdict_under_gemini"],
            "judges": judges, "spec_ratio": round(te["largest_part_ratio_spec"], 2)}


def _pct(ms, sd=False):
    """paper.pct for values read back from numbers.json, where (mean, sd) pairs are lists."""
    return PP.pct(tuple(ms) if isinstance(ms, list) else ms, sd=sd)


def results(N):
    """The paper's tables as rows of formatted percentages (numbers.json), backbones in the paper's
    order (PP.BACKBONES: Gemini, then Claude)."""
    order = list(PP.BACKBONES)

    def row(key):
        cells = []
        for b in order:
            s = N["main"]["clip"] if key == "clip" else N["main"][f"{key}__{b}"]
            cells.append([_pct(s[c], sd=False) for c in PP.MAIN_COLS])
        return cells
    names = {"clip": "CLIPScore (no backbone)", "direct": "Direct judge", "cot": "CoT judge", "structured": "Structured judge",
             "rule_only": "Rule-only validator", "eav": "EduAssetVerify", "extracted": "EduAssetVerify, parsed constraints"}
    detection = [[names[k], row(k)] for k, _ in PP.MAIN_ROWS]
    abl_names = [("eav", "Full EduAssetVerify"), ("vlmrules", "Without rule engine"), ("abl_no_measure", "Without measurement"),
                 ("abl_no_semantic", "Without semantic verifier"), ("abl_no_abstain", "Without abstention")]
    ablation = [[name, [[_pct(N["main"][f"{k}__{b}"][c], sd=False) for c in ("far", "frr", "abstention")] for b in order]]
                for k, name in abl_names]
    ex = N["extras"]
    den = ex["violated_evals_by_operator"]
    ops = []
    for task, rows in PP.OPERATOR_ROWS:
        for op, name in rows:
            ops.append([task, name, [[_pct(ex[f"fa_by_operator__{k}__{b}"].get(op, 0) / den[op], sd=False)
                                      for k in ("direct", "cot", "structured", "eav")] for b in order]])
    combined = sum(v for op, v in den.items() if "+" in op)
    ops.append(["Combined", "Two operators", [[_pct(sum(v for op, v in ex[f"fa_by_operator__{k}__{b}"].items() if "+" in op) / combined)
                                               for k in ("direct", "cot", "structured", "eav")] for b in order]])
    conditions = []
    for sp, name in PP.SPLIT_NAMES:
        conditions.append([name, [[_pct(N["split"][f"{k}__{b}"][sp]["pair_accuracy"], sd=False) for k in ("direct", "cot", "eav")]
                                  for b in order]])
    conditions.append(["Style invariance", [[_pct(N["invariance"][f"{k}__{b}"], sd=False) for k in ("direct", "cot", "eav")]
                                           for b in order]])
    fa = {BACKBONES[b][0]: {k: ex[f"fa_total__{k}__{b}"] for k in ("direct", "cot", "structured", "eav")} for b in BACKBONES}
    # the claims of index.html (section "About these results"), asserted on the numbers
    acc = {(k, b): N["main"][f"{k}__{b}"]["accuracy"][0] for k in ("direct", "cot", "structured", "rule_only", "eav") for b in order}
    gem, cla = order
    judges = ("direct", "cot", "structured")
    claims = {
        "under Gemini every judge is more accurate than EduAssetVerify": all(acc[(k, gem)] > acc[("eav", gem)] for k in judges),
        "under Claude EduAssetVerify is more accurate than every judge": all(acc[("eav", cla)] > acc[(k, cla)] for k in judges),
        "the rule-only validator accepts no violated asset": all(N["main"][f"rule_only__{b}"]["far"][0] == 0 for b in order),
        "the rule-only validator is more accurate than the full method": all(acc[("rule_only", b)] > acc[("eav", b)] for b in order),
    }
    wrong = [c for c, ok in claims.items() if not ok]
    if wrong:
        raise RuntimeError(f"the text of the page no longer holds: {wrong}")
    abst = {BACKBONES[b][0]: _pct(N["main"][f"eav__{b}"]["abstention"], sd=False) for b in BACKBONES}
    return {"order": [BACKBONES[b][1] for b in order], "detection": detection, "ablation": ablation, "operators": ops, "conditions": conditions,
            "fa": fa, "abstention": abst, "n_violated_evals": 3 * N["n_violated_test"], "n_test": N["n_test"],
            "max_sd": round(100 * N["max_sd_main_table"], 1), "errors": N["appendix"]["errors"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--results", default="results/main")
    ap.add_argument("--numbers", default="results/paper/numbers.json")
    ap.add_argument("--out", default="results/demo")
    args = ap.parse_args()
    bench, out = pathlib.Path(args.bench), pathlib.Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    man = MX.load_manifest(bench)
    recs = {(k, b): MX.load_results(pathlib.Path(args.results) / f"{k}__{b}.jsonl") for k, _ in METHODS for b in BACKBONES}
    by = index(recs)
    N = json.loads(pathlib.Path(args.numbers).read_text())
    recs_items, thumbs = items(man, by, bench)
    pairs = [[op, v["correct"], v["violated"]] for op, v in N["appendix"]["pairs"].items()]
    lookup = {iid: uri for imgs in thumbs.values() for iid, uri in imgs.items()}
    data = {"backbones": [[bk, name] for bk, name in BACKBONES.values()],
            "conditions": [list(x) for x in PP.SPLIT_NAMES],
            "operators": [[op, name, task] for task, rows in PP.OPERATOR_ROWS for op, name in rows],
            "pairs": pairs, "embedded": {iid: lookup[iid] for _, c, v in pairs for iid in (c, v)},
            "items": recs_items, "walkthrough": walkthrough(N, man, by, bench, pathlib.Path(args.numbers).parent),
            "results": results(N)}
    head = "/* Generated by eduassetverify/eav/demo.py from the experiment records; do not edit by hand. */\n"
    (out / "data.js").write_text(head + "window.EAV = " + json.dumps(data, separators=(",", ":")) + ";\n")
    (out / "thumbs").mkdir()
    for t, imgs in sorted(thumbs.items()):
        (out / "thumbs" / f"{t}.js").write_text(head + f"EAV_THUMBS({json.dumps(t)}," + json.dumps(imgs, separators=(",", ":")) + ");\n")
    for f in ("index.html", "style.css", "app.js"):
        shutil.copy(SITE / f, out / f)
    (out / ".nojekyll").write_text("")
    # anonymity and portability: no text file may name the author or contain an absolute URL
    bad = [(p.name, mt.group(0)) for p in out.rglob("*") if p.suffix in (".html", ".css", ".js")
           for mt in [FORBIDDEN.search(p.read_text())] if mt]
    if bad:
        raise RuntimeError(f"forbidden strings in the site: {bad}")
    files = [p for p in out.rglob("*") if p.is_file()]
    print(f"wrote {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB to {out} "
          f"(data.js {(out / 'data.js').stat().st_size / 1e6:.2f} MB; largest thumbs file "
          f"{max(p.stat().st_size for p in (out / 'thumbs').iterdir()) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
