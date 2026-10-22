/* ==================================================================== hero: key numbers and the game-card scenario */
function heroStats() {
  const fa = R.fa, n = R.n_violated_evals;
  const rng = b => {
    const v = ["direct", "cot", "structured"].map(k => fa[b][k]);
    const lo = Math.min(...v), hi = Math.max(...v);
    return lo === hi ? String(lo) : `${lo}\u2013${hi}`;
  };
  const zero = PAPER.every(b => fa[b].eav === 0);
  const names = PAPER.map(b => BKN[b]).join(" \u00b7 ");
  $("#stats").innerHTML =
    `<div class="stat">${icon("ruler")}<b>${zero ? `0 <small>of</small> <em data-count="${n}">${fmtInt(n)}</em>` : PAPER.map(b => fa[b].eav).join(" \u00b7 ")}</b>` +
    `<span>violated test evaluations accepted by EduAssetVerify${zero ? ", under each backbone" : ` (${names})`}</span></div>` +
    `<div class="stat judge">${icon("robot")}<b>${PAPER.map(rng).join(" \u00b7 ")}</b><span>of ${fmtInt(n)} accepted by the three VLM judges (${names})</span></div>` +
    `<div class="stat rev">${icon("teacher")}<b>${PAPER.map(b => R.abstention[b] + "%").join(" \u00b7 ")}</b><span>of test assets sent to a person for review instead (${names})</span></div>`;
  $$("[data-count]", $("#stats")).forEach(el => onVisible(el, () => countUp(el)));
}

const HS = { gate: "e", bk: "C", run: 0, shown: null, live: false };
function heroDemo() {
  const host = $("#hero-demo");
  const cons = {};
  WT.constraints.forEach(c => { cons[c[0]] = c[1]; });
  const k = cons.colored_part_count, n = cons.part_count, f = String(cons.fraction_value);
  const answers = [f, `${n - k}/${n}`, `${k}/${n - k}`].filter((a, i, all) => all.indexOf(a) === i);
  host.innerHTML =
    `<div class="demo-head"><h3><span class="chip">Scenario</span> One game card, two gates</h3>${seg("hd-bk", BKS.map(b => [b, BKN[b]]), HS.bk)}</div>` +
    `<div class="demo-ctl"><span class="lab small muted" style="font-weight:800">GATE</span>${seg("hd-gate", [["d", `${icon("robot")} VLM judge (direct)`], ["e", `${icon("ruler")} EduAssetVerify`]], HS.gate)}` +
    `<button class="btn sm" id="hd-replay">${icon("reset")} Replay</button></div>` +
    `<div class="tablet"><div class="screen" id="hd-screen">` +
    `<div class="game-top"><span>Fraction quiz \u00b7 level 3</span><span class="stars">\u2605\u2605\u2606</span></div>` +
    `<div class="game-body"><div class="game-img"><div id="hd-img"></div><div class="stamp" id="hd-stamp"></div></div>` +
    `<div><div class="game-q">This circle has <b>${n} equal parts</b>, and <b>${k}</b> of them are colored. Which fraction is colored?</div>` +
    `<div class="answers" id="hd-ans">${answers.map(a => `<button data-a="${esc(a)}">${esc(a)}</button>`).join("")}</div>` +
    `<div class="game-fb" id="hd-fb"></div></div></div>` +
    `<div class="bubble" id="hd-bubble"></div></div></div>` +
    `<div class="gate-line"><span class="gate-badge" id="hd-badge"></span><span id="hd-msg"></span></div>` +
    `<p class="demo-note">Illustration with the recorded verdicts of pass 1. The card shows the test asset of the paper's first figure; in production it would
      come from an image generator. The retry shows the correct asset of the same benchmark pair.</p>`;
  onSeg("hd-bk", v => { HS.bk = v; heroPlay(); });
  onSeg("hd-gate", v => { HS.gate = v; heroPlay(); });
  $("#hd-replay").addEventListener("click", heroPlay);
  $("#hd-ans").addEventListener("click", e => {
    const b = e.target.closest("button[data-a]");
    if (!b) return;
    const fb = $("#hd-fb"), tz = BYID[WT.item];
    b.classList.add("bump");
    setTimeout(() => b.classList.remove("bump"), 400);
    if (!HS.live) { fb.innerHTML = "This card is held back, so no learner sees it."; return; }
    if (b.getAttribute("data-a") === f)
      fb.innerHTML = HS.shown === tz.i
        ? `<b style="color:var(--red)">Yes, ${k} of ${n} parts are colored.</b> But these parts are not equal, so the picture calls unequal parts eighths.`
        : `<b style="color:var(--purple)">Yes! ${k} of ${n} equal parts are colored.</b>`;
    else fb.innerHTML = "Not quite: count the colored parts, then all the parts.";
  });
  onVisible(host, heroPlay);
}
function heroShow(it, o) {
  HS.shown = it.i;
  const c = D.crops[it.i];
  $("#hd-img").innerHTML = av(it, Object.assign({ bk: HS.bk, w: 0, badge: 0, px: c ? 230 * 512 / (c[2] - c[0]) : 230, crop: c }, o || {}));
}
function heroStamp(kind, text) {
  const s = $("#hd-stamp");
  s.className = "stamp " + kind;
  s.textContent = text;
  void s.offsetWidth;
  s.classList.add("show");
}
function heroBubble(text, purple) {
  const b = $("#hd-bubble");
  b.className = "bubble" + (purple ? " purple" : "");
  b.innerHTML = text;
  void b.offsetWidth;
  b.classList.add("show");
}
async function heroPlay() {
  const run = ++HS.run, alive = () => run === HS.run;
  const tz = BYID[WT.item], pt = BYID[tz.p], gate = HS.gate, bk = HS.bk;
  const who = gate === "e" ? "EduAssetVerify" : `The direct judge (${BKN[bk]})`;
  const badge = $("#hd-badge"), msg = $("#hd-msg");
  const busy = on => { badge.className = "gate-badge" + (gate === "e" ? " eav" : "") + (on ? " busy" : ""); badge.innerHTML = gate === "e" ? I.ruler : I.robot; };
  $("#hd-stamp").className = "stamp";
  $("#hd-bubble").className = "bubble";
  $("#hd-fb").innerHTML = "";
  HS.live = false;
  heroShow(tz);
  busy(true);
  msg.innerHTML = `${who} is checking the card\u2026`;
  await sleep(1100);
  if (!alive()) return;
  busy(false);
  const v = tz.v[bk][gate][0];
  const big = Math.round((WT.spec_ratio - 1) * 100);
  if (v === "V") {
    HS.live = true;
    heroStamp(gate === "e" ? "ok" : "judge", "Approved");
    const big1 = gtBoxes(tz).slice().sort((a, b) => (b[2] - b[0]) * (b[3] - b[1]) - (a[2] - a[0]) * (a[3] - a[1]))[0];
    heroShow(tz, { g: 1, gb: big1 ? [big1] : null });
    msg.innerHTML = `<b>${who} accepted the card</b> (pass 1), so it reaches learners. Try an answer on the tablet.`;
    heroBubble(`Approved, but the dashed part is ${big}% larger than an equal part: learners see unequal parts called eighths.`, false);
    return;
  }
  if (v === "U") {
    heroStamp("rev", "To review");
    msg.innerHTML = `<b>${who} could not decide</b> (pass 1), so a teacher checks the card before any learner sees it.`;
    return;
  }
  heroStamp("bad", "Held back");
  if (gate === "e") {
    heroShow(tz, { w: 1, draw: 1 });
    heroBubble(`<code>equal_area = F</code>: the parts' areas deviate by d = ${WT.measurement.deviation.toFixed(2)} (F from ${Z.equal_area[1].toFixed(2)}). ` +
      `The boxed part is ${big}% larger than an equal part.`, true);
    msg.innerHTML = `<b>EduAssetVerify rejected the card</b> (pass 1) and points at the part that breaks it. The generator tries again.`;
  } else {
    msg.innerHTML = `<b>${who} rejected the card</b> (pass 1), with no evidence of where it breaks. The generator tries again.`;
  }
  await sleep(3400);
  if (!alive()) return;
  $("#hd-stamp").className = "stamp";
  $("#hd-bubble").className = "bubble";
  heroShow(pt);
  busy(true);
  msg.innerHTML = "A new card from the generator: checking\u2026";
  await sleep(1100);
  if (!alive()) return;
  busy(false);
  const v2 = pt.v[bk][gate][0];
  if (v2 === "V") {
    HS.live = true;
    heroStamp(gate === "e" ? "ok" : "judge", "Approved");
    msg.innerHTML = `<b>Approved</b> (pass 1): all parts are equal now, and this card reaches learners.`;
  } else if (v2 === "U") {
    heroStamp("rev", "To review");
    msg.innerHTML = `${who} could not decide on this correct card (pass 1), so a teacher checks it first.`;
  } else {
    heroStamp("bad", "Held back");
    msg.innerHTML = `${who} rejected this correct card too (pass 1): a false rejection.`;
  }
}

/* ==================================================================== simulation: a batch through a gate */
const SIM = { g: "d", bk: "C", p: 0, run: 0 };
function simInit() {
  const host = $("#sim-app");
  host.innerHTML =
    `<div class="ctl">` +
    `<div class="grp"><span class="lab">Gate</span>${seg("sm-g", METH.map(m => [m[0], m[1]]), SIM.g)}</div>` +
    `<div class="grp"><span class="lab">Backbone</span>${seg("sm-b", BKS.map(b => [b, BKN[b]]), SIM.bk)}</div>` +
    `<div class="grp"><span class="lab">Pass</span>${seg("sm-p", [[0, "1"], [1, "2"], [2, "3"]], SIM.p)}</div>` +
    `<div class="grp" style="margin-left:auto"><button class="btn primary sm" id="sm-run">${icon("play")} Run the batch</button>` +
    `<button class="btn sm" id="sm-skip">${icon("skip")} Skip to the end</button></div></div>` +
    `<div class="sim-stage" id="sm-stage">` +
    `<div class="sim-zone sim-gen"><span class="zi">${I.factory}</span><h4>Generator</h4><span class="small muted" id="sm-left"></span></div>` +
    `<div class="belt" id="sm-belt"></div>` +
    `<div class="sim-zone sim-gate" id="sm-gate"><span class="zi" id="sm-gi"></span><h4 id="sm-gn"></h4></div>` +
    `<div class="bins">` +
    `<div class="bin ship" data-k="ship"><span class="zi">${I.tablet}</span><h4>To learners <span class="n">0</span></h4><div class="stack"></div></div>` +
    `<div class="bin back" data-k="back"><span class="zi">${I.back}</span><h4>Back to the generator <span class="n">0</span></h4><div class="stack"></div></div>` +
    `<div class="bin rev" data-k="rev"><span class="zi">${I.teacher}</span><h4>Teacher review <span class="n">0</span></h4><div class="stack"></div></div>` +
    `</div></div>` +
    `<div class="sim-tally" id="sm-tally"></div>` +
    `<div class="fullset" id="sm-full"></div>` +
    `<details class="rule"><summary>How the batch of ${D.sel.sim.length} was picked</summary><p>By rule, to show every route: 6 violated assets that all three
      Claude judges accepted in pass 1 (the paper's first-figure asset first, then by item id); 4 correct assets that every method accepted in every pass
      under both backbones; 3 violated assets that every method rejected in every pass under both backbones; 2 assets that EduAssetVerify (Claude) sent to
      review in pass 1; and 1 correct asset that a Claude judge rejected in pass 1. The last four groups take one asset per task and template in turn, by
      item id. The batch therefore over-represents judge failures; the bar above counts all 900 test assets.</p></details>`;
  const rerun = () => { simReset(); simFull(); };
  onSeg("sm-g", v => { SIM.g = v; rerun(); });
  onSeg("sm-b", v => { SIM.bk = v; rerun(); });
  onSeg("sm-p", v => { SIM.p = +v; rerun(); });
  $("#sm-run").addEventListener("click", () => simRun(false));
  $("#sm-skip").addEventListener("click", () => simRun(true));
  simReset();
  simFull();
  onVisible(host, () => setTimeout(() => { if (!SIM.started) simRun(false); }, 400));
}
function simGate() {
  const e = SIM.g === "e";
  $("#sm-gate").classList.toggle("eav", e);
  $("#sm-gi").innerHTML = e ? I.ruler : I.robot;
  $("#sm-gn").textContent = MNAME[SIM.g];
}
function simReset() {
  SIM.run++;
  simGate();
  const stage = $("#sm-stage");
  $$(".token", stage).forEach(t => t.remove());
  $$(".bin", stage).forEach(b => { $(".stack", b).innerHTML = ""; $(".n", b).textContent = "0"; });
  $("#sm-belt").classList.remove("run");
  const ids = D.sel.sim;
  ids.slice().reverse().forEach((iid, r) => {
    const i = ids.length - 1 - r, it = BYID[iid];
    const t = document.createElement("div");
    t.className = "token";
    t.setAttribute("data-i", iid);
    t.innerHTML = av(it, { w: 0, badge: 0, px: 66 }) + `<span class="tv"></span>`;
    t.style.transform = `translate(${22 + (i % 4) * 7}px, ${96 + Math.min(i, 8) * 9}px)`;
    t.style.zIndex = String(40 - i);
    stage.appendChild(t);
  });
  $("#sm-left").textContent = `${ids.length} cards waiting`;
  SIM.c = { ship: 0, fa: 0, back: 0, fr: 0, rev: 0, n: 0 };
  simTally();
}
function simTally() {
  const c = SIM.c, nv = D.sel.sim.filter(i => BYID[i].y === "I").length, nc = D.sel.sim.length - nv;
  $("#sm-tally").innerHTML =
    `<div class="tally${c.fa ? " alarm" : ""}"><b>${c.fa}</b><span>violated cards that reached learners (of ${nv} violated in the batch)</span></div>` +
    `<div class="tally"><b>${c.fr}</b><span>correct cards sent back: false rejections (of ${nc} correct)</span></div>` +
    `<div class="tally"><b>${c.rev}</b><span>cards a teacher has to check</span></div>`;
}
const binOf = v => v === "V" ? "ship" : v === "I" ? "back" : "rev";
function simLand(it, v) {
  const k = binOf(v), bin = $(`#sm-stage .bin[data-k="${k}"]`);
  const flag = k === "ship" && it.y === "I", fr = k === "back" && it.y === "V";
  const m = document.createElement("span");
  m.className = "mini" + (flag ? " flag" : "") + (fr ? " fr" : "");
  m.setAttribute("data-i", it.i);
  m.title = `${it.y === "V" ? "correct" : "violated"} asset, ${VNAME[v]}`;
  m.innerHTML = av(it, { w: 0, badge: 0, px: 40 });
  $(".stack", bin).appendChild(m);
  const n = $(".n", bin);
  n.textContent = String(+n.textContent + 1);
  const c = SIM.c;
  c.n++;
  if (k === "ship") c[it.y === "I" ? "fa" : "ship"]++;
  else if (k === "back") c[it.y === "V" ? "fr" : "back"]++;
  else c.rev++;
  simTally();
  $("#sm-left").textContent = `${D.sel.sim.length - c.n} cards waiting`;
}
async function simRun(instant) {
  SIM.started = true;
  simReset();
  const run = SIM.run, alive = () => run === SIM.run;
  const stage = $("#sm-stage"), belt = $("#sm-belt"), gi = $("#sm-gi");
  const tokens = D.sel.sim.map(iid => $(`.token[data-i="${iid}"]`, stage));
  const W = stage.clientWidth, H = stage.clientHeight, narrow = W < 600;
  const gx = narrow ? W - 140 : W / 2 - 33, gy = narrow ? 120 : 126;
  if (!instant) belt.classList.add("run");
  for (const t of tokens) {
    if (!alive()) return;
    const it = BYID[t.getAttribute("data-i")], v = it.v[SIM.bk][SIM.g][SIM.p];
    if (instant) { t.remove(); simLand(it, v); continue; }
    t.style.zIndex = "60";
    t.style.transform = `translate(${narrow ? 30 : 150}px, ${gy}px)`;
    await sleep(380);
    if (!alive()) return;
    t.style.transform = `translate(${gx}px, ${gy}px)`;
    await sleep(560);
    if (!alive()) return;
    gi.classList.add("busy");
    await sleep(260);
    gi.classList.remove("busy");
    const tv = $(".tv", t);
    tv.className = "tv " + v;
    tv.textContent = v === "V" ? "valid" : v === "I" ? "invalid" : v === "U" ? "review" : "no answer";
    t.classList.add("verdict");
    if (v === "V" && it.y === "I") t.classList.add("flag");
    await sleep(240);
    if (!alive()) return;
    const bin = $(`.bin[data-k="${binOf(v)}"]`, stage), br = bin.getBoundingClientRect(), sr = stage.getBoundingClientRect();
    t.style.transform = `translate(${br.left - sr.left + br.width / 2 - 33}px, ${br.top - sr.top + br.height / 2 - 33}px) scale(0.55)`;
    t.style.opacity = "0.2";
    setTimeout(() => { if (!alive()) return; t.remove(); simLand(it, v); }, 620);
  }
  setTimeout(() => { if (alive()) belt.classList.remove("run"); }, 700);
}
function simFull() {
  const c = { ship: 0, fa: 0, back: 0, fr: 0, rev: 0, na: 0 };
  D.items.forEach(it => {
    const v = it.v[SIM.bk][SIM.g][SIM.p];
    if (v === "V") c[it.y === "V" ? "ship" : "fa"]++;
    else if (v === "I") c[it.y === "I" ? "back" : "fr"]++;
    else if (v === "U") c.rev++;
    else c.na++;
  });
  const parts = [["ship", "sb-ship", "correct, to learners"], ["fa", "sb-fa", "violated, to learners"], ["back", "sb-back", "violated, sent back"],
    ["fr", "sb-fr", "correct, sent back"], ["rev", "sb-rev", "to review"], ["na", "sb-na", "no answer"]];
  const sb = parts.map(p => `<div class="${p[1]}" style="flex-grow:${c[p[0]]}" title="${c[p[0]]} ${p[2]}">${c[p[0]] >= 40 ? c[p[0]] : ""}</div>`).join("");
  $("#sm-full").innerHTML =
    `<h4>All 900 test assets through ${SIM.g === "e" ? "EduAssetVerify" : "the " + esc(MNAME[SIM.g].toLowerCase())} (${esc(BKN[SIM.bk])}, pass ${SIM.p + 1})</h4><div class="stackbar">${sb}</div>` +
    `<div class="legend">${parts.filter(p => c[p[0]] || p[0] === "fa").map(p => `<span><i class="${p[1]}"></i>${c[p[0]]} ${p[2]}</span>`).join("")}</div>` +
    `<p class="small" style="margin:8px 0 0">${c.fa ? `<b style="color:var(--red)">${c.fa} violated assets would reach learners in this pass.</b>` :
      `<b style="color:var(--purple)">No violated asset reaches learners in this pass.</b>`} ` +
    `${c.rev ? `${c.rev} go to a teacher for review. ` : ""}${c.fr ? `${c.fr} correct assets are sent back.` : ""}</p>`;
}
