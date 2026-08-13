#!/usr/bin/env python3
"""Scan generated_art/*/report.json → paper/results/retrospective_summary.{csv,md}."""

from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GEN = ROOT / 'generated_art'
OUT = ROOT / 'paper' / 'results'

SCOPE_NAMES = {
    'Red', 'Grn', 'Blu', 'Yel', 'Pur',
    'Soda0d', 'Soda90', 'LtBl', 'TNT', 'TrPr',
    'Crt1', 'Crt2', 'Crt3', 'Crt4',
}
H3_ALIGN = {
    'fruit_3dCartoonSimple': 'mismatch_theme_field_Alien_folder_fruit — retrospective only',
    'cat_3dCartoonSimple': 'aligns_secondary_Pet',
    'ocean_3dCartoonSimple': 'optional_demo',
    'SteamPunk_3dCartoonSimple': 'optional_demo',
}


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 2) if xs else None


def summarize_run(run_dir: pathlib.Path) -> dict:
    report_path = run_dir / 'report.json'
    base = {
        'run': run_dir.name,
        'has_report': report_path.exists(),
        'h3_note': H3_ALIGN.get(run_dir.name, 'not_in_scope_table'),
        'n_sprites_on_disk': (
            len(list((run_dir / 'sprites').glob('*.png')))
            if (run_dir / 'sprites').is_dir() else 0
        ),
    }
    if not report_path.exists():
        return {**base, 'n_results': 0}

    r = json.loads(report_path.read_text(encoding='utf-8'))
    results = r.get('results') or {}
    statuses: list[str] = []
    iters: list[int] = []
    score_bags: dict[str, list[float]] = {
        k: [] for k in (
            'style_score', 'function_score', 'cohesion_score',
            'progression_score', 'reasonableness_score',
        )
    }
    cutout_fails = 0
    scope_n = scope_pass = scope_nr = 0

    for name, entry in results.items():
        if not isinstance(entry, dict):
            continue
        st = entry.get('status') or ''
        statuses.append(st)
        it = entry.get('iters')
        if isinstance(it, int):
            iters.append(it)
        v = entry.get('verdict') or {}
        for k, bag in score_bags.items():
            if isinstance(v.get(k), (int, float)):
                bag.append(float(v[k]))
        if v.get('cutout_ok') is False:
            cutout_fails += 1
        if name in SCOPE_NAMES:
            scope_n += 1
            if st == 'pass':
                scope_pass += 1
            elif st == 'needs_review':
                scope_nr += 1

    n = len(statuses)

    def rate(status: str) -> float | None:
        return round(statuses.count(status) / n, 3) if n else None

    return {
        **base,
        'style': (r.get('style') or '')[:80],
        'theme': r.get('theme'),
        'mode': r.get('generation_mode'),
        'ablation': (r.get('ablation') or {}).get('name') if isinstance(r.get('ablation'), dict)
        else r.get('ablation'),
        'image_model': r.get('image_model'),
        'critic_model': r.get('critic_model'),
        'n_results': n,
        'pass_rate': rate('pass'),
        'needs_review_rate': rate('needs_review'),
        'failed_rate': rate('failed'),
        'mean_iters': _mean([float(x) for x in iters]),
        'mean_style': _mean(score_bags['style_score']),
        'mean_function': _mean(score_bags['function_score']),
        'mean_cohesion': _mean(score_bags['cohesion_score']),
        'mean_progression': _mean(score_bags['progression_score']),
        'mean_reasonableness': _mean(score_bags['reasonableness_score']),
        'cutout_fail_count': cutout_fails,
        'scope_subset_n': scope_n,
        'scope_pass': scope_pass,
        'scope_needs_review': scope_nr,
        'scope_pass_rate': round(scope_pass / scope_n, 3) if scope_n else None,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for run_dir in sorted(GEN.iterdir()):
        if run_dir.is_dir() and not run_dir.name.startswith('_'):
            rows.append(summarize_run(run_dir))

    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)

    csv_path = OUT / 'retrospective_summary.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    md = [
        '# Retrospective summary (existing generated_art runs)',
        '',
        'Regenerate: `python scripts/research_retrospective.py`',
        '',
        '## H3 notes',
        '',
        '- Primary Fruit ablation → new `research_B*_fruit` runs only.',
        '- `fruit_3dCartoonSimple` report theme=`Alien` → retrospective/qualitative only.',
        '- Scope subset = elements + powerups + crate names from SCOPE.md.',
        '',
        '| run | theme | ablation | n | pass | needs_review | mean_iters | scope_pass_rate | h3_note |',
        '|-----|-------|----------|---|------|--------------|------------|-----------------|---------|',
    ]
    for row in rows:
        md.append(
            f"| {row['run']} | {row.get('theme')} | {row.get('ablation')} | {row.get('n_results')} | "
            f"{row.get('pass_rate')} | {row.get('needs_review_rate')} | {row.get('mean_iters')} | "
            f"{row.get('scope_pass_rate')} | {row.get('h3_note')} |"
        )
    md_path = OUT / 'retrospective_summary.md'
    md_path.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'Wrote {csv_path}')
    print(f'Wrote {md_path}')


if __name__ == '__main__':
    main()
