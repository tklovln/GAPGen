#!/usr/bin/env python3
"""
Generate extra theme packs for research + human-eval (beyond Fruit).

Default: B3 only × 3 themes (Pet / Ocean / Steampunk) with locked cartoon style.
Optional: --conditions B1,B3 · --include-ghibli · --dry-run

Usage:
  PYTHONUNBUFFERED=1 python scripts/research_multi_theme.py
  PYTHONUNBUFFERED=1 python scripts/research_multi_theme.py --conditions B3 --force
  python scripts/research_multi_theme.py --skip-generate --export-survey
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from art_pipeline import gemini_api, pipeline  # noqa: E402
from art_pipeline.manifest import build_manifest  # noqa: E402

# Reuse Fruit ablation asset subset (SCOPE.md)
ASSETS = [
    'Red', 'Grn', 'Blu', 'Yel', 'Pur',
    'Soda0d', 'Soda90', 'LtBl',
    'Crt4', 'Crt3', 'Crt2', 'Crt1',
]

CARTOON = (
    '3D Disney Cartoon Style, Simple design, Clean illustrations, '
    'Intuitive icon, highly recognizable'
)
GHIBLI = 'Ghibli Style, soft watercolor-like lighting, gentle shapes, highly recognizable icons'

# At least 3 new theme combos (+ optional Ghibli Pet from prompt.txt)
COMBOS = [
    {
        'slug': 'pet',
        'theme': 'Pet',
        'style': CARTOON,
        'style_label': '3dCartoonSimple',
        'label_zh': '寵物',
    },
    {
        'slug': 'ocean',
        'theme': 'Ocean',
        'style': CARTOON,
        'style_label': '3dCartoonSimple',
        'label_zh': '海洋',
    },
    {
        'slug': 'steampunk',
        'theme': 'Steampunk',
        'style': CARTOON,
        'style_label': '3dCartoonSimple',
        'label_zh': '蒸汽龐克',
    },
    {
        'slug': 'pet_ghibli',
        'theme': 'Pet',
        'style': GHIBLI,
        'style_label': 'ghibli',
        'label_zh': '寵物（吉卜力風）',
        'optional': True,
    },
]

OUT_CSV = ROOT / 'paper' / 'results' / 'ablation_multi_theme.csv'
OUT_MANIFEST = ROOT / 'paper' / 'human_eval' / 'themes.json'
SURVEY_ASSETS = ROOT / 'paper' / 'human_eval' / 'assets' / 'themes'


def run_name(cond: str, slug: str) -> str:
    return f'research_{cond}_{slug}'


def _metrics(run: str, condition: str, slug: str, theme: str, style_label: str) -> dict:
    report_path = pipeline.GENERATED_ROOT / run / 'report.json'
    base = {
        'condition': condition, 'slug': slug, 'theme': theme,
        'style_label': style_label, 'run_id': run, 'n': 0,
        'pass_rate': None, 'needs_review_rate': None, 'failed_rate': None,
        'mean_iters': None, 'mean_style': None, 'mean_function': None,
        'mean_cohesion': None, 'mean_progression': None, 'cutout_fail_rate': None,
    }
    if not report_path.exists():
        return base
    r = json.loads(report_path.read_text(encoding='utf-8'))
    results = [r['results'][n] for n in ASSETS if n in (r.get('results') or {})]
    n = len(results)
    if n == 0:
        return base

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

    base.update({
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
    })
    return base


def export_survey_assets(
    slugs: list[str],
    condition: str = 'B3',
    *,
    conditions: list[str] | None = None,
) -> dict:
    """Export grids for B3 (theme pick) and B1/B2/B3 per-theme ablation compares."""
    from PIL import Image, ImageDraw

    SURVEY_ASSETS.mkdir(parents=True, exist_ok=True)
    elements = ['Red', 'Grn', 'Blu', 'Yel', 'Pur']
    powerups = ['Soda0d', 'Soda90', 'LtBl']
    crates = ['Crt4', 'Crt3', 'Crt2', 'Crt1']
    singles = ['Red', 'Blu', 'Soda0d', 'Soda90', 'Crt4', 'Crt1', 'Yel', 'LtBl']
    export_conds = conditions or [condition]

    def strip(src: pathlib.Path, names: list[str], out: pathlib.Path, cell: int = 96) -> bool:
        pad = 8
        paths = [src / f'{n}.png' for n in names]
        if not all(p.exists() for p in paths):
            return False
        W = pad + len(names) * (cell + pad)
        H = pad * 2 + cell
        canvas = Image.new('RGB', (W, H), (250, 250, 252))
        x = pad
        for p in paths:
            im = Image.open(p).convert('RGBA')
            im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
            bg = Image.new('RGBA', (cell, cell), (255, 255, 255, 255))
            bg.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
            canvas.paste(bg.convert('RGB'), (x, pad))
            x += cell + pad
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, optimize=True)
        return True

    def contact_grid(src: pathlib.Path, out: pathlib.Path) -> bool:
        rows = [
            ('elements', elements),
            ('powerups', powerups),
            ('crate', crates),
        ]
        cell, pad, label_h = 112, 8, 22
        max_cols = max(len(c) for _, c in rows)
        W = pad + max_cols * (cell + pad)
        H = pad + len(rows) * (cell + label_h + pad)
        canvas = Image.new('RGB', (W, H), (245, 245, 248))
        draw = ImageDraw.Draw(canvas)
        y = pad
        for fam, names in rows:
            draw.text((pad, y), fam, fill=(40, 40, 50))
            y += label_h
            x = pad
            for name in names:
                p = src / f'{name}.png'
                if not p.exists():
                    return False
                im = Image.open(p).convert('RGBA')
                im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
                tile = Image.new('RGB', (cell, cell), (255, 255, 255))
                tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
                canvas.paste(tile, (x, y))
                x += cell + pad
            y += cell + pad
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, optimize=True)
        return True

    def export_70(src: pathlib.Path, dst_dir: pathlib.Path, names: list[str], size: int = 140) -> int:
        n_ok = 0
        dst_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            p = src / f'{name}.png'
            if not p.exists():
                continue
            im = Image.open(p).convert('RGBA')
            im.thumbnail((size, size), Image.Resampling.LANCZOS)
            tile = Image.new('RGBA', (size, size), (248, 248, 250, 255))
            for yy in range(0, size, 8):
                for xx in range(0, size, 8):
                    c = (228, 228, 232, 255) if ((xx // 8) + (yy // 8)) % 2 == 0 else (255, 255, 255, 255)
                    ImageDraw.Draw(tile).rectangle([xx, yy, xx + 7, yy + 7], fill=c)
            tile.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
            tile.convert('RGB').save(dst_dir / f'{name}.png', optimize=True)
            n_ok += 1
        return n_ok

    def export_run(slug: str, label_zh: str, theme: str, style_label: str, cond: str) -> dict | None:
        src = pipeline.GENERATED_ROOT / run_name(cond, slug) / 'sprites'
        if slug == 'fruit':
            src = pipeline.GENERATED_ROOT / f'research_{cond}_fruit' / 'sprites'
        if not src.is_dir():
            return None
        # B3 also mirrored at themes/{slug}/ for Task 5
        dst = SURVEY_ASSETS / slug / cond
        ok = contact_grid(src, dst / 'all.png')
        ok = strip(src, elements, dst / 'elements.png') and ok
        ok = strip(src, powerups, dst / 'powerups.png') and ok
        ok = strip(src, crates, dst / 'crate.png') and ok
        export_70(src, dst / 'sprites', singles)
        if cond == 'B3':
            root = SURVEY_ASSETS / slug
            contact_grid(src, root / 'all.png')
            strip(src, elements, root / 'elements.png')
            strip(src, powerups, root / 'powerups.png')
            strip(src, crates, root / 'crate.png')
            export_70(src, root / 'sprites', singles)
        if not ok:
            print(f'[export] incomplete {slug}/{cond}', flush=True)
            return None
        print(f'[export] {slug}/{cond} → {dst}', flush=True)
        return {
            'slug': slug,
            'theme': theme,
            'label_zh': label_zh,
            'style_label': style_label,
            'run_id': run_name(cond, slug) if slug != 'fruit' else f'research_{cond}_fruit',
            'condition': cond,
        }

    combo_by_slug = {c['slug']: c for c in COMBOS}
    combo_by_slug['fruit'] = {
        'slug': 'fruit', 'theme': 'Fruit', 'label_zh': '水果',
        'style_label': '3dCartoonSimple',
    }
    all_slugs = ['fruit'] + [s for s in slugs if s != 'fruit']

    # Always try B1/B2/B3 when 12 sprites exist (ignore incomplete leftovers)
    want = set(export_conds) | {'B1', 'B2', 'B3'}
    theme_entries = []
    for slug in all_slugs:
        combo = combo_by_slug.get(slug)
        if not combo:
            continue
        available = []
        for cond in ('B1', 'B2', 'B3'):
            if cond not in want:
                continue
            src = pipeline.GENERATED_ROOT / (
                f'research_{cond}_fruit' if slug == 'fruit' else run_name(cond, slug)
            ) / 'sprites'
            if not src.is_dir():
                continue
            n_png = len(list(src.glob('*.png')))
            if n_png < 12:
                print(f'[export] skip incomplete {slug}/{cond} ({n_png}/12)', flush=True)
                continue
            meta = export_run(
                slug, combo['label_zh'], combo['theme'], combo['style_label'], cond,
            )
            if meta:
                available.append(cond)
                # Fruit also mirrors into legacy survey paths used by Task 1–3
                if slug == 'fruit':
                    grids = ROOT / 'paper' / 'human_eval' / 'assets' / 'grids'
                    strip(src, elements, grids / f'{cond}_elements.png')
                    strip(src, powerups, grids / f'{cond}_powerups.png')
                    strip(src, crates, grids / f'{cond}_crate.png')
                    contact_grid(src, grids / f'{cond}_all.png')
                    export_70(src, ROOT / 'paper' / 'human_eval' / 'assets' / cond, ASSETS)
        if available:
            theme_entries.append({
                'slug': slug,
                'theme': combo['theme'],
                'label_zh': combo['label_zh'],
                'style_label': combo['style_label'],
                'conditions': available,
                'run_id': (
                    f'research_B3_fruit' if slug == 'fruit' else run_name('B3', slug)
                ),
                'condition': 'B3',
            })

    ablation_themes = [
        t['slug'] for t in theme_entries
        if ('B1' in t['conditions'] and 'B3' in t['conditions'])
        or ('B1' in t['conditions'] and 'B2' in t['conditions'])
    ]

    payload = {
        'version': 2,
        'baseline_slug': 'fruit',
        'themes': theme_entries,
        'ablation_compare_themes': ablation_themes,
    }
    OUT_MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {OUT_MANIFEST}', flush=True)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description='Multi-theme research packs for eval + survey')
    ap.add_argument('--conditions', default='B3',
                    help='Ablation conditions (default B3; e.g. B1,B3)')
    ap.add_argument('--slugs', default='pet,ocean',
                    help='Comma-separated combo slugs (default pet,ocean; steampunk optional)')
    ap.add_argument('--include-ghibli', action='store_true',
                    help='Also run pet_ghibli (Pet × Ghibli)')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--skip-generate', action='store_true')
    ap.add_argument('--export-survey', action='store_true',
                    help='Export grids + themes.json after runs (default on when generating)')
    ap.add_argument('--no-export-survey', action='store_true')
    args = ap.parse_args()

    conditions = [c.strip().upper() for c in args.conditions.split(',') if c.strip()]
    for c in conditions:
        pipeline.resolve_ablation(c)

    slugs = [s.strip() for s in args.slugs.split(',') if s.strip()]
    if args.include_ghibli and 'pet_ghibli' not in slugs:
        slugs.append('pet_ghibli')

    combo_by_slug = {c['slug']: c for c in COMBOS}
    unknown = [s for s in slugs if s not in combo_by_slug]
    if unknown:
        raise SystemExit(f'Unknown slugs {unknown}; choose from {sorted(combo_by_slug)}')

    names = {a['name'] for a in build_manifest()}
    missing = [n for n in ASSETS if n not in names]
    if missing:
        raise SystemExit(f'Assets missing from manifest: {missing}')

    rows = []
    for slug in slugs:
        combo = combo_by_slug[slug]
        for cond in conditions:
            rname = run_name(cond, slug)
            if not args.skip_generate:
                print(f'\n=== {cond} × {slug} ({combo["theme"]} / {combo["style_label"]}) → {rname} ===',
                      flush=True)
                pipeline.run(
                    style_text=combo['style'],
                    run_name=rname,
                    asset_names=ASSETS,
                    image_model=gemini_api.DEFAULT_IMAGE_MODEL,
                    critic_model=gemini_api.DEFAULT_CRITIC_MODEL,
                    force=args.force,
                    dry_run=args.dry_run,
                    mode='theme_swap',
                    theme_text=combo['theme'],
                    reference_image=False,
                    expand_theme=True,
                    refine_style=True,
                    ablation=cond,
                    source='research_multi_theme',
                )
            rows.append(_metrics(
                rname, cond, slug, combo['theme'], combo['style_label'],
            ))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not (args.dry_run and not args.skip_generate):
        keys = list(rows[0].keys()) if rows else []
        with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f'\nWrote {OUT_CSV}', flush=True)
        for row in rows:
            print(row, flush=True)

    do_export = args.export_survey or (not args.no_export_survey and not args.dry_run)
    if do_export and not args.dry_run:
        export_survey_assets(slugs, conditions=conditions)


if __name__ == '__main__':
    main()
