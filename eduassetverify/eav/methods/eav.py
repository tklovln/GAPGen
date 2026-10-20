"""EduAssetVerify (full method) and the rule-only baseline that shares its grounding.

run_eav makes m value-blind grounding calls and, for semantic constraints, m targeted
re-reading calls on crops; everything it saw is returned, so ablations and the rule-only
baseline are re-scored from the same evidence without new API calls (eav.rules.Config).
"""
from __future__ import annotations

import io
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..evidence import (COUNT_VOCAB, SEMANTIC_CATEGORY, SEMANTIC_TEXT, SHAPE_VOCAB, evidence, norm_text,
                        parse_json, schema_for)
from ..rules import Config, _main_shape, decide
from ..vlm import prompts as P


def _png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def _crop(rgb: np.ndarray, box, pad=0.3, min_side=160) -> np.ndarray:
    x0, y0, x1, y1 = box
    dx, dy = (x1 - x0) * pad + 4, (y1 - y0) * pad + 4
    x0, y0 = max(0, int(x0 - dx)), max(0, int(y0 - dy))
    x1, y1 = min(rgb.shape[1], int(x1 + dx)), min(rgb.shape[0], int(y1 + dy))
    crop = rgb[y0:y1, x0:x1]
    k = max(1.0, min_side / max(1, min(crop.shape[:2])))
    if k > 1:
        crop = np.asarray(Image.fromarray(crop).resize((int(crop.shape[1] * k), int(crop.shape[0] * k)), Image.BICUBIC))
    return crop


def montage(rgb: np.ndarray, boxes: list, tile: int = 128) -> np.ndarray:
    n = len(boxes)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    sheet = Image.new("RGB", (cols * tile, rows * tile), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for i, b in enumerate(boxes):
        crop = Image.fromarray(_crop(rgb, b, pad=0.15, min_side=1))
        k = min((tile - 8) / crop.width, (tile - 30) / crop.height)        # keep the aspect ratio
        c = crop.resize((max(1, int(crop.width * k)), max(1, int(crop.height * k))), Image.BICUBIC)
        x, y = (i % cols) * tile, (i // cols) * tile
        sheet.paste(c, (x + 4 + (tile - 8 - c.width) // 2, y + 26 + (tile - 30 - c.height) // 2))
        draw.rectangle([x, y, x + tile - 1, y + tile - 1], outline=(120, 120, 120))
        draw.text((x + 6, y + 3), str(i + 1), fill=(0, 0, 0), font=font)
    return np.asarray(sheet)


def _text_box(ev: dict):
    texts = [t for t in ev["texts"] if t["box"] and any(ch.isdigit() for ch in t["text"])]
    shape = _main_shape(ev)
    if shape and shape.get("box"):
        sx0, sy0, sx1, sy1 = shape["box"]
        outside = [t for t in texts if not (sx0 < (t["box"][0] + t["box"][2]) / 2 < sx1
                                            and sy0 < (t["box"][1] + t["box"][3]) / 2 < sy1)]
        texts = outside or texts
    return max(texts, key=lambda t: len(t["text"]))["box"] if texts else None


def semantic_reading(constraints, ev, rgb, vlm, sample: str) -> tuple[dict, list[dict]]:
    names = {c["name"] for c in constraints}
    out, calls = {}, []
    if names & SEMANTIC_TEXT:
        box = _text_box(ev)
        crop = _crop(rgb, box) if box else rgb
        r = vlm.ask(P.read_text(), [_png(crop)], sample=sample + "-text")
        calls.append(r)
        js = parse_json(r["text"])
        out["text"] = norm_text(js.get("text")) if js and "text" in js else None
        out["box"] = box
    if names & SEMANTIC_CATEGORY and ev["objects"]:
        boxes = [o["box"] for o in ev["objects"]][:16]
        vocab = COUNT_VOCAB if schema_for(constraints) == "counting" else SHAPE_VOCAB
        r = vlm.ask(P.read_tiles(len(boxes), vocab), [_png(montage(rgb, boxes))], sample=sample + "-tiles")
        calls.append(r)
        js = parse_json(r["text"], allow_list=True) or {}
        if isinstance(js, list):
            js = {"tiles": js}
        cats = [None] * len(boxes)
        for t in js.get("tiles") or []:
            try:
                k = int(t.get("tile")) - 1
            except (TypeError, ValueError, AttributeError):
                continue
            if 0 <= k < len(cats):
                cats[k] = str(t.get("category", "other")).lower().strip()
        out["categories"] = [c if c else "other" for c in cats] if any(cats) else None
    return out, calls


def run_eav(item: dict, png: bytes, rgb: np.ndarray, vlm, pass_idx: int, m: int = 3,
            cfg: Config | None = None, vocab_order=None, image_override: bytes | None = None) -> dict:
    cfg = cfg or Config()
    schema = schema_for(item["constraints"])
    prompt = P.grounding(schema, vocab_order)
    img = image_override or png
    readings, sems, calls = [], [], []
    for r in range(m):
        resp = vlm.ask(prompt, [img], sample=f"p{pass_idx}-g{r}" + ("-perm" if vocab_order else ""))
        calls.append(resp)
        ev = evidence(parse_json(resp["text"]))
        readings.append(ev)
    needs_sem = {c["name"] for c in item["constraints"]} & (SEMANTIC_TEXT | SEMANTIC_CATEGORY)
    for r, ev in enumerate(readings):
        if needs_sem and ev["ok"]:
            sem, cs = semantic_reading(item["constraints"], ev, rgb, vlm, sample=f"p{pass_idx}-s{r}")
            calls += cs
            sems.append(sem)
        else:
            sems.append(None)
    res = decide(item["constraints"], readings, sems, rgb, cfg)
    res.update({"readings": readings, "semantic": sems,
                "calls": len(calls), "errors": [c["error"] for c in calls if c.get("error")],
                "usage": {"input": sum(c["usage"].get("input", 0) for c in calls),
                          "output": sum(c["usage"].get("output", 0) for c in calls),
                          "latency": sum(c.get("latency", 0.0) for c in calls),
                          "cached": sum(bool(c.get("cached")) for c in calls)},
                "unparsable": sum(not ev["ok"] for ev in readings)})
    return res
