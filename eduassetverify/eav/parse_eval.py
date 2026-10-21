"""Extracted-constraint regime and consistency check (paper Section IV-B).

    python -m eav.parse_eval --bench data/bench_v1 --backbone gemini-3.5-flash --thinking-budget 1024

1. Extraction: every distinct objective of dev+test is parsed in 3 passes and compared with
   its gold constraint set (fraction_value, a derived constraint, is not compared).
2. Full pipeline: every test image is verified with the constraints extracted in the same
   pass; grounding prompts depend only on the constraint vocabulary, so readings are reused
   from the gold-regime run through the response cache. An extracted set that fails to
   parse or is inconsistent yields UNCERTAIN (sent to review).
3. Consistency: contradictory variants of test objectives (one stated number or relation
   changed) must be rejected; their unchanged originals must not.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from . import metrics as MX
from .methods.eav import run_eav
from .methods.parser import parse
from .run import GuardedVLM, forbidden_strings
from .vlm.client import make

NO_SUBJECT = {"part_count", "equal_area", "colored_part_count", "label_text", "object_count", "all_objects_category",
              "numeral_label", "mirror_symmetric", "rotated_quarter_cw"}
TEST = ["test_indomain", "test_unseen_template", "test_error_combo", "test_unseen_style"]


def key(c: dict) -> str:
    subj = None if c["name"] in NO_SUBJECT else c["subject"]
    return json.dumps([c["name"], subj, c["value"]], sort_keys=True)


def contradict(obj: str, rng) -> str | None:
    """One stated number or relation changed so that the requirements conflict."""
    m = re.match(r"Show the fraction (\d+)/(\d+): (.*) divided into (\d+) equal (parts|cells) with (\d+)", obj)
    if m:
        n = int(m.group(4))
        n2 = n + 1 if rng.random() < 0.5 or n <= int(m.group(6)) + 1 else n - 1
        return obj.replace(f"divided into {n} equal", f"divided into {n2} equal", 1)
    m = re.match(r"Show exactly (\d+) (\w+) and write the number (\d+) below them\.", obj)
    if m:
        return obj.replace(f"write the number {m.group(3)}", f"write the number {int(m.group(3)) + 1}")
    m = re.match(r"Show exactly (\d+) (\w+) and nothing else\.", obj)
    if m:
        return obj.replace(" and nothing else.", f" and nothing else; there are exactly {int(m.group(1)) + 2} objects in total.")
    m = re.match(r"The (\w+) is (to the left of|above) the (\w+)\.", obj)
    if m:
        return obj + f" The {m.group(3)} is {m.group(2)} the {m.group(1)}."
    m = re.match(r"From left to right, the picture shows an? (\w+), an? (\w+), and an? (\w+)\.", obj)
    if m:
        return obj + f" The {m.group(3)} is to the left of the {m.group(1)}."
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--backbone", required=True)
    ap.add_argument("--thinking-budget", type=int, default=None)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--out", default="results/parse")
    ap.add_argument("--pipeline-splits", default=",".join(TEST), help="images verified with extracted constraints")
    args = ap.parse_args()
    bench, out = pathlib.Path(args.bench), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    man = MX.load_manifest(bench)
    rows = list(man.values())
    vlm = GuardedVLM(make(args.backbone, temperature=0.7, thinking_budget=args.thinking_budget), forbidden_strings(rows))

    gold = {}
    for r in rows:
        gold.setdefault(r["objective"], r["constraints"])
    objs = sorted(gold)
    with ThreadPoolExecutor(args.workers) as ex:
        parsed = {(o, p): f.result() for (o, p), f in
                  {(o, p): ex.submit(parse, o, vlm, f"parse-p{p}") for o in objs for p in range(args.passes)}.items()}

    # 1. extraction accuracy
    ext = []
    for p in range(args.passes):
        exact = c_tp = c_fp = c_fn = incons = 0
        for o in objs:
            g = {key(c) for c in gold[o]}
            x = {key(c) for c in parsed[(o, p)]["constraints"] if c["name"] != "fraction_value"}
            exact += g == x
            c_tp += len(g & x)
            c_fp += len(x - g)
            c_fn += len(g - x)
            incons += bool(parsed[(o, p)]["contradictions"])
        ext.append({"exact": exact / len(objs), "precision": c_tp / max(1, c_tp + c_fp),
                    "recall": c_tp / max(1, c_tp + c_fn), "false_inconsistent": incons / len(objs)})

    # 2. full pipeline with extracted constraints (test images)
    psplits = args.pipeline_splits.split(",")
    tag = "dev" if psplits == ["dev"] else "test"
    test = [r for r in rows if r["split"] in psplits]

    def verify(r, p):
        pr = parsed[(r["objective"], p)]
        if not pr["ok"] or pr["contradictions"]:
            return {"item_id": r["item_id"], "pass": p, "verdict": "UNCERTAIN", "statuses": {}, "confidence": {},
                    "report": [], "calls": 1, "usage": {"input": 0, "output": 0, "latency": 0.0}, "rejected_spec": True}
        png = (bench / r["image"]).read_bytes()
        rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
        res = run_eav({"objective": r["objective"], "constraints": pr["constraints"]}, png, rgb, vlm, p)
        return {"item_id": r["item_id"], "pass": p, "verdict": res["verdict"], "statuses": {}, "confidence": res["confidence"],
                "report": [], "calls": res["calls"] + 1, "usage": res["usage"], "rejected_spec": False}

    with ThreadPoolExecutor(args.workers) as ex:
        recs = list(ex.map(lambda rp: verify(*rp), [(r, p) for p in range(args.passes) for r in test]))
    with open(out / f"eav_extracted_{tag}__{args.backbone}.jsonl", "w") as f:
        for rec in recs:
            f.write(json.dumps(rec) + "\n")
    per = [MX.detection(rs, man) for _, rs in sorted(MX.by_pass(recs).items())]

    # 3. consistency check on contradictory variants
    rng = np.random.default_rng(7)
    pool = sorted({r["objective"] for r in rows if r["split"] in TEST})
    pairs = [(o, contradict(o, rng)) for o in pool]
    pairs = [(o, c) for o, c in pairs if c]
    picked = [pairs[i] for i in rng.permutation(len(pairs))[:60]]
    with ThreadPoolExecutor(args.workers) as ex:
        bad = {(c, p): ex.submit(parse, c, vlm, f"parse-p{p}") for _, c in picked for p in range(args.passes)}
        bad = {k: f.result() for k, f in bad.items()}
    cons = []
    for p in range(args.passes):
        flagged = np.mean([bool(bad[(c, p)]["contradictions"]) for _, c in picked])
        false_alarm = np.mean([bool(parsed[(o, p)]["contradictions"]) for o, _ in picked])
        cons.append({"detected": float(flagged), "false_alarm": float(false_alarm)})

    summary = {"backbone": args.backbone, "objectives": len(objs), "contradiction_items": len(picked),
               "extraction": {k: MX.mean_sd([e[k] for e in ext]) for k in ext[0]},
               "pipeline": {k: MX.mean_sd([q[k] for q in per]) for k in per[0]},
               "spec_rejected": float(np.mean([r["rejected_spec"] for r in recs])),
               "consistency": {k: MX.mean_sd([c[k] for c in cons]) for k in cons[0]},
               "examples": [{"original": o, "contradictory": c, "flags": bad[(c, 0)]["contradictions"]} for o, c in picked[:6]]}
    summary["pipeline_splits"] = psplits
    (out / f"summary_{tag}__{args.backbone}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("objectives", "extraction", "pipeline", "spec_rejected", "consistency")}, indent=1))


if __name__ == "__main__":
    main()
