"""VLM judge baselines: direct, chain-of-thought, and structured (per-requirement)."""
from __future__ import annotations

from ..evidence import parse_json
from ..vlm import prompts as P

BUILDERS = {"direct": P.judge_direct, "cot": P.judge_cot, "structured": P.judge_structured}


def run_judge(kind: str, item: dict, png: bytes, vlm, pass_idx: int, order=None, swap=False,
              image_override: bytes | None = None, tag: str = "") -> dict:
    cons = item["constraints"]
    prompt = BUILDERS[kind](item["objective"], cons, order, swap)
    resp = vlm.ask(prompt, [image_override or png], sample=f"p{pass_idx}{tag}")
    js = parse_json(resp["text"])
    verdict = str(js.get("verdict", "")).strip().upper() if js else ""
    if verdict not in ("VALID", "INVALID"):
        verdict = "UNPARSABLE"
    statuses = {}
    if kind == "structured" and js:
        idx = list(range(len(cons))) if order is None else order
        for k, entry in enumerate(js.get("requirements") or []):
            if not isinstance(entry, dict):
                continue
            try:
                num = int(entry.get("number", k + 1)) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= num < len(idx) and isinstance(entry.get("satisfied"), bool):
                statuses[cons[idx[num]]["id"]] = "T" if entry["satisfied"] else "F"
    return {"verdict": verdict, "statuses": statuses, "calls": 1,
            "errors": [resp["error"]] if resp.get("error") else [],
            "usage": {"input": resp["usage"].get("input", 0), "output": resp["usage"].get("output", 0),
                      "latency": resp.get("latency", 0.0), "cached": int(bool(resp.get("cached")))},
            "unparsable": int(verdict == "UNPARSABLE")}
