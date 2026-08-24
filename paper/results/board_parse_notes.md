# Board-parse evaluation notes

**Run date:** 2026-08-24
**What it is:** render each pack's sprites into real level layouts, then parse the board back and
compare per-cell against the level JSON that `match_engine` actually plays.
**Why it exists:** every other metric here asks a model for an opinion (role accuracy, pairwise) or
measures a similarity whose good direction is unclear (cohesion). This one has an answer key that
predates the question.

**Ground truth chain:** `godot_demo/levels/*.json` per-cell tile ids → `tile_defs.TILE_REGISTRY`
(verified by `auto_eval.py --verify-gt`: 41 assets, 0 category mismatches, 0 stage-HP mismatches).
Layering follows `board.Cell`: `upper` (rope/mud) over `middle` over `bottom` (puddle). `#N`
instance suffixes on 2x2 objects are stripped; `void` cells are excluded.

```bash
python scripts/board_parse_eval.py --self-check
python scripts/board_parse_eval.py --packs human,fruit_3dCartoonSimple,cat_3dCartoonSimple,ocean_3dCartoonSimple,SteamPunk_3dCartoonSimple \
  --parser template --cell 70,48,32,24,16 --levels 20 --out paper/results/board_parse_template.json
python scripts/board_parse_eval.py --packs human,fruit_3dCartoonSimple,cat_3dCartoonSimple \
  --parser vlm --judge openai --cell 70 --levels 8 --out paper/results/board_parse_vlm_openai.json
```

---

## Methodology trap found and fixed: degenerate candidate sets

The first run scored 0.97–1.00 for every pack at every cell size down to 16px — obviously wrong.
Cause: candidates were restricted to the tiles present in *the current level*, and most official
levels use very few distinct tiles. Sampled 20 levels: **per-level median k=3**, several levels k=1.
The task had collapsed to a 1-of-2 choice, which no art quality can fail.

Fixed by using a **global candidate set** (every tile appearing anywhere in the sample that exists
in the pack): **k=19**. `--self-check` now asserts per-level median k ≤ 3 and global k ≥ 3× that, so
the degeneracy cannot silently return. `--per-level-candidates` keeps the old behaviour, documented
as degenerate.

---

## Result 1: template matching saturates — and that is itself the finding

Normalised cross-correlation, k=19, 20 levels, 1121 cells:

| Pack | 70px | 48px | 32px | 24px | 16px |
|---|---|---|---|---|---|
| human | 0.980 | 0.942 | 0.934 | 0.922 | 0.934 |
| fruit | 0.967 | 0.959 | 0.959 | 0.959 | 0.959 |
| cat | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| ocean | 0.959 | 0.959 | 0.959 | 0.959 | 0.959 |
| steampunk | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Barely degrades to 16px. **Do not report this as "the art is legible".** Template matching gets a
per-cell crop that is perfectly axis-aligned with a template drawn from the same source PNG at the
same scale — it is close to the tautological setting warned about in the script docstring, and it
does not model an observer. Its one honest use: **pixel distinguishability**. Every error is
`obstacle→obstacle` (e.g. Crt1/Crt2 damage stages), i.e. the only thing NCC cannot separate is
adjacent stages of the same object — which is exactly the failure the ontology cares about, and it
is worst for human art at 16px (74 errors).

`category_accuracy` is 1.000 everywhere: NCC never confuses an element with an obstacle. So the
coarse task is trivial at the pixel level and only the fine-grained stage task carries signal.

## Result 2: VLM board parse discriminates, but rankings do NOT survive a parser swap

First pass conflated two different failures: a judge that answers wrongly and a judge that
**declines to answer a cell** (`missing`). Gemini abstained on up to 38.9% of cells, and folding
those into "wrong" turns a compliance problem into an apparent art-quality problem. Scoring now
reports `abstain_rate`, `off_label_rate` and `accuracy_on_answered` separately (guarded by a
`--self-check` assertion).

k=12, 8 levels, 422 cells, 70px:

| Pack | template | GPT-4o | GPT-4o answered | GPT-4o abstain | Gemini | Gemini answered | Gemini abstain |
|---|---|---|---|---|---|---|---|
| human | 0.980 | 0.483 | 0.483 | 0.000 | 0.846 | 0.846 | 0.000 |
| fruit | 0.967 | 0.363 | 0.363 | 0.000 | 0.637 | 0.731 | 0.128 |
| cat | 1.000 | 0.289 | 0.289 | 0.000 | 0.465 | 0.636 | 0.270 |
| ocean | 0.959 | 0.337 | 0.337 | 0.000 | 0.512 | 0.512 | 0.000 |
| steampunk | 1.000 | 0.393 | 0.393 | 0.000 | 0.211 | 0.345 | **0.389** |

| Parser | ranking (best → worst) |
|---|---|
| template (NCC) | cat > steampunk > human > fruit > ocean |
| GPT-4o | human > steampunk > fruit > ocean > cat |
| Gemini | human > fruit > cat > ocean > steampunk |

Kendall τ between rankings (5 packs): **GPT-4o vs Gemini 0.20**, GPT-4o vs template 0.00,
Gemini vs template 0.00.

### Correction to an earlier reading in this file

An intermediate 3-pack run had both judges agreeing on human > fruit > cat, and I wrote that
"given a task with a real answer key the judges converge". **Extending to 5 packs destroys that**
(τ=0.20). With 3 items, two rankings coincide by chance 1/6 of the time; that agreement was noise.
The corrected statement is narrower and matches `full_scope_notes.md`:

- **Both judges agree human art is best** (0.483 / 0.846, first place under both, and under both the
  answered-only variant). That single fact is stable across judges, protocols (isolated-sprite,
  board-parse) and scoring variants.
- **Everything below first place is judge-dependent.** `steampunk` is 2nd for GPT-4o and last for
  Gemini; `cat` is last for GPT-4o and 3rd for Gemini. Do not report a full ranking of AI packs.

### The abstention signal is the most actionable result

Gemini declined 38.9% of `steampunk` cells, 27.0% of `cat`, 12.8% of `fruit`, and **0%** of human and
ocean. GPT-4o never abstained. A pack that makes one observer refuse to commit on 2 of every 5 cells
is not shippable, and raw accuracy alone scores that identically to ordinary error. Abstention rate
is cheap, has an unambiguous good direction (lower), and is the one signal here that behaves.

`category_accuracy` stays high (0.61–1.00) and nearly all residual error is intra-category
`obstacle→obstacle`: **which** crate/chiller stage, not **what kind of object**. Stage
disambiguation at board scale is the hard problem this benchmark exposes.

---

## Honest limitations

1. **Not human playability.** A VLM reading a static board is not a player: no animation, no UI, no
   learning the tileset over a few minutes. This measures first-glance machine legibility.
2. **Template matching is near-tautological** as constructed (aligned crops, same-source templates).
   Report it only as pixel distinguishability, never as legibility.
3. **Class imbalance is severe**: 401/422 cells are obstacles (official early levels are
   obstacle-heavy). Micro accuracy is dominated by obstacles; macro is reported alongside. Element
   n=21 is too small to rank packs on.
4. Cell-size sweep does not degrade for template, so it does not yet demonstrate a scale effect.
   The sweep needs the VLM parser to be meaningful, which costs API calls.
5. Levels are official layouts (IP-cleared for release per 2026-08-24 decision), but layouts could
   also be generated procedurally if a cleaner release is wanted.
6. **8 levels per pack, 422 cells, one sample.** No seed variance yet; the 5-pack rankings below
   first place should be treated as unstable until repeated.
7. Claude as a third parser is wired and validated-as-unusable (account has no credit), so the
   agreement result currently rests on two judges.
8. **A 3-pack run in this file previously showed judge agreement that vanished at 5 packs.** Small
   pack counts make rank agreement meaningless; do not report τ on fewer than ~5 items.

## Next

- Repeat with 2–3 level samples (different `--seed`) to get variance on the rankings.
- Run the VLM parser across the cell sweep (70/48/32) to get a real degradation curve.
- Sample levels weighted toward element-heavy layouts to fix the 401:21 imbalance.
- Third judge once Anthropic credit is topped up.
