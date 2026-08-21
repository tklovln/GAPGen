# Human Eval Survey (static)

極簡問卷站（**介面繁體中文**），對應 Match-3 Fruit pack 評測（`human_eval_protocol.md`）。  
下載的 JSON/CSV 欄位鍵名仍為英文，方便後續彙整。

## Local preview

```bash
cd paper/human_eval
python3 -m http.server 8765
# open http://localhost:8765
```

Do not open `index.html` via `file://` if images fail to load in some browsers; use a tiny static server.

## GitHub Pages deploy

### Option A — `/docs` on `main` (simplest for this repo)

1. Copy or symlink this folder to repo `docs/`:

```bash
# from repo root
rm -rf docs
mkdir -p docs
cp -R paper/human_eval/* docs/
```

2. GitHub → Settings → Pages → Build from branch → `main` / `/docs`
3. Site URL: `https://<user>.github.io/<repo>/`

### Option B — keep path `paper/human_eval`

If Pages serves the whole repo root, set the site base to that folder or move contents as in Option A. All asset paths are **relative** (`assets/...`), so either layout works as long as `index.html` and `assets/` stay together.

### After each response

Participants download JSON/CSV and send it to you. Aggregate with:

```bash
# example: put files in paper/results/responses/
# then summarize later into human_eval_summary.csv
```

## Flow

1. Consent  
2. Match-3 role context  
3. Early warm-up — 4 題（上架準則／小尺寸把握／自動通過風險／誰拍板）  
4. Task 1 — role @ ~70px (8 trials, Pack A/B = Fruit B1/B3)  
5. Task 2 — crate order (Pack A then B) + 「哪包更清楚」  
6. Task 3 — 動態 pairwise（Fruit B1/B2/B3；Pet/Ocean 若 `themes.json` 有 B1/B2 也會納入）  
7. Task 5 — multi-theme comparison（Fruit/Pet/Ocean B3）  
8. Agency briefing  
9. Task 4 — 6 Likert items + optional note  
10. Download results（schema `match3-human-eval-v2`）  

Blind mapping `pack_a_is` ∈ {B1, B3}（Task 1–2）與 Task 3 左右條件對應只寫在下載檔。

## Multi-theme generation

```bash
# B3 packs（問卷 Task 5）
PYTHONUNBUFFERED=1 python scripts/research_multi_theme.py --conditions B3 \
  --slugs pet,ocean 2>&1 | tee paper/results/multi_theme_run.log

# B1/B2 packs（問卷 Task 3 擴充）
PYTHONUNBUFFERED=1 python scripts/research_multi_theme.py --conditions B1,B2 \
  --slugs pet,ocean 2>&1 | tee paper/results/multi_theme_b12.log

# 只重匯出問卷素材
python scripts/research_multi_theme.py --skip-generate --export-survey --slugs pet,ocean
```

Steampunk 本 sprint 不做。