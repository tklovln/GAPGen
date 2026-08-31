#!/usr/bin/env python3
"""
Aggregate multi-seed role-recognition results (B0 vs B1) across seeds.

Inputs (paper/results/):
  rep_role_{judge}_p{1..3}.json        — seed-1 packs (research_{cond}_{slug})
  rep_role_seeds_{judge}_p{1..3}.json  — seed-2/3 packs (research_{cond}_{slug}_s{N})

Seed-level value = mean accuracy over the 3 scoring passes of one pack.
Across seeds we report mean +/- SE (sd/sqrt(n_seeds)).

Usage: python scripts/research_seed_stats.py
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / 'paper' / 'results'
JUDGES = ['openai', 'gemini']
PASSES = [1, 2, 3]
THEMES = ['fruit', 'pet', 'ocean', 'steampunk']
CONDS = ['B0', 'B1']
CATS = ['element', 'obstacle', 'powerup']
RUN_RE = re.compile(r'^research_(B\d)_([a-z]+)(?:_s(\d))?$')


def load_all() -> dict:
    """(theme, cond, seed, judge, pass) -> role_recognition dict"""
    data: dict = {}
    for judge in JUDGES:
        for p in PASSES:
            for stem in (f'rep_role_{judge}_p{p}', f'rep_role_seeds_{judge}_p{p}'):
                f = RES / f'{stem}.json'
                if not f.exists():
                    continue
                for run, r in json.loads(f.read_text())['runs'].items():
                    m = RUN_RE.match(run)
                    if not m:
                        continue
                    cond, theme, seed = m.group(1), m.group(2), int(m.group(3) or 1)
                    if cond in CONDS and theme in THEMES:
                        data[(theme, cond, seed, judge, p)] = r['role_recognition']
    return data


def seed_value(data: dict, theme: str, cond: str, seed: int, judge: str,
               cat: str | None = None) -> float | None:
    """Mean over available passes; overall accuracy or one category's."""
    vals = []
    for p in PASSES:
        r = data.get((theme, cond, seed, judge, p))
        if not r:
            continue
        v = r['accuracy'] if cat is None else r['by_category'].get(cat, {}).get('accuracy')
        if v is not None:
            vals.append(v)
    return round(statistics.mean(vals), 4) if vals else None


def mean_se(vals: list[float]) -> tuple[float, float]:
    m = statistics.mean(vals)
    se = statistics.stdev(vals) / len(vals) ** 0.5 if len(vals) > 1 else 0.0
    return round(m, 3), round(se, 3)


def main() -> None:
    data = load_all()
    seeds_by_theme = {
        t: sorted({s for (th, _, s, _, _) in data if th == t}) for t in THEMES
    }
    print(f'loaded {len(data)} (theme,cond,seed,judge,pass) cells')
    for t in THEMES:
        print(f'  {t}: seeds {seeds_by_theme[t]}')

    out_rows = []
    print('\n== Overall accuracy: mean +/- SE across seeds (each seed = mean of 3 passes) ==')
    hdr = f'{"theme":10} {"judge":7} {"B0":>14} {"B1":>14} {"D":>7}  per-seed D (B1-B0)'
    print(hdr)
    for theme in THEMES:
        seeds = seeds_by_theme[theme]
        if not seeds:
            continue
        for judge in JUDGES:
            b0 = [seed_value(data, theme, 'B0', s, judge) for s in seeds]
            b1 = [seed_value(data, theme, 'B1', s, judge) for s in seeds]
            pairs = [(s, x, y) for s, x, y in zip(seeds, b0, b1) if x is not None and y is not None]
            if not pairs:
                continue
            b0v, b1v = [p[1] for p in pairs], [p[2] for p in pairs]
            m0, se0 = mean_se(b0v)
            m1, se1 = mean_se(b1v)
            deltas = [round(y - x, 3) for _, x, y in pairs]
            print(f'{theme:10} {judge:7} {m0:.3f} +/- {se0:.3f} {m1:.3f} +/- {se1:.3f} '
                  f'{m1 - m0:+.3f}  {deltas}')
            out_rows.append({
                'theme': theme, 'judge': judge, 'scope': 'overall',
                'n_seeds': len(pairs), 'seeds': [p[0] for p in pairs],
                'B0_per_seed': b0v, 'B1_per_seed': b1v,
                'B0_mean': m0, 'B0_se': se0, 'B1_mean': m1, 'B1_se': se1,
                'delta_mean': round(m1 - m0, 3), 'delta_per_seed': deltas,
                'delta_sign_stable': all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
                                     or all(d == 0 for d in deltas),
            })

    print('\n== By category ==')
    for cat in CATS:
        print(f'\n-- {cat} --')
        print(hdr)
        for theme in THEMES:
            seeds = seeds_by_theme[theme]
            for judge in JUDGES:
                b0 = [seed_value(data, theme, 'B0', s, judge, cat) for s in seeds]
                b1 = [seed_value(data, theme, 'B1', s, judge, cat) for s in seeds]
                pairs = [(s, x, y) for s, x, y in zip(seeds, b0, b1)
                         if x is not None and y is not None]
                if not pairs:
                    continue
                b0v, b1v = [p[1] for p in pairs], [p[2] for p in pairs]
                m0, se0 = mean_se(b0v)
                m1, se1 = mean_se(b1v)
                deltas = [round(y - x, 3) for _, x, y in pairs]
                print(f'{theme:10} {judge:7} {m0:.3f} +/- {se0:.3f} {m1:.3f} +/- {se1:.3f} '
                      f'{m1 - m0:+.3f}  {deltas}')
                out_rows.append({
                    'theme': theme, 'judge': judge, 'scope': cat,
                    'n_seeds': len(pairs), 'seeds': [p[0] for p in pairs],
                    'B0_per_seed': b0v, 'B1_per_seed': b1v,
                    'B0_mean': m0, 'B0_se': se0, 'B1_mean': m1, 'B1_se': se1,
                    'delta_mean': round(m1 - m0, 3), 'delta_per_seed': deltas,
                    'delta_sign_stable': all(d > 0 for d in deltas) or all(d < 0 for d in deltas)
                                         or all(d == 0 for d in deltas),
                })

    dst = RES / 'seed_replication_stats.json'
    dst.write_text(json.dumps(out_rows, indent=1), encoding='utf-8')
    print(f'\nwrote {dst}')


def self_check() -> None:
    fake = {}
    for p in PASSES:
        fake[('pet', 'B0', 1, 'openai', p)] = {'accuracy': 0.2 + 0.1 * p,
                                               'by_category': {'element': {'accuracy': 0.5}}}
    assert seed_value(fake, 'pet', 'B0', 1, 'openai') == 0.4
    assert seed_value(fake, 'pet', 'B0', 1, 'openai', 'element') == 0.5
    assert seed_value(fake, 'pet', 'B1', 1, 'openai') is None
    m, se = mean_se([0.4, 0.5, 0.6])
    assert m == 0.5 and abs(se - 0.0577) < 1e-3
    assert RUN_RE.match('research_B0_pet_s2').group(3) == '2'
    assert RUN_RE.match('research_B1_ocean').group(3) is None
    print('self-check OK')


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        self_check()
    else:
        main()
