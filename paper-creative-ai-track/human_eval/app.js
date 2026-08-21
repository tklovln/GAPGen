(() => {
  "use strict";

  const ROLES = {
    match: "基本配對元素（三消可清除）",
    h_power: "橫向清除道具",
    v_power: "直向清除道具",
    obstacle: "障礙／阻擋物（如紙箱）",
    unsure: "不確定",
  };

  const TRUE_ROLE = {
    Red: "match",
    Blu: "match",
    Yel: "match",
    Soda0d: "h_power",
    Soda90: "v_power",
    LtBl: "v_power",
    Crt4: "obstacle",
    Crt1: "obstacle",
  };

  const TASK1_ASSETS = ["Red", "Blu", "Soda0d", "Soda90", "Crt4", "Crt1", "Yel", "LtBl"];
  const CRATES = ["Crt4", "Crt3", "Crt2", "Crt1"];
  const GT_ORDER = ["Crt4", "Crt3", "Crt2", "Crt1"];

  const PREF_PAIRS = [
    { id: "overall", label: "整包美術", file: "all.png" },
    { id: "elements", label: "只看基本元素", file: "elements.png" },
    { id: "powerups", label: "只看道具", file: "powerups.png" },
    { id: "crate", label: "只看紙箱損毀階段", file: "crate.png" },
  ];

  // 前段暖身題（任務 1 之前）— 收集「可上架」判斷準則，不綁定特定美術包
  const EARLY_QS = [
    {
      id: "priority_ship",
      title: "上架優先順序",
      prompt: "若只能優化一項，你覺得對「可上架」最重要的是？",
      choices: [
        { id: "role_clarity", label: "功能一眼可辨（道具方向、障礙）" },
        { id: "style_cuteness", label: "畫風可愛／精緻" },
        { id: "theme_fit", label: "主題一致性（整包像同一世界）" },
        { id: "progression", label: "紙箱／階段變化清楚" },
      ],
    },
    {
      id: "board_size_confidence",
      title: "小尺寸判斷",
      prompt: "用約 70px（接近遊玩大小）判斷功能時，你有多有把握？",
      choices: [
        { id: "1", label: "1 · 很沒把握" },
        { id: "2", label: "2" },
        { id: "3", label: "3 · 普通" },
        { id: "4", label: "4" },
        { id: "5", label: "5 · 很有把握" },
      ],
    },
    {
      id: "auto_pass_risk",
      title: "自動通過的風險",
      prompt: "若系統把「看起來還行」的素材直接自動上架，你最擔心什麼？",
      choices: [
        { id: "misread_role", label: "玩家誤判功能（例如道具方向看錯）" },
        { id: "style_drift", label: "風格飄移、整包不統一" },
        { id: "theme_weak", label: "主題不夠明顯" },
        { id: "none", label: "不太擔心，之後再修即可" },
      ],
    },
    {
      id: "who_decides_preview",
      title: "誰決定可玩",
      prompt: "在你心裡，「看起來可玩」比較像是誰該拍板？",
      choices: [
        { id: "human_artist", label: "人類美術／企劃" },
        { id: "auto_critic", label: "自動評審規則" },
        { id: "both", label: "兩者都要：規則篩、人拍板" },
        { id: "players", label: "最終看玩家能不能看懂" },
      ],
    },
  ];

  const LIKERT = [
    { id: "enable", text: "這類系統能讓我比從頭手繪更快探索不同主題美術。" },
    { id: "steer", text: "自動品質規則會把美學方向帶得比我想要的還多。" },
    { id: "final_say", text: "若 borderline 素材會標成 needs_review，且必須由我手動套用，我會覺得自己握有最終決定權。" },
    { id: "trust_critic", text: "我會信任自動評審分數，足以略過逐張檢查每個 sprite。" },
    { id: "board", text: "用接近遊玩大小（約 70px）判斷素材，感覺和看大圖縮圖不一樣。" },
    { id: "friction", text: "當系統標示 needs_review、而不是直接自動上架時，這種摩擦是有用的（而不只是煩人）。" },
  ];

  const app = document.getElementById("app");
  const progressWrap = document.getElementById("progressWrap");
  const stepLabel = document.getElementById("stepLabel");
  const stepCount = document.getElementById("stepCount");
  const barFill = document.getElementById("barFill");

  const THEME_QUESTIONS = [
    {
      id: "best_shippable",
      title: "最想上架的主題",
      prompt: "若只能選一個主題做成可上架的三消遊戲，你選哪一個？",
      focus: "all",
    },
    {
      id: "clearest_powerups",
      title: "道具最清楚",
      prompt: "哪一個主題的「橫向／直向道具」最容易一眼看懂？",
      focus: "powerups",
    },
    {
      id: "clearest_crates",
      title: "紙箱階段最清楚",
      prompt: "哪一個主題的紙箱「完好 → 毀損」階段最清楚？",
      focus: "crate",
    },
    {
      id: "best_cohesion",
      title: "整包最統一",
      prompt: "哪一個主題的整包美術看起來最像「同一套」？",
      focus: "all",
    },
    {
      id: "clearest_elements",
      title: "基本元素最清楚",
      prompt: "哪一個主題的基本配對元素在小尺寸下最好辨認？",
      focus: "elements",
    },
  ];

  const state = {
    screen: "welcome",
    participantId: crypto.randomUUID(),
    startedAt: null,
    consent: false,
    packAIs: Math.random() < 0.5 ? "B1" : "B3",
    themes: [], // from themes.json
    ablationThemes: [],
    early: [],
    earlyIndex: 0,
    task1: [],
    task1Index: 0,
    task1Trials: [],
    task2: { A: [], B: [] },
    task2Pack: "A",
    task2Pool: [],
    task2Picked: [],
    task2Clearer: null,
    task3: [],
    task3Index: 0,
    prefTrials: [],
    task5: [],
    task5Index: 0,
    likert: {},
    likertIndex: 0,
    openNote: "",
  };

  function themeSteps() {
    return state.themes.length >= 2 ? 1 + THEME_QUESTIONS.length : 0;
  }

  function packCode(label) {
    return label === "A" ? state.packAIs : state.packAIs === "B1" ? "B3" : "B1";
  }

  function shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function themeBySlug(slug) {
    return state.themes.find((t) => t.slug === slug);
  }

  function hasCond(slug, cond) {
    const t = themeBySlug(slug);
    return !!(t && Array.isArray(t.conditions) && t.conditions.includes(cond));
  }

  function prefImg(slug, cond, file) {
    if (slug === "fruit") return `assets/grids/${cond}_${file}`;
    return `assets/themes/${slug}/${cond}/${file}`;
  }

  function buildTask1Trials() {
    const halfA = shuffle(TASK1_ASSETS).slice(0, 4);
    const halfB = TASK1_ASSETS.filter((x) => !halfA.includes(x));
    const trials = [
      ...halfA.map((asset) => ({ asset, packLabel: "A", pack: packCode("A") })),
      ...halfB.map((asset) => ({ asset, packLabel: "B", pack: packCode("B") })),
    ];
    return shuffle(trials);
  }

  function buildPrefTrials() {
    const out = [];
    const pushBlock = (slug, labelZh, c1, c2, focuses, prompt) => {
      focuses.forEach((f) => {
        const swap = Math.random() < 0.5;
        out.push({
          theme_slug: slug,
          theme_label: labelZh,
          compare: `${c1}_vs_${c2}`,
          cond_left: swap ? c2 : c1,
          cond_right: swap ? c1 : c2,
          focus_id: f.id,
          focus_label: f.label,
          file: f.file,
          prompt,
        });
      });
    };

    const all4 = PREF_PAIRS;
    const noCrate = PREF_PAIRS.filter((p) => p.id !== "crate");
    const overallPower = PREF_PAIRS.filter((p) => p.id === "overall" || p.id === "powerups");
    const overallOnly = PREF_PAIRS.filter((p) => p.id === "overall");

    if (hasCond("fruit", "B1") && hasCond("fruit", "B3")) {
      pushBlock("fruit", "水果", "B1", "B3", all4, "哪一包更適合作為可上架的水果主題三消美術？");
    }
    if (hasCond("fruit", "B1") && hasCond("fruit", "B2")) {
      pushBlock("fruit", "水果", "B1", "B2", noCrate, "同樣是水果主題：哪一包更清楚、更適合上架？");
    }
    if (hasCond("fruit", "B2") && hasCond("fruit", "B3")) {
      pushBlock("fruit", "水果", "B2", "B3", overallPower, "同樣是水果主題：哪一包更適合上架？");
    }

    ["pet", "ocean"].forEach((slug) => {
      const t = themeBySlug(slug);
      if (!t) return;
      const zh = t.label_zh || t.theme;
      if (hasCond(slug, "B1") && hasCond(slug, "B3")) {
        pushBlock(slug, zh, "B1", "B3", overallPower.concat(PREF_PAIRS.filter((p) => p.id === "crate")),
          `哪一包更適合作為可上架的${zh}主題三消美術？`);
      }
      if (hasCond(slug, "B1") && hasCond(slug, "B2")) {
        pushBlock(slug, zh, "B1", "B2", overallOnly,
          `同樣是${zh}主題：哪一包更清楚、更適合上架？`);
      }
    });

    // Fallback if themes.json old / missing fruit conditions
    if (!out.length) {
      pushBlock("fruit", "水果", "B1", "B3", all4, "哪一包更適合作為可上架的水果主題三消美術？");
    }
    return out;
  }

  function totalSteps() {
    const prefN = state.prefTrials.length || PREF_PAIRS.length;
    return (
      2 +
      EARLY_QS.length +
      1 +
      TASK1_ASSETS.length +
      2 +
      1 + // task2 clearer
      1 +
      prefN +
      themeSteps() +
      1 +
      LIKERT.length +
      1
    );
  }

  function currentStepIndex() {
    const s = state.screen;
    const earlyEnd = 2 + EARLY_QS.length;
    const t1 = earlyEnd + 1;
    const t2 = t1 + TASK1_ASSETS.length;
    const t2clear = t2 + 2;
    const t3 = t2clear + 1;
    const prefN = state.prefTrials.length || PREF_PAIRS.length;
    const t3end = t3 + prefN;
    const t5 = themeSteps();
    if (s === "welcome") return 0;
    if (s === "context") return 1;
    if (s === "early") return 2 + state.earlyIndex;
    if (s === "task1_intro") return earlyEnd;
    if (s === "task1") return t1 + state.task1Index;
    if (s === "task2_intro") return t2;
    if (s === "task2") return t2 + (state.task2Pack === "A" ? 0 : 1);
    if (s === "task2_clearer") return t2clear;
    if (s === "task3_intro") return t2clear;
    if (s === "task3") return t3 + state.task3Index;
    if (s === "task5_intro") return t3end;
    if (s === "task5") return t3end + 1 + state.task5Index;
    if (s === "agency_brief") return t3end + t5;
    if (s === "task4") return t3end + t5 + 1 + state.likertIndex;
    if (s === "done") return totalSteps() - 1;
    return 0;
  }

  function updateProgress() {
    const hide = state.screen === "welcome" || state.screen === "done";
    progressWrap.hidden = hide;
    if (hide) return;
    const idx = currentStepIndex();
    const total = totalSteps() - 1;
    const pct = Math.max(4, Math.round((idx / total) * 100));
    barFill.style.width = `${pct}%`;
    stepCount.textContent = `${idx} / ${total}`;
    const titles = {
      context: "背景說明",
      early: "暖身題",
      task1_intro: "任務 1",
      task1: "任務 1 · 功能辨識",
      task2_intro: "任務 2",
      task2: "任務 2 · 階段排序",
      task2_clearer: "任務 2 · 哪包更清楚",
      task3_intro: "任務 3",
      task3: "任務 3 · 美術包偏好",
      task5_intro: "任務 5",
      task5: "任務 5 · 多主題比較",
      agency_brief: "代理權說明",
      task4: "任務 4 · 代理權感受",
    };
    stepLabel.textContent = titles[state.screen] || "評測";
  }

  async function loadThemes() {
    try {
      const res = await fetch("themes.json", { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      state.themes = Array.isArray(data.themes) ? data.themes : [];
      state.ablationThemes = Array.isArray(data.ablation_compare_themes)
        ? data.ablation_compare_themes
        : [];
    } catch (_) {
      state.themes = [];
      state.ablationThemes = [];
    }
  }

  function afterTask3() {
    if (state.themes.length >= 2) {
      state.screen = "task5_intro";
    } else {
      state.screen = "agency_brief";
    }
    render();
  }

  function el(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function clear() {
    app.innerHTML = "";
    updateProgress();
  }

  function mount(node) {
    clear();
    app.appendChild(node);
  }

  function btn(label, className, onClick, disabled = false) {
    const b = document.createElement("button");
    b.className = className;
    b.textContent = label;
    b.disabled = disabled;
    b.addEventListener("click", onClick);
    return b;
  }

  function renderWelcome() {
    const root = el(`<div class="stack-lg"></div>`);
    root.append(
      el(`<div>
        <h1>誰決定「看起來可玩」？</h1>
        <p class="lead muted">這是一份關於 AI 輔助三消遊戲美術包的短評測。</p>
      </div>`),
      el(`<ul class="checklist">
        <li>約 20–30 分鐘</li>
        <li>任務含：暖身準則、功能辨識、損毀排序、多組 A/B 偏好（含水果／寵物／海洋條件比較）、多主題比較、代理權感受</li>
        <li>無需帳號；作答留在瀏覽器，結束時請下載檔案寄回</li>
      </ul>`),
    );
    const consentLabel = el(`<label class="choice">
      <input type="checkbox" id="consent" />
      <span>我已年滿 18 歲，同意參與。作答可能以去識別化方式用於研究摘要。</span>
    </label>`);
    root.appendChild(consentLabel);
    const actions = el(`<div class="actions"></div>`);
    const next = btn("開始", "btn-primary", async () => {
      const checked = consentLabel.querySelector("#consent").checked;
      if (!checked) return;
      next.disabled = true;
      next.textContent = "載入中…";
      await loadThemes();
      state.consent = true;
      state.startedAt = new Date().toISOString();
      state.task1Trials = buildTask1Trials();
      state.prefTrials = buildPrefTrials();
      state.screen = "context";
      render();
    }, true);
    consentLabel.querySelector("#consent").addEventListener("change", (e) => {
      next.disabled = !e.target.checked;
    });
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderContext() {
    const root = el(`<div class="stack-lg">
      <div>
        <h2>快速背景</h2>
        <p class="muted">接下來會先問幾題「你怎麼判斷可上架」，再評水果主題素材；後半也會看到寵物／海洋等主題。重點是「玩法是否看得懂」，不只是好不好看。</p>
      </div>
      <div class="brief">
        <div class="brief-item"><strong>基本元素</strong> — 有顏色的水果／物件，連成 3 個以上可消除。</div>
        <div class="brief-item"><strong>橫向／直向道具</strong> — 應清楚讀出會清一整列或一整行。</div>
        <div class="brief-item"><strong>紙箱</strong> — 阻擋物，有從完好到毀損的階段變化。</div>
      </div>
      <p class="hint">素材會以接近遊玩大小（約 70px）顯示。成對比較時只標示左側／右側，不標示條件名稱。</p>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("先回答暖身題", "btn-primary", () => {
      state.earlyIndex = 0;
      state.screen = "early";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function renderEarly() {
    const q = EARLY_QS[state.earlyIndex];
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>暖身 · ${q.title}</h2>
      <p class="lead">${q.prompt}</p>
      <p class="muted">第 ${state.earlyIndex + 1} / ${EARLY_QS.length} 題（尚無圖片）</p>
    </div>`));

    const list = el(`<div class="choice-list"></div>`);
    let selected = null;
    q.choices.forEach((c) => {
      const row = el(`<label class="choice"><input type="radio" name="early" value="${c.id}" /><span>${c.label}</span></label>`);
      row.addEventListener("click", () => {
        list.querySelectorAll(".choice").forEach((x) => x.classList.remove("selected"));
        row.classList.add("selected");
        selected = c.id;
        next.disabled = false;
      });
      list.appendChild(row);
    });
    root.appendChild(list);

    const actions = el(`<div class="actions"></div>`);
    const next = btn("下一題", "btn-primary", () => {
      if (!selected) return;
      state.early.push({
        question_id: q.id,
        question: q.prompt,
        choice: selected,
        choice_label: (q.choices.find((c) => c.id === selected) || {}).label || selected,
      });
      if (state.earlyIndex + 1 >= EARLY_QS.length) {
        state.screen = "task1_intro";
      } else {
        state.earlyIndex += 1;
      }
      render();
    }, true);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderTask1Intro() {
    const root = el(`<div class="stack-lg">
      <div>
        <h2>任務 1 · 功能辨識</h2>
        <p>你會連續看到 8 張小尺寸 sprite，請選擇它在遊戲中的功能角色。</p>
      </div>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("開始任務 1", "btn-primary", () => {
      state.task1Index = 0;
      state.screen = "task1";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function renderTask1() {
    const trial = state.task1Trials[state.task1Index];
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>這個素材的功能是？</h2>
      <p class="muted">第 ${state.task1Index + 1} / ${state.task1Trials.length} 題 · 美術包 ${trial.packLabel}</p>
    </div>`));
    root.append(el(`<div class="sprite-stage">
      <img src="assets/${trial.pack}/${trial.asset}.png" alt="遊玩尺寸素材" width="70" height="70" />
    </div>`));

    const list = el(`<div class="choice-list"></div>`);
    let selected = null;
    Object.entries(ROLES).forEach(([key, label]) => {
      const row = el(`<label class="choice"><input type="radio" name="role" value="${key}" /><span>${label}</span></label>`);
      row.addEventListener("click", () => {
        list.querySelectorAll(".choice").forEach((c) => c.classList.remove("selected"));
        row.classList.add("selected");
        selected = key;
        next.disabled = false;
      });
      list.appendChild(row);
    });
    root.appendChild(list);

    const actions = el(`<div class="actions"></div>`);
    const next = btn("下一題", "btn-primary", () => {
      if (!selected) return;
      state.task1.push({
        trial: state.task1Index + 1,
        asset: trial.asset,
        pack_label: trial.packLabel,
        pack: trial.pack,
        true_role: TRUE_ROLE[trial.asset],
        choice: selected,
        correct: selected === TRUE_ROLE[trial.asset],
      });
      if (state.task1Index + 1 >= state.task1Trials.length) {
        state.screen = "task2_intro";
      } else {
        state.task1Index += 1;
      }
      render();
    }, true);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderTask2Intro() {
    const root = el(`<div class="stack-lg">
      <div>
        <h2>任務 2 · 階段排序</h2>
        <p>請把紙箱素材排成：<strong>最完好 → 最毀損</strong>。</p>
        <p class="muted">會做兩次：美術包 A 與美術包 B。依序點選圖塊即可。</p>
      </div>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("先從美術包 A 開始", "btn-primary", () => {
      state.task2Pack = "A";
      state.task2Picked = [];
      state.task2Pool = shuffle([...CRATES]);
      state.screen = "task2";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function kendallTau(order) {
    let conc = 0;
    let disc = 0;
    const rank = Object.fromEntries(GT_ORDER.map((n, i) => [n, i]));
    for (let i = 0; i < order.length; i++) {
      for (let j = i + 1; j < order.length; j++) {
        const s = Math.sign(rank[order[i]] - rank[order[j]]);
        if (s < 0) conc += 1;
        else if (s > 0) disc += 1;
      }
    }
    const n = order.length;
    const denom = (n * (n - 1)) / 2;
    return denom ? (conc - disc) / denom : 1;
  }

  function renderTask2() {
    const pack = packCode(state.task2Pack);
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>最完好 → 最毀損</h2>
      <p class="muted">美術包 ${state.task2Pack} · 依序點選下一張（${state.task2Picked.length}/4）</p>
    </div>`));

    const board = el(`<div class="order-board"></div>`);
    for (let i = 0; i < 4; i++) {
      const row = el(`<div class="order-row"><div class="rank">${i + 1}</div><div class="hint">${state.task2Picked[i] ? "已選" : "—"}</div></div>`);
      if (state.task2Picked[i]) {
        const img = document.createElement("img");
        img.src = `assets/${pack}/${state.task2Picked[i]}.png`;
        img.width = 56;
        img.height = 56;
        img.alt = state.task2Picked[i];
        row.children[1].textContent = "";
        row.children[1].appendChild(img);
      }
      board.appendChild(row);
    }
    root.appendChild(board);

    const opts = el(`<div class="crate-options"></div>`);
    state.task2Pool.forEach((name) => {
      const used = state.task2Picked.includes(name);
      const b = document.createElement("button");
      b.type = "button";
      b.disabled = used;
      b.innerHTML = `<img src="assets/${pack}/${name}.png" alt="${name}" /><span class="hint">圖塊</span>`;
      b.addEventListener("click", () => {
        if (state.task2Picked.length >= 4) return;
        state.task2Picked.push(name);
        render();
      });
      opts.appendChild(b);
    });
    root.appendChild(opts);

    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("復原", "btn-secondary", () => {
      state.task2Picked.pop();
      render();
    }, state.task2Picked.length === 0));
    actions.appendChild(btn("確認排序", "btn-primary", () => {
      if (state.task2Picked.length !== 4) return;
      const rec = {
        pack_label: state.task2Pack,
        pack,
        order: [...state.task2Picked],
        kendall_tau: Number(kendallTau(state.task2Picked).toFixed(3)),
      };
      state.task2[state.task2Pack] = rec;
      if (state.task2Pack === "A") {
        state.task2Pack = "B";
        state.task2Picked = [];
        state.task2Pool = shuffle([...CRATES]);
        render();
      } else {
        state.screen = "task2_clearer";
        render();
      }
    }, state.task2Picked.length !== 4));
    root.appendChild(actions);
    mount(root);
  }

  function renderTask2Clearer() {
    const root = el(`<div class="stack-lg">
      <div>
        <h2>任務 2 補充</h2>
        <p class="lead">剛做完兩包紙箱排序：整體來說，哪一包的「完好 → 毀損」階段比較清楚？</p>
      </div>
    </div>`);
    const list = el(`<div class="choice-list"></div>`);
    let selected = null;
    [
      { id: "A", label: "美術包 A 比較清楚" },
      { id: "B", label: "美術包 B 比較清楚" },
      { id: "tie", label: "差不多／很難說" },
    ].forEach((c) => {
      const row = el(`<label class="choice"><input type="radio" name="clearer" value="${c.id}" /><span>${c.label}</span></label>`);
      row.addEventListener("click", () => {
        list.querySelectorAll(".choice").forEach((x) => x.classList.remove("selected"));
        row.classList.add("selected");
        selected = c.id;
        next.disabled = false;
      });
      list.appendChild(row);
    });
    root.appendChild(list);
    const actions = el(`<div class="actions"></div>`);
    const next = btn("繼續任務 3", "btn-primary", () => {
      if (!selected) return;
      state.task2Clearer = {
        choice_label: selected,
        choice_pack: selected === "tie" ? null : packCode(selected),
      };
      state.screen = "task3_intro";
      render();
    }, true);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderTask3Intro() {
    const n = state.prefTrials.length;
    const root = el(`<div class="stack-lg">
      <div>
        <h2>任務 3 · 美術包偏好</h2>
        <p>會連續比較多組「左側／右側」美術包（含水果，以及已備妥的寵物／海洋條件）。</p>
        <p class="muted">共 ${n} 組；焦點可能是整包、元素、道具或紙箱。請選你覺得更適合上架的那一側。</p>
      </div>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("開始任務 3", "btn-primary", () => {
      state.task3Index = 0;
      state.screen = "task3";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function renderTask3() {
    const trial = state.prefTrials[state.task3Index];
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>${trial.theme_label} · ${trial.focus_label}</h2>
      <p class="lead">${trial.prompt}</p>
      <p class="muted">第 ${state.task3Index + 1} / ${state.prefTrials.length} 組 · 點選偏好的一側</p>
    </div>`));

    const pairEl = el(`<div class="pair"></div>`);
    let selectedSide = null;
    [
      { side: "left", cond: trial.cond_left, label: "左側" },
      { side: "right", cond: trial.cond_right, label: "右側" },
    ].forEach(({ side, cond, label }) => {
      const card = el(`<button type="button" class="pack-card">
        <strong>${label}</strong>
        <img src="${prefImg(trial.theme_slug, cond, trial.file)}" alt="${label}" />
      </button>`);
      card.addEventListener("click", () => {
        pairEl.querySelectorAll(".pack-card").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        selectedSide = side;
        next.disabled = false;
      });
      pairEl.appendChild(card);
    });
    root.appendChild(pairEl);

    const actions = el(`<div class="actions"></div>`);
    const next = btn("下一組", "btn-primary", () => {
      if (!selectedSide) return;
      const winnerCond = selectedSide === "left" ? trial.cond_left : trial.cond_right;
      state.task3.push({
        pair_id: `${trial.theme_slug}_${trial.compare}_${trial.focus_id}`,
        theme_slug: trial.theme_slug,
        theme_label: trial.theme_label,
        compare: trial.compare,
        focus_id: trial.focus_id,
        focus_label: trial.focus_label,
        winner_side: selectedSide,
        winner_pack: winnerCond,
        left_pack: trial.cond_left,
        right_pack: trial.cond_right,
      });
      if (state.task3Index + 1 >= state.prefTrials.length) {
        afterTask3();
      } else {
        state.task3Index += 1;
        render();
      }
    }, true);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderTask5Intro() {
    const names = state.themes.map((t) => t.label_zh || t.theme).join("、");
    const root = el(`<div class="stack-lg">
      <div>
        <h2>任務 5 · 多主題比較</h2>
        <p>接下來會看到多個不同主題的美術包（同一套玩法角色）。</p>
        <p class="muted">目前主題：${names}</p>
      </div>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("開始任務 5", "btn-primary", () => {
      state.task5Index = 0;
      state.screen = "task5";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function renderTask5() {
    const q = THEME_QUESTIONS[state.task5Index];
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>${q.title}</h2>
      <p class="lead">${q.prompt}</p>
      <p class="muted">第 ${state.task5Index + 1} / ${THEME_QUESTIONS.length} 題</p>
    </div>`));

    const grid = el(`<div class="pair" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));"></div>`);
    let selected = null;
    const shuffled = shuffle(state.themes);
    shuffled.forEach((t) => {
      const file = q.focus === "all" ? "all.png" : `${q.focus}.png`;
      const card = el(`<button type="button" class="pack-card">
        <strong>${t.label_zh || t.theme}</strong>
        <span class="hint">${t.style_label || ""}</span>
        <img src="assets/themes/${t.slug}/${file}" alt="${t.label_zh || t.theme}" />
      </button>`);
      card.addEventListener("click", () => {
        grid.querySelectorAll(".pack-card").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        selected = t.slug;
        next.disabled = false;
      });
      grid.appendChild(card);
    });
    root.appendChild(grid);

    const actions = el(`<div class="actions"></div>`);
    const next = btn("下一題", "btn-primary", () => {
      if (!selected) return;
      const chosen = state.themes.find((t) => t.slug === selected);
      state.task5.push({
        question_id: q.id,
        question: q.prompt,
        focus: q.focus,
        winner_slug: selected,
        winner_theme: chosen ? chosen.theme : selected,
        winner_label_zh: chosen ? chosen.label_zh : selected,
        options: state.themes.map((t) => t.slug),
      });
      if (state.task5Index + 1 >= THEME_QUESTIONS.length) {
        state.screen = "agency_brief";
      } else {
        state.task5Index += 1;
      }
      render();
    }, true);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function renderAgencyBrief() {
    const root = el(`<div class="stack-lg">
      <div>
        <h2>進入最後幾題之前</h2>
        <p class="muted">請想像這款遊戲的 AI 美術管線，有以下人類把關：</p>
      </div>
      <div class="brief">
        <div class="brief-item"><strong>暫存區（Staging）</strong> — 新美術先進入審核資料夾，不會直接進正式版。</div>
        <div class="brief-item"><strong>needs_review</strong> — 邊緣案例會被標記，而不是自動通過。</div>
        <div class="brief-item"><strong>套用／還原</strong> — 必須由人明確把美術套進可玩盤面（也可還原）。</div>
      </div>
      <p>請帶著這個流程，回答接下來的同意程度題。</p>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("繼續任務 4", "btn-primary", () => {
      state.likertIndex = 0;
      state.screen = "task4";
      render();
    }));
    root.appendChild(actions);
    mount(root);
  }

  function renderTask4() {
    const item = LIKERT[state.likertIndex];
    const root = el(`<div class="stack-lg"></div>`);
    root.append(el(`<div>
      <h2>任務 4 · 代理權感受</h2>
      <p class="muted">第 ${state.likertIndex + 1} / ${LIKERT.length} 題</p>
      <p class="lead">${item.text}</p>
    </div>`));

    const box = el(`<div class="likert"></div>`);
    box.append(el(`<div class="scale-ends"><span>非常不同意</span><span>非常同意</span></div>`));
    const scale = el(`<div class="likert-scale"></div>`);
    let selected = state.likert[item.id] || null;
    for (let v = 1; v <= 7; v++) {
      const lab = el(`<label><input type="radio" name="likert" value="${v}" ${selected === v ? "checked" : ""}/>${v}</label>`);
      lab.addEventListener("click", () => {
        selected = v;
        next.disabled = false;
      });
      scale.appendChild(lab);
    }
    box.appendChild(scale);
    root.appendChild(box);

    let noteArea = null;
    if (state.likertIndex === LIKERT.length - 1) {
      noteArea = el(`<div class="stack">
        <label class="muted" for="openNote">選填：在上面的任務裡，你覺得是誰在決定「看起來可玩」？</label>
        <textarea id="openNote" placeholder="一兩句即可">${state.openNote}</textarea>
      </div>`);
      root.appendChild(noteArea);
    }

    const actions = el(`<div class="actions"></div>`);
    const next = btn(state.likertIndex + 1 >= LIKERT.length ? "完成" : "下一題", "btn-primary", () => {
      if (!selected) return;
      state.likert[item.id] = selected;
      if (noteArea) state.openNote = noteArea.querySelector("textarea").value.trim();
      if (state.likertIndex + 1 >= LIKERT.length) {
        state.screen = "done";
      } else {
        state.likertIndex += 1;
      }
      render();
    }, !selected);
    actions.appendChild(next);
    root.appendChild(actions);
    mount(root);
  }

  function buildResult() {
    const task1Acc = state.task1.length
      ? state.task1.filter((t) => t.correct).length / state.task1.length
      : null;
    const fruitB1B3 = state.task3.filter((p) => p.theme_slug === "fruit" && p.compare === "B1_vs_B3");
    const b3Wins = fruitB1B3.filter((p) => p.winner_pack === "B3").length;
    return {
      schema: "match3-human-eval-v2",
      locale: "zh-Hant",
      participant_id: state.participantId,
      started_at: state.startedAt,
      finished_at: new Date().toISOString(),
      pack_a_is: state.packAIs,
      pack_b_is: state.packAIs === "B1" ? "B3" : "B1",
      early: state.early,
      task1: state.task1,
      task1_accuracy: task1Acc,
      task2: state.task2,
      task2_clearer: state.task2Clearer,
      task3: state.task3,
      task3_fruit_b1b3_b3_win_rate: fruitB1B3.length ? b3Wins / fruitB1B3.length : null,
      task5_multi_theme: state.task5,
      themes_available: state.themes.map((t) => t.slug),
      theme_conditions: Object.fromEntries(
        state.themes.map((t) => [t.slug, t.conditions || [t.condition].filter(Boolean)]),
      ),
      likert: state.likert,
      open_note: state.openNote,
      user_agent: navigator.userAgent,
    };
  }

  function toCsv(result) {
    const lines = [];
    lines.push("section,key,value");
    lines.push(`meta,participant_id,${result.participant_id}`);
    lines.push(`meta,pack_a_is,${result.pack_a_is}`);
    lines.push(`meta,pack_b_is,${result.pack_b_is}`);
    lines.push(`meta,task1_accuracy,${result.task1_accuracy}`);
    lines.push(`meta,task3_fruit_b1b3_b3_win_rate,${result.task3_fruit_b1b3_b3_win_rate}`);
    (result.early || []).forEach((e) => {
      lines.push(`early,${e.question_id},${e.choice}`);
    });
    result.task1.forEach((t) => {
      lines.push(`task1,${t.trial},${t.asset}|${t.pack}|${t.true_role}|${t.choice}|${t.correct}`);
    });
    ["A", "B"].forEach((k) => {
      const t = result.task2[k];
      if (t) lines.push(`task2,${k},${t.pack}|${t.order.join(">")}|${t.kendall_tau}`);
    });
    if (result.task2_clearer) {
      lines.push(`task2_clearer,choice,${result.task2_clearer.choice_label}|${result.task2_clearer.choice_pack}`);
    }
    result.task3.forEach((p) => {
      lines.push(`task3,${p.pair_id},${p.winner_pack}|${p.theme_slug}|${p.compare}|${p.focus_id}`);
    });
    (result.task5_multi_theme || []).forEach((p) => {
      lines.push(`task5,${p.question_id},${p.winner_slug}|${p.winner_theme}`);
    });
    Object.entries(result.likert).forEach(([k, v]) => lines.push(`likert,${k},${v}`));
    if (result.open_note) lines.push(`note,open,"${result.open_note.replaceAll('"', "'")}"`);
    return lines.join("\n");
  }

  function download(filename, text, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function renderDone() {
    const result = buildResult();
    localStorage.setItem(`human_eval_${result.participant_id}`, JSON.stringify(result));
    const root = el(`<div class="stack-lg">
      <div>
        <h1>謝謝你</h1>
        <p class="lead muted">作答已可下載。請把檔案寄給研究主持人。</p>
      </div>
      <div class="done-box">
        <p><strong>參與者 ID</strong><br/><code>${result.participant_id}</code></p>
        <p class="hint">A／B 與真實條件的對應已寫在檔案內，你不需記。</p>
      </div>
    </div>`);
    const actions = el(`<div class="actions"></div>`);
    actions.appendChild(btn("下載 JSON", "btn-primary", () => {
      download(`human_eval_${result.participant_id}.json`, JSON.stringify(result, null, 2), "application/json");
    }));
    actions.appendChild(btn("下載 CSV", "btn-secondary", () => {
      download(`human_eval_${result.participant_id}.csv`, toCsv(result), "text/csv");
    }));
    actions.appendChild(btn("複製參與者 ID", "btn-secondary", async () => {
      try {
        await navigator.clipboard.writeText(result.participant_id);
      } catch (_) {
        /* ignore */
      }
    }));
    root.appendChild(actions);
    mount(root);
  }

  function render() {
    const map = {
      welcome: renderWelcome,
      context: renderContext,
      early: renderEarly,
      task1_intro: renderTask1Intro,
      task1: renderTask1,
      task2_intro: renderTask2Intro,
      task2: renderTask2,
      task2_clearer: renderTask2Clearer,
      task3_intro: renderTask3Intro,
      task3: renderTask3,
      task5_intro: renderTask5Intro,
      task5: renderTask5,
      agency_brief: renderAgencyBrief,
      task4: renderTask4,
      done: renderDone,
    };
    (map[state.screen] || renderWelcome)();
  }

  render();
})();
