# Full-scope eval notes (GC-Bench pilot)

**Run date:** 2026-08-24 (corrected 16:20 — see "Retracted" below)
**Scope:** all 63 assets in `art_pipeline/asset_roles.json` (previous tables used a hand-picked 12)
**Judge:** GPT-4o (cross-model; generator is Gemini) · **Cohesion:** DINOv2-small, no model judgment
**Data:** `gcbench_full_scope.csv` · raw `auto_eval_full_openai.json`, `auto_eval_human_openai.json`,
`auto_eval_full_cohesion.json`

```bash
HF_HUB_OFFLINE=1 python scripts/auto_eval.py --scope full --tasks cohesion \
  --runs fruit_3dCartoonSimple,cat_3dCartoonSimple,ocean_3dCartoonSimple,SteamPunk_3dCartoonSimple,human,applied \
  --out paper/results/auto_eval_full_cohesion.json

python scripts/auto_eval.py --scope full --tasks role,stage --judge openai --stage-repeats 3 \
  --runs human,applied --out paper/results/auto_eval_human_openai.json
```

Ground truth is ontology-derived (`category`, `family`, `lv` ordering), so labels are human-written,
not model opinions. `--scope core` still reproduces the old 12-asset paper tables.

---

## Retracted: the first version of these notes measured the wrong directory

`godot_demo/resources/sprites/` is **not** human art — `art_pipeline/apply.py` overwrites it with
`DEFAULT_PACKED_ART_RUN` (currently `pixar_cartoon`). The first run therefore compared four AI packs
against a fifth AI pack and concluded "human art has the *lowest* cohesion (0.490)". **That finding
was an artifact and is withdrawn.**

Shipped M8 art survives only in `godot_demo/resources/sprites_original_backup/` (63 PNGs, verified
md5-distinct from the applied pack). `resolve_run('human')` now points there, `'applied'` exposes the
overwritten pack, and `--self-check` asserts the two differ so this cannot silently recur.

---

## Corrected results

| Run | Role acc (63) | element | obstacle | Stage τ macro | DINOv2 cohesion |
|---|---|---|---|---|---|
| fruit | 0.810 | 1.00 | 0.79 | +0.503 | 0.654 |
| cat | 0.857 | 0.20 | 0.90 | **+0.904** | 0.653 |
| ocean | 0.810 | 0.60 | 0.81 | +0.806 | 0.615 |
| steampunk | 0.857 | 0.60 | 0.86 | +0.627 | 0.642 |
| applied (`pixar_cartoon`, AI) | 0.762 | 0.60 | 0.81 | +0.649 | 0.573 |
| **human (shipped M8)** | **0.746** | **0.00** | 0.79 | +0.586 | **0.711** |

### 1. Cohesion: human art is now the *highest* (0.711 vs AI 0.573–0.654)

The direction is the opposite of the retracted claim, and this is the more comfortable result: it
means cohesion behaves like a quality signal, and every AI pack still has headroom to the human
level. The per-family split is where it gets interesting — human art wins on the *structural*
families (`water_chiller` 0.839, `beverage_chiller` 0.715, `postmark` 0.594, `powerups` 0.450,
`movable` 0.504) while AI wins on the *variant* families (`elements` 0.955 vs human 0.368, `pool`
0.949 vs 0.685, `crate` 0.933 vs 0.699).

Read carefully, that is one finding, not two: **AI packs are more self-similar within a family, human
art is more coherent across the pack.** Human elements are deliberately *dissimilar* (0.368) because
players must tell five colors apart at a glance — low intra-family similarity is the design intent,
not a defect. So intra-family cohesion is still not a metric to maximize; it is family-dependent, and
`elements` in particular should probably be scored for *distinguishability* instead.

**Consequence for the paper:** the existing "B3 crate cohesion 0.812 is highest, therefore better"
claim survives as a *relative* statement between conditions, but must not be framed as approaching an
ideal — human crate cohesion is only 0.699, i.e. B3 (0.812) is already *above* the shipped level.

### 2. Role recognition: human art scores LOWEST (0.746), and its elements score 0.00

This is the finding that matters, and it is not a bug: all five human match elements were labelled
something other than `element` by GPT-4o. The shipped game's elements are stylised objects that a VLM
does not read as generic "match pieces", whereas the AI fruit pack (round, plump, uniform template)
scores 1.00.

So role accuracy is **not** a "closer to human = better" metric either. A VLM judge prefers the
prototypical, template-like rendering that our generator produces. Two readings, and we cannot yet
separate them:

1. AI packs are genuinely more legible at 70px than shipped art (plausible — the ontology explicitly
   optimises for icon-like readability).
2. The VLM has a prototype bias that human artists ignore because real players learn a tileset in
   seconds.

Reading 2 is why a human study is not optional. **Do not claim AI art beats shipped art on
readability from this number alone.**

### 3. Stage ordering: human mid-pack (+0.586), and it is worst on the short families

Human τ: crate 0.333, pool 0.333, `beverage_chiller` 0.933, `water_chiller` 0.745. AI `cat` reaches
+0.904 macro. Same caveat as above: τ measures *VLM-legible* progression, and shipped 4-stage crates
apparently do not telegraph damage order to a VLM. `water_chiller` (11 stages) stays the
discriminative slice — nothing scores above 0.79.

---

## Judge swap: the "prototype bias" reading does NOT survive (2026-08-24, evening)

Re-ran the full 63-asset role task with **Gemini-3.5-flash as judge** (same protocol, same
ontology GT) to test this morning's headline that human art scores worst. It does not replicate.

| Pack | Gemini micro | GPT-4o micro | Gemini macro | GPT-4o macro | Gemini elem | GPT-4o elem |
|---|---|---|---|---|---|---|
| fruit | 0.825 | 0.810 | 0.857 | 0.897 | 1.00 | 1.00 |
| cat | 0.857 | 0.857 | 0.866 | 0.776 | 1.00 | 0.20 |
| ocean | 0.889 | 0.810 | 0.831 | 0.852 | 0.60 | 0.60 |
| steampunk | 0.841 | 0.857 | 0.816 | 0.866 | 0.80 | 0.60 |
| **human** | **0.873** | **0.746** | 0.826 | 0.697 | **0.60** | **0.00** |

Where human art ranks among the five packs:

| Metric | human rank |
|---|---|
| Gemini micro | 4 / 5 |
| GPT-4o micro | **1 / 5 (worst)** |
| Gemini macro | 2 / 5 |
| GPT-4o macro | **1 / 5 (worst)** |

**GPT-4o calls human art the worst pack; Gemini calls it the 2nd best.** The `element` column is the
crux: GPT-4o scores human elements **0.00**, Gemini scores the same five images **0.60**. Likewise
`cat` elements are 0.20 for GPT-4o and 1.00 for Gemini.

Per-asset agreement between the two judges is only **0.825 (260/315)**, and the disagreements are
not uniform — they concentrate exactly on the assets that drive the headline.

### What this means

1. **Retract the "VLM prototype bias" framing as a property of VLM judges.** It is a property of
   *GPT-4o*. One judge's idiosyncrasy was about to become a paper's headline.
2. The real, defensible finding is stronger and is about verification, not art:
   **single-judge conclusions are not reproducible.** Two judges that each pass a five-check
   validity battery (below) still rank the same five packs almost inversely. Any paper reporting
   VLM-judged art quality from one judge is reporting noise it cannot see.
3. Micro vs macro also flips rankings (Gemini: 4th micro → 2nd macro), because 52/63 assets are
   obstacles. Both must be reported.
4. This is now the natural Pillar-1 result for the workshop: we have a concrete, quantified case
   where the verifier — not the artifact — determined the conclusion.

### Judge validity battery

Both judges were validated before use (`--validate-judge`, n=10 balanced, results in
`judge_validation_{gemini,openai}.json`):

| Check | Gemini | GPT-4o |
|---|---|---|
| 1 protocol compliance | 1.000 | 1.000 |
| 2 test–retest agreement | 0.900 | 0.900 |
| 3 label-permutation invariance | 0.900 | 0.800 |
| 4 blind control (real vs blank image) | 0.700 vs 0.100 | 0.700 vs 0.100 |
| 5 beats constant-majority guess | 0.700 vs 0.300 | 0.700 vs 0.300 |

Both **USABLE**. Check 4 matters most: on a blank grey image both judges answered `background`
10/10, confirming they read the image rather than the prompt priors. So the disagreement above is
not a broken judge — it is two *valid* judges genuinely disagreeing, which is the worse and more
interesting case.

```bash
python scripts/auto_eval.py --validate-judge --judge openai --validate-pack human
python scripts/auto_eval.py --validate-judge --judge gemini --validate-pack human
python scripts/auto_eval.py --verify-gt          # ontology labels vs engine registry
```

---

## What this changes in the paper

1. Cohesion is family-dependent, not monotone. Report per-family with the human level as a reference
   band; `elements` wants distinguishability, `crate`/`pool` want progression coherence.
2. **Role accuracy is judge-dependent.** Never report it from a single judge. GPT-4o and Gemini rank
   human art 1st-worst vs 2nd-best on identical images. Report both judges + inter-judge agreement,
   and report micro and macro (52/63 assets are obstacles).
3. Stage τ needs repeats (done: 3) and per-family reporting; 11-stage chiller is the hard slice.
4. **The human reference is what makes any of this interpretable** — and it flipped the sign of two of
   our three conclusions within one afternoon. That is the argument for GC-Bench. Dataset release is
   cleared, so the 63 shipped PNGs + ontology + engine-grounded labels can all ship.
5. **Do not claim anything about art quality from VLM judges alone.** The defensible claim is about
   the verifiers: validated judges disagree, so single-judge art evaluation is unreliable.

## Open

- Third judge (Claude) is wired and awaits `ANTHROPIC_API_KEY`. With 3 judges we can report pairwise
  agreement and whether *any* ranking is stable, rather than a 2-judge coin flip.
- 52/63 assets are obstacles → macro-average now computed in `task_role_category`; older JSONs need
  it derived from `by_category`.
- All four themed packs plus `applied` are Gemini output; an external generator is a confound control
  for judge affinity (see `docs/submission/external-generator-tradeoff.md`), scheduled post-workshop.
- Whether human elements are genuinely less legible at 70px, or whether GPT-4o penalises stylised
  art, still needs human subjects. Survey is built.
