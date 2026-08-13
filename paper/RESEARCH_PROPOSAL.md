# Research Proposal: Gameplay-Grounded Creative Agency in Structured Game Art Generation

**Target venue:** NeurIPS 2026 Creative AI Track (Theme: *Agency*)  
**Format:** Research paper, 2–6 pages (excl. references), non-archival, single-blind  
**Working title (EN):** *Who Decides What Looks Playable? Negotiating Creative Agency in Gameplay-Grounded Asset Pack Generation*  
**中文工作標題：** 誰決定「可玩」的長相？遊戲功能約束下的美術包生成與創意代理權協商  
**Codebase anchor:** `art_pipeline/` + AI Art Lab (`pages/6_AI_Art_Lab.py`)  
**Locked scope:** `SCOPE.md` · **Agent queue:** `AGENT_TODO.md`  
**Last updated:** 2026-07-22 evening（決策鎖定 + Fruit/Pet/Ocean B1–B3 證據包就緒；human n 待收）

---

## 1. Executive summary

我們已有一套可運行的 **structured game art generation pipeline**：從主題／風格規劃、family anchor、stage 鏈式參考、到 programmatic postprocess + VLM critic 迭代、再套用進可玩 Godot 盤面。這不只是「好看圖生成」，而是 **gameplay-grounded creative system**——生成物必須在約 70px 格子上可辨識、保留角色功能（match / clear row / obstacle stage…）、且整包風格一致。

NeurIPS 2026 Creative AI 的年度主題是 **Agency**：創意代理權如何在人、模型、工具、平台之間被主張、委派、共享或削弱。我們的系統恰好是一個可量測的實驗場：planner / critic / postprocess 自動化了大量「品味與品質門檻」，人類則透過 staging、`needs_review`、apply／restore、以及「在真實盤面驗收」保留最終代理權。

**核心主張：**  
現有 Creative AI / T2I / ImageSet 研究大多優化美學、身份一致性或敘事連貫；**缺乏**「以遊戲功能本體（role ontology）為約束、以可玩引擎為驗收」的生成與評估框架。我們提出以 Match-3 asset pack 為典範任務，形式化 **Gameplay-Grounded Creative Agency (GGCA)**，並用現有 pipeline 作為可複製的系統實作與實證載體。

> ⚠️ **時程現實：** Creative AI Track 截稿為 **2026-08-03 AoE**（距本文件撰寫日約兩週）。本年投稿應走 **短篇 system + agency 論述 + 小規模 user study / ablation**；完整 benchmark 與大型用戶研究應規劃為後續 archival 延伸（見 `RESEARCH_PLAN.md`）。

---



## 2. Venue fit — NeurIPS 2026 Creative AI Track


| 項目           | 要求                                                                  | 我們的對應                                                |
| ------------ | ------------------------------------------------------------------- | ---------------------------------------------------- |
| Theme        | Agency（研究論文不強制鎖死主題，但鼓勵連結）                                           | 代理權在 planner / critic / human / engine 間的分配與摩擦       |
| Length       | 2–6 pages（不含 references）                                            | 目標 4–5 頁：問題→系統→實驗→agency 討論                          |
| Archival     | **Non-archival**（OpenReview 可查，不進主會 proceedings）                    | 適合先發表系統與概念；後續可投 CHI / SIGGRAPH / ICCC / main NeurIPS |
| Review       | Single-blind（作者名可見）                                                 | 可附系統 demo 連結／影片                                      |
| Presentation | 現場 poster（Sydney）                                                   | 準備 Art Lab live demo + 3 分鐘 video                    |
| Dates        | Portal 6/30 · Deadline **8/3** · Decision 9/18 · Camera-ready 10/23 | 見 plan 衝刺表                                           |


**主題提問（直接對齊 CFP）：**

1. AI 如何改變創意代理權的起點與終點？（planner 展開主題 vs 美術定稿）
2. 當品質門檻被 critic 自動化，誰仍對「可玩／可出貨」負責？
3. 系統是在 **enable** 創意，還是在 **steer** 品味？（rubric 硬規則：no face / fill frame / progression）
4. 摩擦、拒絕、重試、`needs_review` 如何保存人類意圖？（對比一鍵全自動）
5. 當系統可模擬美學偏好，藝術家如何在引擎內主張判斷？（in-game preview 作為 taste 的最終場域）

---



## 3. Existing system — research substrate（我們已有什麼）



### 3.1 Pipeline 架構（已實作）

```
User intent (style / theme / assets)
        │
        ▼
┌─────────────────── Planning layer ───────────────────┐
│ style_planner     → 鎖定畫風規格                         │
│ theme_planner     → 主題 → per-asset 物件指派             │
│ family_style_planner → per-family 材質／裝飾語言（可開關） │
│ stage_planner     → multi-stage 損耗／演進視覺規格          │
└───────────────────┬──────────────────────────────────┘
                    ▼
┌─────────────────── Generation layer ─────────────────┐
│ restyle | theme-swap                                   │
│ refs: original / reference-run / family anchor / prev stage │
│ Gemini image model + structured prompts + hard rules     │
└───────────────────┬──────────────────────────────────┘
                    ▼
┌─────────────────── Verification loop ────────────────┐
│ postprocess (chromakey cutout, coverage, …)            │
│ VLM critic (style / function / cohesion / progression / │
│            reasonableness / cutout / background …)     │
│ retry with critique ≤ N；否則 best-effort + needs_review │
└───────────────────┬──────────────────────────────────┘
                    ▼
        staging: generated_art/<run>/
                    ▼
        human gate → apply → Godot / Streamlit playable preview
```



### 3.2 研究相關的設計選擇（不是工程細節，是 scientific claims 的素材）


| 機制                      | 模組                                   | 研究意涵                                       |
| ----------------------- | ------------------------------------ | ------------------------------------------ |
| Role ontology           | `asset_roles.json`                   | *視覺生成以 **gameplay role** 為一等公民，非純 caption* |
| *Restyle vs theme-swap* | `pipeline.py` */* `roles.py`         | *兩種創意代理模式：保形換皮 vs 功能保留下的物件再發明*             |
| *Family anchor chain*   | `visual_guidance.py`                 | *Intra-family cohesion 的結構化參考協議*           |
| *Stage dual-ref*        | `stage_planner.py`                   | *Style lock + progression lock —— 狀態序列一致性* |
| *Hybrid critic*         | `postprocess.py` *+* `gemini_api.py` | *客觀可測約束 + 主觀／語意約束的分工*                      |
| *Engine-in-the-loop*    | `apply.py` *+ Art Lab*               | 創意驗收場域從「圖好看」移到「盤面可玩」                       |
| Staging / restore       | apply + backup                       | 人類保留覆寫代理權；系統不直接擁有 production truth         |




### 3.3 與「一般 T2I demo」的差異（定位用）

我們不是單一 prompt → 單張圖。我們生成的是 **structured asset pack**：多 family、多 stage、功能可讀、透明切邊、可進引擎。這對齊產業 workflow，卻幾乎沒有對應的學術任務定義。

---



## 4. Related work map & academic gaps



### 4.1 Related work（精選）


| 方向                                  | 代表工作                                                       | 覆蓋                   | 未覆蓋（相對我們）                                        |
| ----------------------------------- | ---------------------------------------------------------- | -------------------- | ------------------------------------------------ |
| Consistent multi-image / ImageSet   | T2IS / AutoT2IS (Jia et al., 2025); ConsiStory; ConsiStyle | 身份／風格／邏輯一致性          | 無 gameplay role、無引擎驗收、無 stage depletion          |
| Sprite / character animation sheets | Sprite Sheet Diffusion (2024)                              | 角色動作幀一致性             | 非道具／障礙物 pack；非 match-3 可讀性                       |
| Multi-agent creative refinement     | CREA (NeurIPS 2025); Planner–Actor–Critic 3D modeling      | Director + Critic 迭代 | 少見 **production constraints**（cutout、70px、功能方向）  |
| Affordance / tile semantics         | GameTileNet; NarrativeScene                                | 語意–功能標註與檢索           | 多為 retrieval／PCG 排版，非端到端 restyle／theme-swap 生成閉環 |
| 3D asset + physics / structure      | PhysX-3D; ShapeCraft; Neural Assets                        | 幾何／物理／程序化結構          | 2D casual game production 路徑不同                   |
| Industry pipelines                  | restyle-sprites; Scenario; 各類 AIGC workflow 文              | 實務 restyle／QA        | 非 peer-reviewed 評估框架；agency 未理論化                 |




### 4.2 學術缺口（Gaps）— 我們可以佔的位置

**Gap A — Gameplay-grounded generation as a first-class task**  
文獻有「一致的一組圖」，少有「一組必須滿足玩法功能本體的 runtime sprites」。  
→ **機會：** 定義 *Gameplay-Grounded Asset Pack Generation (GGAPG)* 任務。

**Gap B — Functional readability at gameplay scale**  
美學分數／CLIP／DINO 一致性 ≠ 玩家能否在 70px 認出「橫向火箭」「損毀一級的箱子」。  
→ **機會：** 提出 *Gameplay Readability* 指標與人類評測協議（board-scale forced choice）。

**Gap C — Structured hierarchy beyond flat ImageSet**  
T2IS 的 identity/style/logic 仍偏扁平；我們有 **theme → family → stage → asset** 層級約束。  
→ **機會：** Hierarchical consistency protocol（anchor + progression chain）的消融與形式化。

**Gap D — Hybrid objective–subjective critics for production readiness**  
CREA 類系統優化「創意原則」；遊戲資產還需要 chromakey 完整性、填滿畫面、禁臉、低對比背景等 **可機器檢查** 的出貨條件。  
→ **機會：** 證明 hybrid critic 在通過率／重工人時／可玩性上的增益，並討論「規則是否偷走品味」。

**Gap E — Theme-swap as constrained creative remapping**  
在保留 color identity / directional affordance 下「換成新主題物件」是創意問題，不是 style transfer。  
→ **機會：** 研究約束下的創意多樣性（novelty vs playability Pareto）。

**Gap F — Agency redistribution in automated art pipelines（主題主線）**  
當 planner 指定物件、critic 決定 retry、引擎畫面成為最終審判，人類代理權被重配置。  
→ **機會：** Creative AI 最吃香的論述層——用可觀察行為（覆寫率、reject 原因、何時開 force）做實證。

**Gap G — Open evaluation artifact**  
缺公開的 match-3／casual puzzle **role-annotated** 美術包 benchmark 與 playable harness。  
→ **機會：** 釋出小型 *MatchArt-Bench*（即使本年只能先發 protocol + 私有結果）。

---



## 5. Research questions

**RQ1 (Task):** 如何形式化「遊戲功能約束下的美術包生成」，使其可評估、可比較、可消融？

**RQ2 (Method):** Hierarchical planning + dual reference（family anchor / prev stage）+ hybrid critic，相對 naive per-asset T2I，在一致性與可玩性上帶來多少增益？

**RQ3 (Creativity):** Theme-swap 在硬約束下，是否仍能產生可感知的創意多樣性？約束如何塑造（而非單純扼殺）創意？

**RQ4 (Agency):** 在帶引擎預覽的人機協作中，人類的代理權表現在哪些可觀察行為？自動化門檻提高時，代理權是被增強還是被預結構化？

**RQ5 (Evaluation):** VLM critic 分數與人類「盤面可玩判斷」的相關／偏誤為何？何處必須保留人類終審？

---



## 6. Proposed framework — GGCA / GGAPG



### 6.1 任務定義（建議投稿用語）

**Input**

- Style specification S（文字 ± 參考圖）  
- Theme concept T（可選；theme-swap 時必要）  
- Asset ontology \mathcal{O}：families, role classes, stage graphs, visual constraints  
- Target subset A \subseteq \mathcal{O}

**Output**

- Asset pack P = I_a_{a \in A}：engine-ready sprites（透明 PNG、尺寸規範）  
- Trace \tau：plans, prompts, critiques, scores, chosen iterations（可審計的創意過程）

**Success criteria（多層）**

1. **Pixel / production:** cutout, coverage, no illegal outline/face（客觀）
2. **Set consistency:** style, intra-family cohesion, stage progression（半客觀 + VLM）
3. **Gameplay readability:** role recognition at board scale（人類／專門評測）
4. **Creative intent:** theme/style alignment（人類）
5. **Agency integrity:** 人類可覆寫、可還原、可標記 needs_review（流程）



### 6.2 Agency model（對齊 CFP 的理論骨架）

建議在論文用一張簡單的 **agency allocation diagram**：


| Actor                | Asserts agency by…                                                    | Can diminish others by…                   |
| -------------------- | --------------------------------------------------------------------- | ----------------------------------------- |
| Human art director   | Choosing theme/style; force regen; apply/restore; final taste in-game | Overriding critic; freezing bad packs     |
| Theme/style planners | Naming objects & visual language                                      | Pre-structuring the creative search space |
| Image model          | Proposing visual forms                                                | Introducing anthropomorphism / drift      |
| Hybrid critic        | Enforcing rubrics; forcing retry                                      | Encoding taste as hard thresholds         |
| Game engine preview  | Making playability the court of appeal                                | Rejecting beautiful-but-unreadable art    |


**Claim for Creative AI：**  
有價值的創意系統不是最大化模型自主，而是 **explicitly design where agency is delegated and where friction preserves human intention**——我們的 staging + needs_review + in-game preview 是一種可操作的設計模式。

### 6.3 方法主張（可消融的組件）

1. **Ontology-conditioned prompting**（role briefs from `asset_roles.json`）
2. **Hierarchical planners**（theme / family / stage）
3. **Reference protocols**（restyle ref, family anchor, prev-stage）
4. **Hybrid verification loop**（programmatic + VLM multi-score）
5. **Engine-in-the-loop human gate**

---



## 7. Contribution plan（按投稿可交付性分層）



### Tier S — NeurIPS 2026 Creative AI（本年必達，短文）

1. **問題與框架：** GGAPG + GGCA（agency 論述綁 CFP）
2. **系統：** 描述現有 Match-3 Art Lab pipeline（可附 demo／影片）
3. **小規模實證：**
  - 消融 3–4 條件（見 plan）  
  - 6–12 人專家／玩家評測（board readability + preference）  
  - 代理權行為日誌分析（覆寫、retry、needs_review 頻率）
4. **討論：** 自動化品味門檻 vs 人類終審；friction as design



### Tier A — 後續 archival / 加長版（截稿後繼續）

1. **MatchArt-Bench** 公開子集 + 評測腳本
2. 更大 user study（美術／企劃／玩家分層）
3. Cross-model 比較（非單一 Gemini）
4. Critic calibration vs human labels（偏誤分析）
5. Theme-swap creativity metrics（diversity–playability frontier）



### Tier B — 探索性延伸（選做）

- 學習型 critic（用人類覆寫微調閾值／rubric）  
- 互動式 agency 控件（哪些規則可調、哪些硬鎖）  
- 從 match-3 泛化到 card / merge / idle icon packs

---



## 8. Evaluation design（精簡可執行版）



### 8.1 Automatic / semi-automatic


| Metric                        | How                                      | Notes                |
| ----------------------------- | ---------------------------------------- | -------------------- |
| Pass@N                        | critic + postprocess 通過率                 | 已有 report.json       |
| Iterations-to-pass            | 平均迭代                                     | 成本／摩擦代理指標            |
| Cohesion / progression scores | VLM rubric                               | 需報告與人類相關性            |
| Cutout integrity              | programmatic + checkerboard critic       | production readiness |
| Style drift (optional)        | embedding distance to style ref / anchor | 輔助                   |




### 8.2 Human evaluation（本年最小可行）

**Tasks**

1. **Role recognition @70px：** 給盤面截圖或格子縮圖，選 gameplay 功能（多選一）
2. **Stage ordering：** 打亂 stage，請受試者排序損耗程度
3. **Pack preference：** 成對比較（有／無 anchor；有／無 critic）
4. **Agency questionnaire：** 誰在做決定？感到被系統 steer 還是 enable？（Likert + 開放題）

**Participants（最低）：** 6–12（含 ≥2 有遊戲／美術背景）。  
**Stimuli（已鎖定／已生成）：** style=`3dCartoonSimple`；themes=**Fruit**（主消融）+ **Pet / Ocean**（延伸）；families=`elements + powerups + crate`（各 12 assets）。Steampunk 不做。  
**Instrument：** `paper/human_eval/`（暖身 + Task1–5 + agency Likert；schema v2）。

### 8.3 Ablations（建議最小集合）


| ID   | Condition                                          | Sprint status |
| ---- | -------------------------------------------------- | ------------- |
| B0   | Naive per-asset prompt（無 ontology / 無 critic loop） | optional / dry-run only |
| B1   | + role ontology prompts                            | ✅ Fruit + Pet + Ocean |
| B2   | + family anchor (+ stage chain if applicable)      | ✅ Fruit + Pet + Ocean |
| B3   | + hybrid critic loop（full system）                  | ✅ Fruit + Pet + Ocean |
| B3+H | Full + mandatory in-game human review before apply | questionnaire / process |


主文消融表以 **Fruit B1/B2/B3** 為主（`results/ablation_preliminary.csv`）；Pet/Ocean 見 `ablation_multi_theme.csv` + survey Task 3/5。

---



## 9. Risks & mitigations


| Risk             | Impact | Mitigation                                  |
| ---------------- | ------ | ------------------------------------------- |
| 截稿僅約兩週           | 無法做大實驗 | 鎖定 Tier S；用既有 runs 做 retrospective + 小評測    |
| 單一商業 VLM/生圖模型    | 可重複性質疑 | 誠實報告 API 設定；強調框架與協議可遷移；附 prompt／rubric      |
| Critic = 自己評自己   | 循環偏誤   | 人類評測為主結論；VLM 分數僅輔助；分開 image/critic model    |
| Non-archival 能見度 | 影響力有限  | 同步準備加長版／部落格／開源；明年投 archival                 |
| 創意主觀難評           | 審稿質疑   | 綁 agency + playability 雙主軸，不硬吹「更有創意」而無操作型定義 |
| IP / 資料集版權       | 釋出困難   | Bench 用自有／授權美術；生成結果授權條款預先釐清                 |


---



## 10. Ethics & responsibility（Creative AI 友善段落）

- 生成美術可能涉及風格模仿；論文需討論 **style appropriation** 與參考圖使用規範。  
- 自動化 critic 可能把某一美學（無臉、無描邊、填滿畫面）固化為「正確」，削弱多元美學代理權——這本身可作為批判性貢獻。  
- API 成本與環境成本：報告典型 run 的呼叫次數。  
- 人類仍對上架內容負責；系統設計上避免 silent overwrite production assets。

---



## 11. Recommended paper narrative（4–5 頁骨架）

1. **Intro (0.75p):** 遊戲美術包 ≠ 單圖生成；Agency 問題登場
2. **Related work (0.75p):** ImageSet / CREA / sprite sheets / affordance — 點出 Gap A–F
3. **Framework (1p):** GGAPG 任務 + agency allocation
4. **System (1p):** pipeline 圖 + ontology / hybrid critic / engine loop
5. **Study (1p):** ablations + small human eval + agency behavioral signals
6. **Discussion (0.5p):** enable vs steer；friction；limitations
7. **Refs**

**可選並行 Artwork track：** 3-min video 展示「同一玩法、多主題美術包」+ agency 介面；與論文互補（非必須）。

---



## 12. Why this is worth doing（對內決策用）

- **差別化強：** 真實可玩產品管線 + 學術缺口清晰。  
- **Agency 主題天然契合：** 不必硬拗。  
- **工程槓桿高：** 多數系統已存在；研究增量在評估、消融、論述與小規模用戶研究。  
- **路徑清晰：** 本年 Creative AI 短文 → 後續 Bench + archival。

**不建議本年硬衝的方向：** 從零訓擴散模型、大型公開數據標註、跨十種遊戲類型泛化——時間與 YAGNI 都不划算。

---



## 13. Immediate go / no-go checklist

- [x] 至少一位作者可 **現場參加 Sydney**（已確認）  
- [x] 鎖定投稿類型：**Paper**（Artwork 影片 optional）  
- [x] 選定刺激：Style=`3dCartoonSimple`；Theme=`Fruit`（主消融）+ `Pet/Ocean`（B1–B3 延伸／問卷）；Families=`elements+powerups+crate` → **`SCOPE.md`**  
- [x] 主 RQ：**RQ2 + RQ4**（RQ1 框架、RQ3 輕觸）  
- [x] Automatic ablation（Fruit 主表 + Pet/Ocean 延伸 CSV）寫進 notes / 可進論文  
- [x] Human-eval **instrument + stimuli**（`paper/human_eval/`，themes.json v2）  
- [ ] 能否在截稿前完成最小 human eval **收樣**？（protocol ✅；**待 Pages 部署 + n≥6**）  
- [ ] Demo 影片腳本（系統 + agency 論點）  
- [x] 若評測不完整：允許 **system + preliminary automatic ablation**（已寫進 `main.tex`；human 表 pending）

**執行清單：** `AGENT_TODO.md`（下一項 **T6 收樣／部署** 或 **T9/T10 polish**）  
**消融解讀：** `results/ablation_notes.md`

---



## References (seed bibliography)

1. NeurIPS 2026 Call for Creative AI — Theme: Agency. [https://neurips.cc/Conferences/2026/CallForCreativeAI](https://neurips.cc/Conferences/2026/CallForCreativeAI)
2. Jia et al. (2025). *Why Settle for One? Text-to-ImageSet Generation and Evaluation* (T2IS). arXiv:2506.23275.
3. CREA: Collaborative Multi-Agent Framework for Creative Image Editing/Generation. NeurIPS 2025.
4. Sprite Sheet Diffusion (2024). arXiv:2412.03685.
5. ConsiStyle (2025). Style diversity in training-free consistent T2I. arXiv:2505.20626.
6. GameTileNet / NarrativeScene — semantic–affordance game tiles (Chen et al.).
7. ShapeCraft; PhysX-3D; Neural Assets — adjacent asset-generation NeurIPS lines.
8. Internal: Match3_sim `art_pipeline/`, AI Art Lab progress docs.

---

*本文件為研究提案，不是相機就緒論文。執行細節與週計畫見* `RESEARCH_PLAN.md`*。*