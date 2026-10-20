"""Shared types for the three educational domains.

Each domain module provides
    TEMPLATES   template id -> {"role": "dev" | "heldout", "sample": fn(rng) -> Item}
    OPERATORS   operator id -> {"category": paper category, "applicable": fn(item) -> bool,
                                "apply": fn(item, rng) -> None (mutates a copy)}
    evaluate(scene, constraints) -> {constraint id: bool}   spec-level ground truth
    primitives(scene) -> [drawing primitive]                 input of eav.render

An Item's `objective` and `constraints` are what a verifier may see. Its `scene`, the
applied operators, targets and ground-truth regions stay with the evaluator.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

# The seven error types of the paper (Section V-C).
CATEGORIES = [
    "Missing Object", "Extra Object", "Incorrect Proportion", "Incorrect Label",
    "Spatial Relation Reversal", "Broken Symmetry", "Semantic Mismatch",
]


@dataclass
class Item:
    domain: str
    template: str
    objective: str
    constraints: list[dict]
    scene: dict
    operators: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    gt_regions: dict = field(default_factory=dict)   # constraint id -> [bbox, ...]

    def copy(self) -> "Item":
        return copy.deepcopy(self)


def constraint(cid: str, ctype: str, name: str, subject, op: str, value, text: str) -> dict:
    return {"id": cid, "type": ctype, "name": name, "subject": subject, "op": op,
            "value": value, "text": text}


class NotApplicable(Exception):
    """An operator cannot change exactly its target constraint on this item."""
