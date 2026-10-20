"""Five-check validity battery, run per backbone and role before any number is reported.

    python -m eav.vlm.battery --bench data/bench_v1 --backbone gemini-3.5-flash --pairs 10

Checks (thresholds as in the game-asset study):
  1. protocol compliance   outputs parse against the schema        >= 0.98 (strict rate reported)
  2. test-retest           same query twice -> same decision        >= 0.80
  3. permutation           shuffled vocabulary / options / order    >= 0.70
  4. blank-image control   grounding sees nothing on a blank image  >= 0.90 empty
                           judge accuracy: real - blank             >= 0.20
  5. above majority        accuracy on real images                  >  constant-majority rate
Roles: "grounding" (value-blind evidence, decided by the rule engine on one reading) and
"judge" (the direct judge prompt).
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib

import numpy as np
from PIL import Image

from ..evidence import evidence, parse_json, schema_for
from ..methods.judges import run_judge
from ..rules import Config, decide
from ..run import GuardedVLM, forbidden_strings, load_rows, view
from . import prompts as P
from .client import make

BLANK = io.BytesIO()
Image.new("RGB", (512, 512), (255, 255, 255)).save(BLANK, format="PNG")
BLANK = BLANK.getvalue()


def _ground(vlm, row, png, rgb, sample, order=None, image=None):
    resp = vlm.ask(P.grounding(schema_for(row["constraints"]), order), [image or png], sample=sample)
    strict = parse_json(resp["text"], repair=False) is not None
    ev = evidence(parse_json(resp["text"]))
    verdict = decide(row["constraints"], [ev], [None], rgb, Config(tau=0.0))["verdict"]
    empty = ev["ok"] and not ev["objects"] and not ev["shapes"]
    return {"ok": ev["ok"], "strict": strict, "verdict": verdict, "empty": empty}


def run_battery(backbone: str, bench: pathlib.Path, pairs: int, thinking_budget=None, temperature=0.7) -> dict:
    rows = load_rows(bench, ["dev"], 2 * pairs, seed=1)
    vlm = GuardedVLM(make(backbone, temperature=temperature, thinking_budget=thinking_budget), forbidden_strings(rows))
    rng = np.random.default_rng(0)
    g = {"a": [], "b": [], "perm": [], "blank": []}
    j = {"a": [], "b": [], "perm": [], "blank": []}
    for row in rows:
        png = (bench / row["image"]).read_bytes()
        rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
        vocab = 8 if schema_for(row["constraints"]) == "spatial" else 7
        order = [int(i) for i in rng.permutation(vocab)]
        g["a"].append(_ground(vlm, row, png, rgb, "battery-a"))
        g["b"].append(_ground(vlm, row, png, rgb, "battery-b"))
        g["perm"].append(_ground(vlm, row, png, rgb, "battery-perm", order=order))
        g["blank"].append(_ground(vlm, row, png, np.full_like(rgb, 255), "battery-blank", image=BLANK))
        req = [int(i) for i in rng.permutation(len(row["constraints"]))]
        j["a"].append(run_judge("direct", view(row), png, vlm, 0, tag="-battery-a"))
        j["b"].append(run_judge("direct", view(row), png, vlm, 0, tag="-battery-b"))
        j["perm"].append(run_judge("direct", view(row), png, vlm, 0, order=req, swap=True, tag="-battery-perm"))
        j["blank"].append(run_judge("direct", view(row), png, vlm, 0, tag="-battery-blank", image_override=BLANK))
    labels = [r["label"] for r in rows]
    majority = max(labels.count("VALID"), labels.count("INVALID")) / len(labels)

    def agree(x, y):
        return float(np.mean([a["verdict"] == b["verdict"] for a, b in zip(x, y)]))

    def acc(x):
        return float(np.mean([a["verdict"] == y for a, y in zip(x, labels)]))

    g_all = g["a"] + g["b"] + g["perm"] + g["blank"]
    j_all = j["a"] + j["b"] + j["perm"] + j["blank"]
    report = {
        "backbone": backbone, "images": len(rows), "majority": majority,
        "grounding": {
            "protocol": float(np.mean([x["ok"] for x in g_all])), "protocol_strict": float(np.mean([x["strict"] for x in g_all])),
            "retest": agree(g["a"], g["b"]), "permutation": agree(g["a"], g["perm"]),
            "blank_empty": float(np.mean([x["empty"] for x in g["blank"]])), "accuracy": acc(g["a"]),
        },
        "judge": {
            "protocol": float(np.mean([x["verdict"] != "UNPARSABLE" for x in j_all])),
            "retest": agree(j["a"], j["b"]), "permutation": agree(j["a"], j["perm"]),
            "accuracy": acc(j["a"]), "blank_accuracy": acc(j["blank"]),
        },
    }
    G, J = report["grounding"], report["judge"]
    report["pass"] = {
        "grounding": {"protocol": G["protocol"] >= 0.98, "retest": G["retest"] >= 0.8, "permutation": G["permutation"] >= 0.7,
                      "blank": G["blank_empty"] >= 0.9, "above_majority": G["accuracy"] > majority},
        "judge": {"protocol": J["protocol"] >= 0.98, "retest": J["retest"] >= 0.8, "permutation": J["permutation"] >= 0.7,
                  "blank": J["accuracy"] - J["blank_accuracy"] >= 0.2, "above_majority": J["accuracy"] > majority},
    }
    report["passed"] = all(all(v.values()) for v in report["pass"].values())
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--backbone", required=True)
    ap.add_argument("--pairs", type=int, default=10)
    ap.add_argument("--thinking-budget", type=int, default=None)
    ap.add_argument("--out", default="results/battery")
    args = ap.parse_args()
    rep = run_battery(args.backbone, pathlib.Path(args.bench), args.pairs, args.thinking_budget)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.backbone}.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
