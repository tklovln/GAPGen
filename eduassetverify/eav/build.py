"""Build the counterfactual educational asset benchmark (seeded, reproducible).

    python -m eav.build --out data/bench_v1            # full build (Table II sizes)
    python -m eav.build --out /tmp/b --scale 0.1       # quick build for development

For every pair (I+, I-) the build
  1. samples a correct scene from a template and checks that the spec satisfies every
     constraint;
  2. applies one error operator (two for the error-combination split) and asserts the
     single-variable property: exactly the targeted constraints change status;
  3. renders both images in the same style and recomputes every constraint from pixels
     (eav.validate); the pair is kept only if pixels and spec agree on every constraint;
  4. writes images under random identifiers with no metadata, and keeps the spec, the
     operator and the labels in evaluator-only files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
from concurrent.futures import ProcessPoolExecutor

import io

import numpy as np

from . import render as R
from .domains import CATEGORIES, Item, NotApplicable, counting, fraction, spatial
from .styles import DEV_STYLES, STYLES, UNSEEN_STYLES
from .validate import validate

DOMAINS = {"fraction": fraction, "counting": counting, "spatial": spatial}

# pairs per domain; Table II: 150 test pairs per domain = 300 images, 900 in total
SPLITS = {
    "dev": {"pairs": 20, "templates": "dev", "compose": False},
    "test_indomain": {"pairs": 50, "templates": "dev", "compose": False},
    "test_unseen_template": {"pairs": 50, "templates": "heldout", "compose": False},
    "test_error_combo": {"pairs": 25, "templates": "dev", "compose": True},
}
# Spatial dev templates carry a single relation each, so no two operators can combine
# there; its error-combination quota moves to the in-domain split (150 test pairs each).
PAIRS_OVERRIDE = {"spatial": {"test_indomain": 75, "test_error_combo": 0}}
UNSEEN_STYLE_PAIRS = 25          # re-rendered from test_indomain pairs, per domain
SEED = 2027


class SingleVariableViolation(AssertionError):
    pass


def _hex_id(rng: np.random.Generator) -> str:
    return "".join(f"{b:02x}" for b in rng.integers(0, 256, 6, dtype=np.uint8))


def _apply(mod, item: Item, ops: list[str], rng) -> Item:
    neg = item.copy()
    for op in ops:
        before = set(neg.gt_regions)
        mod.OPERATORS[op]["apply"](neg, rng)
        new = set(neg.gt_regions) - before
        if len(new) != 1:
            raise NotApplicable(f"{op} did not add exactly one target")
        neg.operators.append(op)
        neg.targets.append(new.pop())
    if len(set(neg.targets)) != len(neg.targets):
        raise NotApplicable("two operators hit the same constraint")
    truth_pos = mod.evaluate(item.scene, item.constraints)
    truth_neg = mod.evaluate(neg.scene, neg.constraints)
    changed = {cid for cid in truth_pos if truth_pos[cid] != truth_neg[cid]}
    if not all(truth_pos.values()):
        raise SingleVariableViolation(f"correct item fails its constraints: {truth_pos}")
    if changed != set(neg.targets) or any(truth_neg[t] for t in neg.targets):
        if len(ops) > 1:   # e.g. wrong_part_count re-equalizes an unequal partition
            raise NotApplicable(f"{ops} interact: changed {sorted(changed)}")
        raise SingleVariableViolation(f"{ops} changed {sorted(changed)}, targeted {neg.targets}")
    return neg


def _candidate(domain: str, split: str, idx: int, seed_seq: np.random.SeedSequence) -> dict | None:
    mod, cfg = DOMAINS[domain], SPLITS[split]
    rng = np.random.default_rng(seed_seq)
    tids = sorted(t for t, v in mod.TEMPLATES.items() if v["role"] == cfg["templates"])
    ops = sorted(mod.OPERATORS)
    for attempt in range(50):
        tid = tids[(idx + attempt) % len(tids)]
        item = mod.TEMPLATES[tid]["sample"](rng)
        if cfg["compose"]:
            pairs = [(a, b) for a in ops for b in ops if a < b]
            order = [pairs[i] for i in rng.permutation(len(pairs))]
        else:   # balance error categories first, operators within a category second
            cats = sorted({mod.OPERATORS[o]["category"] for o in ops})
            order = []
            for j in range(len(cats)):
                cat = cats[(idx + attempt + j) % len(cats)]
                in_cat = [o for o in ops if mod.OPERATORS[o]["category"] == cat]
                order += [(in_cat[(idx // len(cats) + i) % len(in_cat)],) for i in range(len(in_cat))]
        for combo in order:
            try:
                neg = _apply(mod, item, list(combo), rng)
            except NotApplicable:
                continue
            return {"pos": item, "neg": neg, "style": DEV_STYLES[idx % len(DEV_STYLES)].name,
                    "pair_id": "p" + _hex_id(rng), "ids": (_hex_id(rng), _hex_id(rng))}
    return None


def _render_check(task: dict) -> dict:
    """Worker: render one pair in one style and validate both images from pixels."""
    mod = DOMAINS[task["domain"]]
    style = STYLES[task["style"]]
    out = {"ok": True, "reason": None, "images": []}
    for polarity, item, iid in (("+", task["pos"], task["ids"][0]), ("-", task["neg"], task["ids"][1])):
        svg = io.BytesIO()
        rgb = R.render(mod.primitives(item.scene), style, svg_out=svg)
        truth = mod.evaluate(item.scene, item.constraints)
        seen = validate(task["domain"], rgb, style, item.constraints)
        bad = {cid: (truth[cid], seen.get(cid)) for cid in truth if seen.get(cid) is not truth[cid]}
        if bad:
            out["ok"] = False
            out["reason"] = f"{polarity} {item.template} {item.operators}: spec vs pixels {bad}"
        out["images"].append({"polarity": polarity, "item_id": iid, "png": R.png_bytes(rgb),
                              "svg": svg.getvalue()})
    return out


def _manifest_row(task, polarity, item: Item, iid: str, split: str, extra=None) -> dict:
    mod = DOMAINS[task["domain"]]
    row = {
        "item_id": iid, "pair_id": task["pair_id"], "split": split, "domain": task["domain"],
        "template": item.template, "style": task["style"], "polarity": polarity,
        "label": "VALID" if polarity == "+" else "INVALID",
        "objective": item.objective, "constraints": item.constraints,
        "operators": item.operators,
        "operator_categories": [mod.OPERATORS[o]["category"] for o in item.operators],
        "targets": item.targets, "gt_regions": item.gt_regions,
        "image": f"images/{iid}.png", "svg": f"svg/{iid}.svg",
    }
    row.update(extra or {})
    return row


def build(out: pathlib.Path, scale: float = 1.0, workers: int = 32, seed: int = SEED) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for sub in ("images", "svg", "specs"):
        (out / sub).mkdir(exist_ok=True)
    root = np.random.SeedSequence(seed)
    dom_seqs = dict(zip(DOMAINS, root.spawn(len(DOMAINS))))
    report = {"seed": seed, "scale": scale, "discarded": [], "kept": {}, "candidates": {}}
    rows, kept_tasks = [], {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for domain in DOMAINS:
            split_seqs = dict(zip(SPLITS, dom_seqs[domain].spawn(len(SPLITS))))
            for split, cfg in SPLITS.items():
                pairs = PAIRS_OVERRIDE.get(domain, {}).get(split, cfg["pairs"])
                if pairs == 0:
                    continue
                want = max(2, int(round(pairs * scale)))
                seqs = split_seqs[split].spawn(4 * want)
                kept, idx = [], 0
                while len(kept) < want and idx < len(seqs):
                    batch = []
                    while len(batch) < (want - len(kept)) * 2 and idx < len(seqs):
                        cand = _candidate(domain, split, idx, seqs[idx])
                        idx += 1
                        if cand:
                            batch.append(dict(cand, domain=domain, split=split))
                    for task, res in zip(batch, pool.map(_render_check, batch)):
                        if len(kept) >= want:
                            break
                        if not res["ok"]:
                            report["discarded"].append({"domain": domain, "split": split, "reason": res["reason"]})
                            continue
                        kept.append((task, res))
                report["candidates"][f"{domain}/{split}"] = idx
                report["kept"][f"{domain}/{split}"] = len(kept)
                kept_tasks[(domain, split)] = kept
                for task, res in kept:
                    for img, item in zip(res["images"], (task["pos"], task["neg"])):
                        _write(out, img, item, task["domain"], task["style"])
                        rows.append(_manifest_row(task, img["polarity"], item, img["item_id"], split))

        # unseen styles: the same in-domain scenes, re-rendered, never seen in development
        for domain in DOMAINS:
            rng = np.random.default_rng(dom_seqs[domain].spawn(1)[0])
            src = kept_tasks[(domain, "test_indomain")][: max(2, int(round(UNSEEN_STYLE_PAIRS * scale)))]
            batch = []
            for j, (task, _) in enumerate(src):
                batch.append(dict(task, style=UNSEEN_STYLES[j % len(UNSEEN_STYLES)].name,
                                  source_pair=task["pair_id"], pair_id="p" + _hex_id(rng),
                                  ids=(_hex_id(rng), _hex_id(rng)), split="test_unseen_style"))
            n_ok = 0
            for task, res in zip(batch, pool.map(_render_check, batch)):
                if not res["ok"]:
                    report["discarded"].append({"domain": domain, "split": "test_unseen_style",
                                                "style": task["style"], "reason": res["reason"]})
                    continue
                n_ok += 1
                for img, item in zip(res["images"], (task["pos"], task["neg"])):
                    _write(out, img, item, task["domain"], task["style"])
                    rows.append(_manifest_row(task, img["polarity"], item, img["item_id"], "test_unseen_style",
                                              {"source_pair": task["source_pair"]}))
            report["kept"][f"{domain}/test_unseen_style"] = n_ok

    with open(out / "manifest.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    with open(out / "checksums.sha256", "w") as f:
        for r in sorted(rows, key=lambda r: r["item_id"]):
            f.write(f"{hashlib.sha256((out / r['image']).read_bytes()).hexdigest()}  {r['image']}\n")
    report["images"] = len(rows)
    report["by_split"] = {s: sum(r["split"] == s for r in rows) for s in sorted({r["split"] for r in rows})}
    report["by_category"] = {c: sum(c in r["operator_categories"] for r in rows) for c in CATEGORIES}
    (out / "build_report.json").write_text(json.dumps(report, indent=1))
    return report


def _write(out: pathlib.Path, img: dict, item: Item, domain: str, style: str) -> None:
    iid = img["item_id"]
    (out / "images" / f"{iid}.png").write_bytes(img["png"])
    (out / "svg" / f"{iid}.svg").write_bytes(img["svg"])
    spec = {"domain": domain, "template": item.template, "style": style, "scene": item.scene,
            "operators": item.operators, "targets": item.targets}
    (out / "specs" / f"{iid}.json").write_text(json.dumps(spec, sort_keys=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=min(32, os.cpu_count() or 4))
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    rep = build(pathlib.Path(args.out), args.scale, args.workers, args.seed)
    print(json.dumps({k: rep[k] for k in ("images", "kept", "by_split", "by_category")}, indent=1))
    print(f"discarded pairs: {len(rep['discarded'])}")
    for d in rep["discarded"][:30]:
        print("  -", d)


if __name__ == "__main__":
    main()
