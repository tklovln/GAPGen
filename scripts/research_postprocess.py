#!/usr/bin/env python3
"""After research_B*_fruit finishes: rebuild CSV + B1/B3 sprite grids."""

from __future__ import annotations

import csv
import json
import pathlib
import sys  

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.research_ablation import ASSETS, OUT_CSV, _metrics  # noqa: E402

FIG = ROOT / 'paper' / 'figures'
CONDITIONS = ['B0', 'B1', 'B2', 'B3']


def _font(size: int = 16):
    for p in (
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
    ):
        if pathlib.Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def write_csv(conditions: list[str] | None = None) -> pathlib.Path:
    conditions = conditions or ['B1', 'B2', 'B3']
    rows = [_metrics(f'research_{c}_fruit', c) for c in conditions]
    # drop empty optional B0 if missing
    rows = [r for r in rows if r.get('n')]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys()) if rows else []
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f'Wrote {OUT_CSV}')
    for r in rows:
        print(r)
    return OUT_CSV


def sprite_grid(run_name: str, out_name: str) -> pathlib.Path | None:
    sprites = ROOT / 'generated_art' / run_name / 'sprites'
    if not sprites.is_dir():
        print(f'skip grid: missing {sprites}')
        return None
    rows_spec = [
        ('elements', ['Red', 'Grn', 'Blu', 'Yel', 'Pur']),
        ('powerups', ['Soda0d', 'Soda90', 'LtBl']),
        ('crate', ['Crt4', 'Crt3', 'Crt2', 'Crt1']),
    ]
    cell, pad, label_h = 128, 8, 28
    max_cols = max(len(c) for _, c in rows_spec)
    W = pad + max_cols * (cell + pad)
    H = pad + len(rows_spec) * (cell + label_h + pad)
    canvas = Image.new('RGBA', (W, H), (245, 245, 248, 255))
    draw = ImageDraw.Draw(canvas)
    font = _font(16)
    y = pad
    missing = 0
    for fam, names in rows_spec:
        draw.text((pad, y), fam, fill=(40, 40, 50, 255), font=font)
        y += label_h
        x = pad
        for name in names:
            path = sprites / f'{name}.png'
            if path.exists():
                im = Image.open(path).convert('RGBA')
                im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
                tile = Image.new('RGBA', (cell, cell), (255, 255, 255, 255))
                for yy in range(0, cell, 8):
                    for xx in range(0, cell, 8):
                        c = (220, 220, 225, 255) if ((xx // 8) + (yy // 8)) % 2 == 0 else (255, 255, 255, 255)
                        ImageDraw.Draw(tile).rectangle([xx, yy, xx + 7, yy + 7], fill=c)
                tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
                canvas.paste(tile, (x, y))
            else:
                missing += 1
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(180, 80, 80))
            x += cell + pad
        y += cell + pad
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / out_name
    canvas.convert('RGB').save(out, 'PNG')
    print(f'Wrote {out} (missing tiles={missing})')
    return out


def status() -> None:
    for c in CONDITIONS:
        run = f'research_{c}_fruit'
        report = ROOT / 'generated_art' / run / 'report.json'
        if not report.exists():
            print(f'{run}: missing')
            continue
        r = json.loads(report.read_text(encoding='utf-8'))
        res = r.get('results') or {}
        done = [n for n in ASSETS if n in res]
        print(
            f'{run}: {len(done)}/{len(ASSETS)} '
            f"pass={sum(1 for n in done if res[n].get('status')=='pass')} "
            f"review={sum(1 for n in done if res[n].get('status')=='needs_review')} "
            f"fail={sum(1 for n in done if res[n].get('status')=='failed')}"
        )


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--csv', action='store_true')
    ap.add_argument('--figures', action='store_true')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    if args.status or not any([args.csv, args.figures, args.all]):
        status()
    if args.csv or args.all:
        write_csv(['B1', 'B2', 'B3'])
        # include B0 if present
        if (ROOT / 'generated_art' / 'research_B0_fruit' / 'report.json').exists():
            b0 = _metrics('research_B0_fruit', 'B0')
            if b0.get('n'):
                rows = []
                with OUT_CSV.open(encoding='utf-8') as f:
                    rows = list(csv.DictReader(f))
                with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
                    w = csv.DictWriter(f, fieldnames=list(b0.keys()))
                    w.writeheader()
                    w.writerow(b0)
                    for row in rows:
                        w.writerow(row)
                print('Prepended B0 to CSV')
    if args.figures or args.all:
        sprite_grid('research_B1_fruit', 'sprites_grid_research_B1_fruit.png')
        sprite_grid('research_B3_fruit', 'sprites_grid_research_B3_fruit.png')
        sprite_grid('research_B2_fruit', 'sprites_grid_research_B2_fruit.png')


if __name__ == '__main__':
    main()
