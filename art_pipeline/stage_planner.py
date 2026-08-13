"""
Stage planner — LLM expands a multi-stage family (Crt1-4, Pool_lv1-5, …) into a
per-stage visual spec plus a reference chain, so that each stage is *visibly
distinct* from its neighbour while staying in the same design.

Complements:
  theme_planner        — per-element themed object assignment
  family_style_planner — per-family cohesion tokens (material/ornament/…)

This planner is stage-level: for one family it produces
  {
    'family': 'crate',
    'anchor': 'Crt4',                 # pristine end, locks the base design
    'order': ['Crt4', 'Crt3', 'Crt2', 'Crt1'],   # generation order (anchor first)
    'stages': {
      'Crt4': {'visual': 'intact crate, all slats whole', 'ref_from': None},
      'Crt3': {'visual': 'one slat cracked, corner dented', 'ref_from': 'Crt4'},
      ...
    },
  }

Each stage's ``ref_from`` names the previous stage; the pipeline feeds BOTH the
family anchor (locks style) and that previous stage (locks progression) to the
image model — dual reference, which keeps drift bounded while making the step
between adjacent stages unmistakable at ~70px.
"""

from __future__ import annotations

import json

from . import gemini_api
from .roles import get_family_meta, load_config
from .visual_guidance import get_family_anchor_asset


def _lv(asset: dict) -> int | None:
    """Stage level, from asset['lv'] or asset['params']['lv'] (manifest stores it in params)."""
    lv = asset.get('lv', asset.get('params', {}).get('lv'))
    return lv if isinstance(lv, int) else None


def _state(asset: dict) -> str | None:
    return asset.get('state', asset.get('params', {}).get('state'))


def stage_assets_for_family(targets: list[dict], family_id: str) -> list[dict]:
    """Assets in ``targets`` belonging to ``family_id`` that carry a numeric stage ``lv``."""
    out = [a for a in targets
           if a.get('family') == family_id and _lv(a) is not None]
    return sorted(out, key=_lv)


def is_stage_family(family_id: str | None, config: dict | None = None) -> bool:
    """True when this family opts into stage-progression planning (asset_roles.json)."""
    if not family_id:
        return False
    return bool(get_family_meta(family_id, config).get('stage_progression'))


def stage_order(family_id: str, targets: list[dict],
                config: dict | None = None,
                explicit_order: list[str] | None = None) -> list[str]:
    """Generation order: anchor (usually the pristine/full end) first, then descending lv.

    ``explicit_order`` (from LLM auto-detection) wins when given — used for families
    that have no numeric ``lv`` to sort by. Filtered to assets present in ``targets``.
    """
    cfg = config or load_config()
    assets = stage_assets_for_family(targets, family_id)
    if explicit_order:
        present = {a['name'] for a in family_assets(targets, family_id)}
        return [n for n in explicit_order if n in present]
    if not assets:
        return []
    anchor = get_family_anchor_asset(family_id, cfg)
    # Chain runs from the anchor outward. Anchor is typically the highest-HP
    # (pristine/full) stage, so walk lv high -> low from it.
    names = [a['name'] for a in assets]
    if anchor in names:
        names.remove(anchor)
        names_desc = sorted(names, key=lambda n: -_lv_of(n, assets))
        return [anchor] + names_desc
    return sorted((a['name'] for a in assets), key=lambda n: -_lv_of(n, assets))


def family_assets(targets: list[dict], family_id: str) -> list[dict]:
    """All assets in ``targets`` for a family (regardless of numeric lv)."""
    return [a for a in targets if a.get('family') == family_id]


def _lv_of(name: str, assets: list[dict]) -> int:
    for a in assets:
        if a['name'] == name:
            return _lv(a) or 0
    return 0


def ref_from_for(order: list[str]) -> dict[str, str | None]:
    """Chain each stage to the previous one in generation order (first has none)."""
    chain: dict[str, str | None] = {}
    prev: str | None = None
    for name in order:
        chain[name] = prev
        prev = name
    return chain


def detect_stage_families(
    targets: list[dict],
    *,
    config: dict | None = None,
    client=None,
    model: str = gemini_api.DEFAULT_CRITIC_MODEL,
) -> dict[str, dict]:
    """Ask the LLM which families are 'same object at progressive stages', from
    filenames + gameplay function alone (no hardcoded naming rules).

    Only inspects families NOT already flagged ``stage_progression`` in config
    (manual wins). Returns {family_id: {'anchor': name, 'order': [pristine..destroyed]}}
    for families the LLM judges to be genuine progressive stages (>=2 members).

    Filenames are the primary signal (e.g. Crt1..Crt4, Pool_lv1..5), but the model
    must use the gameplay ``function`` text to reject look-alikes that are NOT one
    object — e.g. distinct colors (Red/Green/Blue) or distinct parts (body/lid).
    """
    from google.genai import types

    cfg = config or load_config()

    families: dict[str, list[dict]] = {}
    for a in targets:
        fam = a.get('family')
        if not fam or is_stage_family(fam, cfg):
            continue  # manual flag wins; skip already-known stage families
        families.setdefault(fam, []).append(a)
    # Only families with >=2 members can form a chain.
    families = {f: members for f, members in families.items() if len(members) >= 2}
    if not families:
        return {}

    blocks = []
    for fam, members in families.items():
        lines = [f'Family "{fam}":']
        for a in members:
            lines.append(f'  - {a["name"]}: {a.get("function", "")[:200]}')
        blocks.append('\n'.join(lines))
    families_block = '\n\n'.join(blocks)

    rubric = f"""You are analyzing a match-3 game's art assets to find "stage progression" families.

A STAGE-PROGRESSION family is ONE single object shown at multiple progressive states
(e.g. increasing damage, decreasing water/fill level, wear). Its members differ ONLY by
how damaged/depleted the SAME object is.

It is NOT a stage-progression family if the members are different things, for example:
- different colors of the same shape (e.g. red/green/blue gems)
- different parts/components of an assembly (e.g. body, lid, door)
- different distinct objects that merely share an art style

Use the asset NAMES (numeric suffixes like 1..4 or _lv1.._lv5 often signal stages) as a
strong hint, but you MUST confirm with the gameplay FUNCTION text before deciding.

For each family below, decide if it is a stage-progression family. If yes, also pick:
- "anchor": the member representing the MOST intact / fullest / pristine state — this is
  the visual baseline the other stages derive from.
- "order": ALL members ordered from most-intact (the anchor, first) to most-destroyed (last).

Families:
{families_block}

Return ONLY JSON (no markdown), listing ONLY the families that ARE stage progressions:
{{
  "stage_families": {{
    "<family_id>": {{"anchor": "<member name>", "order": ["<most intact>", ..., "<most destroyed>"]}}
  }}
}}
If none qualify, return {{"stage_families": {{}}}}."""

    if client is None:
        client = gemini_api.get_client()

    def _call():
        return client.models.generate_content(
            model=model,
            contents=rubric,
            config=types.GenerateContentConfig(response_mime_type='application/json'),
        )

    resp = gemini_api._with_retries(
        _call, 'detect_stage_families',
        validate=lambda r: json.loads(r.text))
    try:
        data = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(
            f'Stage-family detector returned invalid JSON: {resp.text[:300]}') from e

    detected: dict[str, dict] = {}
    for fam, spec in (data.get('stage_families') or {}).items():
        if fam not in families:
            continue
        member_names = {a['name'] for a in families[fam]}
        order = [n for n in (spec.get('order') or []) if n in member_names]
        anchor = spec.get('anchor')
        if anchor not in member_names:
            anchor = order[0] if order else None
        if anchor and order[:1] != [anchor]:
            # keep anchor first regardless of what the model listed
            order = [anchor] + [n for n in order if n != anchor]
        if len(order) >= 2 and anchor:
            detected[fam] = {'anchor': anchor, 'order': order}
    return detected


def expand_stage_progression(
    family_id: str,
    targets: list[dict],
    style_text: str,
    *,
    theme_text: str | None = None,
    explicit_order: list[str] | None = None,
    client=None,
    model: str = gemini_api.DEFAULT_CRITIC_MODEL,
    config: dict | None = None,
) -> dict | None:
    """LLM-expand a multi-stage family into discrete, mutually-distinct per-stage visuals.

    ``explicit_order`` (from LLM auto-detection) supplies the chain order for families
    with no numeric ``lv``; otherwise order is derived from ``lv`` + the configured anchor.
    Returns None when the family has fewer than 2 chainable stages.
    """
    from google.genai import types

    cfg = config or load_config()
    order = stage_order(family_id, targets, cfg, explicit_order=explicit_order)
    if len(order) < 2:
        return None

    ref_from = ref_from_for(order)
    meta = get_family_meta(family_id, cfg)
    series_note = meta.get('series_note', '')
    by_name = {a['name']: a for a in family_assets(targets, family_id)}
    n = len(order)

    # Feed the model each stage in intact->destroyed order, with any gameplay hint.
    stage_lines = []
    for pos, name in enumerate(order):
        a = by_name.get(name, {})
        lv = _lv(a)
        authored = _state(a)
        hint_bits = []
        if lv is not None:
            hint_bits.append(f'HP level {lv}')
        if authored:
            hint_bits.append(authored)
        fn = a.get('function')
        if fn:
            hint_bits.append(fn[:160])
        stage_kind = 'MOST intact/full' if pos == 0 else (
            'MOST depleted/consumed' if pos == n - 1 else f'stage {pos + 1} of {n}')
        hint = f' — {"; ".join(hint_bits)}' if hint_bits else ''
        stage_lines.append(f'- {name} ({stage_kind}){hint}')
    stages_block = '\n'.join(stage_lines)
    theme_line = f'\n[Theme concept] {theme_text}' if theme_text else ''

    rubric = f"""You are a game art director for a match-3 game.

[Family] {family_id}
[Series meaning] {series_note}
[Target art style] {style_text}{theme_line}

This family is the SAME object shown at {n} progressive stages, ordered below from the
MOST intact/full to the MOST depleted/consumed.

FIRST, decide the ONE depletion dimension that is NATURAL for THIS specific object and
theme — do NOT default to "shattered/broken debris" for everything. Pick the axis that a
player would find believable for this object, e.g.:
- a pool / puddle / drink → the LIQUID LEVEL drops (surface lowers, more empty basin shows,
  wet area shrinks); the vessel/basin itself stays intact.
- a rope / net / fabric → it FRAYS and loosens (strands break, mesh sags); the material thins.
- a stack/pile (bottles, coins, crates) → the COUNT drops (fewer items remain).
- a solid wooden crate / stone block → THEN cracks, chips and missing chunks are appropriate.
Report this choice in "depletion_axis" (a short phrase, e.g. "water level", "fraying",
"remaining count", "structural cracks").

THEN write a SHORT, CONCRETE visual spec for each stage so that:
1. All stages are clearly the SAME object and design (identical base shape, material, palette).
   Only the chosen depletion axis changes — do NOT turn the whole object into rubble unless
   physical shattering is genuinely the natural axis for it.
2. Each stage is UNMISTAKABLY different from its neighbours when viewed small (~70px):
   use DISCRETE, readable steps along that axis — not subtle gradients
   (e.g. water in clear quarter steps, whole strands gone, one fewer item — not faint scratches).
3. The change is MONOTONIC along the order (depletion only ever increases).

Stages (most intact first):
{stages_block}

Return ONLY JSON (no markdown):
{{
  "depletion_axis": "short phrase naming the single dimension that changes",
  "stages": {{
    {', '.join(f'"{name}": "concrete visual for this stage"' for name in order)}
  }}
}}"""

    if client is None:
        client = gemini_api.get_client()

    def _call():
        return client.models.generate_content(
            model=model,
            contents=rubric,
            config=types.GenerateContentConfig(response_mime_type='application/json'),
        )

    resp = gemini_api._with_retries(
        _call, f'expand_stage_progression({family_id})',
        validate=lambda r: json.loads(r.text))
    try:
        data = json.loads(resp.text)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(
            f'Stage planner returned invalid JSON: {resp.text[:300]}') from e

    raw = data.get('stages') or {}
    depletion_axis = str(data.get('depletion_axis', '')).strip()
    stages: dict[str, dict] = {}
    for name in order:
        visual = str(raw.get(name, '')).strip()
        if not visual:
            raise RuntimeError(f'Stage planner missing visual for {name}')
        stages[name] = {'visual': visual, 'ref_from': ref_from.get(name)}

    return {
        'family': family_id,
        'concept': theme_text,
        'style': style_text,
        'depletion_axis': depletion_axis,
        'anchor': order[0] if order else None,
        'order': order,
        'stages': stages,
    }


def stage_note_for_asset(asset_name: str, stage_plan: dict | None) -> str:
    """Prompt fragment describing THIS stage's target look + the required visible step."""
    if not stage_plan:
        return ''
    entry = stage_plan.get('stages', {}).get(asset_name)
    if not entry:
        return ''
    axis = stage_plan.get('depletion_axis') or 'depletion'
    lines = [f'[This stage\'s target look] {entry["visual"]}']
    ref = entry.get('ref_from')
    if ref:
        ref_visual = stage_plan.get('stages', {}).get(ref, {}).get('visual', '')
        lines.append(
            f'[Progression — MUST be obvious] The attached previous-stage reference is '
            f'"{ref}" ({ref_visual}). This stage is one step FURTHER along "{axis}": show '
            f'clearly MORE {axis} than it, in a discrete step a player notices instantly at '
            f'~70px. Keep the same base object, material and style intact — change ONLY '
            f'"{axis}", do NOT turn the object into unrelated rubble.')
    return '\n' + '\n'.join(lines)


if __name__ == '__main__':
    # self-check: order + ref chain wiring, no network needed
    fake_targets = [
        {'name': 'Crt1', 'family': 'crate', 'lv': 1, 'state': 'almost destroyed'},
        {'name': 'Crt2', 'family': 'crate', 'lv': 2, 'state': 'visibly damaged'},
        {'name': 'Crt3', 'family': 'crate', 'lv': 3, 'state': 'slightly damaged'},
        {'name': 'Crt4', 'family': 'crate', 'lv': 4, 'state': 'intact'},
    ]
    cfg = {'families': {'crate': {'anchor_asset': 'Crt4', 'stage_progression': True,
                                  'series_note': 'same crate, progressive damage'}}}
    assert is_stage_family('crate', cfg)
    assert not is_stage_family('elements', cfg)
    order = stage_order('crate', fake_targets, cfg)
    assert order == ['Crt4', 'Crt3', 'Crt2', 'Crt1'], order
    chain = ref_from_for(order)
    assert chain == {'Crt4': None, 'Crt3': 'Crt4', 'Crt2': 'Crt3', 'Crt1': 'Crt2'}, chain
    plan = {'stages': {
        'Crt4': {'visual': 'intact crate', 'ref_from': None},
        'Crt3': {'visual': 'one slat cracked', 'ref_from': 'Crt4'},
    }}
    note = stage_note_for_asset('Crt3', plan)
    assert 'MUST be obvious' in note and 'Crt4' in note, note
    assert stage_note_for_asset('Crt4', plan).find('Progression') == -1

    # explicit_order path (LLM-detected families with no numeric lv)
    nolv = [{'name': 'BoxA', 'family': 'box'}, {'name': 'BoxB', 'family': 'box'},
            {'name': 'BoxC', 'family': 'box'}]
    eo = stage_order('box', nolv, {'families': {}}, explicit_order=['BoxA', 'BoxB', 'BoxC', 'Ghost'])
    assert eo == ['BoxA', 'BoxB', 'BoxC'], eo  # Ghost filtered (not a target)
    assert family_assets(nolv, 'box') == nolv
    print('stage_planner self-check ok')
