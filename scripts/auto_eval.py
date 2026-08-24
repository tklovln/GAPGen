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

# --------------------------------------------------------------------------- #
# Ontology-derived ground truth (scope=full). asset_roles.json is human-written,
# so these labels are not model opinions.
# --------------------------------------------------------------------------- #
ONTOLOGY = ROOT / 'art_pipeline' / 'asset_roles.json'
# NOTE: resources/sprites/ is a *generated* pack (apply.py overwrites it with
# DEFAULT_PACKED_ART_RUN). The shipped human art only survives in the backup.
HUMAN_SPRITES = ROOT / 'godot_demo' / 'resources' / 'sprites_original_backup'
APPLIED_SPRITES = ROOT / 'godot_demo' / 'resources' / 'sprites'

# Coarse 4-way label space for the full asset set. The fine-grained 19 role
# classes are not visually separable (e.g. static vs movable obstacle), so the
# wide-coverage task uses `category` and the core-12 task keeps the finer
# h_power/v_power split.
CATEGORY_CHOICES = {
    'element': 'basic match element (cleared by matching 3+)',
    'powerup': 'special power-up item (rocket / bomb / color bomb / projectile)',
    'obstacle': 'obstacle / blocker occupying a cell',
    'background': 'board background / backdrop',
}

_ONTO_CACHE: dict = {}


def _ontology() -> dict:
    if 'data' not in _ONTO_CACHE:
        _ONTO_CACHE['data'] = json.loads(ONTOLOGY.read_text(encoding='utf-8'))
    return _ONTO_CACHE['data']


def asset_category() -> dict[str, str]:
    """asset name -> coarse category, straight from the ontology."""
    onto = _ONTO_CACHE.setdefault('cat', {})
    if onto:
        return onto
    data = _ontology()
    for g in data['asset_groups']:
        cat = data['role_classes'][g['role_class']]['category']
        for n in g['names']:
            onto[n] = cat
    return onto


def ontology_families() -> dict[str, list[str]]:
    """family -> all asset names in it (for intra-family cohesion)."""
    fams = _ONTO_CACHE.setdefault('fams', {})
    if fams:
        return fams
    for g in _ontology()['asset_groups']:
        fams.setdefault(g['family'], []).extend(g['names'])
    return fams


def ontology_stage_sets(min_len: int = 3) -> dict[str, list[str]]:
    """label -> names ordered intact->destroyed (descending HP `lv`).

    Keyed per asset_group, not per family: `movable` holds both Barrel and the
    TrafficCone stage pair, which are not one progression.
    """
    sets = _ONTO_CACHE.setdefault('stages', {})
    if sets:
        return {k: v for k, v in sets.items() if len(v) >= min_len}
    for g in _ontology()['asset_groups']:
        lvs = {n: p['lv'] for n, p in (g.get('params') or {}).items()
               if isinstance(p, dict) and 'lv' in p}
        if len(lvs) < 2:
            continue
        label = g['family']
        while label in sets:
            label += '_x'
        sets[label] = sorted(lvs, key=lambda n: -lvs[n])
    return {k: v for k, v in sets.items() if len(v) >= min_len}


def run_dir(theme: str, cond: str) -> pathlib.Path:
    return GEN / f'research_{cond}_{theme}' / 'sprites'


def resolve_run(spec: str) -> pathlib.Path:
    """'human' -> shipped M8 art (backup dir, NOT resources/sprites which is
    an applied generated pack); 'applied' -> whatever is currently applied;
    otherwise a generated_art run name."""
    if spec == 'human':
        return HUMAN_SPRITES
    if spec == 'applied':
        return APPLIED_SPRITES
    return GEN / spec / 'sprites'


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


class ClaudeJudge:
    name = 'claude'

    def __init__(self, model: str = 'claude-sonnet-5'):
        import anthropic

        try:
            from level_generator.ai_generator import _get_key
            key = _get_key('anthropic')
        except Exception:  # noqa: BLE001
            import os
            key = os.environ.get('ANTHROPIC_API_KEY')
        if not key:
            raise SystemExit(
                'Anthropic key not found for --judge claude. Set ANTHROPIC_API_KEY in '
                'config.py, .streamlit/secrets.toml, or the environment.'
            )
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model

    def ask(self, prompt: str, images: list[bytes]) -> dict:
        content: list = []
        for img in images:
            content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': 'image/png',
                           'data': base64.b64encode(img).decode()},
            })
        content.append({'type': 'text', 'text': prompt + '\nReturn ONLY minified JSON.'})
        resp = self._client.messages.create(
            model=self.model, max_tokens=512, temperature=0,
            messages=[{'role': 'user', 'content': content}],
        )
        return _parse_json(''.join(b.text for b in resp.content if b.type == 'text'))


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
def task_role_recognition(judge, src: pathlib.Path) -> dict:
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


def _ask_category(judge, img: bytes, mapping: dict[str, str]) -> str:
    """One forced-choice call under an explicit letter->category mapping."""
    options = '; '.join(f'{k}={CATEGORY_CHOICES[v]}' for k, v in mapping.items())
    prompt = (
        'This is a Match-3 game sprite shown at gameplay size (~70px). '
        f'Pick what it is. {options}. '
        'JSON: {"choice":"' + '|'.join(mapping) + '"}'
    )
    try:
        ans = judge.ask(prompt, [img])
    except Exception as e:  # noqa: BLE001
        return f'error:{type(e).__name__}'
    return mapping.get(str(ans.get('choice', '')).strip().upper()[:1], 'unparsed')


def task_role_category(judge, src: pathlib.Path) -> dict:
    """Wide-coverage variant: every asset present, 4-way ontology category."""
    cats = asset_category()
    mapping = dict(zip('ABCD', CATEGORY_CHOICES))
    trials, correct = [], 0
    per_cat: dict[str, list[int]] = {}
    for asset in sorted(cats):
        p = src / f'{asset}.png'
        if not p.exists():
            continue
        pred = _ask_category(judge, load_png(p, size=70), mapping)
        ok = pred == cats[asset]
        correct += int(ok)
        per_cat.setdefault(cats[asset], []).append(int(ok))
        trials.append({'asset': asset, 'true': cats[asset], 'pred': pred, 'correct': ok})
    n = len(trials)
    by_cat = {k: {'n': len(v), 'accuracy': round(sum(v) / len(v), 3)}
              for k, v in sorted(per_cat.items())}
    return {
        'n': n,
        'accuracy': round(correct / n, 3) if n else None,
        'accuracy_macro': (round(sum(c['accuracy'] for c in by_cat.values()) / len(by_cat), 3)
                           if by_cat else None),
        'by_category': by_cat,
        'trials': trials,
    }



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


def _order_once(judge, src: pathlib.Path, names: list[str]) -> dict:
    import random

    shuffled = names[:]
    random.shuffle(shuffled)
    imgs = [load_png(src / f'{n}.png', size=96) for n in shuffled]
    prompt = (
        f'These {len(shuffled)} images (labeled '
        f'{", ".join(f"{i+1}={shuffled[i]}" for i in range(len(shuffled)))}) '
        'are damage/depletion stages of ONE object. Order them from MOST INTACT '
        'to MOST DESTROYED. JSON: {"order":["<label>",...]} using the given labels.'
    )
    try:
        ans = judge.ask(prompt, imgs)
        order = [str(x) for x in ans.get('order', [])]
    except Exception as e:  # noqa: BLE001
        return {'presented': shuffled, 'error': type(e).__name__, 'kendall_tau': None}
    return {'presented': shuffled, 'predicted_order': order,
            'kendall_tau': _kendall_tau(order, names)}


def task_stage_ordering(judge, src: pathlib.Path, stage_sets: dict[str, list[str]],
                        repeats: int = 1) -> dict:
    """Kendall tau per stage family, averaged over shuffled repeats."""
    out: dict = {'families': {}}
    taus = []
    for label, names in stage_sets.items():
        present = [n for n in names if (src / f'{n}.png').exists()]
        if len(present) < 3:
            continue
        runs = [_order_once(judge, src, present) for _ in range(repeats)]
        vals = [r['kendall_tau'] for r in runs if r.get('kendall_tau') is not None]
        mean = round(sum(vals) / len(vals), 3) if vals else None
        out['families'][label] = {'n_stages': len(present), 'repeats': len(runs),
                                 'kendall_tau_mean': mean, 'runs': runs}
        if mean is not None:
            taus.append(mean)
    out['n_families'] = len(out['families'])
    out['kendall_tau_macro'] = round(sum(taus) / len(taus), 3) if taus else None
    return out



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


def task_cohesion(src: pathlib.Path, families: dict[str, list[str]],
                  *, force_fallback: bool = False) -> dict:
    """Intra-family mean pairwise similarity (higher = more cohesive)."""
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
        result['families'][fam] = {'n_assets': len(paths), 'n_pairs': len(sims),
                                   'mean_sim': fam_mean}
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

    # Validation-battery helpers must be sound before we trust their verdicts.
    assert _agreement(['a', 'b', 'c'], ['a', 'x', 'c']) == 0.667
    assert _agreement([], []) == 0.0
    assert len(_blank_png()) > 0
    if HUMAN_SPRITES.is_dir():
        samp = _balanced_sample(HUMAN_SPRITES, per_cat=3)
        counts = {c: [x[1] for x in samp].count(c) for c in {x[1] for x in samp}}
        assert samp and all(v <= 3 for v in counts.values()), counts
        # a constant answer must not be able to reach high accuracy on the sample
        assert max(counts.values()) / len(samp) < 0.6, counts

    # Ontology-derived GT must agree with the hand-written core-12 tables.
    cats = asset_category()
    assert cats['Red'] == 'element' and cats['Crt4'] == 'obstacle'
    assert cats['Soda0d'] == cats['LtBl'] == 'powerup'
    assert cats['board_bg'] == 'background'
    fams = ontology_families()
    assert fams['elements'] == ELEMENTS
    assert set(POWERUPS) <= set(fams['powerups'])
    stages = ontology_stage_sets()
    assert stages['crate'] == CRATES, stages['crate']            # intact -> destroyed
    assert stages['pool'][0] == 'Pool_lv5' and stages['pool'][-1] == 'Pool_lv1'
    assert 'movable' not in stages or 'Barrel' not in stages['movable']
    assert all(len(v) >= 3 for v in stages.values())

    # Guard the mistake this script already made once: resources/sprites is an
    # applied *generated* pack, so 'human' must not point at it.
    assert resolve_run('human') == HUMAN_SPRITES != APPLIED_SPRITES
    if HUMAN_SPRITES.is_dir() and APPLIED_SPRITES.is_dir():
        import hashlib

        def _md5(p):
            return hashlib.md5(p.read_bytes()).hexdigest()
        same = [n for n in ('Red', 'Crt4', 'Soda0d')
                if (HUMAN_SPRITES / f'{n}.png').exists()
                and (APPLIED_SPRITES / f'{n}.png').exists()
                and _md5(HUMAN_SPRITES / f'{n}.png') == _md5(APPLIED_SPRITES / f'{n}.png')]
        assert not same, f'human art == applied generated art for {same}; backup was overwritten'

    # cohesion works offline on existing sprites via histogram fallback
    if run_dir('fruit', 'B3').is_dir():
        coh = task_cohesion(run_dir('fruit', 'B3'),
                            {'elements': ELEMENTS, 'powerups': POWERUPS, 'crate': CRATES},
                            force_fallback=True)
        assert coh['overall_mean_sim'] is not None
        print('cohesion(fruit,B3) fallback:', coh['method'], coh['overall_mean_sim'])
    print(f'ontology: {len(cats)} assets, {len(fams)} families, '
          f'{len(stages)} stage sets {[(k, len(v)) for k, v in stages.items()]}')
    print('self-check OK')


def verify_gt() -> None:
    """Ground the ontology labels in the engine's own tile registry.

    asset_roles.json was drafted with LLM help, so it cannot be cited as
    ground truth on its own authority. tile_defs.TILE_REGISTRY is executable:
    match_engine runs on it and the shipped levels play against it. Where the
    two overlap, the ontology is a verified transcription; where they diverge,
    say so in the paper instead of trusting the prose.
    """
    import tile_defs as td

    reg = td.TILE_REGISTRY
    data = _ontology()
    cats = asset_category()
    lv_of = {n: p['lv'] for g in data['asset_groups']
             for n, p in (g.get('params') or {}).items()
             if isinstance(p, dict) and 'lv' in p}

    # The ontology's coarse `obstacle` covers engine categories that are all
    # board blockers from the player's point of view.
    equiv = {'obstacle': {'obstacle', 'modifier', 'manufacturer'}}
    shared = sorted(set(cats) & set(reg))
    cat_bad = [(n, cats[n], reg[n]['category']) for n in shared
               if reg[n]['category'] not in equiv.get(cats[n], {cats[n]})]
    hp_bad = [(n, lv_of[n], reg[n].get('health')) for n in shared
              if n in lv_of and reg[n].get('health') is not None
              and lv_of[n] != reg[n]['health']]

    print(f'engine tiles {len(reg)} | ontology assets {len(cats)} | '
          f'checkable overlap {len(shared)}')
    print(f'category mismatches: {cat_bad or "none"}')
    print(f'stage HP mismatches: {hp_bad or "none"}')
    print(f'sprites with no engine tile (visual parts / stage frames): '
          f'{len(set(cats) - set(reg))}')
    missing = sorted(set(reg) - set(cats))
    print(f'engine tiles with no sprite in ontology: {missing}')
    assert not cat_bad, 'ontology category disagrees with the engine'
    assert not hp_bad, 'ontology stage HP disagrees with the engine'
    print('verify-gt OK: labels used for scoring are grounded in tile_defs.py')


def _balanced_sample(src: pathlib.Path, per_cat: int = 3) -> list[tuple[str, str]]:
    """Up to `per_cat` assets per category, so chance level is well defined."""
    cats = asset_category()
    buckets: dict[str, list[str]] = {}
    for a in sorted(cats):
        if (src / f'{a}.png').exists():
            buckets.setdefault(cats[a], []).append(a)
    return [(a, c) for c, names in sorted(buckets.items()) for a in names[:per_cat]]


def _blank_png(size: int = 70) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new('RGB', (size, size), (128, 128, 128)).save(buf, format='PNG')
    return buf.getvalue()


def _agreement(a: list[str], b: list[str]) -> float:
    return round(sum(x == y for x, y in zip(a, b)) / len(a), 3) if a else 0.0


def validate_judge(kind: str, run_spec: str, per_cat: int = 3) -> None:
    """Is this judge actually usable? Five checks, not just 'it returned JSON'.

    A judge can return perfectly valid JSON while ignoring the image entirely
    (answering from prompt priors or always picking the same letter). The
    blank-image control and the permuted-label check are what catch that.
    """
    src = resolve_run(run_spec)
    if not src.is_dir():
        raise SystemExit(f'{src} not found')
    judge = build_judge(kind)
    sample = _balanced_sample(src, per_cat)
    truth = [c for _, c in sample]
    imgs = [load_png(src / f'{a}.png', size=70) for a, _ in sample]
    m1 = dict(zip('ABCD', CATEGORY_CHOICES))
    # Same categories, different letters: a judge that follows content keeps its
    # semantic answer; one that latches onto a letter does not.
    m2 = dict(zip('ABCD', list(CATEGORY_CHOICES)[::-1]))

    print(f'judge={kind} model={getattr(judge, "model", "?")} '
          f'pack={run_spec} n={len(sample)} '
          f'(composition: {dict((c, truth.count(c)) for c in sorted(set(truth)))})')

    pass1 = [_ask_category(judge, im, m1) for im in imgs]
    pass2 = [_ask_category(judge, im, m1) for im in imgs]
    permuted = [_ask_category(judge, im, m2) for im in imgs]
    blind = [_ask_category(judge, _blank_png(), m1) for _ in imgs]

    bad = [p for p in pass1 if p.startswith(('error:', 'unparsed'))]
    acc = _agreement(pass1, truth)
    blind_acc = _agreement(blind, truth)
    chance = round(1 / len(CATEGORY_CHOICES), 3)
    dist = {c: pass1.count(c) for c in sorted(set(pass1))}
    blind_dist = {c: blind.count(c) for c in sorted(set(blind))}
    majority = max(set(truth), key=truth.count)
    majority_acc = _agreement([majority] * len(truth), truth)

    checks = [
        ('1 protocol compliance', f'{1 - len(bad) / len(pass1):.3f} valid',
         len(bad) == 0),
        ('2 test-retest agreement', f'{_agreement(pass1, pass2):.3f}',
         _agreement(pass1, pass2) >= 0.8),
        ('3 label-permutation invariance', f'{_agreement(pass1, permuted):.3f}',
         _agreement(pass1, permuted) >= 0.7),
        ('4 looks at the image (blind control)',
         f'real {acc:.3f} vs blind {blind_acc:.3f} (chance {chance})',
         acc - blind_acc >= 0.2),
        ('5 beats constant-majority guess',
         f'{acc:.3f} vs always-"{majority}" {majority_acc:.3f}',
         acc > majority_acc),
    ]
    print()
    for name, val, ok in checks:
        print(f'  [{"PASS" if ok else "FAIL"}] {name}: {val}')
    print(f'\n  answer distribution (real):  {dist}')
    print(f'  answer distribution (blind): {blind_dist}')

    failed = [n for n, _, ok in checks if not ok]
    print(f'\nverdict: {"USABLE" if not failed else "NOT USABLE — " + ", ".join(failed)}')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    dst = OUT.parent / f'judge_validation_{kind}.json'
    dst.write_text(json.dumps({
        'judge': kind, 'model': getattr(judge, 'model', None), 'pack': run_spec,
        'sample': sample, 'pass1': pass1, 'pass2': pass2,
        'permuted': permuted, 'blind': blind,
        'accuracy': acc, 'blind_accuracy': blind_acc,
        'majority_accuracy': majority_acc, 'chance': chance,
        'checks': {n: {'value': v, 'pass': ok} for n, v, ok in checks},
        'usable': not failed,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {dst}')


def build_judge(kind: str):
    return {'openai': OpenAIJudge, 'claude': ClaudeJudge}.get(kind, GeminiJudge)()


def main() -> None:
    ap = argparse.ArgumentParser(description='Automatic eval (VLM + cohesion proxies)')
    ap.add_argument('--themes', default='fruit', help='comma slugs (fruit,pet,ocean)')
    ap.add_argument('--conditions', default='B1,B3', help='conditions to score')
    ap.add_argument('--runs', default='',
                    help="comma run names to score directly, e.g. "
                         "fruit_3dCartoonSimple,human (bypasses --themes/--conditions)")
    ap.add_argument('--scope', choices=['core', 'full'], default='core',
                    help='core = hand-picked 12 assets (paper table); '
                         'full = every asset in the ontology')
    ap.add_argument('--tasks', default='role,stage,pairwise,cohesion',
                    help='subset of role,stage,pairwise,cohesion')
    ap.add_argument('--judge', choices=['gemini', 'openai', 'claude'], default='gemini')
    ap.add_argument('--pairwise-repeats', type=int, default=2,
                    help='AB-swapped repeats per pair (even = balanced)')
    ap.add_argument('--stage-repeats', type=int, default=1,
                    help='shuffled repeats per stage family (>=3 tames tau noise)')
    ap.add_argument('--out', default=str(OUT), help='output JSON path')
    ap.add_argument('--self-check', action='store_true')
    ap.add_argument('--verify-gt', action='store_true',
                    help='check ontology labels against tile_defs.TILE_REGISTRY')
    ap.add_argument('--validate-judge', action='store_true',
                    help='5-check validity battery for --judge (incl. blind control)')
    ap.add_argument('--validate-pack', default='human',
                    help='pack used by --validate-judge (default: human art)')
    ap.add_argument('--validate-per-cat', type=int, default=3,
                    help='assets per category in the validation sample')
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return
    if args.verify_gt:
        verify_gt()
        return
    if args.validate_judge:
        validate_judge(args.judge, args.validate_pack, args.validate_per_cat)
        return

    full = args.scope == 'full'
    families = ontology_families() if full else {
        'elements': ELEMENTS, 'powerups': POWERUPS, 'crate': CRATES}
    stage_sets = ontology_stage_sets() if full else {'crate': CRATES}

    tasks = {t.strip() for t in args.tasks.split(',') if t.strip()}
    need_vlm = bool(tasks & {'role', 'stage', 'pairwise'})
    judge = build_judge(args.judge) if need_vlm else None

    def score(src: pathlib.Path) -> dict:
        cr: dict = {'sprites': str(src.relative_to(ROOT)),
                    'n_png': len(list(src.glob('*.png')))}
        if 'role' in tasks:
            cr['role_recognition'] = (task_role_category(judge, src) if full
                                      else task_role_recognition(judge, src))
        if 'stage' in tasks:
            cr['stage_ordering'] = task_stage_ordering(judge, src, stage_sets,
                                                       args.stage_repeats)
        if 'cohesion' in tasks:
            cr['cohesion'] = task_cohesion(src, families)
        return cr

    report: dict = {'judge': args.judge if need_vlm else None, 'scope': args.scope}

    if args.runs:
        report['runs'] = {}
        for spec in [r.strip() for r in args.runs.split(',') if r.strip()]:
            src = resolve_run(spec)
            if not src.is_dir():
                print(f'skip {spec}: {src} missing')
                continue
            print(f'-- scoring {spec}')
            report['runs'][spec] = score(src)
    else:
        themes = [t.strip() for t in args.themes.split(',') if t.strip()]
        conds = [c.strip().upper() for c in args.conditions.split(',') if c.strip()]
        report['themes'] = {}
        for theme in themes:
            tr: dict = {}
            for cond in conds:
                if not run_dir(theme, cond).is_dir():
                    continue
                print(f'-- scoring {theme}/{cond}')
                tr[cond] = score(run_dir(theme, cond))
            if 'pairwise' in tasks and len(conds) >= 2:
                pairs = []
                for i in range(len(conds)):
                    for j in range(i + 1, len(conds)):
                        if run_dir(theme, conds[i]).is_dir() and run_dir(theme, conds[j]).is_dir():
                            pairs.append(task_pairwise(judge, theme, conds[i], conds[j],
                                                       args.pairwise_repeats))
                tr['pairwise'] = pairs
            report['themes'][theme] = tr

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
