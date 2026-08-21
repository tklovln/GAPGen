# Locked Scope — NeurIPS 2026 Creative AI (P1)

**Status:** LOCKED 2026-07-22  
**Source decisions:** human notes in `AGENT_TODO.md` (H1–H4)  
**Authoritative for agents:** this file overrides older suggestions in plan/proposal when they conflict.

---

## H1 — Path

| Field | Decision |
|-------|----------|
| Path | **P1** — submit Creative AI research paper by **2026-08-03 AoE** |
| Parallel | P2 (MatchArt-Bench etc.) only **after** submission; do not block 8/3 |
| Track | Paper (Artwork video optional, not required) |

---

## H2 — Authors & attendance

| Field | Decision |
|-------|----------|
| On-site Sydney | **Yes** — presenting author can attend |
| Author list for `\author{}` | **Still open for full names/affiliations** (fill in T9 before submit) |
| Presenting author | Decision-maker for this repo sprint (local: `tkwang`) |

> Agents must not invent coauthor names. Leave `Anonymous` / placeholders until human fills T9.

---

## H3 — Experimental stimuli (LOCKED)

### Style (single style for sprint ablation)

```text
3D Disney Cartoon Style, Simple design, Clean illustrations, Intuitive icon, highly recognizable
```

Short label: `3dCartoonSimple`

### Themes

| Role | Theme concept | Notes |
|------|---------------|-------|
| **Primary (ablation B1–B3)** | **Fruit** | `research_B{1,2,3}_fruit` |
| **Extended (Pet / Ocean × B1–B3)** | **Pet / Ocean** | `research_B{1,2,3}_{pet,ocean}` via `scripts/research_multi_theme.py` |
| **Dropped** | Steampunk | skip for this sprint (do not block survey / paper) |
| **Optional style combo** | **Pet × Ghibli** | `--include-ghibli` → `research_B3_pet_ghibli` |

Survey multi-theme UI reads `paper/human_eval/themes.json`.

### Families (ablation + human eval subset)

```text
elements  +  powerups  +  crate (stage family)
```

- **elements:** Red, Grn, Blu, Yel, Pur  
- **powerups:** at least Soda0d (horizontal), Soda90 / LtBl (vertical) — keep minimal set stable across B1–B3  
- **stage family:** **crate** (`Crt4`→`Crt1` progression; present in existing packs)  
- Pool / chiller: OK for qualitative demo, **not** required for main ablation table

### Existing runs to prefer (reuse)

| Run dir | Style | Theme field in report.json | Use for |
|---------|-------|----------------------------|---------|
| `generated_art/fruit_3dCartoonSimple` | 3dCartoonSimple | report says `Alien` (folder name mismatch) | qualitative / retrospective only; **do not treat as clean Fruit ablation** |
| `generated_art/cat_3dCartoonSimple` | 3dCartoonSimple | `cat` | Pet qualitative, sprite grids, demo |
| `generated_art/ocean_3dCartoonSimple` | 3dCartoonSimple | `ocean` | optional demo |
| `generated_art/SteamPunk_3dCartoonSimple` | 3dCartoonSimple | `SteamPunk` | optional demo |

### New ablation run naming

```text
research_B1_fruit
research_B2_fruit
research_B3_fruit
research_B0_fruit   # optional if time
```

Mode: `theme-swap`  
Flags: `--no-reference-image`  
Assets: elements + powerups + crate only (not full 63-asset pack)

---

## H4 — Research questions (LOCKED)

| Priority | RQ | In paper? |
|----------|----|-----------|
| **Primary** | **RQ2** — Do ontology + dual refs + hybrid critic improve pack consistency / playability vs weaker stacks? | Yes (ablation) |
| **Primary** | **RQ4** — How is creative agency negotiated (enable vs steer; human final say)? | Yes (design + questionnaire) |
| Supporting | RQ1 — task formalization (GGAPG/GGCA) | Yes (framework sections) |
| Light touch | RQ3 — theme-swap creativity/diversity | Qualitative only; no diversity frontier study |

---

## Claim discipline (synced)

**Allowed once evidence lands:** pack consistency / readability gains on Fruit×3dCartoonSimple slice; agency questionnaire descriptives.  
**Forbidden:** T2IS SOTA; “replaces artists”; cross-genre generality; inventing numbers.

---

## Progress (synced 2026-07-22 evening)

| Task | Status |
|------|--------|
| T2 retrospective | ✅ `results/retrospective_summary.*` |
| T3 ablation flags | ✅ `--ablation B0–B3` |
| T4 Fruit ablations | ✅ B1/B2/B3 → `ablation_preliminary.csv` |
| T4b Pet/Ocean | ✅ B1/B2/B3 → `ablation_multi_theme.csv`（Steampunk 不做） |
| T5 figures | ✅ grids in `figures/`; board shot optional |
| T6 human eval | 🟡 instrument+stimuli ✅（`human_eval/` v2）；**待 Pages + n≥6** |
| T7 paper numbers | ✅ Fruit ablation table + grids；human table pending |

### Ablation headline (do not misread) — 3 seeds

**Fruit (main table, mean±std / 3 seeds):**  
B0/B1/B2 pass ≈ 1.00 (postprocess-only; small failed variance); B3 pass 0.89 ± 0.10, needs_review 0.11 ± 0.10, mean_iters 1.95 ± 0.34  
**DINOv2 crate cohesion:** B3 0.81 > B1 0.66 (model-independent)  
**Paper claim:** critic redistributes *variable* friction ≠ higher accept rate is better  

## Auto-eval (replaces human collection)

- `scripts/auto_eval.py`: VLM role-recognition / stage-ordering / pairwise (Gemini or GPT-4o) + DINOv2 cohesion
- Judge default Gemini; `--judge openai` (GPT-4o) for cross-model; key via `_get_key('openai')` (config.py, gitignored)
- Honesty: VLM/DINO are **proxies**, not human; human study = future work

## Next agent / human task

**T6** 部署問卷 + 收樣，或 **T9/T10** bib+polish。  
H1–H4 locked — do not re-ask unless human edits this file.
