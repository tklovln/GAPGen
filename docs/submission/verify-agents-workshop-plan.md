# 投稿計畫 B：NeurIPS 2026 Workshop — Who Verifies the Agents?

**標的**：*Who Verifies the Agents? Toward Reliable Agent Development* · NeurIPS 2026 Workshop · Sydney · 2026/12/11 或 12
**現況基礎**：`art_pipeline/`（critic）+ `scripts/auto_eval.py` + `scripts/ai_auto_test.py` + `level_generator/validator.py` + `paper/results/`
**撰寫日**：2026-08-21

---

## 0. 時程與規則（AoE → 台北 = AoE 日期 +1 天 19:59）

| 項目 | AoE | 台北截止 |
|---|---|---|
| 投稿截止 | Aug 29 | **8/30 (日) 19:59** |
| 審查期 | 8/30 – 9/12 | — |
| 通知 | Sep 29 | — |
| Workshop | Dec 11 或 12 | Sydney（需現場報告 poster） |

- **頁數**：4–9 頁（不含 references / appendix），NeurIPS 2026 模板；demo paper ≤4 頁。
- **雙盲**、**非 archival**（只上 OpenReview）。
- **Dual submission 明文歡迎**：*"We welcome work that is under review or has been recently published at other venues."*
  → **與 NeurIPS Creative AI 在審的稿件、以及 WACV 投稿都不衝突。這是三個標的中政策風險唯一為零的一投，應列為第一優先。**
- 投稿與審查走 OpenReview；作者可能被要求協助審稿。

---

## 1. 定位：GAPGen 的 novelty 在哪，以及怎麼改（2026-08-24 重寫）

### 1.1 先說結論：novelty 不是「我們串了一條 pipeline」

原本的四條件敘事（B0 naive → B1 ontology → B2 refs → B3 critic 全開）暗示的主張是「我們的完整系統最好」。
**這個主張在 3 seeds × 2 判官下不成立**（`paper/results/ablation_notes.md`「Dual-judge, 3-seed rerun」）：

- GPT-4o 排 B1 > B2 > B3 > B0，Gemini 排 B3 > B1 > B2 > B0，判官間 Kendall τ = **0.333**
- 兩個判官都**不是**單調遞增
- B1/B2/B3 之間的差距（0.03–0.22）和 seed 標準差（0.06–0.14）同級

如果照原計畫寫「full system 最好」，這是審稿人一問就倒的宣稱。

### 1.2 活下來的宣稱：ontology 接地的效果**集中在玩法定義的類別**上

跨 **4 主題 × 2 判官**，每格**獨立評分 3 次取平均**（`--scope full`，n=12/格）。
B0 vs B1 只差一個旗標（`pipeline.py:72-73` 的 `use_ontology`，由 `resolve_ablation` self-check 鎖住）。

**噪音已實測**：格內 3 次評分的 sd **≤0.096、平均 0.025**，比單次評分的 ±0.250 小一個數量級。
**重複評分才是正解，加資產數不是**（research packs 只有 12 張 sprite，`--scope full` 把 n 從 8 提到 12，不是 63——我先前說「壓到 1/3」是錯的）。

| 主題 | 判官 | B0 (mean±sd) | B1 (mean±sd) | Δ | Δ > 2·SE |
|---|---|---|---|---|---|
| fruit | GPT-4o | 0.500 ± 0.000 | 1.000 ± 0.000 | +0.500 | yes |
| fruit | Gemini | 0.417 ± 0.000 | 0.917 ± 0.000 | +0.500 | yes |
| pet | GPT-4o | 0.167 ± 0.084 | 0.667 ± 0.000 | +0.500 | yes |
| pet | Gemini | 0.195 ± 0.048 | 0.583 ± 0.000 | +0.388 | yes |
| ocean | GPT-4o | 0.833 ± 0.000 | 0.917 ± 0.000 | +0.084 | yes |
| ocean | Gemini | 0.556 ± 0.096 | 0.917 ± 0.000 | +0.361 | yes |
| steampunk | GPT-4o | 0.583 ± 0.000 | 0.583 ± 0.000 | **+0.000** | **no** |
| steampunk | Gemini | 0.417 ± 0.084 | 0.722 ± 0.096 | +0.306 | yes |

**第二次撤回：「8/8 全為正」是錯的。** steampunk/GPT-4o **恰好為零**，而且不是噪音——
兩條件 sd 皆為 0.000，三次 pass 中 B0 與 B1 錯的是**完全相同的 5 個 element**（Blu/Grn/Pur/Red/Yel），
兩批圖的 SHA-256 不同（確實是不同圖）。更正計數：**7/8 格 Δ > 2·SE，1 格恰為零，0 格為負。**

### 那個零效果格反而揭露了機制

把 Δ 按 ontology 類別拆開，共 24 個（主題 × 判官 × 類別）格：

| 類別 | mean Δ | min | max |
|---|---|---|---|
| obstacle | **+0.417** | +0.000 | **+1.000** |
| powerup | **+0.403** | +0.000 | +0.667 |
| element | +0.217 | +0.000 | +0.467 |

**24/24 格 Δ ≥ 0，零個為負。** 8 個零效果格中 **7 個是天花板**（B0 已達 1.000，無空間可升），
只有 1 個是真零。

主打數字：**fruit 的 obstacle 在兩個判官下都是 0.00 → 1.00**。
沒有 ontology 時**每一個**受損階段的箱子都被誤判；有了之後**每一個**都正確。

**這就是機制，而且正好對應 ontology 編碼的東西。** `asset_roles.json` 寫的是玩法角色與階段進程
（哪個箱子是 4 階段中的第 1 階、哪張圖是橫向消除道具）。所以它對 obstacle（+0.417）
與 powerup（+0.403）幫助最大——**這兩類的身份是「玩法功能」，而外觀本身無法決定它**。
element（單純的配色寶石）獲益最小（+0.217）：它的身份就是顏色，生成器不需要被告知規則就能做對。
**效果最大之處，正是玩法語意無法從像素推得之處**——這就是本文的論點，現在是量測出來的而非宣稱的。

### 因此可寫進論文的四句話

1. **ontology 接地從不造成傷害、通常有幫助：24/24 類別格 Δ ≥ 0，零負值**
2. **增益集中在玩法定義的類別**（obstacle +0.417、powerup +0.403），**在外觀定義的類別最弱**（element +0.217）
3. **必要但不充分**：steampunk/GPT-4o 的 B1 = 0.583，5 個 element 全數認不出——單一主題就能完全打敗它
4. 噪音已刻畫（格內 sd ≤0.096），所以**單格 Δ 現在可報**，這是本檔案先前所有表格都做不到的

### 1.3 所以論文該怎麼改：三個具體修改

**修改 1：主張從「系統贏」換成「一個機制解釋全部效果」。**
新的一句話：

> 生成式素材 pipeline 常疊加多個機制（視覺參考、critic 迴圈、後處理門檻）。
> 我們用引擎接地的評測拆開一個真實生產系統，發現**角色可讀性的效果幾乎全部來自單一機制：
> 把生成條件接到遊戲玩法角色的 ontology 上**，而且**效果集中在玩法語意無法從像素推得的類別**
> （obstacle +0.417、powerup +0.403，vs 純外觀的 element +0.217；24/24 類別格無一為負；
> fruit 的 obstacle 在兩判官下皆 0.00 → 1.00）。
> 疊加在其上的視覺參考與 critic 迴圈**沒有可跨判官複現的角色可讀性增益**。
> 過程中我們的評測推翻了自己六個結論，歸因於四類失效模式，每一類都留下可執行斷言。
> 這是一個關於「創意 agent 的哪些部件真的在做事」的可複現結論，
> 而它之所以可得，是因為我們同時建了能證偽自己的評測基礎設施。

這比「我們的系統最好」**更有 novelty**，因為它是一個負面結果 + 正面機制的組合，
而且需要真的做出接地評測才能發現。單純比較 pipeline 的論文得不到這個結論。

**修改 2：把 refs / critic 的價值改成它們真正可量測的東西，不要掛在 role accuracy 上。**
`report.json` 已經顯示 critic 改變的是**摩擦**（needs_review 0.11 ± 0.10、mean_iters 1.95 ± 0.34），
不是外觀（B2 ≈ B3 pairwise 0.50 平手）。誠實寫法：ontology 負責可讀性，critic 負責攔查與審查負載，
兩者是不同的驗證層，不要互相冒領功勞。這一節反而變成本文對 agent 開發者最實用的建議。

**修改 3：把「評測自己會證偽自己」升格成貢獻，而不是限制。**
今天的過程推翻了六個自己寫下的結論。誠實的計數是**六個被推翻的結論、但只有四個根因**
（#4/#5/#6 同屬「取樣不足產生假結構」，且被同一個介入修好）——論文必須用根因計數，
不能用結論計數浮報。

| # | 當時寫下的錯結論 | 根因 | 怎麼發現 | 防護 |
|---|---|---|---|---|
| 1 | 人類美術 cohesion 最低 → 指標方向反了 | **基準資料被污染**：`apply.py` 把 AI pack 覆蓋進 `resources/sprites` | **由合作者口頭指出**，非自動檢查 | ✅ 可執行（`auto_eval.py:571,581`） |
| 2 | 所有 pack 在盤面上都完全可讀（0.97–1.00，16px 不掉） | **標籤空間退化**：候選集只取該關 tile，官方關卡中位數 k=3 | 察覺全面飽和 | ✅ 可執行（`board_parse_eval.py:339,340`） |
| 3 | Gemini 認為 cat 優於 fruit | **棄答與答錯混算**：`missing` 被計為錯誤，遵循度問題偽裝成品質問題 | 追查 `obstacle->?` 來源 | ✅ 可執行（`board_parse_eval.py:311-313`） |
| 4 | 有答案卷的任務上判官會收斂（3 pack 一致） | **取樣不足**：3 項排名巧合機率 1/6 | 擴到 5 pack → τ=0.20 | ✅ 可執行（`verify_claims.py` R2） |
| 5 | ontology 把可讀性從樂透變成穩定性質 | **取樣不足**：6 格 + 單次評分 | 補 steampunk → B1=0.500 | ✅ 可執行（`verify_claims.py` R3） |
| 6 | 8/8 格全為正 | **取樣不足**：單次評分，判官噪音 ±0.250 | 每格 3 次 → 真零效果格現形 | ✅ 可執行（`verify_claims.py` R1） |

**四個根因**：(a) 基準資料被污染、(b) 標籤空間退化、(c) 棄答與答錯混算、
(d) 取樣不足產生假結構。

**#4/#5/#6 的防護已補上**（原本只有散文註記，違反本文自己的原則 3）。
`scripts/verify_claims.py` 從落盤 JSON 重算頭條數字，並強制三條取樣規則：

| 規則 | 內容 | 對應撤回 |
|---|---|---|
| R1 | 單格 Δ 需 ≥3 次獨立評分 | #6「8/8 全為正」 |
| R2 | 排名相關係數需 ≥5 個項目 | #4「判官會收斂」 |
| R3 | Δ 須超過**實測**噪音 2·SE，而非假設的底線 | #5「ontology 壓低變異」 |

它同時把撤回本身變成測試：**斷言恰好有 1 個真零效果格**，
所以沒人能悄悄把「8/8 全為正」改回去而不被發現。
已驗證會失敗：抽掉一個 pass 後 `CLAIM CHECK FAILED: openai: only 2 passes on disk`。

```bash
python scripts/verify_claims.py --md    # 重算 + 檢查 + 印出可貼進論文的表
```

**一個必須誠實寫出的自我批評**（否則審稿人自己會發現）：
**#1 是由人指出的，不是自動檢查抓到的。** 不可寫成「我們的檢查全部自動抓到」。
可寫的是：一旦被指出，我們就把它變成一個會失敗的斷言，使它不能再犯。

**這是 workshop 主題（Who Verifies the Agents?）的正中央**：我們不只驗證 agent，
還驗證自己的驗證器，並展示四類具體失效模式與其防護，別人可直接照抄這些斷言。

### 1.4 對三個 pillar 的對齊（投稿時逐項寫進 intro）

| Pillar | 我們的對應 |
|---|---|
| 1. 驗證的安全與穩健（reward hacking、判官紅隊） | 通過率作為 reward 會被弱 gate 直接刷滿（B0–B2 pass ≈ 1.0）；critic 紅隊實驗（E3）量測判官的敏感度 / 特異度 |
| 2. 環境接地驗證與模擬器 | Match-3 引擎 + `ai_auto_test.py`（<100ms/場，50 場 <10 秒）當作 verifier；關卡生成 agent 的自報難度 vs 模擬器勝率（E2） |
| 3. 異質可驗證訊號 | 程式檢查 / 模擬器 rollout / VLM critic 四軸（style, cohesion, function, progression）/ DINOv2 / 人類最終決定權，如何組合與各自的失效面 |
| Cross-cutting | 「agent 驗證 agent」：critic agent 驗證 generator agent，並由第三方模型驗證 critic |

**標題（2026-08-25 定稿）**：
> **Grounding, Not Guardrails: What Actually Makes Generated Game Assets Legible**

未採用的候選與理由：*One Mechanism Does All the Work* —— element 仍有 +0.217，「全部」略微超賣；
*Who Verifies the Artist? Six Ways an Asset Benchmark Fooled Us* —— 把負面結果推太前，與「歸因結論 +
失效模式並重」的定調不符。

**姿態（已定）**：歸因結論與六個失效模式**並重**，不偏向任一側。

---

## 1.0 Abstract 草稿（2026-08-25，待逐句核對數字後定稿）

> Generative pipelines for game assets stack mechanisms — role prompting, visual references, critic
> loops, post-processing gates — and report end-to-end quality, so it is unknown which mechanism does
> the work. We study this in a shipping Match-3 asset agent whose ground truth is executable: the game
> engine's own tile registry defines each asset's gameplay category and damage-stage hit points, and we
> verify our 63-asset role ontology against it (41 checkable assets, zero category and zero stage-HP
> mismatches).
>
> Ablating the pipeline one flag at a time and scoring with two independently validated VLM judges,
> three repeated passes per cell, we find the effect is **not** distributed across mechanisms.
> Grounding generation in the gameplay-role ontology never hurts and usually helps (Δ ≥ 0 in 24 of 24
> theme × judge × category cells, zero negative), and the gain concentrates precisely where gameplay
> semantics cannot be inferred from pixels: obstacles +0.417 and power-ups +0.403 versus +0.217 for
> plain match elements, with damage-stage obstacles going from 0.00 to 1.00 under both judges
> independently. The two mechanisms layered on top — dual visual references and a VLM critic loop —
> show **no role-legibility gain that survives a judge swap** (Kendall τ = 0.333 between judges over
> four conditions, neither judge monotone); the critic changes review *friction* (needs-review
> 0.11 ± 0.10, iterations 1.95 ± 0.34), not legibility.
>
> Getting here required repairing our own benchmark. Four distinct failure modes produced six
> conclusions we had to retract: a contaminated baseline (a build step had overwritten the human
> reference art), a degenerate label space (restricting candidates to a level's own tiles silently
> saturates every score), conflating abstention with error (a judge's refusals scored as wrong
> answers, reversing a pack ranking), and under-sampling that manufactures structure (single-pass
> scoring hides a true-zero cell behind ±0.250 of judge noise; three packs agree by chance).
> Ranking asset packs is not judge-stable (τ = 0.20 across five packs), and pixel template matching
> and VLM parsing rank the same packs oppositely. We report each failure mode with the runnable
> assertion that now guards it, and identify judge **abstention rate** (0–38.9% across packs) as the
> one signal with an unambiguous direction. Ontology grounding is necessary but not sufficient: one
> theme defeats it entirely.

**三條貢獻（依強度排序，寫進 intro 的 bullet）**：

- **C1 可執行的接地評測**：引擎 tile registry 即答案卷（46 engine tiles / 63 ontology assets /
  41 可核對重疊，類別與階段 HP 皆零不符，`--verify-gt`）。標籤權威來自出貨程式碼而非作者意見。
- **C2 歸因結論**：效果集中在 ontology 這一個機制，且集中在玩法定義的類別（24/24 Δ ≥ 0；
  obstacle +0.417 / powerup +0.403 vs element +0.217）。同時是負面結果：refs 與 critic
  無可跨判官複現的可讀性增益。
- **C3 四類評測失效模式 + 可執行防護斷言**：基準污染、標籤空間退化、棄答與答錯混算、
  取樣不足產生假結構。共推翻了我們自己六個結論，每一類都附一個會失敗的斷言，可被其他團隊直接照抄。
  **誠實揭露**：其中一類是由人指出而非自動抓到的，我們寫明這一點。

**三個貫穿全篇的評測原則（論文要推銷的方法論）**：
1. 兩個判官同時同意才算結果，且判官須先通過五檢效度電池
2. 單次評分永不可信（判官重跑擺動達 ±0.250，會掩蓋真零效果格）
3. 每個指標留一個會失敗的可執行斷言

**必須明寫的缺口**（誠實是這篇的說服力來源，藏反而扣分）：無人類評測（8/25 決定不發問卷）、
Claude 第三判官缺席（帳戶餘額不足）、n=12/格、單一領域、board-parse 的 VLM 只跑 70px 無退化曲線。

---

## 2. 三個新實驗（全部便宜，皆可在 6 天內跑完）

### E1. 判官自評偏好 gap（Pillar 1）★必做，半天
同一批素材，用三種驗證器打分並比對排名：
- 同家族判官（Gemini critic，即 generator 家族）→ 已有資料，`scripts/critic_backfill.py` / `paper/results/critic_backfill.json`
- 跨家族判官（GPT-4o）→ `python scripts/auto_eval.py --judge openai`（已跑過 fruit）
- 無模型判斷的客觀訊號（DINOv2 cohesion）→ `--tasks cohesion`

**產出**：每個條件的三方分數表 + 排名相關係數（Spearman）+ **self-preference gap**（同家族判官給自家 generator 的分數減去跨家族判官）。
現有資料已經看得到端倪：Gemini critic 給 B3 的 cohesion 9.04/10，但 DINOv2 只有 0.605 overall（crate 0.812）→ **判官分數的絕對值不可信，只有相對排序可用**，這本身就是一個 workshop 級的觀察。

### E2. 環境接地驗證：agent 自報 vs 模擬器真值（Pillar 2）★必做，1 天
關卡生成 agent 已有完整的驗證迴路（`docs/validation_and_regen.md`）：validator error → 塞回 prompt → 最多重生 2 次。
要補的量化：
1. **Validator 錯誤分類學 + 收斂率**：跑 N=50 次生成，統計 (a) JSON 解析失敗率、(b) 各類 error 出現頻率、(c) 一次 / 二次重生後的通過率。→ 「便宜的確定性 verifier 能救回多少比例的 agent 失誤」。
2. **自報難度 vs 模擬器勝率**：讓 agent 在生成時輸出它認為的難度（easy / medium / hard），再用 `python scripts/ai_auto_test.py LEVEL --runs 50` 得到真實勝率，畫散佈圖 + 相關係數。
   → 預期結論：**agent 的自我評估與環境接地真值幾乎不相關**，而模擬器只花 <10 秒就給出真值。這是整篇最漂亮的圖，也最貼 workshop 主題。
3. 對比軸：validator（語法層）抓不到「可玩性」，模擬器（語意層）才抓得到——異質訊號互補的直接證據。

```bash
python scripts/ai_auto_test.py levels/level_01.json --runs 50
python scripts/ai_auto_test.py --batch godot_demo/levels --runs 10 \
  --out ai_test_reports/batch_20.json
```

### E3. Critic 紅隊 / 敏感度測試（Pillar 1）★建議做，1 天
對已通過的素材做**受控擾動**，看 critic 抓不抓得到：

| 擾動 | 應該被哪個軸抓到 | 實作 |
|---|---|---|
| 色相位移 / 飽和度拉高 | style | PIL，一行 |
| 貼上眼睛五官（違反 no-face 硬規則） | 硬規則 | PIL 貼圖 |
| 交換 Crt3 / Crt2 順序 | progression | 檔名交換 |
| 用另一主題的 sprite 替換一格 | cohesion | 跨 run 取檔 |
| 水平 power-up 旋轉 90° | function | 一行 rotate |
| **無擾動對照組** | 不該被抓 | 原圖 |

**產出**：每軸的 detection rate（敏感度）+ 對照組的誤報率（特異度）。這把「critic 有沒有在做事」從敘事變成數字，也直接回答 workshop 關心的「verifier 自己可不可靠」。
成本極低（純本地圖像操作 + 一輪 critic 呼叫），且**不需要重新生圖**。

### E4（選配）驗證成本 / 效益前緣
把三種 verifier 的單位成本（程式檢查 ~0 秒、模擬器 50 場 <10 秒、VLM critic 一次 API）對上它們各自攔下的缺陷比例，畫成一張 cost–coverage 圖。訊息：**先跑最便宜的 verifier，VLM 只用在便宜訊號攔不到的地方**——這是可以被別的 agent 團隊直接照用的結論。

---

## 3. 8 頁結構（2026-08-24 依新主張重排）

| 頁 | 內容 | 資料現況 |
|---|---|---|
| 1 | Abstract + Intro：疊加機制的 pipeline 無法歸因；創意任務缺 ground truth；本文用引擎接地的評測拆開一個真實生產 agent | — |
| 0.5 | 場景與系統：Match-3 素材 agent，B0–B3 四條件是乾淨的單變數階梯（`pipeline.py:72-75`） | ✅ |
| 1 | 評測基礎設施：ontology（41 assets，`--verify-gt` 對 `tile_defs.py` 零不符）+ 引擎關卡當答案 + 判官效度五檢 | ✅ 已跑 |
| **2** | **Result 1（主結果）：ontology 接地的效果集中在玩法定義類別** — 24/24 類別格 Δ ≥ 0 零負值；obstacle +0.417 / powerup +0.403 vs element +0.217；fruit obstacle 兩判官皆 0.00→1.00；格內 sd ≤0.096；ontology 必要但不充分（steampunk/GPT-4o Δ=0） | ✅ 已跑 |
| **1.5** | **Result 2（負面結果）：refs/critic 的角色可讀性增益不可跨判官複現** — τ=0.333，兩判官皆非單調，gap 與 seed sd 同級；critic 改變的是摩擦（needs_review 0.11±0.10、iters 1.95±0.34） | ✅ 已跑 |
| 1.5 | **Result 3：評測自己會騙人** — 六個失效模式與其防護斷言（§1.3 修改 3 的表）；board-parse 上兩判官 τ=0.20、棄答率 0–38.9% 才是唯一行為正常的訊號 | ✅ 已跑 |
| 0.5 | 討論：對 agent 開發者的建議（先接地再加護欄、輪替判官家族、把棄答率當一級指標、單次評分永不可信、每個指標留一個會失敗的斷言） | — |
| 0.5 | 限制 + ethics：單一領域、**n=12/格**、無人類評測、Claude 第三判官因帳戶餘額缺席 | — |

**與 WACV / Creative AI 稿的差異**：那兩篇主體是「怎麼生成」；這篇主體是「哪個部件真的在做事，以及評測本身如何騙過我們」。共用素材（消融 runs、系統圖），但主張與結論相反方向。

---

## 4. 逐日排程（2026-08-24 更新：主結果已到手，剩 6 天）

**現況：Result 1、2、3 的數據全部已跑完並落盤。剩下的是寫，不是跑。**

| 日期 | 工作 | 狀態 |
|---|---|---|
| ~~8/22–8/23~~ | ontology 效度驗證、判官五檢、board-parse | ✅ 完成 |
| **8/24 (一)** | B0 × pet/ocean 生成 + 跨主題跨判官 role 評測 | ✅ 完成 |
| **8/25 (二)** | B0/B1 × steampunk 補齊；**每格 3 次獨立評分 × 2 判官（6 passes）** → 噪音降至 sd ≤0.096，主結果變成 **24/24 類別格 Δ ≥ 0**，並發現效果集中在玩法定義類別 | ✅ 完成 |
| 8/26 (三) | 下載 NeurIPS 2026 模板、開 `paper/workshop/`、寫 Intro + 系統 + 評測基礎設施 + Result 1（主圖：按類別分組的 Δ forest plot，含實測 sd 誤差棒） | |
| 8/27 (四) | 寫 Result 2（τ=0.333 表 + 摩擦指標）、Result 3（六個失效模式表） | |
| 8/28 (五) | 討論 / 限制 / ethics、參考文獻、壓到 8 頁 | |
| 8/29 (六) | 匿名化檢查、內部審一輪；**選配**：Claude 儲值後補第三判官（有則加強，無則寫進限制） | |
| **8/30 (日) 19:59 前** | OpenReview 上傳 | |

**資料狀態：Result 1/2/3 全部跑完並落盤，噪音已刻畫。剩下六天純寫作。**

**選配（有時間才做，非必要）**：
- board-parse 的 cell size 掃描用 VLM 跑（70/48/32）得到退化曲線
- Claude 第三判官（需儲值）
- ~~加 n 到 63~~ 不可行：research packs 只有 12 張 sprite，`--scope full` 上限就是 n=12

**退路**：若 8/28 進度落後，改投 **≤4 頁 demo paper**，只保留 Result 1 主結果 + 四個防護斷言表。
主結果單獨就足以成篇，且已完全跑完。

---

## 5. 預期審稿問題

| 問題 | 準備 |
|---|---|
| **只有 ontology 有效，那你們的系統其他部分不就沒用？** | 這正是論文的貢獻：我們**證明了**refs/critic 對角色可讀性沒有可複現增益，並指出它們真正的作用（摩擦 / 審查負載）。誠實歸因比虛報全系統勝利更有價值，也給後續研究省下重複疊機制的成本 |
| **8 格中有 1 格效果恰為零，這不是反證嗎？** | 反而是最有價值的一格。它是**真零**（sd=0.000，三次 pass 錯的是完全相同 5 個 element），而拆到類別層級後 **24/24 格 Δ ≥ 0、零負值**，8 個零效果格中 7 個是 B0 已達天花板。零效果只出現在「ontology 本來就不該幫」（element = 純外觀）或「已無空間可升」之處——這正是機制的正面證據 |
| **n 仍然小（12 assets/格）** | 誠實回報，但**噪音已實測而非假設**：格內 3 次評分 sd ≤0.096、平均 0.025，7/8 格 Δ > 2·SE。我們用重複評分而非放大 n 來壓噪音，並明文寫出單次評分不可信 |
| **ontology 有效，那 steampunk 還是有 5 個 element 認不出來？** | 正是我們的宣稱：ontology **必要但不充分**。不誇大成「解決了可讀性」，而是「它是唯一有可複現效果的機制，且單一主題就能完全打敗它」——這給後續研究一個明確的未解問題 |
| 判官可信嗎？ | 不預設可信。兩判官都通過五檢效度電池（協定遵循、重測、標籤置換、盲測對照、勝過常數多數猜測）；且主結果**要求兩個判官同時同意**才報 |
| 為什麼 B0 vs B1 是乾淨對照？ | `pipeline.py:72-73` 兩條件只差 `use_ontology`，其餘旗標（refs、critic、max_iters）完全相同，由 `resolve_ablation` 的 self-check 斷言鎖住 |
| 這只是一個 domain 的案例研究，可推廣嗎？ | 主張是可移植的**方法論**（先接地再加護欄、輪替判官家族、棄答率當一級指標、每指標留一個會失敗的斷言）；Match-3 只是同時具備創意產出與可執行 ground truth 的稀有測床 |
| 人類基準？ | 缺席，寫進限制。問卷已就緒（`paper/results/human_eval_protocol.md`）但本次不發（2026-08-24 決定） |
| 第三判官？ | Claude 已接線並通過實作驗證，但帳戶餘額不足而判定 NOT USABLE（`judge_validation_claude.json`）。誠實寫進限制——這本身也展示了效度電池會抓到基礎設施故障 |

---

## 6. 兩份投稿的關係（重要）

```
NeurIPS Creative AI（已投，9/18 通知）  ──  生成系統 GAPGen
        │
        ├─ WACV 2027 Round 2（8/29 台北）  ──  評測套件 + benchmark（有 dual submission 風險，見計畫 A 第 1 節）
        │
        └─ Verify Agents Workshop（8/30 台北）── 驗證方法論（零政策風險，優先做）
```

**若時間只夠一個：做這一份（計畫 B）。** 明文允許 dual submission、非 archival、4 頁 demo 也可，且新實驗 E1–E3 全部不需要重新生圖。
