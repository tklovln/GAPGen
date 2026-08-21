# 投稿計畫 A：WACV 2027（Round 2）

**標的**：IEEE/CVF WACV 2027 · Disney Springs, FL · 2027/1/4–8
**現況基礎**：`paper/main.tex`（GAPGen）+ `art_pipeline/` + `scripts/auto_eval.py` + `paper/results/`
**撰寫日**：2026-08-21

---

## 0. 時程（AoE → 台北時間 = AoE 日期 +1 天 19:59）

| 項目 | AoE | 台北截止 |
|---|---|---|
| Round 2 新論文註冊（enrollment） | Aug 21 | **8/22 (六) 19:59** ← 只剩約 32 小時 |
| Round 2 論文投稿 | Aug 28 | 8/29 (六) 19:59 |
| Round 2 補充材料 | Aug 30 | 8/31 (一) 19:59 |
| Reviews + 最終決議 | Oct 09 | — |
| Camera ready | Nov 02 | — |

**硬規則**：8 頁（不含 references）、**雙盲**、必須用 WACV 2027 Author Kit。未匿名 / 超頁 / 未用模板 = desk reject。
投稿系統：OpenReview（[Round 2 群組](https://openreview.net/group?id=thecvf.com/WACV/2027/Conference_Round_2)）。Round 2 **沒有 rebuttal**，一次定生死。

### 註冊（enrollment）是硬門檻，不是只有 Round 1 退稿才要

作者指南原文：*"New papers can be submitted in either the first or the second round. **Papers must be enrolled at least one week before the submission deadline for each round.**"*
以及 *"After the paper enrollment deadline, **you can no longer create new paper submissions**."* / *"Can we please have an extension...? **NO.**"*

→ **8/22 台北 19:59 前沒註冊，8/28 就完全不能投，且 Round 2 是最後一輪。**
（Dates 頁那句 "Resubmitting Round 1 papers need to be re-register" 是給 Round 1 作者的補充；我們沒有 Round 1 稿件，不適用。）

註冊只需在 OpenReview 建立 submission、填標題 + 摘要（上限 5000 字元）、加齊共同作者。但有三個會咬人的點：

1. **作者名單在註冊截止後凍結**，之後只能調換順序、不能增刪 → 明天前就要決定人類評測協助者是否掛名。
2. **所有共同作者都必須有有效 OpenReview profile**，否則 desk reject；非機構信箱（如 gmail）的 profile 審核最長需兩週 → 現在已來不及，務必先確認自己的 profile 已通過。
3. 標題與摘要在 8/28 投稿截止前仍可修改，但**不完整的投稿會被直接刪除** → 摘要不要留空白佔位，寫一版可用的。

---

## 1. 決策關卡（必須先解，否則其他都白做）

**Dual submission 衝突**：GAPGen 已於 **8/10 投出 NeurIPS 2026 Creative AI Track**，決議日 **9/18**，也就是 WACV Round 2 投稿（8/28）時該稿仍在審。
WACV 政策：審查期間不得有 **內容重疊 ≥20%** 的稿件投在別處，違反會被 reject 並回報對方會議。

三個選項：

| 選項 | 做法 | 風險 | 評估 |
|---|---|---|---|
| **A. 差異化新稿**（建議） | 投 **Evaluations & Datasets track**：貢獻主體改成「玩法一致性的**量測方法 + benchmark**」，GAPGen 只當作被量測的一個系統之一。method 壓到 <1 頁，新增外部 baseline、新 metric、人類評測 | 重疊判定灰色地帶；需 7 天內產出真的新實驗 | 兩邊都保得住，但工作量最大 |
| B. 撤 Creative AI | 撤稿後把完整 GAPGen 擴成 8 頁投 Applications track | 放棄 9/18 一個很可能上的 venue；8 天內補齊 CV 級實驗仍嫌趕 | 政策最乾淨、期望值最差 |
| C. 不投 WACV | 等 9/18 結果，把擴充版投 CVPR 2027（約 11 月截稿） | 少一次曝光 | 品質最高、最安全 |

**行動**：今天先做 Round 2 註冊（保留選擇權），8/24 依實驗進度在 A / C 之間二選一。**B 只在 Creative AI 那稿已確定要改投時才考慮。**

**若走 A，重疊控制的具體要求**：
- 全篇重寫，不沿用 Creative AI 稿的句子（abstract / intro 尤其）。
- 貢獻宣告改為：任務形式化 + **GC-Bench 評測套件** + 跨方法比較 + 人類評測。GAPGen 降級為 method baseline。
- 新增圖表 ≥60% 為新產出（board-parse 圖、外部 baseline 對照圖、人類評測圖）。
- Creative AI 稿的三大貢獻不可原樣複述。

---

## 2. Track 與定位

**首選：Evaluations & Datasets track**（配合上面選項 A）。CFP 明確歡迎「新評測協定」、「以人為中心的評測」、「既有評測的失效模式分析」——這正好是 GAPGen 現有最強、最可信的部分（pass rate 是壞指標、跨模型判官避免自評循環、DINOv2 model-independent 佐證）。
**次選：Applications track**（審查標準是 systems-level innovation + 領域新穎性 + comparative assessment；application areas 明列 "Arts, games, and social media"）。

**論文一句話（E&D 版）**：
> 遊戲素材生成的既有評測只量視覺一致性；我們提出 **gameplay-consistency 評測套件**：角色可辨識度（board scale 70px）、階段進程正確性、家族內聚 / 跨家族區辨，以及一個**下游感知任務**（用生成素材渲染真實關卡盤面，量測盤面解析正確率），並用它比較 5 種生成方法，顯示視覺指標排名與玩法指標排名不一致。

**為什麼這是 CV 論文而不是 workflow 部落格**：核心量測建立在感知任務上（低解析度小圖的角色辨識、序列排序、下游盤面解析），而非生產流程效率。

---

## 3. 需要補的實驗（依 ROI 排序，7 天內可完成）

### E1. 下游盤面解析評測（最高 ROI，最有 CV 味，成本最低）★必做
把每個條件的素材套進真實關卡，量測「盤面能不能被讀懂」。

- 資料：`levels/*.json` + `godot_demo/levels/Level_0xx.json`（已有 100 關）。
- 渲染：重用 `paper/figures/make_qualitative_figures.py` 的 `alpha_composite` 邏輯，把 sprite 依 JSON 貼成 70px/cell 盤面圖（新腳本約 60 行，不要碰引擎 export）。
- 量測：VLM 逐格輸出 tile 標籤 → 與 JSON ground truth 比對，得 **per-cell accuracy / 混淆矩陣**；另加一個零成本對照：**template matching（正規化互相關）**的解析率，完全不靠模型判斷。
- 為什麼強：ground truth 是關卡 JSON，不是模型意見；混淆矩陣直接顯示 B0 把 power-up 誤判成 match element（現有 role accuracy 0.375 的機制證據）。
- 建議規模：3 主題 × 4 條件 × 10 關 = 120 張盤面。

### E2. 外部 baseline（審稿人一定問）★必做
現在只有自家 B0–B3 消融，沒有跟別人的方法比 → Applications / E&D 都會被打「comparative assessment 不足」。
最少要 2 個外部對照：
1. **單提示一次生成整組**（same generator, one prompt, 12 assets in one image → 切圖）：代表「直接叫模型生一套」的實務做法。
2. **set-consistency 代表方法**：SDXL + IP-Adapter（style reference）或 `gpt-image-1`；擇一即可，重點是不同家族的方法。
可選第 3 個：人類美術現有素材（`godot_demo/resources/sprites/`）當 upper bound —— 這個很有說服力且零生成成本。

### E3. 人類評測 n≥12（基礎設施已完成，只差人）★必做
`paper/human_eval/` 靜態問卷 + 三主題 stimuli 都已 export，protocol 在 `paper/results/human_eval_protocol.md`。
- 8/22 部署 GitHub Pages，8/22–8/26 收滿 n≥12（內部同事可）。
- 產出 `paper/results/human_eval_summary.csv`，並計算**人類 vs VLM 判官的一致性（agreement / correlation）**——這是 E&D track 最想看的東西：證明自動指標可以代理人類。

### E4. 穩定化現有噪音指標（半天）
Stage ordering Kendall τ 目前 0.33 / −0.67 / 0.67 / 0.0（每條件只問一次）→ 不能放進論文當證據。
改成每條件 ×5 repeats ×3 seeds，回報 mean ± CI。`scripts/auto_eval.py --tasks stage` 加一個 repeats 參數即可。

### E5. 規模擴張（有餘力才做）
主題 3 → 5（加回 steampunk + 1 個新主題）、資產 12 → 20（加 pools / chillers / background）、seeds 3 → 5。
成本以現有 log 估：`research_ablation.py` 一條件一 seed 12 張，整批擴張約 5×4×20 = 400 張生成 + critic，注意 API 額度與時間；**若與 E1–E3 衝突，優先放棄 E5**。

指令備忘：
```bash
python scripts/auto_eval.py --self-check                          # 離線自檢
python scripts/auto_eval.py --themes fruit,pet,ocean --conditions B0,B1,B2,B3 \
  --judge openai --pairwise-repeats 4                             # 跨模型判官
python scripts/auto_eval.py --tasks cohesion                      # DINOv2，不用 API
python scripts/research_ablation.py --conditions B0,B1,B2,B3 --seeds 3
python scripts/research_postprocess.py --all
```

---

## 4. 8 頁結構分配（E&D 版）

| 頁 | 內容 |
|---|---|
| 1 | Abstract + Intro（問題：視覺一致 ≠ 可上線）+ teaser（同一組素材，視覺分數高但盤面解析失敗的例子） |
| 1 | Related work：consistent multi-image generation / 遊戲素材與 affordance / 生成評測與判官偏誤 |
| 1.5 | **任務與評測套件定義**：三層準則、每個 metric 的定義與 ground truth 來源、判官設計（跨模型、去自評循環） |
| 0.75 | 被評測的方法：外部 baseline ×2 + GAPGen B0–B3（method 壓縮成一段 + 系統圖） |
| 2.5 | 實驗：主表（方法 × metric）、盤面解析混淆矩陣、人類 vs 自動指標一致性、消融、質性失效案例 |
| 0.75 | 分析與限制：pass rate 為何是壞指標、判官自評偏好、樣本規模、單一遊戲類型 |
| 0.5 | Conclusion + Ethics（生成素材的著作權與美術勞動立場） |

**保留的最強敘事**：*higher pass rate is not better*——B0–B2 通過率接近 1.0 但下游盤面解析與角色辨識最差。這是「既有評測失效模式」的教科書級案例，正中 E&D track。

---

## 5. 雙盲匿名檢查清單（漏一項就 desk reject）

- [ ] `main.tex` 移除作者、`Gamania`、`Original Content Center`、email
- [ ] 移除 / 匿名化 GitHub repo 連結、`Match3_sim` 專案名、`godot_demo` 內含公司字樣的路徑截圖
- [ ] 圖片不得含公司 logo、內部工具截圖上的帳號名、Streamlit 頁籤中的專案名
- [ ] PDF metadata（`pdftk dump_data` / `exiftool` 檢查 Author / Producer）
- [ ] 自我引用改為第三人稱（"prior work [X]"，不得寫 "our previous system"）
- [ ] 補充材料（8/30）同樣匿名；**不得包含改良版結果**（WACV 明文禁止）
- [ ] 遊戲美術原始素材若屬公司資產，確認可對外呈現（法務 / 主管確認）

---

## 6. 逐日排程

| 日期 | 工作 | 產出 |
|---|---|---|
| 8/21 (五) | **OpenReview Round 2 註冊**（標題 + 摘要佔位）；下載 Author Kit；E1 渲染腳本寫完 | 註冊完成、`scripts/board_parse_eval.py` |
| 8/22 (六) | 部署人類評測問卷發信招募；E1 跑 fruit 全條件；E4 stage repeats | 首批盤面解析數字 |
| 8/23 (日) | E2 外部 baseline 生成（單提示整組 + IP-Adapter / gpt-image） | baseline 素材 + 通過率 |
| 8/24 (一) | **Go / No-go 決策點**：E1+E2 有沒有出現「視覺贏但玩法輸」的對照？沒有就改走選項 C | 決策紀錄 |
| 8/25 (二) | 主表定稿、混淆矩陣圖、baseline 對照圖 | 全部圖表 |
| 8/26 (三) | 人類評測收斂 n≥12、算人類 vs VLM 一致性 | `human_eval_summary.csv` |
| 8/27 (四) | 全文寫完（套 WACV 模板，8 頁硬限） | 完整 PDF |
| 8/28 (五) | 匿名化檢查、頁數檢查、參考文獻、內部審一輪 | 投稿檔 |
| 8/29 (六) 19:59 前 | **上傳論文** | 完成 |
| 8/31 (一) 19:59 前 | 上傳補充材料（更多質性網格、prompt / rubric 全文、ontology JSON） | 完成 |

---

## 7. 高風險審稿問題與預備答案

| 問題 | 準備 |
|---|---|
| 這只是產業工作流程，CV 貢獻在哪？ | 貢獻是**評測方法 + 下游感知任務**；主表證明視覺指標與玩法指標排名不一致 |
| 只有自家消融，沒有跟 SOTA 比 | E2 兩個外部 baseline + 人類美術 upper bound |
| 判官是 Gemini 評 Gemini 的自評循環 | 跨模型 GPT-4o 判官 + DINOv2 model-independent + 人類一致性 |
| n=12 assets 太小、單一遊戲 | 誠實列為限制；E5 若完成則擴到 20 assets × 5 主題；強調 ground truth 來自關卡 JSON 而非人為標註 |
| 跟 NeurIPS Creative AI 那篇的關係？ | 見第 1 節；若走選項 A 必須能明確說出兩篇貢獻不同 |
| Kendall τ 為什麼是負的？ | E4 已改為多次重複 + CI；原單次結果不再引用 |

---

## 8. 若放棄 WACV（選項 C）的替代路徑

1. 9/18 拿到 Creative AI 決議 → 依審稿意見擴充。
2. 本計畫的 E1–E5 全部仍然有效，直接轉去 **CVPR 2027**（約 11 月截稿）或 **WACV 2027 Workshop**（1/4–5，另有獨立 CFP）。
3. 短期曝光改由計畫 B（NeurIPS Workshop，8/29 截稿、非 archival、明文允許 dual submission）承接——**這條路沒有政策風險，優先度應高於 WACV**。
