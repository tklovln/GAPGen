#!/usr/bin/env python3
"""
Automatic evaluation to replace the human study (Creative AI sprint).

Three proxies, mirroring the human protocol:
  1. Role recognition @70px  — VLM forced 4-choice function label -> accuracy
  2. Stage ordering (crate)  — VLM orders Crt4..Crt1 -> Kendall tau
  3. Pairwise preference      — VLM picks the more shippable pack (with AB swapping)
  4. Cohesion (objective)     — intra-family embedding similarity (DINO if available,
                                 else color-histogram fallback; no model judgment)

Judges:
  --judge gemini   (default; reuses art_pipeline Gemini client — no extra setup)
  --judge openai   (GPT-4o cross-model check; needs OPENAI_API_KEY + `openai`)

Usage:
  python scripts/auto_eval.py --self-check                 # offline, no API
  python scripts/auto_eval.py --tasks cohesion             # DINO/hist only, no API
  python scripts/auto_eval.py --themes fruit --judge gemini
  python scripts/auto_eval.py --themes fruit --judge openai --pairwise-repeats 2

Honesty note (for the paper): these are VLM/embedding *proxies* for readability
and consistency, not human judgments. Report as automatic evidence + future work.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GEN = ROOT / 'generated_art'
OUT = ROOT / 'paper' / 'results' / 'auto_eval.json'

ELEMENTS = ['Red', 'Grn', 'Blu', 'Yel', 'Pur']
POWERUPS = ['Soda0d', 'Soda90', 'LtBl']
CRATES = ['Crt4', 'Crt3', 'Crt2', 'Crt1']  # intact -> destroyed (ground truth order)

# Ground-truth gameplay role for role-recognition scoring
TRUE_ROLE = {
    'Red': 'match', 'Grn': 'match', 'Blu': 'match', 'Yel': 'match', 'Pur': 'match',
    'Soda0d': 'h_power', 'Soda90': 'v_power', 'LtBl': 'v_power',
    'Crt4': 'obstacle', 'Crt3': 'obstacle', 'Crt2': 'obstacle', 'Crt1': 'obstacle',
}
ROLE_CHOICES = {
    'match': 'basic match element (cleared by matching 3+)',
    'h_power': 'horizontal-clearing power-up (clears a row)',
    'v_power': 'vertical-clearing power-up (clears a column)',
    'obstacle': 'obstacle / blocker (e.g. a crate)',
}
ROLE_TASK1_ASSETS = ['Red', 'Blu', 'Soda0d', 'Soda90', 'Crt4', 'Crt1', 'Yel', 'LtBl']


def run_dir(theme: str, cond: str) -> pathlib.Path:
    return GEN / f'research_{cond}_{theme}' / 'sprites'


def load_png(path: pathlib.Path, size: int | None = None) -> bytes:
    from PIL import Image

    im = Image.open(path).convert('RGBA')
    if size:
        im.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))
        canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
        im = canvas
    buf = io.BytesIO()
    im.convert('RGB').save(buf, format='PNG')
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Judges: return parsed JSON dict from an image+prompt call
# --------------------------------------------------------------------------- #
class GeminiJudge:
    name = 'gemini'

    def __init__(self, model: str = 'gemini-3.5-flash'):
        from art_pipeline import gemini_api

        self._api = gemini_api
        self._client = gemini_api.get_client()
        self.model = model

    def ask(self, prompt: str, images: list[bytes]) -> dict:
        from google.genai import types

        contents: list = []
        for img in images:
            contents.append(types.Part.from_bytes(data=img, mime_type='image/png'))
        contents.append(prompt + '\nReturn ONLY minified JSON.')
        resp = self._client.models.generate_content(model=self.model, contents=contents)
        return _parse_json(getattr(resp, 'text', '') or '')


class OpenAIJudge:
    name = 'openai'

    def __init__(self, model: str = 'gpt-4o'):
        from openai import OpenAI

        try:
            from level_generator.ai_generator import _get_key
            key = _get_key('openai')
        except Exception:  # noqa: BLE001
            import os
            key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise SystemExit(
                'OpenAI key not found for --judge openai. Set OPENAI_API_KEY in '
                'config.py, .streamlit/secrets.toml, or the environment.'
            )
        self._client = OpenAI(api_key=key)
        self.model = model

    def ask(self, prompt: str, images: list[bytes]) -> dict:
        content: list = [{'type': 'text', 'text': prompt + '\nReturn ONLY minified JSON.'}]
        for img in images:
            b64 = base64.b64encode(img).decode()
            content.append({
                'type': 'image_url',
                'image_url': {'url': f'data:image/png;base64,{b64}'},
            })
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{'role': 'user', 'content': content}],
            response_format={'type': 'json_object'},
            temperature=0,
        )
        return _parse_json(resp.choices[0].message.content or '')


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.split('```', 2)[1].lstrip('json').strip()
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def task_role_recognition(judge, theme: str, cond: str) -> dict:
    src = run_dir(theme, cond)
    trials, correct = [], 0
    letters = {'A': 'match', 'B': 'h_power', 'C': 'v_power', 'D': 'obstacle'}
    for asset in ROLE_TASK1_ASSETS:
        p = src / f'{asset}.png'
        if not p.exists():
            continue
        prompt = (
            'This is a Match-3 game sprite shown at gameplay size (~70px). '
            'Pick its gameplay function. '
            'A=basic match element; B=horizontal-clearing power-up; '
            'C=vertical-clearing power-up; D=obstacle/blocker (crate). '
            'JSON: {"choice":"A|B|C|D"}'
        )
        try:
            ans = judge.ask(prompt, [load_png(p, size=70)])
            pred = letters.get(str(ans.get('choice', '')).strip().upper()[:1], 'unsure')
        except Exception as e:  # noqa: BLE001
            pred = f'error:{type(e).__name__}'
        ok = pred == TRUE_ROLE[asset]
        correct += int(ok)
        trials.append({'asset': asset, 'true': TRUE_ROLE[asset], 'pred': pred, 'correct': ok})
    n = len(trials)
    return {'n': n, 'accuracy': round(correct / n, 3) if n else None, 'trials': trials}


def _kendall_tau(order: list[str], gt: list[str]) -> float:
    rank = {n: i for i, n in enumerate(gt)}
    order = [o for o in order if o in rank]
    conc = disc = 0
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            s = (rank[order[i]] - rank[order[j]])
            if s < 0:
                conc += 1
            elif s > 0:
                disc += 1
    denom = len(order) * (len(order) - 1) / 2
    return round((conc - disc) / denom, 3) if denom else 1.0


def task_stage_ordering(judge, theme: str, cond: str) -> dict:
    src = run_dir(theme, cond)
    imgs, labels = [], []
    import random

    shuffled = CRATES[:]
    random.shuffle(shuffled)
    for name in shuffled:
        p = src / f'{name}.png'
        if not p.exists():
            return {'n': 0, 'kendall_tau': None}
        imgs.append(load_png(p, size=96))
        labels.append(name)
    prompt = (
        f'These {len(labels)} images (labeled {", ".join(f"{i+1}={labels[i]}" for i in range(len(labels)))}) '
        'are damage stages of ONE crate obstacle. Order them from MOST INTACT to MOST DESTROYED. '
        'JSON: {"order":["<label>",...]} using the given labels.'
    )
    try:
        ans = judge.ask(prompt, imgs)
        order = [str(x) for x in ans.get('order', [])]
    except Exception as e:  # noqa: BLE001
        return {'n': len(labels), 'kendall_tau': None, 'error': type(e).__name__}
    return {'n': len(labels), 'presented': labels,
            'predicted_order': order, 'kendall_tau': _kendall_tau(order, CRATES)}


def task_pairwise(judge, theme: str, c1: str, c2: str, repeats: int) -> dict:
    """Compare two conditions overall; AB-swap to de-bias; win = c2 preferred."""
    from PIL import Image

    def contact(cond: str) -> bytes:
        src = run_dir(theme, cond)
        names = ELEMENTS + POWERUPS + CRATES
        paths = [src / f'{n}.png' for n in names]
        if not all(p.exists() for p in paths):
            return b''
        cell, pad, cols = 80, 6, 6
        rows = (len(paths) + cols - 1) // cols
        W = pad + cols * (cell + pad)
        H = pad + rows * (cell + pad)
        canvas = Image.new('RGB', (W, H), (250, 250, 252))
        for i, p in enumerate(paths):
            im = Image.open(p).convert('RGBA')
            im.thumbnail((cell, cell), Image.Resampling.LANCZOS)
            x = pad + (i % cols) * (cell + pad)
            y = pad + (i // cols) * (cell + pad)
            tile = Image.new('RGB', (cell, cell), (255, 255, 255))
            tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
            canvas.paste(tile, (x, y))
        buf = io.BytesIO()
        canvas.save(buf, format='PNG')
        return buf.getvalue()

    img1, img2 = contact(c1), contact(c2)
    if not img1 or not img2:
        return {'compare': f'{c1}_vs_{c2}', 'n': 0}
    c2_wins = 0
    votes = []
    for r in range(repeats):
        swap = (r % 2 == 1)
        left, right = (c2, c1) if swap else (c1, c2)
        limg, rimg = (img2, img1) if swap else (img1, img2)
        prompt = (
            'Two candidate Match-3 art packs (LEFT and RIGHT), same gameplay roles. '
            'Which is more suitable as shippable game art: clear function readability, '
            'consistent style, clean cutouts? JSON: {"winner":"LEFT|RIGHT"}'
        )
        try:
            ans = judge.ask(prompt, [limg, rimg])
            w = str(ans.get('winner', '')).strip().upper()
            winner_cond = (left if w == 'LEFT' else right if w == 'RIGHT' else None)
        except Exception:  # noqa: BLE001
            winner_cond = None
        if winner_cond == c2:
            c2_wins += 1
        votes.append({'swap': swap, 'winner_cond': winner_cond})
    return {'compare': f'{c1}_vs_{c2}', 'n': repeats,
            f'{c2}_win_rate': round(c2_wins / repeats, 3) if repeats else None,
            'votes': votes}


# --------------------------------------------------------------------------- #
# Cohesion (objective, no VLM)
# --------------------------------------------------------------------------- #
def _dino_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


_DINO_CACHE: dict = {}


def _embed_dino(paths: list[pathlib.Path]):
    import torch
    from PIL import Image
    from transformers import AutoImageProcessor, AutoModel

    if 'proc' not in _DINO_CACHE:
        _DINO_CACHE['proc'] = AutoImageProcessor.from_pretrained('facebook/dinov2-small')
        _DINO_CACHE['model'] = AutoModel.from_pretrained('facebook/dinov2-small').eval()
    proc, model = _DINO_CACHE['proc'], _DINO_CACHE['model']
    embs = []
    with torch.no_grad():
        for p in paths:
            im = Image.open(p).convert('RGB')
            inp = proc(images=im, return_tensors='pt')
            out = model(**inp).last_hidden_state[:, 0]  # CLS
            embs.append(torch.nn.functional.normalize(out, dim=-1)[0])
    return torch.stack(embs)


def _hist_vec(path: pathlib.Path):
    from PIL import Image

    im = Image.open(path).convert('RGB').resize((64, 64))
    hist = im.histogram()  # 768 values (R,G,B x256)
    total = sum(hist) or 1
    return [h / total for h in hist]


def _cos(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def task_cohesion(theme: str, cond: str, *, force_fallback: bool = False) -> dict:
    """Intra-family mean pairwise similarity (higher = more cohesive)."""
    src = run_dir(theme, cond)
    families = {'elements': ELEMENTS, 'powerups': POWERUPS, 'crate': CRATES}
    use_dino = (not force_fallback) and _dino_available()
    method = 'dinov2-small' if use_dino else 'color-histogram(fallback)'
    result: dict = {'method': method, 'families': {}}
    all_sims = []
    for fam, names in families.items():
        paths = [src / f'{n}.png' for n in names if (src / f'{n}.png').exists()]
        if len(paths) < 2:
            continue
        if use_dino:
            embs = _embed_dino(paths)
            sims = []
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    sims.append(float((embs[i] @ embs[j]).item()))
        else:
            vecs = [_hist_vec(p) for p in paths]
            sims = [_cos(vecs[i], vecs[j])
                    for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
        fam_mean = round(sum(sims) / len(sims), 4)
        result['families'][fam] = {'n_pairs': len(sims), 'mean_sim': fam_mean}
        all_sims.extend(sims)
    result['overall_mean_sim'] = round(sum(all_sims) / len(all_sims), 4) if all_sims else None
    return result


# --------------------------------------------------------------------------- #
def self_check() -> None:
    """Offline sanity checks; no API, no heavy deps."""
    assert _kendall_tau(['Crt4', 'Crt3', 'Crt2', 'Crt1'], CRATES) == 1.0
    assert _kendall_tau(['Crt1', 'Crt2', 'Crt3', 'Crt4'], CRATES) == -1.0
    assert abs(_cos([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(_cos([1, 0], [0, 1]) - 0.0) < 1e-9
    assert _parse_json('```json\n{"choice":"A"}\n```')['choice'] == 'A'
    assert _parse_json('noise {"winner":"LEFT"} tail')['winner'] == 'LEFT'
    # cohesion works offline on existing sprites via histogram fallback
    if run_dir('fruit', 'B3').is_dir():
        coh = task_cohesion('fruit', 'B3', force_fallback=True)
        assert coh['overall_mean_sim'] is not None
        print('cohesion(fruit,B3) fallback:', coh['method'], coh['overall_mean_sim'])
    print('self-check OK')


def build_judge(kind: str):
    return OpenAIJudge() if kind == 'openai' else GeminiJudge()


def main() -> None:
    ap = argparse.ArgumentParser(description='Automatic eval (VLM + cohesion proxies)')
    ap.add_argument('--themes', default='fruit', help='comma slugs (fruit,pet,ocean)')
    ap.add_argument('--conditions', default='B1,B3', help='conditions to score')
    ap.add_argument('--tasks', default='role,stage,pairwise,cohesion',
                    help='subset of role,stage,pairwise,cohesion')
    ap.add_argument('--judge', choices=['gemini', 'openai'], default='gemini')
    ap.add_argument('--pairwise-repeats', type=int, default=2,
                    help='AB-swapped repeats per pair (even = balanced)')
    ap.add_argument('--self-check', action='store_true')
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    themes = [t.strip() for t in args.themes.split(',') if t.strip()]
    conds = [c.strip().upper() for c in args.conditions.split(',') if c.strip()]
    tasks = {t.strip() for t in args.tasks.split(',') if t.strip()}
    need_vlm = bool(tasks & {'role', 'stage', 'pairwise'})
    judge = build_judge(args.judge) if need_vlm else None

    report: dict = {'judge': args.judge if need_vlm else None, 'themes': {}}
    for theme in themes:
        tr: dict = {}
        for cond in conds:
            if not run_dir(theme, cond).is_dir():
                continue
            cr: dict = {}
            if 'role' in tasks:
                cr['role_recognition'] = task_role_recognition(judge, theme, cond)
            if 'stage' in tasks:
                cr['stage_ordering'] = task_stage_ordering(judge, theme, cond)
            if 'cohesion' in tasks:
                cr['cohesion'] = task_cohesion(theme, cond)
            tr[cond] = cr
        if 'pairwise' in tasks and len(conds) >= 2:
            pairs = []
            for i in range(len(conds)):
                for j in range(i + 1, len(conds)):
                    if run_dir(theme, conds[i]).is_dir() and run_dir(theme, conds[j]).is_dir():
                        pairs.append(task_pairwise(judge, theme, conds[i], conds[j],
                                                   args.pairwise_repeats))
            tr['pairwise'] = pairs
        report['themes'][theme] = tr

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {OUT}')
    print(json.dumps(report, ensure_ascii=False, indent=2)[:1500])


if __name__ == '__main__':
    main()
