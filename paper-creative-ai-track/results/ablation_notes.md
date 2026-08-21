# Ablation notes

**Updated:** 2026-08-11 (GPT-4o cross-model proxy eval added)  
**Primary CSV:** `ablation_preliminary.csv` (Fruit)  
**Extended CSV:** `ablation_multi_theme.csv` (Pet / Ocean)  
**Claim rule:** higher B1/B2 pass_rate ≠ better quality (weaker gates).

---

## Fruit × 3dCartoonSimple (primary table, 3 seeds)

**Runs:** `research_B{0,1,2,3}_fruit` (seed 1) + `_s2`, `_s3`  
**Headline CSV:** `ablation_preliminary.csv` (mean ± std)  
**Per-seed CSV:** `ablation_seeds.csv`

| Condition | Gates | Pass (mean±std) | Needs review | Mean iters | Cohesion / Prog (B3 critic) |
|-----------|-------|-----------------|--------------|------------|------------------------------|
| B0 Naive | postprocess only | 1.00 ± 0.00 | 0.00 | 1.00 | — |
| B1 Ontology | postprocess only | 0.97 ± 0.04 | 0.00 | 1.00 | — |
| B2 + Refs | postprocess only | 0.97 ± 0.04 | 0.00 | 1.00 | — |
| B3 Full | postprocess + VLM critic ≤3 | 0.89 ± 0.10 | 0.11 ± 0.10 | 1.95 ± 0.34 | 9.04 ± 0.93 / 9.78 ± 0.32 |

Models: image `gemini-3.1-flash-image`, critic/planners `gemini-3.5-flash`. n=12 assets/run, 3 seeds.

**Reading:**
1. B0/B1/B2 pass ~1.0 under postprocess-only gates; small `failed` variance (seed 2) is real — do not report a flat 1.00.
2. **B3 friction is variable:** `needs_review` 0.11 ± 0.10 (range 0–0.25 across seeds), mean_iters 1.95 ± 0.34. This variance *is* the point — critic friction is not a fixed constant.
3. Do **not** claim B1/B2 beat B3 on pass rate; their gates are weaker.

## Cross-model proxy eval — judge GPT-4o (generator Gemini)

Script: `scripts/auto_eval.py --judge openai` → `paper/results/auto_eval.json`.
Judge (GPT-4o) ≠ generator/critic (Gemini) → no self-circularity.

**Role recognition @70px** (forced 4-choice, 8 assets):

| Cond | accuracy |
|------|----------|
| B0 | 0.375 |
| B1 | 0.625 |
| B2 | 0.750 |
| B3 | 0.750 |

Monotone rise; B0 collapses power-ups/obstacles onto `match`. This is the headline readability signal.

**Pairwise pack preference** (4 AB-swapped repeats, win rate of the higher condition):

| Compare | win rate |
|---------|----------|
| B1 vs B0 | 0.50 (tie) |
| B2 vs B0 | 0.75 (B2) |
| B3 vs B0 | 0.75 (B3) |
| B2 vs B1 | 1.00 (B2) |
| B3 vs B1 | 1.00 (B3) |
| B3 vs B2 | 0.50 (tie) |

Refs (B2) and critic (B3) both clearly preferred over B1; B2≈B3 (critic changes friction, not appearance).

**Stage ordering (Kendall τ):** B0 0.33 / B1 −0.67 / B2 0.67 / B3 0.0 — **noisy** (single ordering/cond). Not primary evidence; report as limitation only.

## DINOv2 intra-family cohesion (objective, no VLM)

Independent of the generation model (`--tasks cohesion`, `facebook/dinov2-small`):

| Cond | overall | elements | powerups | crate |
|------|---------|----------|----------|-------|
| B0 | 0.524 | 0.532 | 0.395 | 0.575 |
| B1 | 0.556 | 0.528 | 0.448 | 0.658 |
| B2 | 0.566 | 0.544 | 0.428 | 0.673 |
| B3 | 0.605 | 0.522 | 0.463 | **0.812** |

B3 (family anchor + critic) shows highest crate intra-family cohesion (0.812) — supports RQ2 with a model-independent metric, no critic-circularity.

---

## Pet / Ocean × 3dCartoonSimple (extended; survey + appendix)

**Runs:** `research_B{1,2,3}_{pet,ocean}` · script `scripts/research_multi_theme.py`  
**Steampunk:** dropped for survey/paper sprint (local `research_B3_steampunk` may exist; do not put in `themes.json`).

| Theme | Cond | n | Pass | Needs review | Mean iters | Style / Fn / Coh / Prog |
|-------|------|---|------|--------------|------------|-------------------------|
| Pet | B1 | 12 | 1.00 | 0.00 | 1.00 | — |
| Pet | B2 | 12 | 1.00 | 0.00 | 1.00 | — |
| Pet | B3 | 12 | 0.75 | 0.25 | 2.25 | 8.17 / 8.42 / 8.44 / 10.0 |
| Ocean | B1 | 12 | 1.00 | 0.00 | 1.00 | — |
| Ocean | B2 | 12 | 1.00 | 0.00 | 1.00 | — |
| Ocean | B3 | 12 | 0.917 | 0.083 | 1.67 | 9.33 / 9.08 / 9.22 / 9.67 |

Same reading as Fruit: B3 redistributes friction (`needs_review` / retries); do not rank by pass rate alone.

---

## How to read (for paper + agents)

1. **Do not claim B1/B2 beat B3 on pass rate.** Their accept criteria are weaker.
2. **Agency reading:** B3 inserts friction where B1/B2 would ship all tiles.
3. **Readability/preference** use cross-model VLM proxies (GPT-4o judge) + DINOv2; human study is future work.
4. Paper **main ablation table** = Fruit; Pet/Ocean support multi-theme survey + optional appendix.

---

## Figures / survey assets

- Fruit grids: `paper/figures/sprites_grid_research_B{1,2,3}_fruit.png`
- Qualitative Pet (older): `sprites_grid_cat_3dCartoonSimple.png`, `board_scale_70px_cat.png`
- Survey export: `paper/human_eval/themes.json` + `assets/themes/{fruit,pet,ocean}/{B1,B2,B3}/`

---

## Reproduce

```bash
python scripts/research_ablation.py --conditions B1,B2,B3 --force   # Fruit; costly
python scripts/research_postprocess.py --all

PYTHONUNBUFFERED=1 python scripts/research_multi_theme.py --conditions B1,B2,B3 \
  --slugs pet,ocean 2>&1 | tee paper/results/multi_theme_b12.log

python scripts/research_multi_theme.py --skip-generate --export-survey --slugs pet,ocean
```
