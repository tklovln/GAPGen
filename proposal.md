# EduAssetVerify: Constraint-Grounded Verification of AI-Generated Visual Assets for Educational Games

**Target Conference:** AAIE 2027  
**Research Area:** Generative AI for Teaching, Learning, and Assessment  
**Keywords:** Generative AI, Multimodal Verification, Educational Game Assets, Vision-Language Models, Constraint Satisfaction, Counterfactual Evaluation

---

## Abstract

建議 150–200 words，包含：

1. **Background:** 生成式 AI 已逐漸被用於教育遊戲與視覺教材製作，但生成內容可能存在不容易被察覺的知識或結構錯誤。
2. **Problem:** 現有視覺評估方法偏重美感、語意相似度與整體品質，未必能可靠辨識違反教學概念的圖像。
3. **Method:** 提出 EduAssetVerify，透過形式化教育約束、程式化驗證與 Vision-Language Model（VLM），檢測生成素材的教學語意及結構錯誤。
4. **Benchmark:** 建立涵蓋 Fraction Understanding、Object Counting、Spatial Reasoning 的可控反事實圖像驗證資料集。
5. **Experiments:** 比較不同驗證策略的錯誤偵測能力、誤判率、錯誤定位、跨模型泛化與驗證成本。
6. **Results:** 填入實際實驗結果，不預先宣稱效能提升。
7. **Contribution:** 提供一個可重現、不依賴真人評估的教育視覺素材驗證框架。

## 1. Introduction

### 1.1 Background and Motivation

- Generative AI 在教育遊戲、數位教材與互動式學習內容中的應用。
- Text-to-Image 與 Multimodal Generative Models 降低教育視覺素材的製作成本。
- 教育素材除了視覺品質，也需要滿足明確且可檢驗的教學概念。
- 現有 VLM-based Evaluation 的可靠性限制。

### 1.2 Problem Statement

- 視覺上合理的生成素材，可能不符合教育目標。
- VLM 評估可能忽略物件數量、幾何比例、空間關係等細節。
- 單純依賴語意相似度，無法確保必要教學約束得到滿足。
- 缺乏能精確評估視覺教育概念錯誤的受控 Benchmark。

**Research Question:**

> Can constraint-grounded multimodal verification reliably detect educational concept violations in AI-generated visual assets without requiring human evaluation?

### 1.3 Research Challenges

**C1. Educational Constraint Representation**

如何將抽象的教學需求轉換成可機器驗證的結構化約束？

**C2. Visual-to-Constraint Grounding**

如何從生成圖片推斷可驗證的視覺證據，而不是直接相信 VLM 的整體評分？

**C3. Robust Counterfactual Verification**

當圖像出現局部錯誤時，模型能否識別真正的教學概念違規，而非受到風格或背景因素影響？

### 1.4 Main Contributions

本文預計提出三項貢獻：

1. **Educational Constraint Schema:** 建立教育遊戲視覺素材的形式化約束表示，支援數量、比例、幾何與空間關係等規則。
2. **Constraint-Grounded Multimodal Verifier:** 結合 VLM 視覺解析與確定性規則檢查，提高教育圖像錯誤偵測的可解釋性。
3. **Counterfactual Educational Asset Benchmark:** 建立含受控錯誤、精確 Ground Truth 與未見條件測試的教育素材驗證資料集。

---

## 2. Related Work

### 2.1 Generative AI for Educational Visual Content

- Text-to-Image Generation for Educational Materials
- Multimodal Content Generation
- AI-assisted Educational Game Development
- Educational Content Quality Assessment

### 2.2 Vision-Language Models for Visual Verification

- VLM-as-a-Judge
- Visual Question Answering
- Object Counting and Spatial Reasoning
- Visual Hallucination Detection
- Grounded Multimodal Reasoning

### 2.3 Constraint-Based Generation and Verification

- Constraint Satisfaction
- Neuro-Symbolic Verification
- Structured Visual Representation
- Rule-based Validation
- Generation–Verification Pipelines

### 2.4 Counterfactual and Metamorphic Evaluation

- Counterfactual Visual Reasoning
- Metamorphic Testing for Generative AI
- Controlled Perturbation Benchmarking
- Robustness and Generalization Evaluation

### 2.5 Research Gap

整理既有方法的限制：

| Existing Approach | Limitation |
|---|---|
| Image Quality Metrics | 無法直接檢查教育概念正確性 |
| Text–Image Similarity | 對精確數量、比例或空間關係可能不敏感 |
| VLM-as-a-Judge | 可能產生錯誤判斷或缺乏可驗證證據 |
| Rule-based Verification | 對非結構化生成圖片缺乏足夠感知能力 |
| General Visual Reasoning Benchmarks | 不一定涵蓋教育約束與受控錯誤配對 |

**Positioning:** 本研究聚焦於將視覺內容轉換為可驗證證據，再檢查教學約束是否成立，而不是提出另一個泛用圖片品質評分模型。

---

## 3. Problem Formulation

### 3.1 Educational Asset Generation Task

定義教育視覺素材生成任務：

- Learning objective: \(L\)
- Asset generation prompt: \(P\)
- Generated image: \(I\)
- Educational constraint set: \(C=\{c_1,\ldots,c_n\}\)

目標為驗證：

\[
V(I,C)\rightarrow
\{\text{Valid},\text{Invalid},\text{Uncertain}\}
\]

其中 Uncertain 用來表示證據不足或無法可靠判斷的情況。

### 3.2 Educational Constraint Representation

定義四種約束類型：

1. **Cardinality Constraints:** 物件數量、集合大小。
2. **Geometric Constraints:** 比例、對稱、角度、區域面積。
3. **Spatial Constraints:** 方位、排列、包含與相對位置。
4. **Semantic Constraints:** 物件類別、教學概念與標籤對應。

結構化約束示例：

```json
{
  "task": "fraction_understanding",
  "learning_objective": "represent_one_fourth",
  "constraints": [
    {"type": "part_count", "operator": "eq", "value": 4},
    {"type": "equal_area", "operator": "true"},
    {"type": "colored_part_count", "operator": "eq", "value": 1},
    {"type": "fraction_value", "operator": "eq", "value": 0.25}
  ]
}
```

### 3.3 Verification Objectives

定義三個研究目標：

- **Validity:** 是否正確判斷圖像符合所有必要教育約束。
- **Violation Localization:** 能否指出發生錯誤的物件、區域或約束。
- **Robustness:** 在不同圖像風格、生成模型與錯誤類型下是否維持可靠性。

---

## 4. Proposed Method: EduAssetVerify

### 4.1 Framework Overview ( 請最大程度的參考我們 workshop paper 的技術細節, 確保不會踩坑)

建議架構圖 Figure 1：

```text
Learning Objective
        |
        v
Educational Constraint Parser
        |
        v
Structured Constraint Set
        |
        +------------------------+
        |                        |
        v                        v
AI-Generated Image       Constraint Graph
        |                        |
        v                        |
VLM Visual Grounding             |
        |                        |
        v                        |
Visual Evidence Graph            |
        |                        |
        +------------+-----------+
                     |
                     v
       Deterministic Rule Engine
                     |
                     v
       Constraint Violation Report
                     |
                     v
        Valid / Invalid / Uncertain
```

### 4.2 Educational Constraint Parser

**Input:** Learning Objective、Asset Requirements。

**Output:** Structured Constraint Graph。

主要處理：

- 擷取必要教學概念。
- 將自然語言需求轉換成結構化約束。
- 識別必要物件與其關係。
- 檢查約束間是否存在矛盾。

實驗應區分：

- 使用人工預先定義之標準約束，測試驗證能力。
- 使用 LLM 自動抽取約束，測試完整 Pipeline。

避免將約束抽取錯誤與圖像驗證錯誤混在同一個結果。

### 4.3 Multimodal Visual Grounding

利用 VLM 從圖片提取：

- Object identity
- Object count
- Bounding regions
- Spatial relations
- Geometric attributes
- Semantic labels

轉換為 Visual Evidence Graph：

\[
G_I=(O_I,R_I,A_I)
\]

其中：

- \(O_I\)：辨識出的物件。
- \(R_I\)：物件間的空間或語意關係。
- \(A_I\)：物件屬性。

Grounding 階段必須根據圖像內容推論，不可直接讀取產生 Ground Truth 的隱藏參數。

### 4.4 Hybrid Constraint Verification

結合兩種機制：

**A. Deterministic Verification**

- Exact object count
- Fraction / ratio validation
- Spatial relation checking
- Geometric consistency
- Logical constraint checking

**B. VLM Semantic Verification**

- Semantic correctness
- Object-category consistency
- Educational concept grounding
- Ambiguous visual relationship detection

規則引擎負責處理已有足夠證據的明確約束；證據不足時需保留不確定性，不能將推測當成形式保證。

### 4.5 Constraint Violation Detection and Localization

對每項約束輸出：

- Constraint ID
- Satisfaction status
- Supporting visual evidence
- Violation type
- Affected object or region
- Confidence / uncertainty

輸出範例：

```json
{
  "asset_id": "fraction_001",
  "valid": false,
  "violations": [
    {
      "constraint": "equal_area",
      "reason": "Unequal partition areas",
      "affected_region": "upper_right",
      "status": "violated"
    }
  ]
}
```

### 4.6 Verification Confidence and Abstention

加入可拒絕判斷的設計：

- 感知證據不足時輸出 Uncertain。
- 不同驗證器結果衝突時保留衝突資訊。
- 透過 Confidence Threshold 控制 False Acceptance。
- 評估 Coverage–Risk Trade-off。

---

## 5. Counterfactual Educational Asset Benchmark

### 5.1 Benchmark Design Principles

Benchmark 需要滿足：

1. **Programmatically Verifiable Ground Truth**
2. **Controlled Counterfactual Pairs**
3. **Multiple Educational Domains**
4. **Visual Diversity**
5. **Unseen-condition Generalization**

### 5.2 Educational Task Categories

**Task A: Fraction Understanding**

- Equal partition
- Colored fraction
- Fraction comparison
- Part-to-whole representation

**Task B: Object Counting and Classification**

- Exact object counting
- Category-based counting
- Group comparison
- Distractor objects

**Task C: Spatial Reasoning**

- Left / Right
- Above / Below
- Rotation
- Reflection
- Symmetry
- Relative positioning

### 5.3 Counterfactual Error Generation

對正確樣本施加單一可控變化：

\[
I^{-}=T_k(I^{+})
\]

其中 \(T_k\) 為第 \(k\) 種錯誤操作。

錯誤類型包含：

- Missing Object
- Extra Object
- Incorrect Proportion
- Incorrect Label
- Spatial Relation Reversal
- Broken Symmetry
- Semantic Mismatch

建立配對資料：

\[
D=\{(I^+,I^-,C,y^+,y^-)\}
\]

其中正確與錯誤版本共享相同教學約束。

### 5.4 Dataset Construction

建議初版：

| Domain | Correct Assets | Violated Assets | Total |
|---|---:|---:|---:|
| Fraction | 150 | 150 | 300 |
| Counting | 150 | 150 | 300 |
| Spatial Reasoning | 150 | 150 | 300 |
| **Total** | **450** | **450** | **900** |

以上為預計資料規模，非已完成數據。

資料來源：

- Procedural SVG / Python Renderer
- Controlled asset transformations
- AI-generated raster image variants
- Independent rule-based ground-truth validation

### 5.5 Data Split and Generalization

避免同一張原圖的不同變體同時進入訓練與測試。

建議分成：

- In-domain Test
- Unseen Asset Template
- Unseen Error Combination
- Unseen Visual Style
- Cross-generator Test

真實生成模型的輸出不一定具有可自動確認的正確答案，因此需要獨立檢查，或將缺乏可信標籤的樣本排除於主要 Accuracy 評估之外。

---

## 6. Experimental Setup

### 6.1 Research Questions

**RQ1:** Does constraint-grounded verification outperform conventional VLM-based judging in detecting educational visual errors?

**RQ2:** Can EduAssetVerify correctly localize constraint violations?

**RQ3:** Does the framework generalize across educational tasks, visual styles, and generation models?

**RQ4:** What is the trade-off between verification accuracy, abstention, latency, and computational cost?

### 6.2 Baseline Methods

| Method | Description |
|---|---|
| Text–Image Similarity | 使用語意相似度估計素材是否符合需求 |
| VLM Direct Judge | 直接詢問 VLM 圖像是否正確 |
| VLM Chain-of-Thought Judge | 使用分步視覺推理檢查 |
| VLM Structured Judge | 要求 VLM 逐項檢查結構化約束 |
| Rule-only Validator | 以視覺解析輸出的結構化證據執行規則檢查 |
| EduAssetVerify | VLM Grounding + Hybrid Constraint Verification |

所有方法應使用一致的輸入資訊與可比較的模型能力。

### 6.3 Evaluation Metrics

**Error Detection**

- Precision
- Recall
- F1-score
- False Acceptance Rate
- False Rejection Rate

**Constraint-level Evaluation**

- Constraint Satisfaction Accuracy
- Violation Type Accuracy
- Constraint Localization Accuracy

**Counterfactual Evaluation**

- Pairwise Discrimination Accuracy
- Counterfactual Consistency
- Invariance under Style Changes

**Reliability and Efficiency**

- Abstention Rate
- Risk–Coverage Curve
- Inference Latency
- Token Consumption
- Estimated Cost per Asset

### 6.4 Implementation Details

應報告：

- VLM model names and versions
- Prompt templates
- Image resolution
- Constraint representation
- Rule engine implementation
- Generation settings
- Evaluation hardware
- Repeated-run settings

若使用隨機生成的 Benchmark，固定隨機種子並提供可重建資料的程式。

---

## 7. Results and Analysis

> 本章節應待實驗完成後填寫實際數據。

### 7.1 Overall Verification Performance

**Table 1. Educational Constraint Violation Detection**

比較所有 Baseline 的：

- Precision
- Recall
- F1
- False Acceptance Rate

主要回答 RQ1。

### 7.2 Performance across Educational Domains

**Table 2. Performance by Constraint Type**

依 Fraction、Counting、Spatial Reasoning 分別報告效能。

分析哪些錯誤適合確定性規則，哪些需要 VLM 語意能力。

### 7.3 Counterfactual Robustness

**Table 3. Counterfactual Pair Evaluation**

比較：

- Correct vs. Violated pairs
- Style-preserving transformations
- Unseen error combinations
- Cross-generator performance

主要回答 RQ3。

### 7.4 Ablation Study

**Table 4. Component Ablation**

| Configuration | Purpose |
|---|---|
| Full EduAssetVerify | 完整方法 |
| w/o Rule Engine | 驗證確定性規則的貢獻 |
| w/o Structured Grounding | 驗證結構化視覺證據的必要性 |
| w/o Semantic Verification | 驗證 VLM 語意判斷的貢獻 |
| w/o Abstention | 測試不確定性處理的效果 |

### 7.5 Qualitative Error Analysis

**Figure 3. Example Verification Results**

展示：

- Correctly accepted assets
- Correctly rejected assets
- False acceptance cases
- False rejection cases
- Uncertain cases

每個案例包含生成圖片、約束、AI 判斷以及真實標籤。

### 7.6 Computational Efficiency

**Table 5. Verification Cost and Latency**

比較：

- Average latency per image
- VLM calls per asset
- Input / output tokens
- Cost per 1,000 assets

主要回答 RQ4。

---

## 8. Discussion

### 8.1 Implications for Generative AI in Education

- 對 AI 生成教育遊戲素材的品質控管價值。
- 對自動化教材生產流程的可擴充性。
- 對多模態內容驗證及可信生成式 AI 的啟示。

### 8.2 Advantages of Constraint-Grounded Verification

- 明確區分美感與教學概念正確性。
- 將自由形式的視覺判斷轉換為可檢查的結構化證據。
- 提供可重現的錯誤類型及失敗分析。
- 支援低人工介入的素材驗證流程。

### 8.3 Limitations

- 本研究不直接驗證學生學習成果。
- 僅涵蓋具有可形式化約束的教育概念。
- VLM 感知錯誤可能導致規則驗證失敗。
- 合成 Benchmark 與真實教育內容存在 Domain Gap。
- 部分教學品質無法完全透過程式規則判定。

### 8.4 Future Work

- 更複雜的教育概念與圖表。
- Multimodal Educational Content Verification。
- Interactive Game-based Learning Assessment。
- Automatic Error Repair。
- Real-world educational deployment。

---

## 9. Conclusion

本研究提出 EduAssetVerify，一個以教育約束為基礎的多模態生成素材驗證框架。

結論應總結：

1. 教育視覺素材的結構化約束表示。
2. VLM 與確定性規則結合的驗證方法。
3. 可重現的反事實教育視覺 Benchmark。
4. 實際實驗結果證實或否定的研究假說。
5. 方法的適用範圍及限制。

避免在沒有真人學習研究的情況下宣稱提升學生理解力或學習成績。

---

## References

建議依照下列領域蒐集 15–25 篇相關文獻：

1. Generative AI in Education
2. Multimodal Educational Content Generation
3. Vision-Language Models as Judges
4. Visual Reasoning and Object Counting
5. Constraint-based / Neuro-symbolic Verification
6. Counterfactual Visual Evaluation
7. Metamorphic Testing of AI Systems
8. Educational Game Asset Generation
9. Multimodal Hallucination Detection
10. Reliable and Trustworthy Generative AI

正式文獻需補齊作者、年份、出版場域、DOI 或可驗證的論文連結。

---

## Appendix（Optional）

### A. Educational Constraint Schema

完整的 JSON Schema 與各約束定義。

### B. Prompt Templates

VLM Judge、Constraint Parser、Visual Grounding 所使用的 Prompt。

### C. Benchmark Generation Algorithm

正確／錯誤圖像配對生成演算法與參數。

### D. Additional Qualitative Results

更多失敗案例、模型判斷與錯誤定位結果。

### E. Reproducibility Checklist

- [ ] 固定 Benchmark 生成種子
- [ ] 公開實驗設定
- [ ] 記錄模型版本
- [ ] 公開 Baseline Prompts
- [ ] 提供原始評估指標
- [ ] 區分程序化樣本與生成式模型樣本
- [ ] 避免隱藏 Ground Truth 洩漏至驗證模型

---

## Suggested Paper Length

| Section | Estimated Pages |
|---|---:|
| Abstract + Introduction | 1.0 |
| Related Work | 1.0 |
| Problem Formulation | 0.75 |
| Proposed Method | 2.0 |
| Benchmark Construction | 1.0 |
| Experimental Setup | 1.0 |
| Results and Analysis | 1.5 |
| Discussion + Conclusion | 0.75 |
| **Total (excluding References)** | **9.0** |

這是建議分配，最後依 AAIE 官方模板與頁數要求調整。