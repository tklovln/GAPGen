#!/usr/bin/env python3
"""
Recompute the paper's headline numbers from the scored JSON, and refuse to report
any that violate our own sampling rules.

Why this exists: three of the six conclusions this project retracted came from one
root cause -- under-sampling that manufactures structure. Each was "fixed" only by
a note in a markdown file, which cannot fail. This file is the runnable guard the
paper's own principle 3 demands: if someone reports a single-pass delta, or a
Kendall tau over three items, or a cell whose repeats disagree too much, this exits
nonzero.

Rules enforced (each traceable to a specific retraction):
  R1  A per-cell delta needs >= MIN_PASSES independent scoring passes.
      (retraction: "8 of 8 cells positive" -- single pass hid a true-zero cell)
  R2  A rank correlation needs >= MIN_RANK_ITEMS items.
      (retraction: "judges converge on objective tasks" -- 3 packs agree by chance)
  R3  A reported delta must exceed the measured noise, not an assumed floor.
      (retraction: "ontology stabilises legibility" -- 6 cells, one pass each)

Usage:
  python scripts/verify_claims.py            # recompute + assert
  python scripts/verify_claims.py --md       # also print paper-ready tables
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'paper' / 'results'

MIN_PASSES = 3        # R1
MIN_RANK_ITEMS = 5    # R2
NOISE_K = 2.0         # R3: delta must beat NOISE_K * SE

THEMES = ['fruit', 'pet', 'ocean', 'steampunk']
JUDGES = ['openai', 'gemini']
CATEGORIES = ['element', 'obstacle', 'powerup']


def _role_block(run: dict) -> dict:
    """Scored role task, whichever scope was used."""
    for k in ('role_category', 'role_recognition'):
        if k in run:
            return run[k]
    raise KeyError(f'no role block in {list(run)}')


def load_passes(judge: str) -> list[dict]:
    """All repeated scoring passes available for one judge."""
    out = []
    for p in sorted(RESULTS.glob(f'rep_role_{judge}_p*.json')):
        out.append(json.loads(p.read_text(encoding='utf-8'))['runs'])
    return out


def cell(passes: list[dict], theme: str, cond: str) -> list[float]:
    return [_role_block(p[f'research_{cond}_{theme}'])['accuracy'] for p in passes]


def cell_by_cat(passes: list[dict], theme: str, cond: str, cat: str) -> list[float]:
    vals = []
    for p in passes:
        bc = _role_block(p[f'research_{cond}_{theme}'])['by_category'].get(cat)
        if bc:
            vals.append(bc['accuracy'])
    return vals


def kendall_tau(order_a: list[str], order_b: list[str]) -> float:
    """Tau over the items present in both orderings. Enforces R2."""
    items = [x for x in order_a if x in order_b]
    if len(items) < MIN_RANK_ITEMS:
        raise ValueError(
            f'R2 violated: rank correlation over {len(items)} items, '
            f'need >= {MIN_RANK_ITEMS}. Three items agree by chance 1/6 of the time.'
        )
    ra = {x: order_a.index(x) for x in items}
    rb = {x: order_b.index(x) for x in items}
    conc = disc = 0
    for x, y in itertools.combinations(items, 2):
        s = (ra[x] - ra[y]) * (rb[x] - rb[y])
        conc += s > 0
        disc += s < 0
    return round((conc - disc) / (conc + disc), 3) if conc + disc else 0.0


def delta(b0: list[float], b1: list[float]) -> tuple[float, float, bool]:
    """Mean delta, its standard error, and whether it clears the noise. Enforces R1/R3."""
    if len(b0) < MIN_PASSES or len(b1) < MIN_PASSES:
        raise ValueError(
            f'R1 violated: {min(len(b0), len(b1))} scoring pass(es), need >= {MIN_PASSES}. '
            'Single-pass scoring hid a true-zero cell behind +-0.250 of judge noise.'
        )
    d = st.mean(b1) - st.mean(b0)
    se = (st.stdev(b0) ** 2 / len(b0) + st.stdev(b1) ** 2 / len(b1)) ** 0.5
    return d, se, d > NOISE_K * se


def main() -> None:
    ap = argparse.ArgumentParser(description="Recompute and guard the paper's claims")
    ap.add_argument('--md', action='store_true', help='print paper-ready tables')
    args = ap.parse_args()

    passes = {j: load_passes(j) for j in JUDGES}
    for j, ps in passes.items():
        assert len(ps) >= MIN_PASSES, f'{j}: only {len(ps)} passes on disk'

    # ---- Claim 1: overall per-cell deltas -----------------------------------
    overall = []
    for th in THEMES:
        for j in JUDGES:
            d, se, sig = delta(cell(passes[j], th, 'B0'), cell(passes[j], th, 'B1'))
            overall.append((th, j, d, se, sig))

    n_sig = sum(1 for *_, sig in overall if sig)
    n_zero = sum(1 for _, _, d, _, _ in overall if d == 0)
    n_neg = sum(1 for _, _, d, _, _ in overall if d < 0)
    assert n_neg == 0, f'a negative overall cell appeared: {overall}'
    assert n_sig + n_zero == len(overall), (n_sig, n_zero, len(overall))

    # The retraction itself is now a test: exactly one cell must be a true zero,
    # so nobody can quietly restore the "8 of 8 positive" claim.
    assert n_zero == 1, (
        f'expected exactly 1 true-zero cell (steampunk/openai), found {n_zero}. '
        'If this changed, the abstract must change with it.'
    )

    # ---- Claim 2: per-category deltas ---------------------------------------
    per_cat: dict[str, list[float]] = {c: [] for c in CATEGORIES}
    cat_cells = 0
    for th in THEMES:
        for j in JUDGES:
            for c in CATEGORIES:
                b0 = cell_by_cat(passes[j], th, 'B0', c)
                b1 = cell_by_cat(passes[j], th, 'B1', c)
                if len(b0) < MIN_PASSES or len(b1) < MIN_PASSES:
                    continue
                per_cat[c].append(st.mean(b1) - st.mean(b0))
                cat_cells += 1

    neg = {c: [round(x, 3) for x in v if x < 0] for c, v in per_cat.items()}
    assert not any(neg.values()), f'negative category cell(s): {neg}'

    means = {c: round(st.mean(v), 3) for c, v in per_cat.items()}
    # The mechanism claim: gameplay-defined categories gain more than appearance-
    # defined ones. This is the paper's thesis; if it flips, the paper is wrong.
    assert means['obstacle'] > means['element'], means
    assert means['powerup'] > means['element'], means

    # ---- R2: tau must refuse small item counts ------------------------------
    try:
        kendall_tau(['a', 'b', 'c'], ['a', 'c', 'b'])
        raise AssertionError('R2 not enforced: tau accepted 3 items')
    except ValueError:
        pass

    print(f'passes on disk: ' + ', '.join(f'{j}={len(p)}' for j, p in passes.items()))
    print(f'overall cells: {len(overall)}  significant: {n_sig}  '
          f'true-zero: {n_zero}  negative: {n_neg}')
    print(f'category cells: {cat_cells}  negative: 0  means: {means}')
    print(f'R1 >= {MIN_PASSES} passes, R2 >= {MIN_RANK_ITEMS} items, '
          f'R3 delta > {NOISE_K}*SE  -- all enforced')
    print('verify-claims OK')

    if args.md:
        print('\n| Theme | Judge | Δ | SE | Δ > 2·SE |')
        print('|---|---|---|---|---|')
        for th, j, d, se, sig in overall:
            print(f'| {th} | {j} | {d:+.3f} | {se:.3f} | {"yes" if sig else "**no**"} |')
        print('\n| Category | mean Δ | min | max | cells |')
        print('|---|---|---|---|---|')
        for c in ('obstacle', 'powerup', 'element'):
            v = per_cat[c]
            print(f'| {c} | {st.mean(v):+.3f} | {min(v):+.3f} | {max(v):+.3f} | {len(v)} |')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, ValueError) as e:
        print(f'CLAIM CHECK FAILED: {e}', file=sys.stderr)
        raise SystemExit(1)
