"""Text-image similarity baseline: CLIPScore (Hessel et al.), thresholded on the dev split.

    python -m eav.methods.clip_score --bench data/bench_v1 --out results/main

CLIPScore = 2.5 * max(cos(image, objective), 0) with CLIP ViT-B/32 (OpenAI weights), the
configuration of the original paper. The threshold maximizes balanced accuracy on dev.
Deterministic, so a single pass is reported (sd 0).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np
import torch
from PIL import Image


def scores(rows, bench: pathlib.Path, device: str) -> dict[str, float]:
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai", device=device)
    tok = open_clip.get_tokenizer("ViT-B-32")
    model.eval()
    out = {}
    with torch.no_grad():
        for i in range(0, len(rows), 64):
            batch = rows[i:i + 64]
            ims = torch.stack([preprocess(Image.open(bench / r["image"]).convert("RGB")) for r in batch]).to(device)
            txt = tok([r["objective"] for r in batch]).to(device)
            fi = model.encode_image(ims)
            ft = model.encode_text(txt)
            fi = fi / fi.norm(dim=-1, keepdim=True)
            ft = ft / ft.norm(dim=-1, keepdim=True)
            cos = (fi * ft).sum(-1).clamp(min=0).cpu().numpy()
            for r, c in zip(batch, cos):
                out[r["item_id"]] = float(2.5 * c)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="data/bench_v1")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    bench, out = pathlib.Path(args.bench), pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(x) for x in (bench / "manifest.jsonl").read_text().splitlines()]
    t0 = time.time()
    sc = scores(rows, bench, "cuda" if torch.cuda.is_available() else "cpu")
    per = (time.time() - t0) / len(rows)
    dev = [r for r in rows if r["split"] == "dev"]
    cands = sorted({sc[r["item_id"]] for r in dev})
    best_t, best_acc = None, -1.0
    for t in cands:
        acc = np.mean([(sc[r["item_id"]] >= t) == (r["label"] == "VALID") for r in dev])
        if acc > best_acc:
            best_t, best_acc = t, float(acc)
    with open(out / "clip__ViT-B-32.jsonl", "w") as f:
        for r in rows:
            s = sc[r["item_id"]]
            f.write(json.dumps({"item_id": r["item_id"], "method": "clip", "backbone": "ViT-B-32", "pass": 0,
                                "verdict": "VALID" if s >= best_t else "INVALID", "score": s,
                                "confidence": {"score": abs(s - best_t)}, "statuses": {}, "calls": 0,
                                "errors": [], "unparsable": 0,
                                "usage": {"input": 0, "output": 0, "latency": per, "cached": 0}}) + "\n")
    print(f"threshold {best_t:.4f} (dev accuracy {best_acc:.3f}); {len(rows)} images, {per * 1000:.1f} ms/image")


if __name__ == "__main__":
    main()
