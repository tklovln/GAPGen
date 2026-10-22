/* ==================================================================== rule playground: edit a fraction picture */
const PL = { mode: "pie", n: 8, b: [], col: new Set(), kt: 2, nt: 8, start: -90, drag: -1 };
const PCX = 200, PCY = 200, PR = 150, SX0 = 30, SX1 = 370, SY0 = 70, SY1 = 190, GAP = 0.012;
function plEqual(n, colored) {
  PL.n = n;
  PL.b = Array.from({ length: n }, (_, i) => i / n);
  PL.start = -90;
  PL.col = new Set(Array.from({ length: Math.min(colored, n) }, (_, i) => i));
}
function plSizes() {
  const n = PL.n, b = PL.b;
  if (PL.mode === "pie") return b.map((v, i) => (i === n - 1 ? b[0] + 1 : b[i + 1]) - v);
  const cuts = [0, ...b.slice(1), 1];
  return Array.from({ length: n }, (_, i) => cuts[i + 1] - cuts[i]);
}
function plPreset(k) {
  if (k === "equal") plEqual(PL.nt, PL.kt);
  else if (k === "fig1") {
    PL.mode = "pie"; PL.nt = 8; PL.kt = 2;
    const sz = WT.spec.sizes;
    PL.n = sz.length;
    let acc = 0;
    PL.b = sz.map(s => { const v = acc; acc += s; return v; });
    PL.start = WT.spec.start;
    PL.col = new Set(WT.spec.colored.map((c, i) => c ? i : -1).filter(i => i >= 0));
  } else if (k === "colored") plEqual(PL.nt, Math.min(PL.nt, PL.kt + 1));
  else if (k === "count") plEqual(Math.max(2, PL.nt - 1), PL.kt);
  else if (k === "near") {
    plEqual(PL.nt, PL.kt);
    const n = PL.n, dev = 0.15;
    if (PL.mode === "pie") { PL.b[1] = PL.b[0] + (1 + dev) / n; }
    else { PL.b[1] = (1 + dev) / n; }
  }
  plRender();
}
function plEval() {
  const sizes = plSizes(), n = PL.n, ratios = sizes.map(s => s * n);
  let d = 0, worst = 0;
  ratios.forEach((r, i) => { if (Math.abs(r - 1) > d) { d = Math.abs(r - 1); worst = i; } });
  const eT = Z.equal_area[0], eF = Z.equal_area[1], m = Z.area_margin, tau = Z.tau;
  let zone, w;
  if (d <= eT) { zone = "T"; w = Math.min(1, (eT - d) / m + 0.5); }
  else if (d >= eF) { zone = "F"; w = Math.min(1, (d - eF) / m + 0.5); }
  else { zone = "U"; w = 0; }
  const eq = zone !== "U" && w >= tau ? zone : "U";
  const k = PL.col.size;
  const rows = [
    ["fraction_value", `${k}/${n}`, k * PL.nt === PL.kt * n && n > 0 ? "T" : "F", `colored / parts equals ${PL.kt}/${PL.nt}`],
    ["part_count", String(n), n === PL.nt ? "T" : "F", `the whole is divided into ${PL.nt} parts`],
    ["equal_area", `d = ${d.toFixed(3)}`, eq, zone === "U" ? "d is between the zones: undecided" :
      w >= tau ? `zone ${zone}, confidence q = ${w.toFixed(2)} \u2265 \u03c4 = ${tau}` : `zone ${zone}, but q = ${w.toFixed(2)} < \u03c4 = ${tau}: too close to a threshold`],
    ["colored_part_count", String(k), k === PL.kt ? "T" : "F", `exactly ${PL.kt} of the parts are colored`],
  ];
  const st = rows.map(r => r[2]);
  const verdict = st.includes("F") ? "INVALID" : st.every(s => s === "T") ? "VALID" : "UNCERTAIN";
  return { rows, verdict, d, worst, ratios, zone, w };
}
function pt(a) { const t = (PL.start + 360 * a) * Math.PI / 180; return [PCX + PR * Math.cos(t), PCY + PR * Math.sin(t)]; }
function wedge(a0, a1) {
  const p0 = pt(a0), p1 = pt(a1), large = a1 - a0 > 0.5 ? 1 : 0;
  return `M${PCX},${PCY} L${p0[0].toFixed(2)},${p0[1].toFixed(2)} A${PR},${PR} 0 ${large} 1 ${p1[0].toFixed(2)},${p1[1].toFixed(2)} Z`;
}
function plSVG(ev) {
  const n = PL.n, b = PL.b;
  let h = "";
  if (PL.mode === "pie") {
    for (let i = 0; i < n; i++) {
      const a0 = b[i], a1 = i === n - 1 ? b[0] + 1 : b[i + 1];
      h += `<path class="part ${PL.col.has(i) ? "col" : "plain"}" data-p="${i}" d="${wedge(a0, a1)}"/>`;
    }
    h += `<circle class="edge" cx="${PCX}" cy="${PCY}" r="${PR}"/>`;
    b.forEach(a => { const p = pt(a); h += `<line class="edge" x1="${PCX}" y1="${PCY}" x2="${p[0]}" y2="${p[1]}"/>`; });
    if (ev.verdict !== "VALID" && ev.rows[2][2] !== "T") {
      const a0 = b[ev.worst], a1 = ev.worst === n - 1 ? b[0] + 1 : b[ev.worst + 1];
      h += `<path class="worst" d="${wedge(a0, a1)}"/>`;
    }
    b.forEach((a, i) => { const p = pt(a); h += `<circle class="handle${PL.drag === i ? " drag" : ""}" data-h="${i}" cx="${p[0]}" cy="${p[1]}" r="11"/>`; });
  } else {
    const cuts = [0, ...b.slice(1), 1], X = v => SX0 + (SX1 - SX0) * v;
    for (let i = 0; i < n; i++) h += `<rect class="part ${PL.col.has(i) ? "col" : "plain"}" data-p="${i}" x="${X(cuts[i])}" y="${SY0}" width="${X(cuts[i + 1]) - X(cuts[i])}" height="${SY1 - SY0}"/>`;
    h += `<rect class="edge" x="${SX0}" y="${SY0}" width="${SX1 - SX0}" height="${SY1 - SY0}"/>`;
    for (let i = 1; i < n; i++) h += `<line class="edge" x1="${X(cuts[i])}" y1="${SY0}" x2="${X(cuts[i])}" y2="${SY1}"/>`;
    if (ev.verdict !== "VALID" && ev.rows[2][2] !== "T") h += `<rect class="worst" x="${X(cuts[ev.worst]) + 3}" y="${SY0 + 3}" width="${X(cuts[ev.worst + 1]) - X(cuts[ev.worst]) - 6}" height="${SY1 - SY0 - 6}"/>`;
    for (let i = 1; i < n; i++) h += `<circle class="handle${PL.drag === i ? " drag" : ""}" data-h="${i}" cx="${X(cuts[i])}" cy="${SY0 - 16}" r="11"/>` +
      `<line class="edge" x1="${X(cuts[i])}" y1="${SY0 - 5}" x2="${X(cuts[i])}" y2="${SY0}" style="stroke-width:2"/>`;
  }
  const vh = PL.mode === "pie" ? 400 : 240;
  h += `<text class="hint" x="200" y="${vh - 12}">drag the white handles \u00b7 tap a part to color it</text>`;
  return `<svg viewBox="0 0 400 ${vh}" id="pl-svg" role="img" aria-label="editable fraction picture">${h}</svg>`;
}
function plInit() {
  const host = $("#play-app");
  host.innerHTML =
    `<div class="play-grid"><div><div class="canvas" id="pl-canvas"></div>` +
    `<div class="play-ctl" style="margin-top:12px">${seg("pl-mode", [["pie", "Circle"], ["strip", "Strip"]], PL.mode)}` +
    `<span class="lab small muted" style="font-weight:800">PARTS</span><span class="stepper-n"><button data-d="-1" aria-label="fewer parts">\u2212</button>` +
    `<span id="pl-n"></span><button data-d="1" aria-label="more parts">+</button></span>` +
    `<button class="btn sm" id="pl-eq">Make equal</button></div></div>` +
    `<div><div class="play-ctl"><span class="lab small muted" style="font-weight:800">OBJECTIVE</span><span class="objective" style="margin:0">Show the fraction ` +
    `<span class="stepper-n" id="pl-k"><button data-d="-1">\u2212</button><span></span><button data-d="1">+</button></span> / ` +
    `<span class="stepper-n" id="pl-t"><button data-d="-1">\u2212</button><span></span><button data-d="1">+</button></span></span></div>` +
    `<div class="presets" id="pl-presets"><span class="lab small muted" style="font-weight:800;align-self:center">TRY</span>` +
    `<button class="btn sm" data-p="equal">Equal parts</button><button class="btn sm" data-p="fig1">The paper's Fig. 1</button>` +
    `<button class="btn sm" data-p="near">Near a threshold</button><button class="btn sm" data-p="colored">Wrong colored count</button>` +
    `<button class="btn sm" data-p="count">Wrong part count</button></div>` +
    `<div class="verdict-big" id="pl-verdict"></div>` +
    `<table class="rules-tbl" id="pl-rules"></table>` +
    `<div id="pl-gauge-box"></div><div class="ratio-bars" id="pl-bars"></div></div></div>`;
  plPreset("fig1");
  onSeg("pl-mode", v => { PL.mode = v; plEqual(PL.n, PL.col.size); plRender(); });
  $(".stepper-n", host).addEventListener("click", e => { const b = e.target.closest("button[data-d]"); if (!b) return; const n = clamp(PL.n + +b.getAttribute("data-d"), 2, 12); plEqual(n, Math.min(PL.col.size, n)); plRender(); });
  $("#pl-k").addEventListener("click", e => { const b = e.target.closest("button[data-d]"); if (!b) return; PL.kt = clamp(PL.kt + +b.getAttribute("data-d"), 1, PL.nt); plRender(); });
  $("#pl-t").addEventListener("click", e => { const b = e.target.closest("button[data-d]"); if (!b) return; PL.nt = clamp(PL.nt + +b.getAttribute("data-d"), 2, 12); PL.kt = Math.min(PL.kt, PL.nt); plRender(); });
  $("#pl-eq").addEventListener("click", () => { plEqual(PL.n, PL.col.size); plRender(); });
  $("#pl-presets").addEventListener("click", e => { const b = e.target.closest("button[data-p]"); if (b) plPreset(b.getAttribute("data-p")); });
  const cv = $("#pl-canvas");
  cv.addEventListener("pointerdown", e => {
    const h = e.target.closest(".handle");
    if (h) { PL.drag = +h.getAttribute("data-h"); cv.setPointerCapture(e.pointerId); e.preventDefault(); plRender(true); return; }
    const p = e.target.closest(".part");
    if (p) { const i = +p.getAttribute("data-p"); if (PL.col.has(i)) PL.col.delete(i); else PL.col.add(i); plRender(); }
  });
  cv.addEventListener("pointermove", e => {
    if (PL.drag < 0) return;
    const svg = $("#pl-svg"), r = svg.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width * 400, y = (e.clientY - r.top) / r.width * 400;
    plDrag(x, y);
    plRender(true);
  });
  const end = () => { if (PL.drag >= 0) { PL.drag = -1; plRender(); } };
  cv.addEventListener("pointerup", end);
  cv.addEventListener("pointercancel", end);
}
function plDrag(x, y) {
  const i = PL.drag, n = PL.n, b = PL.b;
  if (PL.mode === "pie") {
    let a = (Math.atan2(y - PCY, x - PCX) * 180 / Math.PI - PL.start) / 360;
    a = a - Math.floor(a);
    let best = a, dist = 9;
    [-2, -1, 0, 1, 2].forEach(m => { const c = a + m; if (Math.abs(c - b[i]) < dist) { dist = Math.abs(c - b[i]); best = c; } });
    const lo = (i === 0 ? b[n - 1] - 1 : b[i - 1]) + GAP, hi = (i === n - 1 ? b[0] + 1 : b[i + 1]) - GAP;
    b[i] = clamp(best, lo, hi);
  } else {
    const v = (x - SX0) / (SX1 - SX0);
    const lo = (i === 1 ? 0 : b[i - 1]) + GAP, hi = (i === n - 1 ? 1 : b[i + 1]) - GAP;
    b[i] = clamp(v, lo, hi);
  }
}
function plRender(fast) {
  const ev = plEval();
  $("#pl-canvas").innerHTML = plSVG(ev);
  $("#pl-n").textContent = PL.n;
  $("#pl-k span").textContent = PL.kt;
  $("#pl-t span").textContent = PL.nt;
  const why = ev.rows.filter(r => r[2] !== "T").map(r => `<code>${r[0]} = ${r[2]}</code>`).join(", ");
  const vb = $("#pl-verdict");
  const prev = vb.getAttribute("data-v");
  vb.className = "verdict-big " + ev.verdict;
  vb.setAttribute("data-v", ev.verdict);
  vb.innerHTML = `<span class="vb">${ev.verdict}</span><span class="why">${ev.verdict === "VALID" ? "Every constraint is T." :
    ev.verdict === "INVALID" ? `Some constraint is F: ${why}.` : `No constraint is F, but ${why}: a person reviews the asset.`}</span>`;
  if (prev && prev !== ev.verdict && !fast) { vb.classList.remove("bump"); void vb.offsetWidth; vb.classList.add("bump"); }
  $("#pl-rules").innerHTML = ev.rows.map(r => `<tr><td>${r[0]}</td><td class="small">${esc(r[3])}</td><td style="text-align:right">${esc(r[1])}</td><td>${stChip(r[2])}</td></tr>`).join("");
  if (!$("#pl-gauge")) $("#pl-gauge-box").innerHTML = gaugeHTML(ev.d, "pl-gauge");
  gaugeSet("pl-gauge", ev.d);
  $("#pl-bars").innerHTML = ratioBars(ev.ratios.map((r, i) => [null, r, PL.col.has(i) ? 1 : 0]));
  $$("#pl-bars .fill").forEach(f => { f.style.transition = "none"; f.style.width = f.getAttribute("data-w"); });
}
