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

## 1. 定位：把 GAPGen 從「生成系統」重寫成「驗證問題」

**論文一句話**：
> 創意型 agent 的**通過率是可被 hack 的指標**。我們以一個真實的遊戲素材生產 agent 為場域，組合三種異質驗證訊號——確定性程式檢查、**模擬器 rollout**、VLM critic——並量化：(a) 只靠程式檢查會 100% 放行不合玩法的素材，(b) VLM critic 存在自評偏好，(c) agent 自報的品質與模擬器接地的真實值系統性背離。結論：可靠的 agent 開發要看的是**驗證摩擦的分布**，不是通過率。

**標題候選**：
- *Pass Rate Is Not Progress: Environment-Grounded Verification of Creative Game Agents*
- *Who Verifies the Artist? Heterogeneous Verification for Game-Asset Agents*

**對三個 pillar 的對齊（投稿時逐項寫進 intro）**：

| Pillar | 我們的對應 |
|---|---|
| 1. 驗證的安全與穩健（reward hacking、判官紅隊） | 通過率作為 reward 會被弱 gate 直接刷滿（B0–B2 pass ≈ 1.0）；critic 紅隊實驗（E3）量測判官的敏感度 / 特異度 |
| 2. 環境接地驗證與模擬器 | Match-3 引擎 + `ai_auto_test.py`（<100ms/場，50 場 <10 秒）當作 verifier；關卡生成 agent 的自報難度 vs 模擬器勝率（E2） |
| 3. 異質可驗證訊號 | 程式檢查 / 模擬器 rollout / VLM critic 四軸（style, cohesion, function, progression）/ DINOv2 / 人類最終決定權，如何組合與各自的失效面 |
| Cross-cutting | 「agent 驗證 agent」：critic agent 驗證 generator agent，並由第三方模型驗證 critic |

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

## 3. 8 頁結構

| 頁 | 內容 |
|---|---|
| 1 | Abstract + Intro：驗證是瓶頸；創意任務沒有 ground truth；本文用一個真實生產 agent 當測床 |
| 0.5 | 場景與系統：Match-3 素材 agent + 關卡 agent，兩者都有一個驗證迴路（一張系統圖，重用 `paper/figures/GAPGen-system-overview.png` 改標） |
| 1 | 異質驗證訊號的形式化：程式檢查 / 模擬器 rollout / VLM critic / 客觀嵌入 / 人類，各自的 ground truth 來源與覆蓋範圍 |
| 1.5 | **Result 1：通過率是壞 reward**（B0–B3，pass 1.00 → 0.89、needs_review 0.11 ± 0.10、iters 1.95 ± 0.34；弱 gate 拿滿分） |
| 1.5 | **Result 2：判官自評偏好**（E1 三方比對 + Spearman + gap） |
| 1.5 | **Result 3：環境接地 vs 自報**（E2 散佈圖 + validator 錯誤分類學 + 重生收斂） |
| 1 | **Result 4：critic 紅隊敏感度 / 特異度**（E3 表）+ E4 cost–coverage |
| 0.5 | 討論：對 agent 開發者的建議（把摩擦當指標、驗證器要輪替家族、便宜 verifier 優先）；限制（單一領域、n 小、非人類評測） |
| 0.5 | Conclusion + 限制 + ethics |

**與 WACV / Creative AI 稿的差異**：那兩篇的主體是「怎麼生成」，這篇的主體是「怎麼驗證，以及驗證器自己有多不可靠」。素材（消融數字、系統圖）可重用，但主張、實驗（E1–E4 全新）、結論完全不同。

---

## 4. 逐日排程（刻意排在 WACV 之後，共用素材）

| 日期 | 工作 |
|---|---|
| 8/22 (六) | 下載 NeurIPS 2026 模板、開 `paper/workshop/` 目錄、寫 intro + 場景兩節（可與 WACV 並行，內容不重疊） |
| 8/23 (日) | **E3 紅隊**：擾動腳本 + 跑一輪 critic（本地為主，API 呼叫少） |
| 8/24 (一) | **E2**：50 次關卡生成 + validator 統計 + 50 場 ×N 關模擬器勝率 |
| 8/25 (二) | E2 散佈圖 + E1 三方比對表（資料多半已在 `paper/results/`） |
| 8/26 (三) | E4 cost–coverage 圖；四個 Result 節寫完 |
| 8/27 (四) | （WACV 收尾日，本計畫暫停） |
| 8/28 (五) | 討論 / 限制 / ethics、參考文獻、壓到 8 頁 |
| 8/29 (六) | 匿名化檢查、內部審一輪 |
| **8/30 (日) 19:59 前** | OpenReview 上傳 |

**若進度落後的退路**：改投 **≤4 頁 demo paper**——主題「異質驗證儀表板：程式檢查 + 模擬器 + VLM critic 的並列稽核介面」，用現成的 `pages/3_AI_Auto_Test.py` 與 critic 報表截圖 + E2 一張圖即可成篇。這條退路幾乎穩投得出去，不要讓 8/30 空手。

---

## 5. 預期審稿問題

| 問題 | 準備 |
|---|---|
| 這只是一個 domain 的案例研究，可推廣嗎？ | 主張是可移植的**方法論**（摩擦分布 > 通過率、輪替判官家族、便宜 verifier 優先）；Match-3 只是有 ground truth（關卡 JSON + 模擬器）的稀有測床 |
| 為什麼不用既有 agent benchmark？ | 既有 benchmark 沒有創意產出 + 可執行環境同時存在；本文的價值正是提供這種雙重接地的場域 |
| VLM critic 的分數可信嗎？ | 不主張可信——E1、E3 就是在量它多不可信，這是結論而非前提 |
| 樣本數 | 誠實回報 n（12 assets × 3 seeds × 3 主題、E2 的 50 次生成、E3 的擾動數）；重點在效果方向而非精確效果量 |
| 人類基準？ | 問卷已就緒（`paper/results/human_eval_protocol.md`）；若 WACV 那邊收到 n≥12，本篇直接引用作為人類 vs 自動驗證器一致性 |

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
