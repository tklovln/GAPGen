#!/usr/bin/env python3
"""
Multi-seed replication for Pet/Ocean/Steampunk x B0/B1 (Fruit methodology:
3 independent seeds, distinct run names, since the Gemini image API has no
seed parameter — see research_ablation.py).

Run names: seed 1 = research_{cond}_{slug} (already exists),
seeds >=2 = research_{cond}_{slug}_s{N} (same convention as fruit_s2/_s3).

Usage:
  python scripts/research_seed_replication.py --dry-run
  python scripts/research_seed_replication.py            # seeds 2,3 x B0,B1 x 3 themes
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from art_pipeline import gemini_api, pipeline  # noqa: E402
from scripts.research_multi_theme import ASSETS, COMBOS  # noqa: E402

SLUGS = ['pet', 'ocean', 'steampunk']
CONDITIONS = ['B0', 'B1']
COMBO = {c['slug']: c for c in COMBOS}


def run_name(cond: str, slug: str, seed: int) -> str:
    base = f'research_{cond}_{slug}'
    return base if seed == 1 else f'{base}_s{seed}'


def complete(rname: str) -> bool:
    sprites = pipeline.GENERATED_ROOT / rname / 'sprites'
    return sprites.is_dir() and sum(1 for n in ASSETS if (sprites / f'{n}.png').exists()) == len(ASSETS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='2,3')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(',')]

    failures = []
    for slug in SLUGS:
        combo = COMBO[slug]
        for cond in CONDITIONS:
            for seed in seeds:
                rname = run_name(cond, slug, seed)
                if complete(rname):
                    print(f'[skip] {rname} already complete (12/12)', flush=True)
                    continue
                print(f'\n=== {cond} x {slug} seed {seed} -> {rname} ===', flush=True)
                for attempt in (1, 2):  # retry once, pipeline resumes passed assets
                    try:
                        pipeline.run(
                            style_text=combo['style'],
                            run_name=rname,
                            asset_names=ASSETS,
                            image_model=gemini_api.DEFAULT_IMAGE_MODEL,
                            critic_model=gemini_api.DEFAULT_CRITIC_MODEL,
                            force=False,
                            dry_run=args.dry_run,
                            mode='theme_swap',
                            theme_text=combo['theme'],
                            reference_image=False,
                            expand_theme=True,
                            refine_style=True,
                            ablation=cond,
                            source='research_seed_replication',
                        )
                        break
                    except Exception:  # noqa: BLE001
                        traceback.print_exc()
                        if attempt == 2:
                            failures.append(rname)
                            print(f'[FAIL] {rname} after retry, continuing', flush=True)
                if not args.dry_run and not complete(rname):
                    if rname not in failures:
                        failures.append(rname)
                    print(f'[WARN] {rname} incomplete', flush=True)

    print(f'\nDone. failures={failures or "none"}', flush=True)
    if failures:
        sys.exit(1)


if __name__ == '__main__':
    main()
