"""Run verification methods over benchmark splits, with caching and leakage guards.

    python -m eav.run --bench data/bench_v1 --backbone gpt-4o-2024-11-20 \
        --methods eav,direct,cot,structured --splits dev --passes 1 --limit 6 --out results/smoke

Each method only ever receives the verifier view of an item: image bytes, objective and
constraints. Every prompt is scanned for evaluator-only strings before it is sent.
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

from .domains import counting, fraction, spatial
from .methods.eav import run_eav
from .methods.judges import run_judge
from .methods.vlm_rules import run_vlm_rules
from .vlm.client import cost, make

SPLITS = ["dev", "test_indomain", "test_unseen_template", "test_error_combo", "test_unseen_style"]


class LeakError(AssertionError):
    pass


class GuardedVLM:
    """Refuses to send a prompt that contains any evaluator-only string."""

    def __init__(self, vlm, forbidden: set[str]):
        self.vlm, self.model = vlm, vlm.model
        self.pattern = re.compile("|".join(sorted(map(re.escape, forbidden), key=len, reverse=True)))

    def ask(self, prompt, images, sample="0", **kw):
        hit = self.pattern.search(prompt)
        if hit:
            raise LeakError(f"prompt contains evaluator-only string {hit.group(0)!r}")
        return self.vlm.ask(prompt, images, sample, **kw)


def forbidden_strings(rows: list[dict]) -> set[str]:
    out = {"polarity", "violated", "operator", "test_", "unseen", "heldout"}
    for mod in (fraction, counting, spatial):
        out |= set(mod.OPERATORS) | set(mod.TEMPLATES)
    for r in rows:
        out |= {r["item_id"], r["pair_id"]}
    return out


def load_rows(bench: pathlib.Path, splits: list[str], limit: int | None, seed: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in (bench / "manifest.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["split"] in splits]
    if limit:
        # keep pairs together, spread over domains
        by_pair: dict[str, list] = {}
        for r in rows:
            by_pair.setdefault(r["pair_id"], []).append(r)
        pids = sorted(by_pair, key=lambda p: (by_pair[p][0]["domain"], p))
        rng = np.random.default_rng(seed)
        doms = sorted({by_pair[p][0]["domain"] for p in pids})
        chosen = []
        per = max(1, limit // (2 * len(doms)))
        for d in doms:
            ps = [p for p in pids if by_pair[p][0]["domain"] == d]
            chosen += list(rng.permutation(ps)[:per])
        rows = [r for p in chosen for r in by_pair[p]]
    return rows


def view(row: dict) -> dict:
    return {"objective": row["objective"], "constraints": row["constraints"]}


def run_method(method: str, row: dict, bench: pathlib.Path, vlm, pass_idx: int, m: int, deps: dict) -> dict:
    png = (bench / row["image"]).read_bytes()
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    t0 = time.time()
    if method == "eav":
        res = run_eav(view(row), png, rgb, vlm, pass_idx, m=m)
    elif method == "vlmrules":     # needs the eav readings of the same item and pass
        res = run_vlm_rules(view(row), deps[(row["item_id"], pass_idx)], rgb, vlm, pass_idx)
    else:
        res = run_judge(method, view(row), png, vlm, pass_idx)
    res["wall"] = time.time() - t0
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--backbone", required=True)
    ap.add_argument("--methods", default="eav,direct,cot,structured")
    ap.add_argument("--splits", default="dev")
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--first-pass", type=int, default=0)
    ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="number of images (pairs kept together)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--thinking-budget", type=int, default=None, help="Gemini thinking tokens per call")
    ap.add_argument("--out", required=True)
    ap.add_argument("--offline", action="store_true", help="cache only; never call an API")
    args = ap.parse_args()

    bench, out = pathlib.Path(args.bench), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = load_rows(bench, args.splits.split(","), args.limit)
    base = make(args.backbone, temperature=args.temperature, thinking_budget=args.thinking_budget)
    if args.offline:
        orig = base.ask
        base.ask = lambda p, i, s="0", **kw: orig(p, i, s, allow_network=False)
    vlm = GuardedVLM(base, forbidden_strings(rows))
    print(f"{len(rows)} images x {args.passes} passes x methods {args.methods} on {args.backbone}", flush=True)
    for method in args.methods.split(","):
        path = out / f"{method}__{args.backbone}.jsonl"
        deps = {}
        if method == "vlmrules":
            src = out / f"eav__{args.backbone}.jsonl"
            for line in src.read_text().splitlines():
                d = json.loads(line)
                deps[(d["item_id"], d["pass"])] = d
        done = set()
        if path.exists():
            for line in path.read_text().splitlines():
                d = json.loads(line)
                done.add((d["item_id"], d["pass"]))
        todo = [(r, p) for p in range(args.first_pass, args.first_pass + args.passes) for r in rows
                if (r["item_id"], p) not in done]
        t0 = time.time()
        with ThreadPoolExecutor(args.workers) as ex, open(path, "a") as f:
            todo = [(r, p) for r, p in todo if method != "vlmrules" or (r["item_id"], p) in deps]
            futs = [(r, p, ex.submit(run_method, method, r, bench, vlm, p, args.m, deps)) for r, p in todo]
            usage = {"input": 0, "output": 0, "calls": 0, "errors": 0, "unparsable": 0, "ok": 0}
            for k, (r, p, fut) in enumerate(futs, 1):
                res = fut.result()
                rec = {"item_id": r["item_id"], "method": method, "backbone": args.backbone, "pass": p, **res}
                f.write(json.dumps(rec) + "\n")
                f.flush()
                usage["input"] += res["usage"]["input"]
                usage["output"] += res["usage"]["output"]
                usage["calls"] += res["calls"]
                usage["errors"] += len(res["errors"])
                usage["unparsable"] += res["unparsable"]
                usage["ok"] += res["verdict"] == r["label"]
                if k % 25 == 0 or k == len(futs):
                    print(f"  {method}: {k}/{len(futs)} correct {usage['ok']} | calls {usage['calls']} errors "
                          f"{usage['errors']} unparsable {usage['unparsable']} | tokens in {usage['input']} out "
                          f"{usage['output']} ~${cost(args.backbone, usage):.3f} | {time.time() - t0:.0f}s", flush=True)
    print(f"API calls made {base.calls}, cache hits {base.cache_hits}", file=sys.stderr)


if __name__ == "__main__":
    main()
