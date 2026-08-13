#!/usr/bin/env python3
"""
Post-hoc cohesion/progression backfill for the B0/B1/B2 ablation conditions.

B0/B1/B2 ship sprites under programmatic-only gates and never invoke the
gameplay-consistency critic, so their report.json carries no cohesion/progression
scores (tab:ablation shows n/a). This script re-runs the *same* critic
(gemini_api.critique_image, mode='theme_swap') over the already-finalized sprites
in generated_art/research_{cond}_fruit[/_s{N}]/sprites/, purely as a measurement.
It does NOT regenerate images or change any gate — it only asks the critic to
score the shipped tiles so the two columns can be reported for every condition.

Family anchors and the crate stage chain mirror the B3 setup exactly:
  elements anchor=Red, powerups anchor=Soda0d, crate anchor=Crt4,
  crate progression chain Crt4->Crt3->Crt2->Crt1 (ref_from from the run's stage_plans).
As in B3, the anchor tile of each family has no cohesion score, and only crate
non-anchor stages have a progression score.

Usage:
  python scripts/critic_backfill.py --conditions B0,B1,B2 --seeds 3
  python scripts/critic_backfill.py --conditions B0 --seeds 1 --dry-run   # list plan, no API
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from art_pipeline import gemini_api, pipeline  # noqa: E402
from art_pipeline.manifest import build_manifest  # noqa: E402
from art_pipeline.visual_guidance import get_family_anchor_asset  # noqa: E402

STYLE = (
    '3D Disney Cartoon Style, Simple design, Clean illustrations, '
    'Intuitive icon, highly recognizable'
)
ASSETS = [
    'Red', 'Grn', 'Blu', 'Yel', 'Pur',
    'Soda0d', 'Soda90', 'LtBl',
    'Crt4', 'Crt3', 'Crt2', 'Crt1',
]


def run_name_for(cond: str, seed: int) -> str:
    return f'research_{cond}_fruit' if seed == 1 else f'research_{cond}_fruit_s{seed}'


def _crate_prev_map(report: dict) -> dict[str, str | None]:
    """name -> ref_from, read from the run's own crate stage plan."""
    stages = ((report.get('stage_plans') or {}).get('crate') or {}).get('stages') or {}
    return {name: spec.get('ref_from') for name, spec in stages.items()}


def backfill_run(client, run_name: str, manifest: dict) -> dict:
    """Score every shipped sprite of one run; return {name: verdict-ish dict}."""
    run_dir = pipeline.GENERATED_ROOT / run_name
    sprites = run_dir / 'sprites'
    report = json.loads((run_dir / 'report.json').read_text(encoding='utf-8'))
    prev_of = _crate_prev_map(report)

    # anchor image bytes per family (the shipped anchor sprite)
    anchor_bytes: dict[str, bytes] = {}
    for fam in {manifest[n]['family'] for n in ASSETS if n in manifest}:
        anchor_name = get_family_anchor_asset(fam)
        p = sprites / manifest[anchor_name]['file']
        if p.is_file():
            anchor_bytes[fam] = p.read_bytes()

    out: dict[str, dict] = {}
    for name in ASSETS:
        asset = manifest.get(name)
        if not asset:
            continue
        img_path = sprites / asset['file']
        if not img_path.is_file():
            continue
        fam = asset['family']
        is_anchor = name == get_family_anchor_asset(fam)
        # cohesion: every non-anchor family member gets the family anchor (matches B3)
        family_anchor = None if is_anchor else anchor_bytes.get(fam)
        # progression: crate stages whose stage plan names a previous stage
        prev_name = prev_of.get(name)
        prev_stage = None
        if prev_name and manifest.get(prev_name):
            pp = sprites / manifest[prev_name]['file']
            prev_stage = pp.read_bytes() if pp.is_file() else None

        verdict = gemini_api.critique_image(
            client, gemini_api.DEFAULT_CRITIC_MODEL, None, img_path.read_bytes(),
            STYLE, asset, None, mode='theme_swap',
            family_anchor=family_anchor, prev_stage_image=prev_stage)
        out[name] = {
            'cohesion_score': verdict.get('cohesion_score'),
            'progression_score': verdict.get('progression_score'),
            'style_score': verdict.get('style_score'),
            'function_score': verdict.get('function_score'),
        }
        print(f"    {name:7s} coh={out[name]['cohesion_score']} "
              f"prog={out[name]['progression_score']}", flush=True)
    return out


def _mean(xs: list[float]) -> float | None:
    return round(statistics.mean(xs), 2) if xs else None


def main() -> None:
    ap = argparse.ArgumentParser(description='Post-hoc critic backfill for B0/B1/B2')
    ap.add_argument('--conditions', default='B0,B1,B2')
    ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true', help='List sprites/plan, no API calls')
    args = ap.parse_args()

    conditions = [c.strip().upper() for c in args.conditions.split(',') if c.strip()]
    seeds = list(range(1, max(1, args.seeds) + 1))
    manifest = {a['name']: a for a in build_manifest()}

    client = None if args.dry_run else gemini_api.get_client()

    summary: dict[str, dict] = {}
    for cond in conditions:
        seed_coh: list[float] = []   # per-seed mean cohesion
        seed_prog: list[float] = []  # per-seed mean progression
        for seed in seeds:
            run_name = run_name_for(cond, seed)
            if not (pipeline.GENERATED_ROOT / run_name / 'report.json').exists():
                print(f'[skip] {run_name}: no report.json')
                continue
            print(f'\n=== {cond} seed {seed} -> {run_name} ===', flush=True)
            if args.dry_run:
                continue
            scores = backfill_run(client, run_name, manifest)
            (pipeline.GENERATED_ROOT / run_name / 'critic_backfill.json').write_text(
                json.dumps(scores, ensure_ascii=False, indent=2), encoding='utf-8')
            coh = [v['cohesion_score'] for v in scores.values()
                   if isinstance(v['cohesion_score'], (int, float))]
            prog = [v['progression_score'] for v in scores.values()
                    if isinstance(v['progression_score'], (int, float))]
            if coh:
                seed_coh.append(statistics.mean(coh))
            if prog:
                seed_prog.append(statistics.mean(prog))
        if args.dry_run:
            continue
        summary[cond] = {
            'cohesion_mean': _mean(seed_coh),
            'cohesion_std': round(statistics.pstdev(seed_coh), 2) if len(seed_coh) > 1 else 0.0,
            'progression_mean': _mean(seed_prog),
            'progression_std': round(statistics.pstdev(seed_prog), 2) if len(seed_prog) > 1 else 0.0,
            'n_seeds': len(seed_coh),
        }

    if args.dry_run:
        return
    out_path = ROOT / 'paper' / 'results' / 'critic_backfill.json'
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n===== SUMMARY (mean +/- std across seeds) =====')
    for cond, s in summary.items():
        print(f"{cond}: cohesion {s['cohesion_mean']}+/-{s['cohesion_std']}  "
              f"progression {s['progression_mean']}+/-{s['progression_std']}  "
              f"(n_seeds={s['n_seeds']})")
    print(f'Wrote {out_path}')


if __name__ == '__main__':
    main()
