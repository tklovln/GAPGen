"""Benchmark invariants: the guards of Table IV that concern the data itself.

Run:  .venv/bin/python -m pytest -q tests
"""
from __future__ import annotations

import json
import pathlib
import re

import numpy as np
import pytest
from PIL import Image

from eav import build as B
from eav.domains import counting, fraction, spatial
from eav.styles import STYLES
from eav.validate import validate

MODS = {"fraction": fraction, "counting": counting, "spatial": spatial}


@pytest.fixture(scope="module")
def bench(tmp_path_factory) -> pathlib.Path:
    out = tmp_path_factory.mktemp("bench")
    B.build(out, scale=0.1, workers=8)
    return out


def _rows(bench):
    return [json.loads(line) for line in (bench / "manifest.jsonl").read_text().splitlines()]


def test_build_is_deterministic(bench, tmp_path):
    B.build(tmp_path, scale=0.1, workers=8)
    assert (tmp_path / "checksums.sha256").read_text() == (bench / "checksums.sha256").read_text()


def test_every_pair_is_single_variable(bench):
    for r in _rows(bench):
        spec = json.loads((bench / "specs" / f"{r['item_id']}.json").read_text())
        truth = MODS[r["domain"]].evaluate(spec["scene"], r["constraints"])
        if r["polarity"] == "+":
            assert all(truth.values()), r["item_id"]
        else:
            assert {cid for cid, ok in truth.items() if not ok} == set(r["targets"]), r["item_id"]


def test_labels_survive_independent_pixel_check(bench):
    for r in _rows(bench):
        rgb = np.asarray(Image.open(bench / r["image"]).convert("RGB"))
        seen = validate(r["domain"], rgb, STYLES[r["style"]], r["constraints"])
        for c in r["constraints"]:
            assert seen[c["id"]] is (c["id"] not in r["targets"]), (r["item_id"], c["id"])


def test_images_carry_pixels_only(bench):
    for r in _rows(bench):
        path = bench / r["image"]
        assert re.fullmatch(r"images/[0-9a-f]{12}\.png", r["image"])
        assert Image.open(path).info == {}, f"metadata in {path}"
        assert b"tEXt" not in path.read_bytes() and b"iTXt" not in path.read_bytes()


def test_verifier_visible_fields_do_not_leak_the_answer(bench):
    forbidden = set()
    for mod in MODS.values():
        forbidden |= set(mod.OPERATORS) | set(mod.TEMPLATES)
    forbidden |= {"INVALID", "polarity", "violated", "target"}
    for r in _rows(bench):
        visible = json.dumps({"objective": r["objective"], "constraints": r["constraints"]})
        assert not [w for w in forbidden if w in visible], r["item_id"]


def test_pairs_share_constraints_and_style(bench):
    pairs: dict[str, list] = {}
    for r in _rows(bench):
        pairs.setdefault(r["pair_id"], []).append(r)
    for pid, rs in pairs.items():
        assert sorted(x["polarity"] for x in rs) == ["+", "-"], pid
        assert rs[0]["constraints"] == rs[1]["constraints"] and rs[0]["style"] == rs[1]["style"], pid


def test_templates_do_not_cross_splits(bench):
    roles = {t: v["role"] for m in MODS.values() for t, v in m.TEMPLATES.items()}
    for r in _rows(bench):
        want = "heldout" if r["split"] == "test_unseen_template" else "dev"
        assert roles[r["template"]] == want, (r["split"], r["template"])
        style_role = STYLES[r["style"]].role
        assert style_role == ("unseen" if r["split"] == "test_unseen_style" else "dev")
