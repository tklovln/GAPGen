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

### 1.2 活下來的宣稱：ontology 接地本身就是全部效果（方向極穩，量級不可解析）

跨 **4 主題 × 2 判官 = 8 格**，B0（無 ontology）vs B1（有 ontology，其餘完全相同——
`pipeline.py:72-73` 只差 `use_ontology`，由 `resolve_ablation` self-check 鎖住的乾淨單變數對照）：

| 主題 | 判官 | B0 | B1 | Δ |
|---|---|---|---|---|
| fruit (3 seeds) | GPT-4o | 0.375 | 0.786 | **+0.411** |
| fruit (3 seeds) | Gemini | 0.375 | 0.911 | **+0.536** |
| pet | GPT-4o | 0.250 | 0.750 | **+0.500** |
| pet | Gemini | 0.375 | 0.750 | **+0.375** |
| ocean | GPT-4o | 0.500 | 0.875 | **+0.375** |
| ocean | Gemini | 0.500 | 0.875 | **+0.375** |
| steampunk | GPT-4o | 0.250 | 0.500 | **+0.250** |
| steampunk | Gemini | 0.500 | 0.750 | **+0.250** |

**8/8 格全為正，Δ +0.250 ~ +0.536。**

**但必須同時報噪音底線。** 加入 steampunk 時重跑了 pet/ocean，等於同一批圖被同一判官打兩次分：
8 個數字有 3 個變動，最大變動 **0.250**（n=8，每個 asset 值 0.125，即 1–2 張圖翻面）。
**這個噪音和最小的 Δ 同級。** 所以證據力來自「8 格方向一致無例外」，
不是任何單一格的數值——任何單格數字都不可單獨採信。

**已撤回的宣稱（8/24 曾寫、8/25 被自己推翻）**：6 格版本中 B1 全部 ≥0.750，
我曾寫下「ontology 把可讀性從樂透變成穩定性質」。
**這是錯的**：steampunk/GPT-4o 的 B1 只有 0.500，而 B1 跨格的散布（0.500–0.911）
比 B0（0.250–0.500）**更寬**。那個變異宣稱是 6 格 + 單次評分的產物。

**因此可寫進論文的三句話**：
1. ontology 接地的**效果方向**在 4 主題 × 2 判官下無例外為正（8/8），Δ ≥ +0.250
2. **量級在此 n 下不可解析**，須與 ±0.250 的噪音底線一起報
3. ontology 是**必要但不充分**：最難的主題（steampunk）B1 仍有一半素材認不出來

### 1.3 所以論文該怎麼改：三個具體修改

**修改 1：主張從「系統贏」換成「一個機制解釋全部效果」。**
新的一句話：

> 生成式素材 pipeline 常疊加多個機制（視覺參考、critic 迴圈、後處理門檻）。
> 我們用引擎接地的評測拆開一個真實生產系統，發現**角色可讀性的效果幾乎全部來自單一機制：
> 把生成條件接到遊戲玩法角色的 ontology 上**（跨 4 主題 × 2 獨立判官，8/8 為正，Δ +0.25~+0.54），
> 而疊加在其上的視覺參考與 critic 迴圈**沒有可跨判官複現的角色可讀性增益**。
> 過程中我們的評測**五次騙過我們自己**，每次都被自己的檢查抓到並留下斷言。
> 這是一個關於「創意 agent 的哪些部件真的在做事」的可複現結論，
> 而它之所以可得，是因為我們同時建了能證偽自己的評測基礎設施。

這比「我們的系統最好」**更有 novelty**，因為它是一個負面結果 + 正面機制的組合，
而且需要真的做出接地評測才能發現。單純比較 pipeline 的論文得不到這個結論。

**修改 2：把 refs / critic 的價值改成它們真正可量測的東西，不要掛在 role accuracy 上。**
`report.json` 已經顯示 critic 改變的是**摩擦**（needs_review 0.11 ± 0.10、mean_iters 1.95 ± 0.34），
不是外觀（B2 ≈ B3 pairwise 0.50 平手）。誠實寫法：ontology 負責可讀性，critic 負責攔查與審查負載，
兩者是不同的驗證層，不要互相冒領功勞。這一節反而變成本文對 agent 開發者最實用的建議。

**修改 3：把「我們的指標會證偽自己」升格成貢獻，而不是限制。**
今天一天推翻了三個自己的結論（cohesion 方向、原型偏誤、判官收斂），
每一次都是被自己的檢查抓到的，並且都留下了 `--self-check` 斷言：

| 陷阱 | 症狀 | 已寫成斷言 |
|---|---|---|
| 量到被覆蓋的 AI run 當人類基準 | 人類 cohesion 最低 | `auto_eval.py` self_check 阻止把 `resources/sprites` 當人類美術 |
| 候選集退化（每關只有 1–3 種 tile） | board-parse 全部 0.97–1.00 | `board_parse_eval.py` 斷言 per-level median k ≤ 3 < global k |
| 棄答被算成答錯 | Gemini 排名反轉 | 斷言 `abstain_rate` 與 `accuracy_on_answered` 分離 |
| 3 個 pack 的排名一致 | 誤判為「判官會收斂」 | notes 明載 τ 需 ≥5 項才可報 |
| **單格 n=8，判官重跑擺動 0.250** | **誤判為「ontology 壓低變異」** | **notes 明載單格不可採信，須跨格一致** |

**這是 workshop 主題（Who Verifies the Agents?）的正中央**：我們不只驗證 agent，
還驗證自己的驗證器，並且展示了四個具體的評測失效模式與其防護。
別人可以直接照抄這四個斷言。

### 1.4 對三個 pillar 的對齊（投稿時逐項寫進 intro）

| Pillar | 我們的對應 |
|---|---|
| 1. 驗證的安全與穩健（reward hacking、判官紅隊） | 通過率作為 reward 會被弱 gate 直接刷滿（B0–B2 pass ≈ 1.0）；critic 紅隊實驗（E3）量測判官的敏感度 / 特異度 |
| 2. 環境接地驗證與模擬器 | Match-3 引擎 + `ai_auto_test.py`（<100ms/場，50 場 <10 秒）當作 verifier；關卡生成 agent 的自報難度 vs 模擬器勝率（E2） |
| 3. 異質可驗證訊號 | 程式檢查 / 模擬器 rollout / VLM critic 四軸（style, cohesion, function, progression）/ DINOv2 / 人類最終決定權，如何組合與各自的失效面 |
| Cross-cutting | 「agent 驗證 agent」：critic agent 驗證 generator agent，並由第三方模型驗證 critic |

**標題候選（依 §1.3 的新主張更新）**：
- *One Mechanism Does All the Work: Engine-Grounded Ablation of a Creative Asset Agent*
- *Grounding, Not Guardrails: What Actually Makes Generated Game Assets Legible*
- *Who Verifies the Artist? Four Ways an Asset Benchmark Fooled Us*

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
| **2** | **Result 1（主結果）：ontology 接地解釋全部效果** — 4 主題 × 2 判官 8/8 為正，Δ +0.25~+0.54，與 ±0.25 噪音底線並列報告；ontology 必要但不充分（steampunk B1=0.500） | ✅ 已跑 |
| **1.5** | **Result 2（負面結果）：refs/critic 的角色可讀性增益不可跨判官複現** — τ=0.333，兩判官皆非單調，gap 與 seed sd 同級；critic 改變的是摩擦（needs_review 0.11±0.10、iters 1.95±0.34） | ✅ 已跑 |
| 1.5 | **Result 3：評測自己會騙人** — 五個失效模式與其防護斷言（§1.3 修改 3 的表）；board-parse 上兩判官 τ=0.20、棄答率 0–38.9% 才是唯一行為正常的訊號 | ✅ 已跑 |
| 0.5 | 討論：對 agent 開發者的建議（先接地再加護欄、輪替判官家族、把棄答率當一級指標、單格永不可信、每個指標留一個會失敗的斷言） | — |
| 0.5 | 限制 + ethics：單一領域、**n=8/格導致 0.125 量化與 ±0.25 擺動**、無人類評測、Claude 第三判官因帳戶餘額缺席 | — |

**與 WACV / Creative AI 稿的差異**：那兩篇主體是「怎麼生成」；這篇主體是「哪個部件真的在做事，以及評測本身如何騙過我們」。共用素材（消融 runs、系統圖），但主張與結論相反方向。

---

## 4. 逐日排程（2026-08-24 更新：主結果已到手，剩 6 天）

**現況：Result 1、2、3 的數據全部已跑完並落盤。剩下的是寫，不是跑。**

| 日期 | 工作 | 狀態 |
|---|---|---|
| ~~8/22–8/23~~ | ontology 效度驗證、判官五檢、board-parse | ✅ 完成 |
| **8/24 (一)** | B0 × pet/ocean 生成 + 跨主題跨判官 role 評測 | ✅ 完成 |
| **8/25 (二)** | B0/B1 × steampunk 補齊 → **主結果 8/8 為正**；量出判官重跑噪音 ±0.25 並撤回變異宣稱 | ✅ 完成 |
| 8/26 (三) | 下載 NeurIPS 2026 模板、開 `paper/workshop/`、寫 Intro + 系統 + 評測基礎設施 + Result 1（主圖：8 格 Δ forest plot，含噪音底線帶） | |
| 8/27 (四) | 寫 Result 2（τ=0.333 表 + 摩擦指標）、Result 3（五個失效模式表） | |
| 8/28 (五) | 討論 / 限制 / ethics、參考文獻、壓到 8 頁 | |
| 8/29 (六) | 匿名化檢查、內部審一輪；**選配**：Claude 儲值後補第三判官（有則加強，無則寫進限制） | |
| **8/30 (日) 19:59 前** | OpenReview 上傳 | |

**最高價值的選配實驗（若要加強主結果，這個優先）**：
**把 role 題的 n 從 8 加到 63（full ontology scope）**。目前每格 n=8 造成 0.125 量化與 ±0.25 擺動，
是所有不確定性的根源。`auto_eval.py --scope full` 已支援，跑 B0/B1 × 4 主題 × 2 判官
即可把噪音底線壓到約 1/3，讓 Δ 的量級變成可報的數字而非只有方向。
這比再加主題或再加 seed 都划算——**加主題只增加格數，加 n 才降低每格噪音**。

**次要選配**：board-parse 的 cell size 掃描用 VLM 跑（70/48/32）得到退化曲線。

**退路**：若 8/28 進度落後，改投 **≤4 頁 demo paper**，只保留 Result 1 主結果 + 四個防護斷言表。
主結果單獨就足以成篇，且已完全跑完。

---

## 5. 預期審稿問題

| 問題 | 準備 |
|---|---|
| **只有 ontology 有效，那你們的系統其他部分不就沒用？** | 這正是論文的貢獻：我們**證明了**refs/critic 對角色可讀性沒有可複現增益，並指出它們真正的作用（摩擦 / 審查負載）。誠實歸因比虛報全系統勝利更有價值，也給後續研究省下重複疊機制的成本 |
| **8 格全正，但 n 很小（8 assets/格 role 題，pet/ocean/steampunk 各 1 seed）** | 誠實回報，且**主動報噪音底線**：同判官重跑最大擺動 0.250，與最小 Δ 同級。強度不靠單格數值而靠**方向的無例外性**（4 主題 × 2 獨立判官 8/8 為正）。我們明文寫出「任何單格數字不可採信」 |
| **ontology 有效，那還是有一半素材認不出來（steampunk B1=0.500）？** | 正是我們的宣稱：ontology **必要但不充分**。不誇大成「解決了可讀性」，而是「它是唯一有可複現效果的機制，且仍不足夠」——這給後續研究一個明確的未解問題 |
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
