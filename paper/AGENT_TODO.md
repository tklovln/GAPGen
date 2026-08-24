# Agent TODO — NeurIPS 2026 Creative AI Sprint

**目標：** 8/3 AoE 前提交 Creative AI paper（P1）  
**權威文件：** `SCOPE.md` · `RESEARCH_PROPOSAL.md` · `RESEARCH_PLAN.md` · `main.tex` · `results/ablation_notes.md`  
**截止：** 2026-08-03 AoE  
**Scope locked:** 2026-07-22 · **Last sync:** 2026-07-22 evening

---

## 已完成

- [x] Proposal / plan / SCOPE / 初稿骨架
- [x] H1–H4 決策鎖定
- [x] T1 SCOPE.md
- [x] T2 retrospective → `results/retrospective_summary.*`
- [x] T3 ablation flags（`--ablation B0–B3`）
- [x] T4 Fruit B1/B2/B3 → `ablation_preliminary.csv` + `ablation_notes.md`
- [x] T4b Pet/Ocean B1/B2/B3 → `ablation_multi_theme.csv`（Steampunk 不做）
- [x] T5 sprite grids（cat + Fruit B1/B2/B3）
- [x] T6 protocol + static survey + stimuli export（`human_eval/` v2）
- [x] T7 **部分**：`main.tex` 消融表、模型 ID、B1/B3 圖、Abstract/Intro 誠實解讀

---



## 人類決策（LOCKED）— 見 `SCOPE.md`

H1 P1 ✅ · H2 可去 Sydney（全名 T9）✅ · H3 Fruit + Pet/Ocean × 3dCartoonSimple / elements+powerups+crate ✅ · H4 RQ2+RQ4 ✅

---



## 進行中 / 下一項



### T6. Mini human eval ⬅️ **NEXT（需人類招募／部署）**

- [x] Protocol（`results/human_eval_protocol.md`）
- [x] Static survey（暖身 4 題 + Task1–5；繁中）
- [x] Stimuli：Fruit/Pet/Ocean × B1–B3 已進 `themes.json`
- [ ] Deploy Pages + 分享 URL
- [ ] n≥6 收集（下載 JSON/CSV 寄回）
- [ ] `results/human_eval_summary.csv`

- **Done when：** 有描述統計，或論文明確寫 pending + 只用設計層 agency 論點



### T7. 補 `main.tex`（剩餘）

- [x] Table `tab:ablation` + 解讀 + Fig grids（Fruit）
- [ ] 可選一句／appendix：Pet/Ocean automatic（見 `ablation_notes.md`）
- [ ] Human table 填數（等 T6）或交稿前維持 pending
- [ ] 可選：B0 真跑後補一列
- [ ] 刪已解決的 `\pending`



### T8. 圖進論文

- [x] Fig pipeline + Fig B1/B3 grids
- [ ] 可選 board screenshot（apply B3 後）
- [ ] 可選 cat／Pet 圖若版面允許



### T9. 文獻與作者

- [ ] 補齊 `refs.bib` 完整作者
- [ ] 人類填真實 `\author{}`
- [ ] checklist 若 track 需要則填



### T10. 寫作 polish

- [ ] 跟 `research-paper-writing/SKILL.md` 過一輪
- [ ] 交稿前刪 Draft Self-Review
- [ ] 確認正文 ≤6 頁（Creative AI）



### T11–T13

- [ ] Demo 影片（建議）
- [ ] `REPRO.md`
- [ ] 編譯 + OpenReview 提交

---



## 明確不要做

- ❌ 訓模型 / 重寫 pipeline  
- ❌ 把 B1 pass_rate>B3 寫成「B1 比較好」  
- ❌ 沒有 human data 就宣稱「更可玩」  
- ❌ 重問 H1–H4  
- ❌ 把 Steampunk 塞回問卷（已決定不做）

---



## Agent prompt（可複製）

```text
Read paper/SCOPE.md, paper/AGENT_TODO.md, paper/results/ablation_notes.md, paper/main.tex.
Next: T6 (Pages deploy + collect n≥6) and/or T9–T10 polish.
Do not invent human-eval numbers. Do not claim B1>B3 on pass rate.
Sync markdown (AGENT_TODO, SCOPE, RESEARCH_PLAN, RESEARCH_PROPOSAL) when finishing a task.
```

