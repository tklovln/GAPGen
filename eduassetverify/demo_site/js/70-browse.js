/* ==================================================================== outcome map: 900 cells, three stripes each */
const MP = { m: "e", bk: "C", cells: [] };
const OUTC = { okV: "#EEECE1", okI: "#E3DAEE", fa: "#D50000", fr: "#E16981", rev: "#9B7EBD", na: "#A9A3B4" };
const OUTN = { okV: "correct asset accepted", okI: "violation caught", fa: "false acceptance", fr: "false rejection", rev: "sent to review", na: "no parsable answer" };
const outcome = (v, y) => v === "U" ? "rev" : v === "X" ? "na" : v === "V" ? (y === "V" ? "okV" : "fa") : (y === "I" ? "okI" : "fr");
function mapInit() {
  const host = $("#map-app");
  const tasks = ["fraction", "counting", "spatial"], byT = {};
  D.items.forEach(it => { (byT[it.t] = byT[it.t] || []).push(it); });
  const tmpls = tasks.map(d => Object.keys(byT).filter(t => byT[t][0].dm === d).sort());
  const C = 14, G = 2, P = C + G, COLS = 12, BW = COLS * P, GX = 30, LH = 18, GY = 14, TOP = 26;
  const nrows = Math.max(...tmpls.map(ts => ts.length));
  const rows = Array.from({ length: nrows }, (_, ri) => Math.max(...tmpls.map(ts => ts[ri] ? Math.ceil(byT[ts[ri]].length / COLS) : 0)));
  const ys = rows.map((_, ri) => TOP + rows.slice(0, ri).reduce((a, r) => a + LH + r * P + GY, 0));
  const W = 3 * BW + 2 * GX, H = ys[nrows - 1] + LH + rows[nrows - 1] * P + 4;
  let s = "";
  tasks.forEach((d, ti) => {
    const x0 = ti * (BW + GX);
    s += `<text class="th" x="${x0}" y="16">${TASKN[d]}</text>`;
    tmpls[ti].forEach((t, ri) => {
      const y0 = ys[ri];
      s += `<text class="tl" x="${x0}" y="${y0 + 12}">${esc(D.templates[t] || t)}</text>`;
      byT[t].forEach((it, j) => {
        const x = x0 + (j % COLS) * P, y = y0 + LH + Math.floor(j / COLS) * P;
        s += `<g class="cellg" data-i="${it.i}"><rect x="${x}" y="${y}" width="${C / 3 + 0.05}" height="${C}"/><rect x="${x + C / 3}" y="${y}" width="${C / 3 + 0.05}" height="${C}"/>` +
          `<rect x="${x + 2 * C / 3}" y="${y}" width="${C / 3}" height="${C}"/><rect class="frame" x="${x - 0.5}" y="${y - 0.5}" width="${C + 1}" height="${C + 1}" rx="2"/></g>`;
      });
    });
  });
  host.innerHTML = `<div class="map-wrap"><div><div class="ctl" style="margin-bottom:10px"><span class="lab">Method</span>${seg("mp-m", METH.map(m => [m[0], m[1]]), MP.m)}` +
    `<span class="lab">Backbone</span>${seg("mp-b", BKS.map(b => [b, BKN[b]]), MP.bk)}</div>` +
    `<svg class="map-svg" id="mp-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="outcome of every test asset">${s}</svg></div>` +
    `<div class="map-side"><h3 id="mp-title"></h3><p class="small muted" style="margin:4px 0 0">One cell per test asset, stripes = passes 1\u20133. Correct and violated assets of a pair sit side by side.</p>` +
    `<div class="cnt" id="mp-cnt"></div><p class="small muted">Hover a cell for its picture; select it to open the asset.</p></div></div>`;
  MP.cells = $$("#mp-svg .cellg").map(g => ({ it: BYID[g.getAttribute("data-i")], r: $$("rect", g).slice(0, 3) }));
  onSeg("mp-m", v => { MP.m = v; mapPaint(); });
  onSeg("mp-b", v => { MP.bk = v; mapPaint(); });
  const svg = $("#mp-svg");
  svg.addEventListener("mousemove", e => {
    const g = e.target.closest(".cellg");
    if (!g) { hideTip(); return; }
    const it = BYID[g.getAttribute("data-i")];
    if (TIP.getAttribute("data-i") !== it.i) {
      TIP.setAttribute("data-i", it.i);
      showTip(av(it, { bk: MP.bk, w: 1, badge: 1, px: 220 }) + `<p>${esc(it.o)}</p><p>${METH.map(m => `${m[1]} ${passes(it.v[MP.bk][m[0]], it.y)}`).join("<br>")}</p>`, e.clientX, e.clientY);
    } else moveTip(e.clientX, e.clientY);
  });
  svg.addEventListener("mouseleave", () => { hideTip(); TIP.removeAttribute("data-i"); });
  svg.addEventListener("click", e => { const g = e.target.closest(".cellg"); if (g) { hideTip(); openModal(g.getAttribute("data-i"), MP.bk); } });
  mapPaint();
}
function mapPaint() {
  const cnt = { okV: 0, okI: 0, fa: 0, fr: 0, rev: 0, na: 0 };
  MP.cells.forEach(c => {
    const v = c.it.v[MP.bk][MP.m];
    c.r.forEach((r, p) => { const o = outcome(v[p], c.it.y); cnt[o]++; r.setAttribute("fill", OUTC[o]); });
  });
  $("#mp-title").innerHTML = `${esc(MNAME[MP.m])} <span class="small muted">(${esc(BKN[MP.bk])})</span>`;
  $("#mp-cnt").innerHTML = Object.keys(OUTN).filter(k => cnt[k] || k === "fa").map(k =>
    `<div><span><i style="background:${OUTC[k]}"></i>${OUTN[k]}</span><b${k === "fa" && cnt[k] ? ' style="color:var(--red)"' : ""}>${fmtInt(cnt[k])}</b></div>`).join("") +
    `<div style="background:none;padding:0 10px" class="small muted"><span>of ${fmtInt(3 * D.items.length)} evaluations</span></div>`;
}

/* ==================================================================== gallery */
const GL = { bk: "C", show: "all", dm: "all", sp: "all", op: "all", y: "all", n: 30, list: [] };
const SHOWS = [["all", "All test assets"], ["judge-fa", "A judge accepted a violated asset"], ["ours-catch", "A judge accepted it, EduAssetVerify rejected it in every pass"],
  ["ours-fa", "EduAssetVerify accepted a violated asset"], ["ours-review", "EduAssetVerify sent the asset to review"], ["ours-fr", "EduAssetVerify rejected a correct asset"],
  ["judge-fr", "A judge rejected a correct asset"]];
function shows(it, key, b) {
  const v = it.v[b], J = v.d + v.c + v.s, E = v.e;
  switch (key) {
    case "judge-fa": return it.y === "I" && J.includes("V");
    case "ours-catch": return it.y === "I" && J.includes("V") && E === "III";
    case "ours-fa": return it.y === "I" && E.includes("V");
    case "ours-review": return E.includes("U");
    case "ours-fr": return it.y === "V" && E.includes("I");
    case "judge-fr": return it.y === "V" && J.includes("I");
    default: return true;
  }
}
const keep = it => shows(it, GL.show, GL.bk) && (GL.dm === "all" || it.dm === GL.dm) && (GL.sp === "all" || it.sp === GL.sp) &&
  (GL.op === "all" || it.op.includes(GL.op)) && (GL.y === "all" || it.y === GL.y);
const sel = (id, opts, cur) => `<select id="${id}">${opts.map(o => `<option value="${esc(o[0])}"${o[0] === cur ? " selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
function galleryInit() {
  const host = $("#gallery-app");
  host.innerHTML = `<div class="filters" id="gl-filters"></div><div class="grid" id="gl-grid"></div><div class="more" id="gl-more"></div>`;
  galleryControls();
  galleryGrid();
  const grid = $("#gl-grid");
  const open = e => { const c = e.target.closest(".acard"); if (c && (e.type === "click" || e.key === "Enter" || e.key === " ")) { e.preventDefault(); openModal(c.getAttribute("data-i"), GL.bk, GL.list); } };
  grid.addEventListener("click", open);
  grid.addEventListener("keydown", open);
  $("#gl-more").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; GL.n = b.getAttribute("data-m") === "all" ? 900 : GL.n + 30; galleryGrid(); });
}
function galleryControls() {
  const f = $("#gl-filters");
  f.innerHTML = seg("gl-bk", BKS.map(b => [b, BKN[b]]), GL.bk) +
    `<label>Show ${sel("gl-show", SHOWS.map(s => [s[0], `${s[1]} (${D.items.filter(it => shows(it, s[0], GL.bk)).length})`]), GL.show)}</label>` +
    `<label>Task ${sel("gl-dm", [["all", "All"], ["fraction", "Fraction"], ["counting", "Counting"], ["spatial", "Spatial"]], GL.dm)}</label>` +
    `<label>Condition ${sel("gl-sp", [["all", "All"], ...D.conditions], GL.sp)}</label>` +
    `<label>Error ${sel("gl-op", [["all", "All"], ...D.operators.map(o => [o[0], o[1]])], GL.op)}</label>` +
    `<label>Label ${sel("gl-y", [["all", "All"], ["V", "Correct"], ["I", "Violated"]], GL.y)}</label><span class="count" id="gl-count"></span>`;
  onSeg("gl-bk", v => { GL.bk = v; galleryControls(); galleryGrid(); });
  [["gl-show", "show"], ["gl-dm", "dm"], ["gl-sp", "sp"], ["gl-op", "op"], ["gl-y", "y"]].forEach(([id, k]) => {
    $("#" + id).addEventListener("change", e => { GL[k] = e.target.value; GL.n = 30; galleryGrid(); });
  });
}
function card(it) {
  const v = it.v[GL.bk];
  return `<div class="acard" tabindex="0" role="button" data-i="${it.i}">${av(it, { bk: GL.bk, w: 1, badge: 1, px: 210 })}<div class="meta"><div class="obj">${esc(it.o)}</div>` +
    (it.op.length ? `<div class="ops">${it.op.map(o => `<span class="chip red">${esc(OPN[o])}</span>`).join("")}</div>` : "") +
    METH.map(m => `<div class="vrow"><span class="mn${m[0] === "e" ? " ours" : ""}">${m[1]}</span>${passes(v[m[0]], it.y)}</div>`).join("") + `</div></div>`;
}
function galleryGrid() {
  GL.list = D.items.filter(keep).map(it => it.i);
  const shown = GL.list.slice(0, GL.n), rest = GL.list.length - shown.length;
  $("#gl-count").textContent = `${GL.list.length} of ${D.items.length} \u00b7 verdicts under ${BKN[GL.bk]}`;
  $("#gl-grid").innerHTML = shown.length ? shown.map(i => card(BYID[i])).join("") : `<div class="empty">No test asset matches these filters.</div>`;
  $("#gl-more").innerHTML = rest > 0 ? `<button class="btn sm" data-m="30">Show ${Math.min(30, rest)} more</button><button class="btn sm" data-m="all">Show all ${GL.list.length}</button>` : "";
}

/* ==================================================================== modal: one asset with its evidence */
const MD = { id: null, bk: "C", w: 1, g: 1, ms: 1, ev: -1, lens: 0, cmp: 0, list: null };
function openModal(iid, bk, list) {
  if (!BYID[iid]) return;
  MD.id = iid;
  if (bk) MD.bk = bk;
  MD.list = list || null;
  MD.cmp = 0;
  const it = BYID[iid];
  need(it.t);
  renderModal();
  $("#modal").hidden = false;
  document.body.style.overflow = "hidden";
}
function closeModal() { $("#modal").hidden = true; document.body.style.overflow = ""; MD.id = null; hideTip(); }
function tog(k, label, color) { return `<span class="tog${MD[k] ? " on" : ""}" data-t="${k}"><i style="background:${color}"></i>${label}</span>`; }
function renderModal() {
  const it = BYID[MD.id], bk = MD.bk, p = BYID[it.p], det = detailOf(it, bk);
  const hasMs = det && det.ms, hasG = gtBoxes(it).length > 0;
  const view = MD.cmp && p
    ? cmpHTML(it.y === "V" ? it : p, it.y === "V" ? p : it, { l: { bk, w: 0, px: 470 }, r: { bk, w: 1, g: MD.g, px: 470 } })
    : av(it, { bk, w: MD.w, g: MD.g && hasG, ms: MD.ms && hasMs ? 1 : 0, ev: MD.ev, px: 470, badge: 1, live: 1 });
  const rep = {};
  (it.r[bk] || []).forEach(r => { rep[r[0]] = r; });
  const rds = {};
  ((det && det.rd) || []).forEach(d => { rds[d[0]] = d; });
  const tg = new Set(it.tg);
  const clist = it.c.map(c => {
    const r = rep[c[1]], d = rds[c[1]];
    return `<li class="${tg.has(c[0]) ? "tgt" : ""}"><span>${r ? stChip(r[1]) : ""}</span><span><code>${esc(c[1])}</code> ${esc(c[2])}${tg.has(c[0]) ? " <b style=\"color:var(--red)\">(perturbed)</b>" : ""}` +
      `<br><span class="val">${r && r[2] !== "" ? "value " + esc(r[2]) + " \u00b7 " : ""}${r ? "q = " + r[3] + " \u00b7 " + esc(r[5] || "") : ""}</span></span>` +
      `<span class="rds" title="the three readings">${d ? d[4].map(x => stChip(x[0])).join("") : ""}</span></li>`;
  }).join("");
  const J = judgeAns(it, bk);
  const req = J && J.s ? J.s.map((s, i) => `${esc((it.c[i] || [])[2] || "requirement " + (i + 1))} ${s === "T" ? "\u2713" : s === "F" ? "\u2717" : "?"}`).join("; ") : "";
  const sm = det && det.sm ? det.sm.map((s, i) => s ? `reading ${i + 1}: ${s.x !== undefined ? `text \u201c${esc(s.x)}\u201d` : ""}${s.k ? ` ${esc(s.k.join(", "))}` : ""}` : "").filter(Boolean).join("<br>") : "";
  const ops = it.op.map(o => esc(OPN[o])).join(" + ");
  $("#m-body").innerHTML =
    `<p class="mhead">Test asset <code>${it.i}</code> \u00b7 ${esc(TASKN[it.dm])} \u00b7 template: ${esc(it.tn)} \u00b7 style: ${esc(STYLEN[it.st] || it.st)} \u00b7 ${esc(CONDN[it.sp])}` +
    ` \u00b7 <a href="#item=${it.i}&b=${bk}">link</a></p><div class="mgrid"><div>` +
    `<div class="mtools">${seg("m-bk", BKS.map(b => [b, BKN[b]]), bk)}</div>` +
    `<div class="mtools">${tog("w", "witness", "var(--red)")}${hasG ? tog("g", "perturbed region", "#241c30") : ""}${hasMs ? tog("ms", "measured", "var(--purple)") : ""}` +
    `<span class="lab small muted" style="font-weight:800">VLM READING</span>${seg("m-ev", [[-1, "off"], [0, "1"], [1, "2"], [2, "3"]], MD.ev, "rose")}` +
    `${tog("lens", "magnifier", "var(--lilac)")}</div>` +
    `<div id="m-view" style="position:relative">${view}<div class="lens" id="m-lens"></div></div>` +
    (det ? "" : `<p class="small muted">Loading evidence and measurements\u2026</p>`) +
    (p ? `<div class="partner-row">${av(p, { bk, w: 0, badge: 0, px: 86 })}<div><div class="small muted">Counterfactual partner: ${p.y === "V" ? "the correct asset" : "the violated asset"}</div>` +
      `<div class="mtools" style="margin:6px 0 0"><button class="btn sm" id="m-cmp">${MD.cmp ? "Back to this asset" : "Compare with a slider"}</button><button class="btn sm" id="m-partner">Open it</button></div></div></div>` : "") +
    `</div><div><h3 id="m-title">${it.y === "V" ? "Correct asset" : "Violated asset: " + ops}</h3><p class="objective" style="font-size:1.05rem">\u201c${esc(it.o)}\u201d</p>` +
    `<div class="sect">EduAssetVerify report (${esc(BKN[bk])}, pass 1)</div><ul class="clist">${clist}</ul>` +
    `<div class="sect">Verdicts, passes 1\u20133</div>${vtable(it)}` +
    `<div class="sect">Judges' first-pass answers (${esc(BKN[bk])})</div>` +
    (J ? `<div class="jans"><b>CoT judge</b>: \u201c${esc(J.c || "")}\u201d</div><div class="jans"><b>Structured judge</b>: ${req || "no per-requirement answer"}</div>` : `<p class="small muted">loading\u2026</p>`) +
    (sm ? `<div class="sect">Semantic re-reading</div><p class="small">${sm}</p>` : "") +
    `<p class="kbd">\u2190 \u2192 previous or next asset \u00b7 Esc closes</p></div></div>`;
  onSeg("m-bk", v => { MD.bk = v; renderModal(); });
  onSeg("m-ev", v => { MD.ev = +v; MD.cmp = 0; renderModal(); });
  $$("#m-body .tog").forEach(t => t.addEventListener("click", () => { const k = t.getAttribute("data-t"); MD[k] = MD[k] ? 0 : 1; if (k !== "lens") MD.cmp = 0; renderModal(); }));
  const c = $("#m-cmp");
  if (c) c.addEventListener("click", () => { MD.cmp = MD.cmp ? 0 : 1; renderModal(); });
  const op = $("#m-partner");
  if (op) op.addEventListener("click", () => { MD.id = it.p; MD.cmp = 0; need(BYID[it.p].t); renderModal(); });
  cmpBind($("#m-body"));
  lensBind();
}
function lensBind() {
  const view = $("#m-view"), lens = $("#m-lens");
  if (!view || !lens) return;
  const z = 2.6;
  view.addEventListener("mousemove", e => {
    if (!MD.lens || MD.cmp) { lens.style.display = "none"; return; }
    const el = $(".av", view), r = el.getBoundingClientRect(), vr = view.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    if (x < 0 || y < 0 || x > r.width || y > r.height) { lens.style.display = "none"; return; }
    lens.style.display = "block";
    lens.style.backgroundImage = `url("${imgOf(MD.id)}")`;
    lens.style.backgroundSize = `${r.width * z}px ${r.height * z}px`;
    lens.style.backgroundPosition = `${75 - x * z}px ${75 - y * z}px`;
    lens.style.left = (e.clientX - vr.left - 75) + "px";
    lens.style.top = (e.clientY - vr.top - 75) + "px";
  });
  view.addEventListener("mouseleave", () => { lens.style.display = "none"; });
}
function modalStep(dir) {
  const list = MD.list && MD.list.includes(MD.id) ? MD.list : D.items.map(it => it.i);
  const j = list.indexOf(MD.id);
  if (j < 0) return;
  MD.id = list[(j + dir + list.length) % list.length];
  MD.cmp = 0;
  need(BYID[MD.id].t);
  renderModal();
}
REFRESH_HOOKS.push(ids => { if (MD.id && (ids.has(MD.id) || ids.has(BYID[MD.id].p))) renderModal(); });

/* ==================================================================== start */
function navSpy() {
  const links = $$(".navlinks a"), map = {};
  links.forEach(a => { map[a.getAttribute("href").slice(1)] = a; });
  if (!("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { links.forEach(a => a.classList.remove("on")); const a = map[e.target.id]; if (a) a.classList.add("on"); }
  }), { rootMargin: "-45% 0px -50% 0px" });
  $$("main > section").forEach(s => io.observe(s));
}
function safe(f, name) { try { f(); } catch (e) { console.error(name, e); } }
function start() {
  icons(document);
  $$(".reveal").forEach(el => onVisible(el));
  safe(heroStats, "stats");
  safe(heroDemo, "hero");
  lazy("#sim-app", () => safe(simInit, "simulation"));
  lazy("#how-app", () => safe(howInit, "walkthrough"));
  lazy("#play-app", () => safe(plInit, "playground"));
  lazy("#spot-app", () => safe(spInit, "game"));
  lazy("#pairs-app", () => safe(pairsInit, "pairs"));
  lazy("#results-app", () => safe(resultsInit, "results"));
  lazy("#map-app", () => safe(mapInit, "map"));
  lazy("#gallery-app", () => safe(galleryInit, "gallery"));
  navSpy();
  setTimeout(() => need("featured"), 30);
  $("#m-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", e => { if (e.target === $("#modal")) closeModal(); });
  document.addEventListener("keydown", e => {
    if ($("#modal").hidden) return;
    if (e.key === "Escape") closeModal();
    if (e.key === "ArrowRight" && !e.target.closest(".knob")) modalStep(1);
    if (e.key === "ArrowLeft" && !e.target.closest(".knob")) modalStep(-1);
  });
  const fromHash = () => {
    const h = (location.hash || "").replace(/^#/, "");
    if (h.indexOf("=") < 0) return;
    const q = {};
    h.split("&").forEach(kv => { const p = kv.split("="); q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || ""); });
    if (q.only) $$("main > section").forEach(s => { if (s.id !== q.only) s.hidden = true; });
    if (q.only === "top") $$("main > section").forEach(s => { s.hidden = true; });
    if (q.item) openModal(q.item, q.b || "C");
  };
  window.addEventListener("hashchange", fromHash);
  fromHash();
}
start();
