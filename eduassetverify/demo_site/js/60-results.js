/* ==================================================================== results dashboard */
const RS = { bk: "C", metric: "accuracy", fam: "d" };
const MAINN = { clip: "CLIPScore", direct: "Direct judge", cot: "CoT judge", structured: "Structured judge", rule_only: "Rule-only validator",
  eav: "EduAssetVerify", extracted: "EduAssetVerify, parsed constraints" };
const KEYOF = { d: "direct", c: "cot", s: "structured", e: "eav" };
const barCls = k => k === "eav" || k === "extracted" || k === "e" ? "ours" : k === "rule_only" ? "rule" : k === "clip" ? "clip" : "";
function brow(name, w, val, k, sub, cls) {
  return `<div class="brow${cls ? " " + cls : ""}"><span class="nm${barCls(k) === "ours" ? " ours" : ""}">${esc(name)}</span><span class="tr"><i class="${barCls(k)}" data-w="${clamp(w, 0, 1) * 100}%"></i></span>` +
    `<span class="val">${val}${sub ? ` <small>${sub}</small>` : ""}</span></div>`;
}
function grow(root) { requestAnimationFrame(() => requestAnimationFrame(() => $$(".tr i[data-w]", root).forEach(i => { i.style.width = i.getAttribute("data-w"); }))); }
function resultsInit() {
  const host = $("#results-app");
  host.innerHTML =
    `<div class="dash-top"><div class="ctl"><span class="lab">Backbone</span>${seg("rs-bk", BKS.map(b => [b, BKN[b]]), RS.bk)}</div>` +
    `<span class="small muted">Standard deviation over passes: at most ${R.max_sd} points in the paper's Table I.</span></div>` +
    `<div class="dash">` +
    `<div class="card span-7 reveal" id="rs-fa"></div><div class="card span-5 reveal" id="rs-main"></div>` +
    `<div class="card span-12 reveal" id="rs-ops"></div>` +
    `<div class="card span-6 reveal" id="rs-task"></div><div class="card span-6 reveal" id="rs-cond"></div>` +
    `<div class="card span-6 reveal" id="rs-abl"></div><div class="card span-6 reveal" id="rs-cost"></div>` +
    `<div class="card span-12 reveal" id="rs-loc"></div></div>`;
  onSeg("rs-bk", v => { RS.bk = v; resultsRender(); });
  resultsRender();
  $$(".dash > .card", host).forEach(c => onVisible(c, () => grow(c)));
  rsOps();
}
function resultsRender() {
  rsFA(); rsMain(); rsTask(); rsCond(); rsAbl(); rsCost(); rsLoc();
  $$("#results-app .dash > .card.in").forEach(grow);
}
function rsFA() {
  const bk = RS.bk, fa = R.fa[bk], n = R.n_violated_evals;
  const max = Math.max(10, ...BKS.map(b => Math.max(...Object.values(R.fa[b]))));
  const rows = [["direct", "Direct judge"], ["cot", "CoT judge"], ["structured", "Structured judge"], ["rule_only", "Rule-only validator"], ["eav", "EduAssetVerify"]]
    .map(([k, nm]) => brow(nm, fa[k] / max, fa[k] === 0 ? `<span class="zero-badge">${icon("check")} 0</span>` : fa[k], k, `/ ${fmtInt(n)}`)).join("");
  const box = $("#rs-fa");
  box.innerHTML = `<h3>False acceptances</h3><p class="sub">Violated test evaluations judged valid (450 violated assets \u00d7 3 passes), ${esc(BKN[bk])}.</p>` +
    `<div class="bars">${rows}</div>` +
    `<div class="ctl" style="margin-top:14px"><span class="lab">One dot per evaluation</span>${seg("rs-fam", METH.map(m => [m[0], m[1]]), RS.fam)}</div>` +
    `<div class="dotm" id="rs-dots"></div><p class="small muted" style="margin:0">Red: accepted although violated. Ordered by task (fraction, counting, spatial), then template; hover a red dot, select it to open the asset.</p>`;
  onSeg("rs-fam", v => { RS.fam = v; rsDots(); });
  rsDots();
  const dots = $("#rs-dots");
  dots.addEventListener("mousemove", e => {
    const d = e.target.closest("i[data-i]");
    if (!d || !d.classList.contains("fa")) { hideTip(); return; }
    const it = BYID[d.getAttribute("data-i")];
    showTip(av(it, { bk: RS.bk, w: 0, g: 1, badge: 1, px: 220 }) + `<p>${esc(it.o)}</p><p>${MNAME[RS.fam]}: ${passes(it.v[RS.bk][RS.fam], it.y)}</p>`, e.clientX, e.clientY);
  });
  dots.addEventListener("mouseleave", hideTip);
  dots.addEventListener("click", e => { const d = e.target.closest("i.fa[data-i]"); if (d) { hideTip(); openModal(d.getAttribute("data-i"), RS.bk); } });
}
function rsDots() {
  const bk = RS.bk, f = RS.fam;
  let h = "";
  D.items.forEach(it => { if (it.y !== "I") return; for (let p = 0; p < 3; p++) h += `<i data-i="${it.i}"${it.v[bk][f][p] === "V" ? ' class="fa"' : ""}></i>`; });
  $("#rs-dots").innerHTML = h;
}
function rsMain() {
  const bk = RS.bk, m = RS.metric;
  const rows = Object.keys(R.main).map(k => [k, R.main[k][bk][m]]);
  const acc = m === "accuracy";
  const max = acc ? 1 : Math.max(0.02, ...rows.filter(r => r[0] !== "clip").map(r => r[1][0]));
  const lo = acc ? 0.5 : 0;
  $("#rs-main").innerHTML = `<h3>Detection (the paper's Table I)</h3><p class="sub">${esc(BKN[bk])}; ${acc ? "bars start at 50%; abstentions count as errors" : "bars scaled to the largest value apart from CLIPScore"}.</p>` +
    `<div class="table-tabs">${seg("rs-metric", [["accuracy", "Accuracy"], ["far", "FAR"], ["frr", "FRR"], ["abstention", "Abstention"]], m)}</div>` +
    `<div class="bars">${rows.map(([k, v]) => brow(MAINN[k], (v[0] - lo) / (max - lo), v[1] + "%", k, k === "clip" && !acc && v[0] > max ? "off scale" : "")).join("")}</div>` +
    `<p class="small muted" style="margin:8px 0 0">CLIPScore uses no backbone. Parsed constraints: the parser's constraint sets instead of the gold ones.</p>`;
  onSeg("rs-metric", v => { RS.metric = v; rsMain(); grow($("#rs-main")); });
}
function heatColor(t) {
  const stops = [[0, [248, 247, 242]], [0.3, [244, 155, 171]], [0.62, [225, 105, 129]], [1, [213, 0, 0]]];
  t = clamp(t, 0, 1);
  for (let i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    const [a, ca] = stops[i - 1], [b, cb] = stops[i], u = (t - a) / (b - a);
    return `rgb(${ca.map((c, j) => Math.round(c + (cb[j] - c) * u)).join(",")})`;
  }
  return "rgb(213,0,0)";
}
function rsOps() {
  const kinds = [["direct", "Direct"], ["cot", "CoT"], ["structured", "Structured"], ["eav", "Ours"]];
  const vmax = Math.max(...R.ops.flatMap(o => PAPER.flatMap(b => kinds.map(k => o[3][b][k[0]][0]))));
  let task = "", rows = "";
  R.ops.forEach(o => {
    if (o[2] !== task) { task = o[2]; rows += `<tr><td class="task" colspan="9">${esc(task)}</td></tr>`; }
    rows += `<tr><td class="nm">${esc(o[1])}</td>` + PAPER.map(b => kinds.map(k => {
      const c = o[3][b][k[0]], t = c[0] / vmax;
      return `<td class="${k[0] === "eav" ? "ours" : ""}" style="background:${heatColor(t)};color:${t > 0.5 ? "#fff" : "var(--ink)"}" title="${c[2]} of ${c[3]} evaluations">${c[1]}</td>`;
    }).join("")).join("") + `</tr>`;
  });
  $("#rs-ops").innerHTML = `<h3>False acceptance by error type (%)</h3><p class="sub">The judges miss errors that are measured quantities: unequal partitions, part counts,
    broken symmetries. Of the ${R.errors.fa_judges_both_backbones} false acceptances of all judges under both backbones, ${R.errors.fa_measured_operators_only} involve only
    part counts, colored counts, unequal partitions, or broken symmetries. Hover a cell for the counts.</p>` +
    `<div style="overflow-x:auto"><table class="heat"><tr><th></th>${PAPER.map(b => `<th class="grp" colspan="4">${esc(BKN[b])}</th>`).join("")}</tr>` +
    `<tr><th></th>${PAPER.map(() => kinds.map(k => `<th>${k[1]}</th>`).join("")).join("")}</tr>${rows}</table></div>`;
}
function rsTask() {
  const bk = RS.bk, T = R.domain[bk];
  const ks = [["direct", "Direct judge"], ["cot", "CoT judge"], ["structured", "Structured judge"], ["rule_only", "Rule-only validator"], ["eav", "EduAssetVerify"]];
  const max = Math.max(0.01, ...BKS.flatMap(b => ks.flatMap(k => ["fraction", "counting", "spatial"].map(d => R.domain[b][k[0]][d][0]))));
  $("#rs-task").innerHTML = `<h3>False acceptance by task</h3><p class="sub">${esc(BKN[bk])}; same scale for both backbones.</p>` +
    ["fraction", "counting", "spatial"].map(d => `<div class="sect" style="margin-top:8px">${TASKN[d]}</div><div class="bars">` +
      ks.map(k => brow(k[1], T[k[0]][d][0] / max, T[k[0]][d][1] + "%", k[0])).join("") + `</div>`).join("");
}
function rsCond() {
  const bk = RS.bk, lo = 0.8;
  const pos = v => clamp((v - lo) / (1 - lo), 0, 1) * 100;
  $("#rs-cond").innerHTML = `<h3>Pair accuracy by test condition</h3><p class="sub">Pairs with the correct image judged valid and the violated one invalid; abstentions count as errors (${esc(BKN[bk])}).</p>` +
    `<div class="legend" style="margin:0 0 8px">${METH.map(m => `<span><i class="dp ${m[0]}" style="position:static;display:inline-block;margin:0 5px 0 0;vertical-align:-2px"></i>${m[1]}</span>`).join("")}</div>` +
    `<div class="dotplot">${R.conditions.map(c => `<div class="dp-row"><span>${esc(c[1])}</span><div class="dp-track">` +
      METH.map(m => { const v = c[2][bk][KEYOF[m[0]]]; return `<i class="dp ${m[0]}" style="left:${pos(v[0])}%" title="${m[1]}: ${v[1]}%"></i>`; }).join("") + `</div></div>`).join("")}</div>` +
    `<div class="dp-axis"><span>80%</span><span>90%</span><span>100%</span></div>` +
    `<p class="small muted" style="margin:8px 0 0">Style invariance: unseen-style images whose verdict matches the same scene in its base style.</p>`;
}
function rsAbl() {
  const bk = RS.bk;
  const max = Math.max(0.01, ...R.ablation.flatMap(a => BKS.flatMap(b => ["far", "frr", "abstention"].map(m => a[2][b][m][0]))));
  $("#rs-abl").innerHTML = `<h3>Component ablation (the paper's Table II)</h3><p class="sub">${esc(BKN[bk])}. Variants reuse the full method's readings; without the rule
    engine, the VLM decides from the same evidence.</p>` +
    `<div class="abl"><div class="ah"><span></span><span>FAR</span><span>FRR</span><span>Abstention</span></div>` +
    R.ablation.map(a => `<div class="ar"><span class="nm${a[0] === "eav" ? " ours" : ""}">${esc(a[1])}</span>` +
      [["far", "pink"], ["frr", ""], ["abstention", "rule"]].map(m => {
        const v = a[2][bk][m[0]];
        return `<span class="tr mb"><i class="${a[0] === "eav" ? "ours" : m[1]}" data-w="${v[0] / max * 100}%"></i><b>${v[1]}%</b></span>`;
      }).join("") + `</div>`).join("") + `</div>` +
    `<p class="small muted" style="margin:10px 0 0">Measurement matters most. The semantic verifier shows no measurable benefit, and abstention prevents no false
      acceptance: it turns false rejections into reviews.</p>`;
}
function rsCost() {
  const bk = RS.bk, C = R.cost[bk];
  const ks = [["direct", "Direct judge"], ["cot", "CoT judge"], ["structured", "Structured judge"], ["rule_only", "Rule-only validator"], ["eav", "EduAssetVerify"]];
  const max = Math.max(...BKS.flatMap(b => ks.map(k => R.cost[b][k[0]].usd)));
  const r = R.cost_ratio[bk];
  $("#rs-cost").innerHTML = `<h3>Cost</h3><p class="sub">US dollars per 1,000 assets at assumed token rates, and VLM calls per asset (${esc(BKN[bk])}).</p>` +
    `<div class="bars">${ks.map(k => brow(k[1], C[k[0]].usd / max, "$" + C[k[0]].usd.toFixed(2), k[0], `${C[k[0]].calls} call${C[k[0]].calls === 1 ? "" : "s"}`, "wide")).join("")}</div>` +
    `<div class="callout purple">EduAssetVerify costs <b>${r[0]}\u2013${r[1]}\u00d7</b> a judge here: three value-blind readings, and re-readings for labels and categories.
    Summed latency ${C.eav.lat} s per asset, against ${Math.min(...["direct", "cot", "structured"].map(k => C[k].lat))}\u2013${Math.max(...["direct", "cot", "structured"].map(k => C[k].lat))} s for a judge.</div>`;
}
function donut(v, label, cls) {
  const r = 46, c = 2 * Math.PI * r;
  return `<div class="donut"><svg viewBox="0 0 108 108"><circle class="bgc" cx="54" cy="54" r="${r}"/>` +
    `<circle class="fgc ${cls || ""}" cx="54" cy="54" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}" data-off="${c * (1 - clamp(v[0], 0, 1))}"/>` +
    `<text x="54" y="54">${v[1]}%</text></svg><p>${label}</p></div>`;
}
function rsLoc() {
  const box = $("#rs-loc");
  box.innerHTML = `<h3>Reports, witnesses, and parsing</h3><p class="sub">Over correct rejections of localizable errors, and over the parser's runs on all objectives.</p>` +
    `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px">` + PAPER.map(b => `<div><div class="sect" style="margin-top:0">${esc(BKN[b])}</div><div class="donuts">` +
      donut(R.loc[b].type, "the reported violation is a perturbed constraint") + donut(R.loc[b].witness, "the witness hits the perturbed region", "lil") +
      donut(R.parse[b].exact, "the parser reproduces the gold constraint set", "rose") + donut(R.parse[b].detected, "contradictory objectives rejected by the consistency check", "rose") +
      `</div></div>`).join("") + `</div>` +
    `<p class="small muted" style="margin:8px 0 0">Witness misses come from symmetry, where the moved element and its partner are indistinguishable, and from text boxes smaller than the ground truth.</p>`;
  onVisible(box, () => requestAnimationFrame(() => requestAnimationFrame(() => $$(".fgc", box).forEach(c => { c.style.strokeDashoffset = c.getAttribute("data-off"); }))));
  if (box.classList.contains("in")) $$(".fgc", box).forEach(c => { c.style.strokeDashoffset = c.getAttribute("data-off"); });
}
