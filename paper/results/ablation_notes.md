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

> **SUPERSEDED 2026-08-24.** The table below is one seed under one judge. Rerun at 3 seeds × 2
> judges (`ablation_role_openai.json`, `ablation_role_gemini.json`) and the monotone rise does not
> survive. See "Dual-judge, 3-seed rerun" below — read that instead. Kept here only to show what the
> single-seed protocol reported.

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

---

## Dual-judge, 3-seed rerun (2026-08-24) — what actually replicates

Same 12 runs, role recognition @70px, forced 4-choice, 8 assets, scored independently by both judges.
Both judges passed the 5-check validity battery on this pack (`judge_validation_*.json`).

```bash
python scripts/auto_eval.py --task role --judge openai --runs research_B{0,1,2,3}_fruit{,_s2,_s3} \
  --out paper/results/ablation_role_openai.json      # and again with --judge gemini
```

| Cond | GPT-4o mean±sd | per-seed | Gemini mean±sd | per-seed |
|---|---|---|---|---|
| B0 Naive | 0.375 ± 0.000 | 0.375, 0.375, 0.375 | 0.375 ± 0.000 | 0.375, 0.375, 0.375 |
| B1 Ontology | 0.786 ± 0.139 | 0.625, 0.857, 0.875 | **0.911 ± 0.078** | 1.000, 0.857, 0.875 |
| B2 + Refs | 0.786 ± 0.062 | 0.750, 0.857, 0.750 | 0.780 ± 0.085 | 0.750, 0.714, 0.875 |
| B3 Full | 0.750 ± 0.125 | 0.750, 0.625, 0.875 | **1.000 ± 0.000** | 1.000, 1.000, 1.000 |

**What replicates (report this):**

- **B0 → ontology is a large, judge-independent, seed-independent effect.** B0 = 0.375 under both
  judges with sd = 0.000 across all three seeds — it is not noise, it is a hard floor: without
  ontology conditioning the generator collapses power-ups and obstacles onto `match`, and *both*
  judges see the same collapse. Adding ontology lifts this to 0.75–1.00: **+0.375 (GPT-4o), +0.625
  (Gemini)**. The direction and rough magnitude survive a judge swap and 3 seeds.

**What does NOT replicate (do not report as a result):**

- **The monotone B0 < B1 < B2 < B3 rise.** Neither judge is non-decreasing. GPT-4o ranks
  B1 > B2 > B3 > B0; Gemini ranks B3 > B1 > B2 > B0. Kendall τ between judges over the four
  conditions = **0.333**.
- **Any claim that refs (B2) or critic (B3) improve role recognition over ontology alone (B1).**
  GPT-4o has B1 ≈ B2 > B3; Gemini has B3 > B1 > B2. The two judges disagree on which of the three
  is best, and per-seed sd (0.06–0.14) is comparable to the gaps between them.
- The old single-seed "monotone rise 0.375 → 0.625 → 0.750 → 0.750" was an artifact of n=1 seed and
  n=1 judge.

**Reading.** The ablation supports exactly one causal claim, and it is the claim the method is
actually about: **grounding generation in an ontology of gameplay roles is what makes assets
role-legible.** The two increments layered on top of it (dual visual refs, VLM critic loop) do not
have a role-recognition effect that survives a judge swap — consistent with the earlier finding that
B2 ≈ B3 on pairwise preference, and with `report.json` showing the critic changes *friction*
(needs_review, iters) rather than appearance. Refs/critic should be justified by what they measurably
do (style-drift control, review load), not by role accuracy.

---

## Cross-theme transfer of the ontology effect (2026-08-24, extended 2026-08-25)

B0 previously existed only for fruit, so the ontology effect could not be separated from that one
theme. Generated `research_B0_{pet,ocean}` then `research_B{0,1}_steampunk` (12 assets each, no
critic, max_iters=1 — cheap) and scored B0 vs B1 under both judges. B0 and B1 differ in **exactly
one flag** (`pipeline.py:72-73`: `use_ontology` False/True; refs, critic and max_iters identical),
locked by a `resolve_ablation` self-check — a clean single-variable contrast.

```bash
python scripts/research_multi_theme.py --conditions B0,B1 --slugs steampunk
python scripts/auto_eval.py --task role --judge openai \
  --runs research_B{0,1}_pet,research_B{0,1}_ocean,research_B{0,1}_steampunk \
  --out paper/results/transfer_role_openai.json      # and again with --judge gemini
```

| Theme | Judge | B0 | B1 | Δ |
|---|---|---|---|---|
| fruit (3 seeds) | GPT-4o | 0.375 | 0.786 | **+0.411** |
| fruit (3 seeds) | Gemini | 0.375 | 0.911 | **+0.536** |
| pet | GPT-4o | 0.250 | 0.750 | **+0.500** |
| pet | Gemini | 0.375 | 0.750 | **+0.375** |
| ocean | GPT-4o | 0.500 | 0.875 | **+0.375** |
| ocean | Gemini | 0.500 | 0.875 | **+0.375** |
| steampunk | GPT-4o | 0.250 | 0.500 | **+0.250** |
| steampunk | Gemini | 0.500 | 0.750 | **+0.250** |

**8 of 8 (theme × judge) cells positive. Δ range +0.250 to +0.536, mean +0.384.**

> **SUPERSEDED by the repeated-scoring rerun below.** Every number in this table is a *single*
> scoring pass, and judge run-to-run noise is ±0.250 — the same size as the smallest Δ here. The
> "8 of 8 positive" count is **wrong**: with 3-pass averaging, steampunk/GPT-4o is exactly zero.
> Read the next section instead.

---

## Repeated-scoring rerun (2026-08-25) — the definitive version

Everything above measured each cell **once**, so judge run-to-run noise (±0.250) was inseparable from
effect. Fixed by scoring every cell **3 independent times** with both judges, at `--scope full`
(n=12 assets/cell, i.e. every ontology asset the research packs contain — the packs hold 12 sprites,
not 63, so `--scope full` raises n from 8 to 12, not to 63).

```bash
for P in 1 2 3; do for J in openai gemini; do
  python scripts/auto_eval.py --task role --scope full --judge $J \
    --runs research_B{0,1}_{fruit,pet,ocean,steampunk} \
    --out paper/results/rep_role_${J}_p${P}.json
done; done
```

**Noise is now measured, not assumed:** within-cell sd across 3 passes is **≤0.096, mean 0.025** —
an order of magnitude below the ±0.250 seen in single-pass scoring. Repetition, not more assets, was
the right fix.

| Theme | Judge | B0 (mean±sd) | B1 (mean±sd) | Δ | Δ > 2·SE |
|---|---|---|---|---|---|
| fruit | GPT-4o | 0.500 ± 0.000 | 1.000 ± 0.000 | +0.500 | yes |
| fruit | Gemini | 0.417 ± 0.000 | 0.917 ± 0.000 | +0.500 | yes |
| pet | GPT-4o | 0.167 ± 0.084 | 0.667 ± 0.000 | +0.500 | yes |
| pet | Gemini | 0.195 ± 0.048 | 0.583 ± 0.000 | +0.388 | yes |
| ocean | GPT-4o | 0.833 ± 0.000 | 0.917 ± 0.000 | +0.084 | yes |
| ocean | Gemini | 0.556 ± 0.096 | 0.917 ± 0.000 | +0.361 | yes |
| steampunk | GPT-4o | 0.583 ± 0.000 | 0.583 ± 0.000 | **+0.000** | **no** |
| steampunk | Gemini | 0.417 ± 0.084 | 0.722 ± 0.096 | +0.306 | yes |

### Second retraction: "8 of 8 positive" is false

steampunk/GPT-4o is **exactly zero**, and it is not noise: sd = 0.000 on both conditions, and across
all three passes B0 and B1 got the **identical 5 assets wrong** (Blu, Grn, Pur, Red, Yel — all
elements). The two packs are genuinely different images (different SHA-256). Corrected count:
**7 of 8 cells positive with Δ > 2·SE, 1 cell exactly zero, 0 negative.**

### What the zero cell revealed: the mechanism is category-specific

Breaking Δ down by ontology category over all 24 (theme × judge × category) cells:

| Category | mean Δ | min | max | Δ > 0 |
|---|---|---|---|---|
| obstacle | **+0.417** | +0.000 | **+1.000** | 5/8 |
| powerup | **+0.403** | +0.000 | +0.667 | 6/8 |
| element | +0.217 | +0.000 | +0.467 | 5/8 |

**Δ ≥ 0 in 24 of 24 cells. Zero negative cells.** Of the 8 zero cells, **7 are ceilings**
(B0 already at 1.000 — no headroom), and only 1 is a true zero (steampunk/GPT-4o elements, stuck at
0.00 under both conditions).

The headline number is **obstacles on fruit: 0.00 → 1.00 under both judges independently.** Without
ontology, *every* damage-stage crate is misread; with it, *every* one is read correctly.

**This is the mechanism, and it is exactly what the ontology encodes.** `asset_roles.json` names
gameplay roles and progression stages — which crate is stage 1 of 4, which sprite is a
horizontal-clearing power-up. So it lifts obstacles (+0.417) and power-ups (+0.403) hardest, because
those are the categories whose *identity is a gameplay function that appearance alone underdetermines*.
Elements (the plain match-3 colours) gain least (+0.217): their identity is just colour, which the
generator gets right without being told the rules. **The effect is largest exactly where gameplay
semantics cannot be inferred from pixels** — which is the paper's thesis, now measured rather than
asserted.

### Claim, at the strength the data supports

1. **Ontology grounding never hurts and usually helps: Δ ≥ 0 in 24/24 category cells, 0 negative.**
2. **The gain concentrates on gameplay-defined categories** (obstacle +0.417, powerup +0.403) and is
   weakest on appearance-defined ones (element +0.217).
3. **It is necessary but not sufficient**: steampunk/GPT-4o B1 = 0.583, with all 5 elements still
   unreadable; a theme can defeat it entirely.
4. Noise is characterised (within-cell sd ≤0.096), so per-cell Δ is now reportable — unlike every
   earlier table in this file.

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
