# Mini Human Evaluation Protocol (T6)

**Study slice:** Fruit × 3dCartoonSimple (primary) + Pet / Ocean (extended packs)  
**Style:** `3dCartoonSimple` · **Steampunk:** skipped  
**Target n:** ≥6 (internal OK) · descriptive stats if underpowered  
**RQs:** RQ2 (pack quality) · RQ4 (agency)  
**Instrument:** static site `paper/human_eval/` (zh-Hant UI; schema `match3-human-eval-v2`)  
**Updated:** 2026-07-22

---

## Materials

| ID | Material | Source |
|----|----------|--------|
| Fruit B1/B2/B3 | 70px sprites + grids | `generated_art/research_B*_fruit` → `human_eval/assets/` |
| Pet B1/B2/B3 | grids per condition | `research_B*_{pet}` → `assets/themes/pet/{B1,B2,B3}/` |
| Ocean B1/B2/B3 | grids per condition | `research_B*_{ocean}` → `assets/themes/ocean/{B1,B2,B3}/` |
| Manifest | theme list + available conditions | `human_eval/themes.json` (v2) |

Task 1–2 blind labels: Pack A / Pack B = Fruit B1↔B3 (randomize per participant; store `pack_a_is`).  
Task 3: left/right blinds; download records true conditions.

---

## Early warm-up (before Task 1) — 4 items

1. Priority for “shippable” (role clarity / cuteness / theme fit / progression)  
2. Confidence judging @ ~70px (1–5)  
3. Biggest risk if auto-pass “looks OK” art  
4. Who should decide “looks playable”

---

## Task 1 — Role recognition @ ~70px (8 trials)

Forced choice: match / h-power / v-power / obstacle / unsure.  
Assets: Red, Blu, Soda0d, Soda90, Crt4, Crt1, Yel, LtBl · half Pack A, half Pack B.

**Metric:** accuracy overall; by pack; by role class.

---

## Task 2 — Stage ordering (crate)

Order Crt4→Crt1 (intact→destroyed) for Pack A then Pack B.  
Then one forced item: which pack’s progression was clearer (A / B / tie).

**Metric:** Kendall τ vs `Crt4 > Crt3 > Crt2 > Crt1`; clearer-pack choice.

---

## Task 3 — Pairwise preference (dynamic ~17 pairs)

Built from `themes.json` conditions:

| Block | Compare | Foci (approx.) |
|-------|---------|----------------|
| Fruit | B1 vs B3 | overall, elements, powerups, crate |
| Fruit | B1 vs B2 | overall, elements, powerups |
| Fruit | B2 vs B3 | overall, powerups |
| Pet | B1 vs B3 | overall, powerups, crate |
| Pet | B1 vs B2 | overall |
| Ocean | B1 vs B3 | overall, powerups, crate |
| Ocean | B1 vs B2 | overall |

**Metric:** win rates by theme × compare × focus (descriptive).

---

## Task 5 — Multi-theme comparison (B3 packs)

Themes: Fruit + Pet + Ocean (B3 contact sheets).

1. Best shippable theme overall  
2. Clearest power-ups  
3. Clearest crate progression  
4. Best pack cohesion  
5. Clearest elements at board size  

---

## Task 4 — Agency Likert (1–7)

After brief staging / `needs_review` / apply explanation:

1. enable · 2. steer · 3. final_say · 4. trust_critic · 5. board · 6. friction  

**Optional open:** Who decided what looked playable?

---

## Procedure (~20–30 min)

1. Consent → context  
2. Early warm-up → Task 1 → Task 2 (+ clearer) → Task 3  
3. Task 5 (if ≥2 themes in manifest)  
4. Agency brief → Task 4 → download JSON/CSV  

Deploy: copy `paper/human_eval/*` → `docs/` for GitHub Pages, or local `python3 -m http.server`.

---

## Aggregation

Participants email downloaded files → `paper/results/responses/`  
Aggregate → `paper/results/human_eval_summary.csv` (do **not** invent numbers in `main.tex` until then).

---

## Status

| Item | State |
|------|-------|
| Protocol + static survey | ✅ |
| Stimuli Fruit/Pet/Ocean B1–B3 exported | ✅ |
| Pages URL + n≥6 | ⬜ next |
| Summary CSV + fill `tab:human` | ⬜ |
