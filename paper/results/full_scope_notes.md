# Full-scope eval notes (GC-Bench pilot)

**Run date:** 2026-08-24
**Scope:** all 63 assets in `art_pipeline/asset_roles.json` (previous tables used a hand-picked 12)
**Judge:** GPT-4o (cross-model; generator is Gemini) · **Cohesion:** DINOv2-small, no model judgment
**Data:** `gcbench_full_scope.csv` · raw `auto_eval_full_openai.json`, `auto_eval_full_cohesion.json`
**Reproduce:**

```bash
HF_HUB_OFFLINE=1 python scripts/auto_eval.py --scope full --tasks cohesion \
  --runs fruit_3dCartoonSimple,cat_3dCartoonSimple,ocean_3dCartoonSimple,SteamPunk_3dCartoonSimple,human \
  --out paper/results/auto_eval_full_cohesion.json

python scripts/auto_eval.py --scope full --tasks role,stage --judge openai --stage-repeats 3 \
  --runs fruit_3dCartoonSimple,cat_3dCartoonSimple,ocean_3dCartoonSimple,SteamPunk_3dCartoonSimple,human \
  --out paper/results/auto_eval_full_openai.json
```

Ground truth is ontology-derived (`category`, `family`, `lv` ordering), so labels are human-written,
not model opinions. `--scope core` still reproduces the old 12-asset paper tables.

---

## Headline: the human-art baseline breaks two of our metrics

| Run | Role acc (63) | Stage τ macro | DINOv2 cohesion |
|---|---|---|---|
| fruit | 0.810 | +0.503 | 0.654 |
| cat (pet) | 0.857 | **+0.904** | 0.653 |
| ocean | 0.810 | +0.806 | 0.615 |
| steampunk | 0.857 | +0.627 | 0.642 |
| **human (shipped art)** | **0.889** | +0.586 | **0.490** |

### 1. Cohesion is NOT a quality metric — it is a sameness metric

Shipped human art scores the **lowest** cohesion of all five packs (0.490 vs 0.615–0.654), and it is
lowest in almost every family. If higher cohesion were better, we would be claiming our generator
beats the human artists that shipped the actual game. It does not; the generator is *more repetitive*.

**Consequence for the paper:** the existing claim "B3 has the highest crate cohesion 0.812, therefore
better" (see `ablation_notes.md`) is **not supported as a quality claim**. Cohesion must be reported
as a descriptive statistic with the human level as the *reference point*, not as a maximization
target. A pack far above the human level is a style-collapse warning, not a win.

This is now our strongest E&D-track finding: a widely-used set-consistency proxy is
non-monotone w.r.t. shippability, and you only see it once a human reference is in the benchmark.

### 2. Role recognition: AI packs sit below human art, and the gap is in obstacles

Human 0.889 is the ceiling; AI packs land 0.810–0.857. So role accuracy *does* behave like a
quality metric (unlike cohesion), and there is real headroom — good news for the metric's validity.

Dominant error for every pack, human included: **obstacle → element / powerup** (52 of 63 assets are
obstacles, so this dominates). The judge cannot tell a blocker from a match piece at 70px.
`cat` is a striking outlier: element accuracy **0.20** (4/5 elements read as power-ups), yet its
overall 0.857 is one of the highest — a per-class breakdown is mandatory, the aggregate hides it.

### 3. Stage ordering is now usable, and fruit is the worst theme

Old numbers (single ordering per condition: 0.33 / −0.67 / 0.67 / 0.0) were noise. With 4 stage
families × 3 shuffled repeats, the ranking is stable and interpretable: cat +0.904 > ocean +0.806 >
steampunk +0.627 > **human +0.586** > fruit +0.503.

Two things to note. First, `water_chiller` (11 stages) is the discriminative task — everything
scores 0.59–0.79 there and nobody solves it. Second, human art scoring mid-pack means progression
legibility is genuinely hard for a VLM even on shipped assets, so **τ should be read as
"VLM-legible progression", not "correct progression"**. Do not claim a pack above human τ is better
than human art.

---

## What this changes in the paper

1. **Drop** "higher cohesion = better". Reframe as: cohesion has a human reference band; deviation in
   either direction is a defect (too low = style drift, too high = style collapse).
2. **Keep** role accuracy as a quality metric, but always report per-category — aggregates hid a
   0.20 element accuracy behind a 0.857 overall.
3. **Report** stage τ with repeats and per-family, and treat the 11-stage chiller as the hard slice.
4. **Human art is the calibration anchor of the benchmark, not just an upper bound.** Two of three
   metrics only became interpretable once it was included. This is the argument for why GC-Bench
   needs shipped art in it — and the reason to resolve the IP question fast.

## Open

- 52/63 assets are obstacles → role task is unbalanced; consider reporting macro-average over
  categories alongside micro accuracy.
- Cohesion here is measured within `family`, which mixes progression families (crate) with
  variant families (elements). Splitting the two would sharpen the "sameness vs drift" reading.
- Still single-generator (Gemini) for all four AI packs; external baseline remains the top gap.
