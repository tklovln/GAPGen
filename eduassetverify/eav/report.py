"""Aggregate result files into the paper's tables (mean +- sd over evaluation passes).

    python -m eav.report --bench data/bench_v1 --results results/main --splits dev
    python -m eav.report ... --rescore        # re-decide eav records under a rules.Config

Re-scoring re-runs only the rule engine on stored evidence: the ablations "w/o structured
grounding" (no measurement), "w/o semantic verification", "w/o abstention", the rule-only
baseline, and threshold sweeps all reuse the same VLM readings at zero API cost.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import pathlib
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np
from PIL import Image

from . import metrics as MX
from .rules import Config, decide
from .vlm.client import cost

# Rule-engine variants decided from the same stored readings (no new API calls).
# "w/o rule engine" is the separate vlmrules run (eav.methods.vlm_rules).
CONFIGS = {
    "eav": Config(),
    "rule_only": replace(Config(), use_semantic=False, abstain=False, tau=0.0),
    "abl_no_measure": replace(Config(), use_measure=False),
    "abl_no_semantic": replace(Config(), use_semantic=False),
    "abl_no_abstain": replace(Config(), abstain=False, tau=0.0),
}


def _rescore_one(args):
    rec, row, bench, cfg = args
    png = (bench / row["image"]).read_bytes()
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    sems = rec.get("semantic") or [None] * len(rec["readings"])
    if not cfg.use_semantic:
        sems = [None] * len(rec["readings"])
    out = decide(row["constraints"], rec["readings"], sems, rgb, cfg)
    return dict(rec, **{k: out[k] for k in ("verdict", "statuses", "confidence", "report")})


def rescore(records: list[dict], man: dict, bench: pathlib.Path, cfg: Config, workers: int = 48) -> list[dict]:
    jobs = [(r, man[r["item_id"]], bench, cfg) for r in records]
    with ProcessPoolExecutor(workers) as ex:
        return list(ex.map(_rescore_one, jobs, chunksize=16))


def pass_stats(records: list[dict], man: dict, splits: list[str], fn=MX.summarize) -> dict:
    recs = [r for r in records if man[r["item_id"]]["split"] in splits]
    per = [fn(rs, man) for _, rs in sorted(MX.by_pass(recs).items())]
    if not per:
        return {}
    keys = per[0].keys()
    return {k: MX.mean_sd([p[k] for p in per]) for k in keys} | {"passes": len(per)}


def fmt(ms: tuple[float, float], pct: bool = True, digits: int = 1) -> str:
    m, s = ms
    if m is None or math.isnan(m):
        return "--"
    k = 100.0 if pct else 1.0
    return f"{m * k:.{digits}f} ± {s * k:.{digits}f}"


def load_all(results: pathlib.Path) -> dict[tuple[str, str], list[dict]]:
    out = {}
    for f in sorted(results.glob("*.jsonl")):
        method, backbone = f.stem.split("__", 1)
        out[(method, backbone)] = MX.load_results(f)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--results", default="results/main")
    ap.add_argument("--splits", default="dev")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    bench, results = pathlib.Path(args.bench), pathlib.Path(args.results)
    man = MX.load_manifest(bench)
    splits = args.splits.split(",")
    allres = load_all(results)
    table = {}
    for (method, backbone), recs in allres.items():
        recs = [r for r in recs if man[r["item_id"]]["split"] in splits]
        if not recs:
            continue
        if method == "eav" and args.rescore:
            for name, cfg in CONFIGS.items():
                table[(name, backbone)] = pass_stats(rescore(recs, man, bench, cfg), man, splits)
        else:
            table[(method, backbone)] = pass_stats(recs, man, splits)
    print(f"splits: {splits}")
    hdr = f"{'method':16s} {'backbone':34s} {'acc':>13s} {'F1':>13s} {'FAR':>13s} {'FRR':>13s} {'abst':>13s} {'pair':>13s} {'loc':>13s} {'calls':>6s} {'$/1k':>7s}"
    print(hdr)
    for (method, backbone), st in sorted(table.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if not st:
            continue
        usd = cost(backbone, {"input": st["tokens_in"][0] * 1000, "output": st["tokens_out"][0] * 1000})
        print(f"{method:16s} {backbone:34s} {fmt(st['accuracy']):>13s} {fmt(st['f1']):>13s} {fmt(st['far']):>13s} "
              f"{fmt(st['frr']):>13s} {fmt(st['abstention']):>13s} {fmt(st['pair_accuracy']):>13s} "
              f"{fmt(st['localization_accuracy']):>13s} {st['calls_per_item'][0]:6.1f} {usd:7.2f}")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({f"{m}__{b}": v for (m, b), v in table.items()}, indent=1))


if __name__ == "__main__":
    main()
