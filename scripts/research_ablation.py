#!/usr/bin/env python3
"""
Run SCOPE.md Fruit ablations (B0/B1/B2/B3) across seeds and write per-run + aggregate CSV.

Usage:
  python scripts/research_ablation.py --dry-run
  python scripts/research_ablation.py --conditions B0,B1,B2,B3 --seeds 3
  python scripts/research_ablation.py --conditions B3 --force   # regen one condition
  python scripts/research_ablation.py --skip-generate --seeds 3 # just recompute CSVs

Seed 1 uses run name research_{cond}_fruit (existing runs = seed 1).
Seeds >=2 use research_{cond}_fruit_s{N}. Gemini image API is non-deterministic,
so distinct run names act as independent seeds without a pipeline seed param.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from art_pipeline import gemini_api, pipeline  # noqa: E402
from art_pipeline.manifest import build_manifest  # noqa: E402

STYLE = (
    '3D Disney Cartoon Style, Simple design, Clean illustrations, '
    'Intuitive icon, highly recognizable'
)
THEME = 'Fruit'
MODE = 'theme_swap'
ASSETS = [
    'Red', 'Grn', 'Blu', 'Yel', 'Pur',
    'Soda0d', 'Soda90', 'LtBl',
    'Crt4', 'Crt3', 'Crt2', 'Crt1',
]
OUT_CSV = ROOT / 'paper' / 'results' / 'ablation_preliminary.csv'
OUT_SEEDS_CSV = ROOT / 'paper' / 'results' / 'ablation_seeds.csv'


def run_name_for(cond: str, seed: int) -> str:
    return f'research_{cond}_fruit' if seed == 1 else f'research_{cond}_fruit_s{seed}'


def _metrics(run_name: str, condition: str) -> dict:
    report_path = pipeline.GENERATED_ROOT / run_name / 'report.json'
    if not report_path.exists():
        return {
            'condition': condition, 'run_id': run_name, 'n': 0,
            'pass_rate': None, 'needs_review_rate': None, 'failed_rate': None,
            'mean_iters': None, 'mean_style': None, 'mean_function': None,
            'mean_cohesion': None, 'mean_progression': None,
            'cutout_fail_rate': None,
        }
    r = json.loads(report_path.read_text(encoding='utf-8'))
    results = [r['results'][n] for n in ASSETS if n in (r.get('results') or {})]
    n = len(results)
    if n == 0:
        return {'condition': condition, 'run_id': run_name, 'n': 0}

    def rate(st: str) -> float:
        return round(sum(1 for x in results if x.get('status') == st) / n, 3)

    iters = [x['iters'] for x in results if isinstance(x.get('iters'), int)]
    bags: dict[str, list[float]] = {
        'style_score': [], 'function_score': [],
        'cohesion_score': [], 'progression_score': [],
    }
    cutout_fail = 0
    scored = 0
    for x in results:
        v = x.get('verdict') or {}
        if v.get('skipped_critic'):
            continue
        scored += 1
        for k, bag in bags.items():
            if isinstance(v.get(k), (int, float)):
                bag.append(float(v[k]))
        if v.get('cutout_ok') is False:
            cutout_fail += 1

    def mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 2) if xs else None

    return {
        'condition': condition,
        'run_id': run_name,
        'n': n,
        'pass_rate': rate('pass'),
        'needs_review_rate': rate('needs_review'),
        'failed_rate': rate('failed'),
        'mean_iters': mean([float(i) for i in iters]),
        'mean_style': mean(bags['style_score']),
        'mean_function': mean(bags['function_score']),
        'mean_cohesion': mean(bags['cohesion_score']),
        'mean_progression': mean(bags['progression_score']),
        'cutout_fail_rate': round(cutout_fail / scored, 3) if scored else None,
    }


def _aggregate(condition: str, per_seed: list[dict]) -> dict:
    """Mean +/- std across seeds for the headline metrics (ignores empty runs)."""
    valid = [r for r in per_seed if r.get('n')]
    out: dict = {'condition': condition, 'n_seeds': len(valid)}
    metrics = [
        'pass_rate', 'needs_review_rate', 'failed_rate', 'mean_iters',
        'mean_style', 'mean_function', 'mean_cohesion', 'mean_progression',
        'cutout_fail_rate',
    ]
    for m in metrics:
        vals = [r[m] for r in valid if isinstance(r.get(m), (int, float))]
        if vals:
            out[f'{m}_mean'] = round(statistics.mean(vals), 3)
            out[f'{m}_std'] = round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0
        else:
            out[f'{m}_mean'] = None
            out[f'{m}_std'] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description='Fruit × 3dCartoonSimple research ablations')
    ap.add_argument('--conditions', default='B1,B2,B3',
                    help='Comma-separated B0,B1,B2,B3 (default B1,B2,B3)')
    ap.add_argument('--seeds', type=int, default=1,
                    help='Number of independent runs per condition (default 1)')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--skip-generate', action='store_true',
                    help='Only recompute CSVs from existing reports')
    args = ap.parse_args()

    conditions = [c.strip().upper() for c in args.conditions.split(',') if c.strip()]
    for c in conditions:
        pipeline.resolve_ablation(c)  # validate
    seeds = list(range(1, max(1, args.seeds) + 1))

    # Sanity: assets exist in manifest
    names = {a['name'] for a in build_manifest()}
    missing = [n for n in ASSETS if n not in names]
    if missing:
        raise SystemExit(f'Assets missing from manifest: {missing}')

    seed_rows = []   # one row per (condition, seed)
    agg_rows = []    # one row per condition (mean/std across seeds)
    for cond in conditions:
        per_seed = []
        for seed in seeds:
            run_name = run_name_for(cond, seed)
            if not args.skip_generate:
                print(f'\n=== {cond} seed {seed} → {run_name} ===', flush=True)
                pipeline.run(
                    style_text=STYLE,
                    run_name=run_name,
                    asset_names=ASSETS,
                    image_model=gemini_api.DEFAULT_IMAGE_MODEL,
                    critic_model=gemini_api.DEFAULT_CRITIC_MODEL,
                    force=args.force,
                    dry_run=args.dry_run,
                    mode=MODE,
                    theme_text=THEME,
                    reference_image=False,
                    expand_theme=True,
                    refine_style=True,
                    ablation=cond,
                    source='research_ablation',
                )
            m = _metrics(run_name, cond)
            m['seed'] = seed
            per_seed.append(m)
            seed_rows.append(m)
        agg_rows.append(_aggregate(cond, per_seed))

    if args.dry_run and not args.skip_generate:
        print('[dry-run] skip writing ablation CSVs (no results yet)')
        return

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    # Per-seed CSV (full detail)
    seed_keys = ['condition', 'seed', 'run_id', 'n', 'pass_rate', 'needs_review_rate',
                 'failed_rate', 'mean_iters', 'mean_style', 'mean_function',
                 'mean_cohesion', 'mean_progression', 'cutout_fail_rate']
    with OUT_SEEDS_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=seed_keys, extrasaction='ignore')
        w.writeheader()
        w.writerows(seed_rows)
    print(f'\nWrote {OUT_SEEDS_CSV}')

    # Headline CSV: if multi-seed → aggregate; else keep flat per-condition (back-compat)
    if len(seeds) > 1:
        keys = list(agg_rows[0].keys()) if agg_rows else []
        with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(agg_rows)
        print(f'Wrote {OUT_CSV} (mean±std over {len(seeds)} seeds)')
        for row in agg_rows:
            print(row)
    else:
        flat = [{k: v for k, v in r.items() if k != 'seed'} for r in seed_rows]
        keys = list(flat[0].keys()) if flat else []
        with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)
        print(f'Wrote {OUT_CSV}')
        for row in flat:
            print(row)


if __name__ == '__main__':
    main()
