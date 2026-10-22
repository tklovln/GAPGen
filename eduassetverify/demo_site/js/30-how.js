/* ==================================================================== how it works: the Fig. 1 asset through every module */
const STEPS = [
  { key: "parse", kind: "model", name: "Constraint parser" },
  { key: "check", kind: "det", name: "Consistency check" },
  { key: "ground", kind: "model", name: "Value-blind grounding \u00d73" },
  { key: "measure", kind: "det", name: "Measurement" },
  { key: "rules", kind: "det", name: "Three-valued rules" },
  { key: "verdict", kind: "io", name: "Verdict and report" },
];
const KIND = { model: ["model", "queries a model"], det: ["det", "deterministic"], io: ["io", "output"] };
const HW = { step: 0, playing: false, timer: null, cyc: null, reading: 0, started: false };
function consMap() { const m = {}; WT.constraints.forEach(c => { m[c[0]] = c[1]; }); return m; }
function conText(c) { return c[1] === true ? c[0] : `${c[0]} = ${c[1]}`; }
function howInit() {
  const host = $("#how-app");
  host.innerHTML =
    `<div class="steps" id="hw-steps">${STEPS.map((s, i) => `<button class="step-pill ${s.kind}" data-s="${i}"><span class="n">${i + 1}</span>${s.name}</button>`).join("")}` +
    `<div class="how-play"><button class="btn sm" id="hw-prev" aria-label="Previous step">\u2039</button>` +
    `<button class="btn sm primary" id="hw-play"></button><button class="btn sm" id="hw-next" aria-label="Next step">\u203a</button></div></div>` +
    `<div class="progress"><i id="hw-prog"></i></div>` +
    `<div class="how-grid"><div class="stage"><div id="hw-stage"></div><div class="stage-cap" id="hw-cap"></div></div><div class="panel" id="hw-panel"></div></div>`;
  $("#hw-steps").addEventListener("click", e => { const b = e.target.closest(".step-pill"); if (b) { howStop(); howShow(+b.getAttribute("data-s")); } });
  $("#hw-prev").addEventListener("click", () => { howStop(); howShow(Math.max(0, HW.step - 1)); });
  $("#hw-next").addEventListener("click", () => { howStop(); howShow(Math.min(STEPS.length - 1, HW.step + 1)); });
  $("#hw-play").addEventListener("click", () => { if (HW.playing) howStop(); else { if (HW.step === STEPS.length - 1) howShow(0); howPlay(); } });
  howShow(0);
  howPlayBtn();
  onVisible(host, () => { if (!HW.started) { HW.started = true; howPlay(); } });
}
function howPlayBtn() { const b = $("#hw-play"); if (b) b.innerHTML = HW.playing ? `${icon("pause")} Pause` : `${icon("play")} Play`; }
function howStop() { HW.playing = false; clearTimeout(HW.timer); clearInterval(HW.cyc); howPlayBtn(); }
function howPlay() {
  HW.playing = true;
  howPlayBtn();
  const tick = () => {
    if (!HW.playing) return;
    if (HW.step >= STEPS.length - 1) { howStop(); return; }
    howShow(HW.step + 1);
    HW.timer = setTimeout(tick, STEPS[HW.step].key === "ground" ? 6200 : 5200);
  };
  HW.timer = setTimeout(tick, STEPS[HW.step].key === "ground" ? 6200 : 5200);
}
function howStage(o, cap) {
  const tz = BYID[WT.item];
  $("#hw-stage").innerHTML = av(tz, Object.assign({ bk: WT.bk, w: 0, ev: -1, ms: 0, px: 440, badge: 0, live: 1 }, o));
  $("#hw-cap").innerHTML = cap || "";
}
function howShow(i) {
  HW.step = i;
  clearInterval(HW.cyc);
  $$("#hw-steps .step-pill").forEach((b, j) => { b.classList.toggle("on", j === i); b.classList.toggle("done", j < i); });
  $("#hw-prog").style.width = ((i + 1) / STEPS.length * 100) + "%";
  const s = STEPS[i], K = KIND[s.kind], cons = consMap(), P = $("#hw-panel");
  const head = `<h3><span class="kind ${K[0]}">${K[1]}</span>${i + 1} \u00b7 ${s.name}</h3>`;
  if (s.key === "parse") {
    howStage({}, `<span class="chip cream">input</span> the test asset, unchanged`);
    P.innerHTML = head + `<p>The learning objective, in plain words:</p><div class="quote">\u201c${esc(WT.objective)}\u201d</div>` +
      `<p>The parser, which is the verifier's own backbone, turns it into constraints that can be checked:</p>` +
      `<div class="cons">${WT.constraints.map((c, j) => `<span class="con" style="animation-delay:${0.25 + j * 0.28}s">${esc(conText(c))}</span>`).join("")}</div>` +
      (WT.parser_same_everywhere ? `<p class="small muted">The same constraints in all three passes and under both backbones.</p>` : "") +
      `<details class="raw"><summary>The parser's answer, as returned</summary><pre class="code">${esc(WT.parser_answer)}</pre></details>`;
  } else if (s.key === "check") {
    howStage({}, `<span class="chip cream">no image needed yet</span>`);
    const k = cons.colored_part_count, n = cons.part_count, f = cons.fraction_value;
    P.innerHTML = head + `<p>Before any image is verified, the constraints must agree with each other:</p>` +
      `<ul class="checks"><li style="animation-delay:.2s"><span class="ok">\u2713</span>${k} colored \u2264 ${n} parts</li>` +
      `<li style="animation-delay:.55s"><span class="ok">\u2713</span>${esc(f)} = ${k} colored / ${n} parts</li></ul>` +
      `<p class="small muted">A contradictory objective, such as one third shown as one of four equal parts, is rejected here.</p>`;
  } else if (s.key === "ground") {
    const r = HW.reading;
    howStage({ ev: r }, `<span class="chip rose">pink: what the VLM reported</span> numbered dots are its parts (filled = colored); hover a dot for its box`);
    P.innerHTML = head + `<p>The VLM reads the image three times. The prompt names what to look for, and never the target values:</p>` +
      `<div class="readtabs" id="hw-reads">${[0, 1, 2].map(j => readTab(j)).join("")}</div>` +
      `<details class="raw"><summary>The grounding prompt</summary><pre class="code prompt">${markVocab(WT.grounding_prompt)}</pre></details>` +
      `<details class="raw"><summary>Reading 1, as returned</summary><pre class="code">${esc(WT.grounding_answer)}</pre></details>`;
    $("#hw-reads").addEventListener("click", e => { const b = e.target.closest(".readtab"); if (b) { clearInterval(HW.cyc); howReading(+b.getAttribute("data-r")); } });
    howReading(r);
    if (HW.playing) HW.cyc = setInterval(() => howReading((HW.reading + 1) % 3), 1900);
  } else if (s.key === "measure") {
    const M = WT.measurement;
    howStage({ ms: 1 }, `<span class="chip">purple: what was measured</span> regions bounded by color edges inside the VLM's box; hover a region`);
    P.innerHTML = head + `<p>Inside the box the VLM reported, deterministic operators find the regions between color edges, with no knowledge of the
      palette. They count ${M.regions} regions, ${M.colored} of them colored, and compare every area with the mean:</p>` +
      `<div class="ratio-bars" id="hw-bars">${ratioBars(WT.measured.p)}</div>` +
      `<p class="minline">d = max |area / mean \u2212 1| = <b style="color:var(--red)">${M.deviation.toFixed(2)}</b></p>` +
      `<p class="small muted">Largest part \u00d7${M.largest.toFixed(2)}, smallest \u00d7${M.smallest.toFixed(2)} of the mean area. Bands: within
      \u00b1${Z.equal_area[0].toFixed(2)} counts as equal, from \u00b1${Z.equal_area[1].toFixed(2)} as unequal.</p>`;
    requestAnimationFrame(() => requestAnimationFrame(() => $$("#hw-bars .fill").forEach(f => { f.style.width = f.getAttribute("data-w"); })));
  } else if (s.key === "rules") {
    howStage({ ms: 1, w: 1 }, `<span class="chip red">red: the witness</span> the region that violates the constraint`);
    const rep = {};
    (WT.report || []).forEach(d => { rep[d[0]] = d; });
    const rows = WT.rules.map((r, j) => {
      const rd = rep[r[0]];
      const reads = rd ? rd[4].map(x => stChip(x[0])).join(" ") : `<span class="small muted">from the parse</span>`;
      return `<tr style="animation-delay:${0.15 + j * 0.3}s"><td>${esc(r[0])}</td><td>${esc(r[0] === "equal_area" ? "d = " + r[1] : r[1])}</td><td>${reads}</td><td>${stChip(r[2])}</td></tr>`;
    }).join("");
    const st = WT.rules.map(r => r[2]);
    const low = st.reduce((a, s2) => ({ F: 0, U: 1, T: 2 })[s2] < ({ F: 0, U: 1, T: 2 })[a] ? s2 : a, "T");
    P.innerHTML = head + `<p>Each constraint gets T, F, or U. A measured value is decided by zones, three readings vote, and a decision needs
      confidence q \u2265 \u03c4 = ${Z.tau}:</p>` + gaugeHTML(WT.measurement.deviation, "hw-gauge") +
      `<table class="rules-tbl"><tr><td class="small muted" style="font-family:var(--body)">constraint</td><td class="small muted">value</td>` +
      `<td class="small muted">readings 1\u20133</td><td class="small muted">status</td></tr>${rows}</table>` +
      `<p class="small muted">${esc(WT.agree)} readings agree on every constraint, q = 1.0 \u2265 \u03c4 = ${Z.tau}.</p>` +
      `<p class="minline">min(${st.join(", ")}) = ${stChip(low)} <span class="small muted">with F &lt; U &lt; T</span></p>`;
    requestAnimationFrame(() => requestAnimationFrame(() => gaugeSet("hw-gauge", WT.measurement.deviation)));
  } else {
    howStage({ w: 1, draw: 1 }, `<span class="chip red">the witness</span> reported with the verdict`);
    const fails = WT.rules.filter(r => r[2] === "F").map(r => r[0]);
    const J = WT.judges[WT.bk] || {};
    const req = ((J.structured || {}).requirements || []).map((q, j) => `requirement ${q.number || j + 1} ${q.satisfied ? "\u2713" : "\u2717"}`).join(", ");
    P.innerHTML = head + `<div class="pills3">${["VALID", "INVALID", "UNCERTAIN"].map(v => `<span class="pill3 ${v}${v === WT.verdict ? " on" : ""}">${v}</span>`).join("")}</div>` +
      `<p>The report names the violated constraint, <code>${esc(fails.join(", "))} = F</code>, and the witness box shows where.` +
      (WT.same_verdict_gemini ? ` With Gemini 3.5 Flash as backbone, the verdict is the same.` : "") + `</p>` +
      `<div class="sect">What the ${esc(WT.backbone)} judges answered for the same card</div>` +
      `<div class="quote"><b>Direct</b>: ${esc((J.direct || {}).verdict)}</div>` +
      `<div class="quote"><b>CoT</b>: \u201c${esc((J.cot || {}).reasoning)}\u201d \u2192 ${esc((J.cot || {}).verdict)}</div>` +
      `<div class="quote"><b>Structured</b>: ${esc(req)} \u2192 ${esc((J.structured || {}).verdict)}</div>` +
      `<p class="small muted">A judge returns a verdict, and at most a description: nothing in it can be checked against the image.</p>`;
  }
}
function readTab(j) {
  const ev = (WT.readings || [])[j];
  const sh = ev && ev.s && ev.s[0];
  const txt = sh ? `${esc(sh[0])} \u00b7 ${sh[2].length} parts \u00b7 ${sh[2].filter(p => p[1]).length} colored` : "did not parse";
  const tx = ev && ev.t ? ev.t.map(t => `\u201c${esc(t[0])}\u201d`).join(", ") : "no text";
  return `<button class="readtab${j === HW.reading ? " on" : ""}" data-r="${j}"><b>Reading ${j + 1}</b><span>${txt} \u00b7 ${tx}</span></button>`;
}
function howReading(j) {
  HW.reading = j;
  $$("#hw-reads .readtab").forEach((b, x) => b.classList.toggle("on", x === j));
  const el = $("#hw-stage .av");
  if (!el) return;
  const o = JSON.parse(el.getAttribute("data-o"));
  o.ev = j;
  el.setAttribute("data-o", JSON.stringify(o));
  $("svg.ov", el).innerHTML = overlay(BYID[WT.item], o);
}
function markVocab(text) {
  return esc(text).replace(/\b(shapes?|parts?|colored|texts?|boxe?s?)\b/g, "<mark>$1</mark>");
}
function ratioBars(parts) {
  const eT = Z.equal_area[0], eF = Z.equal_area[1];
  return parts.map((p, j) => {
    const r = p[1], dev = Math.abs(r - 1);
    const cls = (p[2] ? " col" : "") + (dev >= eF ? " far" : dev > eT ? " mid" : "");
    return `<div class="rbar"><span>part ${j + 1}${p[2] ? " \u25cf" : ""}</span><span class="track">` +
      `<i class="zoneU" style="left:${(1 - eF) * 50}%;width:${eF * 100}%"></i><i class="zoneT" style="left:${(1 - eT) * 50}%;width:${eT * 100}%"></i>` +
      `<i class="fill${cls}" data-w="${clamp(r / 2, 0, 1) * 100}%"></i><i class="mean" style="left:50%"></i></span><b>\u00d7${r.toFixed(2)}</b></div>`;
  }).join("") + `<div class="small muted" style="margin-left:62px">bar = area relative to the mean part (line at \u00d71.00); shaded: the equal and the undecided band</div>`;
}
const GMAX = 0.8;
function gaugeHTML(d, id) {
  const eT = Z.equal_area[0], eF = Z.equal_area[1];
  return `<div class="gauge" id="${id}"><div class="needle-wrap"><span class="needle" style="left:0%"></span></div>` +
    `<div class="scale"><div class="zt" style="width:${eT / GMAX * 100}%">T</div><div class="zu" style="width:${(eF - eT) / GMAX * 100}%">U</div>` +
    `<div class="zf" style="flex:1">F: parts not equal</div></div>` +
    `<div class="ticks"><span>d = 0</span><span style="position:absolute;left:${eT / GMAX * 100}%;transform:translateX(-50%)">${eT.toFixed(2)}</span>` +
    `<span style="position:absolute;left:${eF / GMAX * 100}%;transform:translateX(-50%)">${eF.toFixed(2)}</span><span>${GMAX.toFixed(1)}+</span></div></div>`;
}
function gaugeSet(id, d) { const n = $(`#${id} .needle`); if (n) n.style.left = clamp(d / GMAX, 0, 1) * 100 + "%"; }
