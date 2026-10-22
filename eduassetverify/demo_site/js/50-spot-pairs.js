/* ==================================================================== spot the error */
const SP = { set: 0, round: 0, per: 8, bk: "C", res: [], tap: null, done: false };
function spItem() { const L = D.sel.game; return BYID[L[(SP.set * SP.per + SP.round) % L.length]]; }
function spInit() {
  const host = $("#spot-app");
  host.innerHTML =
    `<div class="spot-grid"><div><div class="spot-target" id="sp-target"></div>` +
    `<div class="mtools"><button class="btn rose sm" id="sp-fine">${icon("check")} Looks fine to me</button>` +
    `<span class="small muted" id="sp-hint">Tap the picture where it breaks its objective.</span></div></div>` +
    `<div><div class="ctl" style="margin-bottom:10px"><span class="lab">Compare with</span>${seg("sp-bk", BKS.map(b => [b, BKN[b]]), SP.bk)}</div>` +
    `<div class="score" id="sp-score"></div><div class="dots" id="sp-dots"></div>` +
    `<div class="small muted" id="sp-round"></div><div class="objective" id="sp-obj"></div><div id="sp-reveal"></div></div></div>`;
  onSeg("sp-bk", v => { SP.bk = v; spScore(); if (SP.done) spReveal(); });
  $("#sp-target").addEventListener("click", e => {
    if (SP.done) return;
    const r = e.currentTarget.getBoundingClientRect();
    SP.tap = [(e.clientX - r.left) / r.width * 512, (e.clientY - r.top) / r.height * 512];
    spReveal();
  });
  $("#sp-fine").addEventListener("click", () => { if (!SP.done) { SP.tap = null; spReveal(); } });
  spRound();
}
function spRound() {
  SP.done = false;
  SP.tap = null;
  const it = spItem();
  $("#sp-target").className = "spot-target";
  $("#sp-target").innerHTML = av(it, { bk: SP.bk, w: 0, g: 0, badge: 0, px: 460 });
  $("#sp-round").innerHTML = `Round ${SP.round + 1} of ${SP.per} \u00b7 set ${SP.set + 1} \u00b7 ${esc(TASKN[it.dm])}, ${esc(it.tn)} template, ${esc(STYLEN[it.st] || it.st)} style`;
  $("#sp-obj").innerHTML = `\u201c${esc(it.o)}\u201d`;
  $("#sp-reveal").innerHTML = "";
  $("#sp-fine").disabled = false;
  $("#sp-hint").textContent = "Tap the picture where it breaks its objective.";
  spDots();
  spScore();
}
function spDots() {
  $("#sp-dots").innerHTML = Array.from({ length: SP.per }, (_, j) => {
    const r = SP.res[j];
    return `<i class="${j === SP.round && !SP.done ? "cur" : r ? (r.hit ? "hit" : "miss") : ""}"></i>`;
  }).join("");
}
function spScore() {
  const done = SP.res.filter(Boolean), n = done.length;
  const caught = k => done.filter(r => BYID[r.i].v[SP.bk][k][0] === "I").length;
  const rev = done.filter(r => BYID[r.i].v[SP.bk].e[0] === "U").length;
  const f = x => n ? `${x} / ${n}` : "\u2013";
  $("#sp-score").innerHTML =
    `<div class="sc you"><b>${f(done.filter(r => r.hit).length)}</b><span>you found the error</span></div>` +
    ["d", "c", "s"].map(k => `<div class="sc judge"><b>${f(caught(k))}</b><span>${MNAME[k]} rejected it (pass 1)</span></div>`).join("") +
    `<div class="sc eav"><b>${f(caught("e"))}</b><span>EduAssetVerify rejected it${rev ? `, ${rev} sent to review` : ""} (pass 1)</span></div>`;
}
function spReveal() {
  const it = spItem(), bk = SP.bk;
  const fresh = !SP.done;
  SP.done = true;
  const gts = gtBoxes(it), wb = witnessOf(it, bk);
  const hitBoxes = gts.length ? gts : (wb ? [wb] : []);
  const pad = 18;
  const hit = !!SP.tap && hitBoxes.some(b => SP.tap[0] >= b[0] - pad && SP.tap[0] <= b[2] + pad && SP.tap[1] >= b[1] - pad && SP.tap[1] <= b[3] + pad);
  if (fresh) SP.res[SP.round] = { i: it.i, hit };
  const t = $("#sp-target");
  t.className = "spot-target done";
  t.innerHTML = av(it, { bk, w: 1, g: 1, badge: 0, px: 460, draw: 1 }) +
    (SP.tap ? `<span class="tapmark ${hit ? "hit" : "miss"}" style="left:${SP.tap[0] / 5.12}%;top:${SP.tap[1] / 5.12}%"></span>` : "");
  if (hit && fresh) confetti(t);
  $("#sp-fine").disabled = true;
  $("#sp-hint").innerHTML = `<span class="chip red">red: EduAssetVerify's witness</span> <span class="chip ghost">dashed: the perturbed region</span>`;
  const tg = new Set(it.tg), cmap = {};
  it.c.forEach(c => { cmap[c[0]] = c; });
  const broken = it.c.filter(c => tg.has(c[0])).map(c => `<code>${esc(c[1])}</code>: ${esc(c[2])}`).join("; ");
  const fails = (it.r[bk] || []).filter(r => r[1] === "F").map(r => `<code>${esc(r[0])} = F</code>${r[2] ? ` (value ${esc(r[2])})` : ""}`).join(", ");
  const unc = (it.r[bk] || []).filter(r => r[1] === "U").map(r => `<code>${esc(r[0])} = U</code>`).join(", ");
  const J = judgeAns(it, bk);
  const allV = ["d", "c", "s"].every(k => it.v[bk][k] === "VVV");
  const head = !SP.tap ? (allV ? `It looked fine to all three ${esc(BKN[bk])} judges too, in every pass. But:` : "It does look fine at first sight. But:")
    : hit ? "Nice catch!" : "Not quite. The error is elsewhere:";
  $("#sp-reveal").innerHTML = `<div class="reveal-box"><h4>${head}</h4>` +
    `<p style="margin:4px 0">${it.op.map(o => `<span class="chip red">${esc(OPN[o])}</span>`).join(" ")} breaks ${broken || "the objective"}.</p>` +
    `<p style="margin:4px 0" class="small">EduAssetVerify (${esc(BKN[bk])}, pass 1): ${fails ? `${fails} \u2192 <b>INVALID</b>` : unc ? `${unc} \u2192 <b>sent to review</b>` : "no violation found"}</p>` +
    vtable(it) +
    (J && J.c ? `<div class="quote"><b>${esc(BKN[bk])} CoT judge, pass 1</b>: \u201c${esc(J.c)}\u201d</div>` : "") +
    `<div class="mtools"><button class="btn primary sm" id="sp-next">${SP.round === SP.per - 1 ? "See your score" : "Next asset \u203a"}</button>` +
    `<button class="btn sm" id="sp-open">Open the full report</button></div></div>`;
  $("#sp-next").addEventListener("click", spNext);
  $("#sp-open").addEventListener("click", () => openModal(it.i, bk, D.sel.game));
  spDots();
  spScore();
}
function spNext() {
  if (SP.round < SP.per - 1) { SP.round++; spRound(); return; }
  const done = SP.res.filter(Boolean), you = done.filter(r => r.hit).length;
  const best = Math.max(...["d", "c", "s"].map(k => done.filter(r => BYID[r.i].v[SP.bk][k][0] === "I").length));
  const eav = done.filter(r => BYID[r.i].v[SP.bk].e[0] === "I").length;
  $("#sp-reveal").innerHTML = `<div class="reveal-box"><h4>${you >= best ? "You beat the best judge!" : "Well played!"}</h4>` +
    `<p>You found ${you} of ${done.length} errors. The best ${esc(BKN[SP.bk])} judge rejected ${best} of them in pass 1, and EduAssetVerify rejected ${eav}.</p>` +
    `<p class="small muted">These assets were chosen because a judge accepted them: on all 900 test assets, the judges' error rates are far lower (see the results).</p>` +
    `<button class="btn primary sm" id="sp-again">Play the next ${SP.per}</button></div>`;
  if (you >= best) confetti($("#sp-target"));
  $("#sp-again").addEventListener("click", () => { SP.set++; SP.round = 0; SP.res = []; spRound(); });
}

/* ==================================================================== counterfactual pairs: compare sliders */
function cmpHTML(left, right, o) {
  o = o || {};
  return `<div class="cmp" style="--x:50%">${av(left, Object.assign({ w: 0, badge: 0, px: 280 }, o.l || {}))}` +
    `<div class="top">${av(right, Object.assign({ w: 0, g: 1, badge: 0, px: 280 }, o.r || {}))}</div>` +
    `<div class="bar"></div><div class="knob" tabindex="0" aria-label="drag to compare"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l-6 6 6 6M15 6l6 6-6 6"/></svg></div>` +
    `<span class="lab l">${esc(o.ll || "correct")}</span><span class="lab r">${esc(o.rl || "violated")}</span></div>`;
}
function cmpBind(root) {
  $$(".cmp", root).forEach(c => {
    if (c.getAttribute("data-bound")) return;
    c.setAttribute("data-bound", "1");
    let drag = false;
    const set = e => { const r = c.getBoundingClientRect(); c.style.setProperty("--x", clamp((e.clientX - r.left) / r.width * 100, 0, 100) + "%"); };
    c.addEventListener("pointerdown", e => { drag = true; c.setPointerCapture(e.pointerId); set(e); });
    c.addEventListener("pointermove", e => { if (drag) set(e); });
    c.addEventListener("pointerup", () => { drag = false; });
    c.addEventListener("pointercancel", () => { drag = false; });
    const k = $(".knob", c);
    k.addEventListener("keydown", e => {
      const x = parseFloat(c.style.getPropertyValue("--x")) || 50;
      if (e.key === "ArrowLeft") c.style.setProperty("--x", clamp(x - 5, 0, 100) + "%");
      if (e.key === "ArrowRight") c.style.setProperty("--x", clamp(x + 5, 0, 100) + "%");
    });
  });
}
function cmpSweep(c) {
  if (REDUCED) return;
  const t0 = performance.now(), dur = 2600;
  const f = t => {
    const p = clamp((t - t0) / dur, 0, 1);
    c.style.setProperty("--x", (50 + 36 * Math.sin(p * Math.PI * 2)) + "%");
    if (p < 1) requestAnimationFrame(f); else c.style.setProperty("--x", "50%");
  };
  requestAnimationFrame(f);
}
function pairsInit() {
  const host = $("#pairs-app");
  host.innerHTML = D.sel.pairs.map(p => {
    const op = p[0], ci = BYID[p[1]], vi = BYID[p[2]];
    const tgt = vi.c.filter(c => vi.tg.includes(c[0])).map(c => c[1]);
    const flips = tgt.map(name => {
      const a = (ci.r.C || []).find(r => r[0] === name), b = (vi.r.C || []).find(r => r[0] === name);
      return `<span class="fl"><code>${esc(name)}</code>${a ? stChip(a[1]) : "?"}<span>\u2192</span>${b ? stChip(b[1]) : "?"}</span>`;
    }).join(" ");
    return `<div class="card pair reveal" data-op="${esc(op)}"><h4>${esc(OPN[op])} <small>${esc(TASKN[vi.dm])} \u00b7 ${esc(vi.tn)}</small></h4>` +
      cmpHTML(ci, vi) +
      `<div class="flip"><span>${flips}</span><button class="btn sm" data-open="${vi.i}">Open ${icon("search")}</button></div>` +
      `<div class="small muted">perturbed constraint: EduAssetVerify's status, correct \u2192 violated (Claude, pass 1)</div></div>`;
  }).join("");
  cmpBind(host);
  host.addEventListener("click", e => { const b = e.target.closest("button[data-open]"); if (b) openModal(b.getAttribute("data-open"), "C"); });
  $$(".pair", host).forEach((card, j) => onVisible(card, () => setTimeout(() => cmpSweep($(".cmp", card)), 200 + j * 120)));
}
