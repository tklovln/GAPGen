#!/usr/bin/env python3
"""
Board-parse evaluation: can an observer read the game state off a rendered board?

Every other metric in this repo asks a model for an opinion (role accuracy,
pairwise preference) or measures a similarity whose good direction is unclear
(cohesion). This one has an answer key that predates the question: the level
JSON that `match_engine` actually plays, with per-cell tile ids grounded in
`tile_defs.TILE_REGISTRY`.

Two parsers, neither of which is the generator's own family:
  template  — normalised cross-correlation against the pack's own sprites.
              Zero API cost, deterministic. Measures *pixel distinguishability*:
              if the correct template cannot win, those sprites are confusable.
  vlm       — a judge reads the board image cell by cell. Measures *semantic
              legibility* for a machine observer.

Anti-tautology note: template matching against the identical PNG at identical
scale is trivially 100% and meaningless. Rendering therefore goes through the
real pipeline losses -- downscale 512->cell px, board background, layer
compositing (bottom under, upper over) -- and matching happens on the composited
crop, not the source file. The `--cell` sweep is the evidence that the task is
non-trivial: accuracy must fall as cells shrink.

Usage:
  python scripts/board_parse_eval.py --self-check
  python scripts/board_parse_eval.py --packs human,fruit_3dCartoonSimple --parser template
  python scripts/board_parse_eval.py --packs human --parser template --cell 70,48,32,24
  python scripts/board_parse_eval.py --packs human --parser vlm --judge openai --levels 5
"""

from __future__ import annotations

import argparse
import base64
import collections
import io
import json
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.auto_eval import (  # noqa: E402
    HUMAN_SPRITES, asset_category, build_judge, resolve_run,
)

LEVELS = ROOT / 'godot_demo' / 'levels'
OUT = ROOT / 'paper' / 'results' / 'board_parse.json'
BG = (232, 226, 214)          # flat board background
GRID = (214, 206, 192)        # cell separator


def strip_instance(tile: str) -> str:
    """'Pool_lv5#2' -> 'Pool_lv5'. `#N` marks which 2x2 object a cell belongs to."""
    return tile.split('#', 1)[0]


def load_level(path: pathlib.Path) -> dict:
    d = json.loads(path.read_text(encoding='utf-8'))
    board = d['board']
    if not isinstance(board, dict):           # internal format: flat middle grid
        board = {'middle': board}
    return {'name': d.get('name', path.stem), 'rows': d['rows'], 'cols': d['cols'],
            'layers': {k: board[k] for k in ('bottom', 'middle', 'upper') if k in board}}


def cell_truth(level: dict, r: int, c: int) -> str | None:
    """Topmost drawn tile at (r,c), or None for an empty/void cell.

    `upper` (rope/mud) draws over `middle`, which draws over `bottom` (puddle),
    matching board.Cell. A void cell is not part of the board.
    """
    for lay in ('upper', 'middle', 'bottom'):
        grid = level['layers'].get(lay)
        if not grid or r >= len(grid) or c >= len(grid[r]):
            continue
        t = grid[r][c]
        if t and t != 'void':
            return strip_instance(t)
        if t == 'void' and lay == 'middle':
            return None
    return None


class SpriteBank:
    """Sprites for one pack, rendered down to a given cell size."""

    def __init__(self, src: pathlib.Path, cell: int):
        from PIL import Image

        self.cell = cell
        self.sprites: dict[str, Image.Image] = {}
        for p in sorted(src.glob('*.png')):
            im = Image.open(p).convert('RGBA')
            im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
            self.sprites[p.stem] = im

    def has(self, name: str) -> bool:
        return name in self.sprites

    def paste(self, canvas, name: str, x: int, y: int) -> None:
        im = self.sprites[name]
        canvas.alpha_composite(im, (x + (self.cell - im.width) // 2,
                                    y + (self.cell - im.height) // 2))


def render_board(level: dict, bank: SpriteBank):
    """Composite a board exactly as the engine layers it. Returns (img, cells)."""
    from PIL import Image, ImageDraw

    cell = bank.cell
    W, H = level['cols'] * cell, level['rows'] * cell
    canvas = Image.new('RGBA', (W, H), BG + (255,))
    draw = ImageDraw.Draw(canvas)
    for i in range(1, level['cols']):
        draw.line([(i * cell, 0), (i * cell, H)], fill=GRID, width=1)
    for i in range(1, level['rows']):
        draw.line([(0, i * cell), (W, i * cell)], fill=GRID, width=1)

    cells = []
    for r in range(level['rows']):
        for c in range(level['cols']):
            x, y = c * cell, r * cell
            drawn = None
            # bottom -> middle -> upper, so upper wins visually
            for lay in ('bottom', 'middle', 'upper'):
                grid = level['layers'].get(lay)
                if not grid or r >= len(grid) or c >= len(grid[r]):
                    continue
                t = grid[r][c]
                if not t or t == 'void':
                    continue
                name = strip_instance(t)
                if bank.has(name):
                    bank.paste(canvas, name, x, y)
                    drawn = name
            truth = cell_truth(level, r, c)
            if truth is not None and drawn is not None:
                cells.append({'r': r, 'c': c, 'truth': truth})
    return canvas.convert('RGB'), cells


# --------------------------------------------------------------------------- #
# Parser 1: template matching (deterministic, no API)
# --------------------------------------------------------------------------- #
def _ncc(a, b) -> float:
    """Normalised cross-correlation of two equal-size float arrays."""
    import numpy as np

    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom else 0.0


def parse_template(img, cells, bank: SpriteBank, candidates: list[str]) -> list[str]:
    """Pick the candidate sprite whose flattened-on-background render best matches."""
    import numpy as np
    from PIL import Image

    cell = bank.cell
    refs = {}
    for name in candidates:
        flat = Image.new('RGBA', (cell, cell), BG + (255,))
        bank.paste(flat, name, 0, 0)
        refs[name] = np.asarray(flat.convert('L'), dtype=np.float64)

    arr = np.asarray(img.convert('L'), dtype=np.float64)
    preds = []
    for cd in cells:
        y, x = cd['r'] * cell, cd['c'] * cell
        crop = arr[y:y + cell, x:x + cell]
        best, best_s = None, -2.0
        for name, ref in refs.items():
            if ref.shape != crop.shape:
                continue
            s = _ncc(crop, ref)
            if s > best_s:
                best, best_s = name, s
        preds.append(best or 'unmatched')
    return preds


# --------------------------------------------------------------------------- #
# Parser 2: VLM reads the board
# --------------------------------------------------------------------------- #
def parse_vlm(judge, img, cells, candidates: list[str]) -> list[str]:
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    coords = ', '.join(f'(r{cd["r"]},c{cd["c"]})' for cd in cells[:60])
    prompt = (
        'This is a Match-3 game board. Rows and columns are 0-indexed from the '
        'top-left. For each listed cell, name which of these tiles is drawn '
        f'there: {", ".join(sorted(candidates))}. '
        f'Cells: {coords}. '
        'JSON: {"cells":{"r<row>c<col>":"<tile name>", ...}}'
    )
    try:
        ans = judge.ask(prompt, [buf.getvalue()])
        got = ans.get('cells', {}) or {}
    except Exception as e:  # noqa: BLE001
        return [f'error:{type(e).__name__}'] * len(cells)
    return [str(got.get(f'r{cd["r"]}c{cd["c"]}', 'missing')) for cd in cells[:60]]


# --------------------------------------------------------------------------- #
def score(truths: list[str], preds: list[str]) -> dict:
    cats = asset_category()
    n = len(truths)
    exact = sum(t == p for t, p in zip(truths, preds))
    cat_ok = sum(cats.get(t) == cats.get(p) for t, p in zip(truths, preds))
    # A parser can decline to answer a cell ('missing') or return a name outside
    # the label space. Folding those into "wrong" hides a compliance problem as
    # an art-quality problem, so they are counted and reported separately.
    abstain = sum(p == 'missing' for p in preds)
    off_label = sum(p not in cats and p != 'missing' for p in preds)
    per_cat: dict[str, list[int]] = {}
    confusion: collections.Counter = collections.Counter()
    for t, p in zip(truths, preds):
        per_cat.setdefault(cats.get(t, '?'), []).append(int(t == p))
        if t != p:
            tag = 'missing' if p == 'missing' else cats.get(p, 'off_label')
            confusion[f'{cats.get(t,"?")}->{tag}'] += 1
    by_cat = {k: {'n': len(v), 'accuracy': round(sum(v) / len(v), 3)}
              for k, v in sorted(per_cat.items())}
    answered = n - abstain
    return {
        'n_cells': n,
        'cell_accuracy': round(exact / n, 4) if n else None,
        'category_accuracy': round(cat_ok / n, 4) if n else None,
        'accuracy_macro': (round(sum(c['accuracy'] for c in by_cat.values()) / len(by_cat), 4)
                           if by_cat else None),
        'abstain_rate': round(abstain / n, 4) if n else None,
        'off_label_rate': round(off_label / n, 4) if n else None,
        'accuracy_on_answered': round(exact / answered, 4) if answered else None,
        'by_category': by_cat,
        'top_confusions': dict(confusion.most_common(8)),
    }


def run_pack(pack: str, level_paths: list[pathlib.Path], cell: int,
             parser: str, judge=None, *, global_candidates: bool = True) -> dict:
    """Parse every sampled level with one pack's sprites.

    `global_candidates` is what keeps the task honest. Restricting candidates to
    the tiles present in the current level collapses most levels to a 1-3 way
    choice (many official levels use a single obstacle type), and everything
    scores ~1.0 regardless of art quality. The global set -- every tile that
    appears anywhere in the sample and exists in the pack -- keeps the label
    space fixed across levels, which is also what a real observer faces.
    """
    src = resolve_run(pack)
    bank = SpriteBank(src, cell)
    levels = [load_level(lp) for lp in level_paths]

    if global_candidates:
        pool = {cd['truth'] for lv in levels
                for cd in render_board(lv, bank)[1]}
        candidates = sorted(t for t in pool if bank.has(t))
    else:
        candidates = None

    truths: list[str] = []
    preds: list[str] = []
    for level in levels:
        img, cells = render_board(level, bank)
        cells = [cd for cd in cells if bank.has(cd['truth'])]
        if not cells:
            continue
        cand = candidates or sorted({cd['truth'] for cd in cells})
        if parser == 'template':
            got = parse_template(img, cells, bank, cand)
        else:
            cells = cells[:60]
            got = parse_vlm(judge, img, cells, cand)
        truths.extend(cd['truth'] for cd in cells)
        preds.extend(got)
    out = score(truths, preds)
    out.update({'pack': pack, 'cell_px': cell, 'parser': parser,
                'n_levels': len(level_paths), 'n_candidates': len(candidates or []),
                'global_candidates': global_candidates})
    return out


def self_check() -> None:
    """Offline checks: layering, instance stripping, and NCC sanity."""
    import numpy as np

    assert strip_instance('Pool_lv5#2') == 'Pool_lv5'
    assert strip_instance('Crt2') == 'Crt2'

    lvl = {'rows': 2, 'cols': 2, 'layers': {
        'bottom': [['Puddle_lv2', None], [None, None]],
        'middle': [['Red', 'void'], ['Crt2', None]],
        'upper': [[None, None], ['Mud', None]]}}
    assert cell_truth(lvl, 0, 0) == 'Red'      # middle covers bottom
    assert cell_truth(lvl, 0, 1) is None       # void
    assert cell_truth(lvl, 1, 0) == 'Mud'      # upper covers middle
    assert cell_truth(lvl, 1, 1) is None

    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert abs(_ncc(a, a) - 1.0) < 1e-9
    assert abs(_ncc(a, -a) + 1.0) < 1e-9
    assert abs(_ncc(a, a * 3 + 5) - 1.0) < 1e-9   # scale/offset invariant

    # Abstentions must be visible, not silently folded into "wrong answer".
    s = score(['Red', 'Crt1', 'Crt2', 'Mud'], ['Red', 'missing', 'Crt1', 'Mud'])
    assert s['cell_accuracy'] == 0.5 and s['abstain_rate'] == 0.25
    assert s['accuracy_on_answered'] == round(2 / 3, 4)
    assert s['top_confusions'].get('obstacle->missing') == 1

    real = sorted(LEVELS.glob('*.json'))
    if real and HUMAN_SPRITES.is_dir():
        level = load_level(real[0])
        bank = SpriteBank(HUMAN_SPRITES, 70)
        img, cells = render_board(level, bank)
        assert img.size == (level['cols'] * 70, level['rows'] * 70)
        assert cells, 'no scorable cells'
        # Truth must never be a raw instance id and must be a real sprite name.
        assert all('#' not in cd['truth'] for cd in cells)
        print(f'render {real[0].name}: {img.size[0]}x{img.size[1]}px, '
              f'{len(cells)} scorable cells, '
              f'{len({cd["truth"] for cd in cells})} distinct tiles')

        # Guard the degeneracy that silently saturated the first run: per-level
        # candidate sets make this a 1-3 way choice on most official levels.
        paths = sorted(LEVELS.glob('*.json'))
        random.Random(0).shuffle(paths)
        sample = paths[:20]
        bank70 = SpriteBank(HUMAN_SPRITES, 70)
        per_level = [len({cd['truth'] for cd in render_board(load_level(p), bank70)[1]})
                     for p in sample]
        glob_k = len({cd['truth'] for p in sample
                      for cd in render_board(load_level(p), bank70)[1]})
        median = sorted(per_level)[len(per_level) // 2]
        assert median <= 3, f'expected degenerate per-level k, got median {median}'
        assert glob_k >= 3 * median, (glob_k, median)
        print(f'candidate set: per-level median k={median} (degenerate) vs '
              f'global k={glob_k} -> global is the honest setting')
    print('self-check OK')


def main() -> None:
    ap = argparse.ArgumentParser(description='Board-parse eval (engine-grounded GT)')
    ap.add_argument('--packs', default='human',
                    help='comma pack names; "human" = shipped art')
    ap.add_argument('--parser', choices=['template', 'vlm'], default='template')
    ap.add_argument('--judge', choices=['gemini', 'openai', 'claude'], default='openai')
    ap.add_argument('--cell', default='70', help='comma cell sizes in px, e.g. 70,48,32,24')
    ap.add_argument('--levels', type=int, default=10, help='number of levels to sample')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--per-level-candidates', action='store_true',
                    help='restrict candidates to tiles in each level (degenerate: '
                         'most levels have 1-3 tiles, so accuracy saturates)')
    ap.add_argument('--out', default=str(OUT))
    ap.add_argument('--self-check', action='store_true')
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    all_levels = sorted(LEVELS.glob('*.json'))
    random.Random(args.seed).shuffle(all_levels)
    level_paths = all_levels[:args.levels]
    judge = build_judge(args.judge) if args.parser == 'vlm' else None

    report: dict = {'parser': args.parser, 'levels': [p.name for p in level_paths],
                    'judge': args.judge if args.parser == 'vlm' else None, 'results': []}
    for pack in [p.strip() for p in args.packs.split(',') if p.strip()]:
        if not resolve_run(pack).is_dir():
            print(f'skip {pack}: not found')
            continue
        for cell in [int(c) for c in args.cell.split(',') if c.strip()]:
            r = run_pack(pack, level_paths, cell, args.parser, judge,
                         global_candidates=not args.per_level_candidates)
            report['results'].append(r)
            print(f'{pack:28s} cell={cell:3d}px  k={r["n_candidates"]:2d}  '
                  f'cell_acc={r["cell_accuracy"]}  cat_acc={r["category_accuracy"]}  '
                  f'macro={r["accuracy_macro"]}  n={r["n_cells"]}')

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
