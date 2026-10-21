/* EduAssetVerify demo page. Reads window.EAV (data.js, generated from the experiment records) and
   the test images, one script per template (thumbs/<template>.js, loaded when first needed). It uses
   no fetch and stores nothing, so it also runs as a sandboxed page; the few requests it makes keep it
   within the request limit of the anonymous mirror. */
(function () {
  "use strict";
  var D = window.EAV;
  if (!D) {
    document.body.insertAdjacentHTML("afterbegin", "<p style='padding:20px'>The result data (data.js) did not load.</p>");
    return;
  }

  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmtInt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  var BKN = {};
  D.backbones.forEach(function (b) { BKN[b[0]] = b[1]; });
  var BKS = D.backbones.map(function (b) { return b[0]; });          // display order: Claude, Gemini
  var PAPER = D.results.order.map(function (name) {                   // paper order: Gemini, Claude
    return BKS.filter(function (k) { return BKN[k] === name; })[0];
  });
  var OPN = {}, OPT = {};
  D.operators.forEach(function (o) { OPN[o[0]] = o[1]; OPT[o[0]] = o[2]; });
  var CONDN = {};
  D.conditions.forEach(function (c) { CONDN[c[0]] = c[1]; });
  var BYID = {};
  D.items.forEach(function (it) { BYID[it.i] = it; });
  var METH = [["d", "Direct judge"], ["c", "CoT judge"], ["s", "Structured judge"], ["e", "EduAssetVerify"]];
  var SYM = { V: "\u2713", I: "\u2717", U: "?", X: "\u2013" };
  var VNAME = { V: "valid", I: "invalid", U: "uncertain: sent to review", X: "no parsable answer" };
  var TASKN = { fraction: "Fraction", counting: "Counting", spatial: "Spatial" };
  var STYLEN = { flat_blue: "flat blue", flat_green: "flat green", flat_orange: "flat orange", dark: "dark",
    paper: "paper", pastel_thick: "pastel, thick", sketch: "sketch" };

  function cls(v, y) { return (v === "U" || v === "X") ? "rev" : (v === y ? "ok" : "bad"); }
  function passes(s, y) {
    return '<span class="pg">' + s.split("").map(function (v, k) {
      return '<i class="pass ' + cls(v, y) + '" title="pass ' + (k + 1) + ": " + VNAME[v] + '">' + SYM[v] + "</i>";
    }).join("") + "</span>";
  }
  function box(c, b) {
    return '<span class="' + c + '" style="left:' + (100 * b[0]).toFixed(2) + "%;top:" + (100 * b[1]).toFixed(2) +
      "%;width:" + (100 * (b[2] - b[0])).toFixed(2) + "%;height:" + (100 * (b[3] - b[1])).toFixed(2) + '%"></span>';
  }
  function witness(it, b) {
    var r = it.r[b] || [];
    for (var k = 0; k < r.length; k++) if (r[k][1] === "F" && r[k][4]) return r[k][4];
    return null;
  }
  function gtBoxes(it) {
    var out = [];
    (it.tg || []).forEach(function (t) { (it.g[t] || []).forEach(function (b) { if (b) out.push(b); }); });
    return out;
  }
  /* test images: thumbs/<template>.js calls EAV_THUMBS(template, {item id: data URI}) */
  var TH = {}, REQ = {}, BLANK = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  function src(it) { return (TH[it.t] && TH[it.t][it.i]) || D.embedded[it.i] || ""; }
  function need(t) {
    if (TH[t] || REQ[t]) return;
    REQ[t] = "loading";
    var el = document.createElement("script");
    el.src = "thumbs/" + encodeURIComponent(t) + ".js";
    el.onerror = function () {
      REQ[t] = "failed";
      [].forEach.call(document.querySelectorAll('img[data-t="' + t + '"]'), function (im) {
        if (im.parentNode) im.parentNode.className = im.parentNode.className.replace(" wait", "") + " fail";
      });
    };
    document.head.appendChild(el);
  }
  window.EAV_THUMBS = function (t, map) {
    TH[t] = map;
    [].forEach.call(document.querySelectorAll('img[data-t="' + t + '"]'), function (im) {
      var u = map[im.getAttribute("data-i")];
      if (u) { im.src = u; im.parentNode.className = im.parentNode.className.replace(" wait", ""); }
    });
  };
  function shot(it, b, o) {
    o = o || {};
    var u = src(it);
    if (!u) need(it.t);
    var h = '<div class="shot' + (u ? "" : REQ[it.t] === "failed" ? " fail" : " wait") + '"><img src="' + (u || BLANK) +
      '" alt="' + esc(it.o) + '" width="320" height="320" data-t="' + esc(it.t) + '" data-i="' + esc(it.i) + '">';
    if (o.gt) gtBoxes(it).forEach(function (g) { h += box("gbox", g); });
    var w = o.witness === false ? null : witness(it, b);
    if (w) h += box("wbox", w);
    if (o.badge !== false) h += '<span class="badge ' + (it.y === "V" ? "ok" : "bad") + '">' + (it.y === "V" ? "Correct" : "Violated") + "</span>";
    return h + "</div>";
  }
  function stChip(s) { return '<span class="st ' + esc(s) + '">' + esc(s) + "</span>"; }

  /* ------------------------------------------------------------------ overview */
  function overview() {
    var R = D.results, n = fmtInt(R.n_violated_evals);
    var eavFa = PAPER.map(function (b) { return R.fa[b].eav; });
    var judgeFa = PAPER.map(function (b) {
      var v = [R.fa[b].direct, R.fa[b].cot, R.fa[b].structured];
      var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
      return lo === hi ? String(lo) : lo + "\u2013" + hi;
    });
    var names = PAPER.map(function (b) { return BKN[b]; }).join(" \u00b7 ");
    var allZero = eavFa.every(function (x) { return x === 0; });
    $("#tiles").innerHTML =
      '<div class="tile"><b>' + (allZero ? "0 of " + n : eavFa.join(" \u00b7 ")) + "</b><span>violated test evaluations accepted by EduAssetVerify" +
      (allZero ? ", under each backbone" : " (" + names + ")") + "</span></div>" +
      '<div class="tile judge"><b>' + judgeFa.join(" \u00b7 ") + "</b><span>of " + n + " accepted by the three VLM judges under " + names + "</span></div>" +
      '<div class="tile"><b>' + PAPER.map(function (b) { return R.abstention[b] + "%"; }).join(" \u00b7 ") +
      "</b><span>of test assets EduAssetVerify sent to review instead (" + names + ")</span></div>";

    var W = D.walkthrough, it = BYID[W.item];
    var jC = it.v.C, jG = it.v.G;
    $("#teaser").innerHTML =
      '<div class="shot" style="max-width:300px;margin:0 auto"><img src="' + esc(W.asset) + '" alt="test asset" width="322" height="322">' +
      box("wbox", W.witness) + "</div>" +
      '<table class="mini"><tr><th></th>' + BKS.map(function (b) { return "<th>" + esc(BKN[b]) + "</th>"; }).join("") + "</tr>" +
      METH.map(function (m) {
        return "<tr" + (m[0] === "e" ? ' class="ours"' : "") + "><td>" + m[1] + "</td>" +
          BKS.map(function (b) { return "<td>" + passes(it.v[b][m[0]], it.y) + "</td>"; }).join("") + "</tr>";
      }).join("") + "</table>" +
      "<figcaption>A test asset meant to show " + esc(fractionOf(W.objective)) + " in equal parts; one part is " +
      Math.round(100 * (W.spec_ratio - 1)) + "% too large. Each judge gives three verdicts (one per pass); the red box is the witness that " +
      "EduAssetVerify reported. " + (jC.d + jC.c + jC.s === "VVVVVVVVV" ? "With Claude Sonnet 5, all three judges accepted it in every pass. " : "") +
      (jG.d + jG.c + jG.s === "IIIIIIIII" ? "With Gemini 3.5 Flash, none did. " : "") +
      '<a href="#walkthrough">Follow it through every module.</a></figcaption>';
  }
  function fractionOf(o) { var m = /fraction (\d+\/\d+)/.exec(o); return m ? m[1] : "the fraction"; }

  /* ------------------------------------------------------------------ walkthrough */
  function mod(kind, title, body, tag) {
    return '<div class="mod ' + kind + '"><span class="chip">' + esc(title) + "</span>" + (tag ? '<span class="tag">' + esc(tag) + "</span>" : "") + body + "</div>";
  }
  function walkthrough() {
    var W = D.walkthrough, it = BYID[W.item], cons = {};
    W.constraints.forEach(function (c) { cons[c[0]] = c[1]; });
    $("#wt-lead").innerHTML = "The test asset of the first figure of the paper, under " + esc(W.backbone) +
      " in the first pass. Every box shows what the module produced: model answers as returned (pretty-printed), " +
      "measurements and rule decisions as recorded. Pink modules query a model; purple modules are deterministic.";
    var k = cons.colored_part_count, n = cons.part_count, f = cons.fraction_value;
    var M = W.measurement, z = W.zones;
    var rules = '<table class="rules">' + W.rules.map(function (r) {
      return "<tr><td>" + esc(r[0]) + "</td><td>" + esc(r[0] === "equal_area" ? "d = " + r[1] : r[1]) + "</td><td>" + stChip(r[2]) + "</td></tr>";
    }).join("") + "</table>";
    var mins = W.rules.map(function (r) { return r[2]; });
    var verdictPills = '<div class="pills">' + ["VALID", "INVALID", "UNCERTAIN"].map(function (v) {
      return '<div class="pill' + (v === W.verdict ? " on" : "") + '">' + v + "</div>";
    }).join("") + "</div>";
    var failed = W.rules.filter(function (r) { return r[2] === "F"; }).map(function (r) { return r[0] + " = F"; }).join(", ");
    $("#wt").innerHTML =
      mod("io", "Learning objective", "<p><q>" + esc(W.objective) + "</q></p>") +
      mod("model", "Constraint parser", "<p>Answer of the language model (the verifier's backbone):</p><pre class='code'>" + esc(W.parser_answer) + "</pre>" +
        (W.parser_same_everywhere ? "<p class='note'>The same four constraints in all three passes and under both backbones.</p>" : ""), "queries a model") +
      mod("det", "Consistency check", "<p>" + esc(k) + " colored \u2264 " + esc(n) + " parts \u2713</p><p>" + esc(f) + " = " + esc(k) + " colored / " + esc(n) + " parts \u2713</p>" +
        "<p class='note'>A contradictory objective, such as one third shown as one of four equal parts, is rejected here, before any image is verified.</p>", "deterministic") +
      mod("io", "Asset to verify", '<div class="shot"><img src="' + esc(W.asset) + '" alt="test asset" width="322" height="322"></div>' +
        "<p class='note'>Benchmark test asset, " + esc(STYLEN[it.st] || it.st) + " style (" + esc(CONDN[it.sp]) + ").</p>") +
      mod("model", "Value-blind grounding \u00d7" + W.readings, "<p>The prompt names what to look for, never the target values (no 8, no 2):</p>" +
        "<details><summary>Grounding prompt</summary><pre class='code'>" + esc(W.grounding_prompt) + "</pre></details>" +
        "<p>Answer of reading 1 of " + W.readings + ":</p><pre class='code'>" + esc(W.grounding_answer) + "</pre>", "queries a model") +
      mod("det", "Measurement", '<div class="shot" style="background:#fff"><img src="' + esc(W.regions) + '" alt="measured regions" width="322" height="322"></div>' +
        "<p>" + M.regions + " regions, " + M.colored + " colored. Largest part \u00d7" + M.largest.toFixed(2) + ", smallest \u00d7" + M.smallest.toFixed(2) +
        " of the mean area: deviation d = " + M.deviation.toFixed(2) + ".</p><p class='note'>Regions are bounded by color edges inside the box the VLM reported; the operator knows nothing about the palette.</p>", "deterministic") +
      mod("model", "Semantic re-reading", "<p class='note'>Labels are re-read from a crop, categories from a numbered montage of the grounded objects. This asset has neither, so the module was not triggered.</p>", "not triggered here").replace('class="mod model"', 'class="mod model" style="border-style:dashed;opacity:.8"') +
      mod("det", "Three-valued rules", rules + "<p class='note'>equal_area: T if d \u2264 " + z.equal_area[0].toFixed(2) + ", F if d \u2265 " + z.equal_area[1].toFixed(2) +
        ", U otherwise. " + esc(W.agree) + " readings agree, q = 1.0 \u2265 \u03c4 = " + z.tau + ".</p><p><b>min(" + mins.join(", ") + ") = " +
        mins.reduce(function (a, s) { return ({ F: 0, U: 1, T: 2 })[s] < ({ F: 0, U: 1, T: 2 })[a] ? s : a; }, "T") + "</b> &nbsp;(F &lt; U &lt; T)</p>", "deterministic") +
      mod("io", "Verdict + report", verdictPills + "<p><code>" + esc(failed) + "</code>, witness:</p>" +
        '<div class="shot"><img src="' + esc(W.asset) + '" alt="witness" width="322" height="322">' + box("wbox", W.witness) + "</div>" +
        (W.same_verdict_gemini ? "<p class='note'>Gemini 3.5 Flash as backbone yields the same verdict.</p>" : ""));

    $("#wt-judges").innerHTML = BKS.map(function (b) {
      var J = W.judges[b] || {}, v = it.v[b];
      var req = (J.structured && J.structured.requirements) || [];
      return '<div class="jcol"><h4>' + esc(BKN[b]) + " judges</h4>" +
        '<div class="jans"><b>Direct</b>: ' + esc((J.direct || {}).verdict) + ' &nbsp;<span class="note">passes 1\u20133:</span> ' + passes(v.d, it.y) + "</div>" +
        '<div class="jans"><b>CoT</b>: <q>' + esc((J.cot || {}).reasoning) + "</q> \u2192 " + esc((J.cot || {}).verdict) + " &nbsp;" + passes(v.c, it.y) + "</div>" +
        '<div class="jans"><b>Structured</b>: ' + req.map(function (q, i) {
          return "requirement " + (q.number || i + 1) + " " + (q.satisfied ? "\u2713" : "\u2717");
        }).join(", ") + " \u2192 " + esc((J.structured || {}).verdict) + " &nbsp;" + passes(v.s, it.y) + "</div></div>";
    }).join("");
  }

  /* ------------------------------------------------------------------ browser */
  var PAGE = 60;
  var S = { b: "C", show: "all", dm: "all", sp: "all", op: "all", y: "all", n: PAGE };
  var SHOWS = [
    ["all", "All test assets"],
    ["judge-fa", "A judge accepted a violated asset"],
    ["ours-catch", "A judge accepted it, EduAssetVerify rejected it in every pass"],
    ["ours-fa", "EduAssetVerify accepted a violated asset"],
    ["ours-review", "EduAssetVerify sent the asset to review"],
    ["ours-fr", "EduAssetVerify rejected a correct asset"],
    ["judge-fr", "A judge rejected a correct asset"]
  ];
  function shows(it, key, b) {
    var v = it.v[b], J = v.d + v.c + v.s, E = v.e;
    switch (key) {
      case "judge-fa": return it.y === "I" && J.indexOf("V") >= 0;
      case "ours-catch": return it.y === "I" && J.indexOf("V") >= 0 && E === "III";
      case "ours-fa": return it.y === "I" && E.indexOf("V") >= 0;
      case "ours-review": return E.indexOf("U") >= 0;
      case "ours-fr": return it.y === "V" && E.indexOf("I") >= 0;
      case "judge-fr": return it.y === "V" && J.indexOf("I") >= 0;
      default: return true;
    }
  }
  function keep(it) {
    return shows(it, S.show, S.b) && (S.dm === "all" || it.dm === S.dm) && (S.sp === "all" || it.sp === S.sp) &&
      (S.op === "all" || it.op.indexOf(S.op) >= 0) && (S.y === "all" || it.y === S.y);
  }
  function card(it) {
    var v = it.v[S.b];
    return '<div class="card" tabindex="0" role="button" data-id="' + it.i + '">' + shot(it, S.b) +
      '<div class="meta"><div class="obj">' + esc(it.o) + "</div>" +
      (it.op.length ? '<div class="ops">' + it.op.map(function (o) { return '<span class="chipo">' + esc(OPN[o]) + "</span>"; }).join("") + "</div>" : "") +
      METH.map(function (m) {
        return '<div class="vrow"><span class="mn' + (m[0] === "e" ? " ours" : "") + '">' + m[1] + "</span><span>" + passes(v[m[0]], it.y) + "</span></div>";
      }).join("") + "</div></div>";
  }
  function options(sel, list, val) {
    sel.innerHTML = list.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (o[0] === val ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("");
  }
  function controls() {
    $("#bk").innerHTML = BKS.map(function (b) { return '<button data-b="' + b + '"' + (b === S.b ? ' class="on"' : "") + ">" + esc(BKN[b]) + "</button>"; }).join("");
    options($("#f-show"), SHOWS.map(function (s) {
      var n = D.items.filter(function (it) { return shows(it, s[0], S.b); }).length;
      return [s[0], s[1] + " (" + n + ")"];
    }), S.show);
    options($("#f-dm"), [["all", "All"], ["fraction", "Fraction"], ["counting", "Counting"], ["spatial", "Spatial"]], S.dm);
    options($("#f-sp"), [["all", "All"]].concat(D.conditions), S.sp);
    options($("#f-op"), [["all", "All"]].concat(D.operators.map(function (o) { return [o[0], o[1]]; })), S.op);
    options($("#f-y"), [["all", "All"], ["V", "Correct"], ["I", "Violated"]], S.y);
  }
  function grid() {
    var list = D.items.filter(keep), shown = list.slice(0, S.n), rest = list.length - shown.length;
    $("#count").textContent = list.length + " of " + D.items.length + " test assets \u00b7 verdicts under " + BKN[S.b];
    $("#grid").innerHTML = list.length ? shown.map(card).join("") : '<div class="empty">No test asset matches these filters.</div>';
    $("#more").innerHTML = rest > 0 ? '<button data-more="' + PAGE + '">Show ' + Math.min(PAGE, rest) + " more</button>" +
      '<button data-more="all">Show all ' + list.length + "</button>" : "";
  }
  function bindBrowser() {
    $("#bk").addEventListener("click", function (e) {
      var t = e.target.closest("button");
      if (!t) return;
      S.b = t.getAttribute("data-b");
      controls(); grid();
    });
    [["#f-show", "show"], ["#f-dm", "dm"], ["#f-sp", "sp"], ["#f-op", "op"], ["#f-y", "y"]].forEach(function (p) {
      $(p[0]).addEventListener("change", function (e) { S[p[1]] = e.target.value; S.n = PAGE; grid(); });
    });
    $("#more").addEventListener("click", function (e) {
      var t = e.target.closest("button");
      if (!t) return;
      S.n = t.getAttribute("data-more") === "all" ? D.items.length : S.n + PAGE;
      grid();
    });
    function open(e) {
      var c = e.target.closest(".card");
      if (c && (e.type === "click" || e.key === "Enter" || e.key === " ")) { e.preventDefault(); openItem(c.getAttribute("data-id"), S.b); }
    }
    $("#grid").addEventListener("click", open);
    $("#grid").addEventListener("keydown", open);
  }

  /* ------------------------------------------------------------------ modal */
  var M = { id: null, b: "C", w: true, g: true };
  function openItem(id, b) {
    if (!BYID[id]) return;
    M.id = id; M.b = b || M.b;
    renderModal();
    $("#modal").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeModal() { $("#modal").hidden = true; document.body.style.overflow = ""; }
  function renderModal() {
    var it = BYID[M.id], b = M.b, tg = {};
    (it.tg || []).forEach(function (t) { tg[t] = 1; });
    var hasGt = gtBoxes(it).length > 0;
    var vt = '<table class="vt"><tr><th></th>' + BKS.map(function (k) { return '<th colspan="1">' + esc(BKN[k]) + "</th>"; }).join("") + "</tr>" +
      METH.map(function (m) {
        return "<tr><td>" + m[1] + "</td>" + BKS.map(function (k) { return "<td>" + passes(it.v[k][m[0]], it.y) + "</td>"; }).join("") + "</tr>";
      }).join("") + "</table>";
    var rep = '<table class="vt"><tr><th>Constraint</th><th>Status</th><th>Value</th><th>q</th><th>Source</th></tr>' +
      (it.r[b] || []).map(function (r) {
        return "<tr><td><code>" + esc(r[0]) + "</code></td><td>" + stChip(r[1]) + "</td><td>" + esc(r[2]) + "</td><td>" + esc(r[3]) + "</td><td>" + esc(r[5]) + "</td></tr>";
      }).join("") + "</table>";
    var J = it.j[b] || {};
    var req = (J.s || []).map(function (s, i) {
      var c = it.c[i];
      return (c ? esc(c[2]) : "requirement " + (i + 1)) + " " + (s === "T" ? "\u2713" : s === "F" ? "\u2717" : "?");
    }).join("; ");
    var p = BYID[it.p];
    $("#m-body").innerHTML =
      '<p class="mhead">Test asset <code>' + esc(it.i) + "</code> \u00b7 " + esc(TASKN[it.dm]) + " \u00b7 template: " + esc(it.tn) +
      " \u00b7 style: " + esc(STYLEN[it.st] || it.st) + " \u00b7 " + esc(CONDN[it.sp]) + "</p>" +
      '<div class="mgrid"><div>' + shot(it, b, { gt: M.g && hasGt, witness: M.w }) +
      '<div class="toggles"><label><input type="checkbox" id="m-w"' + (M.w ? " checked" : "") + '> witness (red, first pass)</label>' +
      (hasGt ? '<label><input type="checkbox" id="m-g"' + (M.g ? " checked" : "") + "> perturbed region (dashed)</label>" : "") + "</div>" +
      '<div class="seg" id="m-bk" style="margin-top:8px">' + BKS.map(function (k) { return '<button data-b="' + k + '"' + (k === b ? ' class="on"' : "") + ">" + esc(BKN[k]) + "</button>"; }).join("") + "</div>" +
      (p ? '<div class="partner">' + shot(p, b, { badge: false }) + '<div><div class="note">Counterfactual partner: ' +
        (p.y === "V" ? "the correct asset" : "the violated asset") + '</div><button class="btn" id="m-partner">Open it</button></div></div>' : "") +
      "</div><div>" +
      '<h3 id="m-title">' + (it.y === "V" ? "Correct asset" : "Violated asset: " + it.op.map(function (o) { return esc(OPN[o]); }).join(" + ")) + "</h3>" +
      "<p><q>" + esc(it.o) + "</q></p>" +
      '<ul class="clist">' + it.c.map(function (c) {
        return "<li" + (tg[c[0]] ? ' class="tgt"' : "") + "><code>" + esc(c[1]) + "</code>: " + esc(c[2]) + (tg[c[0]] ? " (perturbed)" : "") + "</li>";
      }).join("") + "</ul>" +
      "<b>Verdicts, passes 1\u20133</b>" + vt +
      "<b>EduAssetVerify report, first pass (" + esc(BKN[b]) + ")</b>" + rep +
      "<b>Judges, first pass (" + esc(BKN[b]) + ")</b>" +
      '<p class="note">CoT judge: <q>' + esc(J.c || "") + "</q></p>" +
      '<p class="note">Structured judge: ' + (req || "no per-requirement answer") + "</p>" +
      "</div></div>";
    var mw = $("#m-w"), mg = $("#m-g"), mp = $("#m-partner");
    if (mw) mw.addEventListener("change", function () { M.w = mw.checked; renderModal(); });
    if (mg) mg.addEventListener("change", function () { M.g = mg.checked; renderModal(); });
    if (mp) mp.addEventListener("click", function () { M.id = it.p; renderModal(); });
    $("#m-bk").addEventListener("click", function (e) {
      var t = e.target.closest("button");
      if (t) { M.b = t.getAttribute("data-b"); renderModal(); }
    });
  }
  function bindModal() {
    $("#m-close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", function (e) { if (e.target === $("#modal")) closeModal(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !$("#modal").hidden) closeModal(); });
  }

  /* ------------------------------------------------------------------ pairs */
  function pairs() {
    $("#pair-list").innerHTML = D.pairs.map(function (p) {
      var c = BYID[p[1]], v = BYID[p[2]];
      if (!c || !v) return "";
      return '<div class="pair"><h4>' + esc(OPN[p[0]]) + ' <span class="note">(' + esc(TASKN[v.dm]) + ")</span></h4>" +
        '<div class="two"><div data-id="' + c.i + '">' + shot(c, "C", { badge: false }) + "<small>correct</small></div>" +
        '<div data-id="' + v.i + '">' + shot(v, "C", { badge: false }) + "<small>violated</small></div></div>" +
        '<button data-op="' + esc(p[0]) + '">Browse every ' + esc(OPN[p[0]].toLowerCase()) + " asset</button></div>";
    }).join("");
    $("#pair-list").addEventListener("click", function (e) {
      var t = e.target.closest("[data-id]"), bt = e.target.closest("button[data-op]");
      if (bt) {
        S.op = bt.getAttribute("data-op"); S.show = "all"; S.y = "all"; S.dm = "all"; S.sp = "all"; S.n = PAGE;
        controls(); grid();
        $("#browser").scrollIntoView({ block: "start" });
      } else if (t) openItem(t.getAttribute("data-id"), S.b);
    });
  }

  /* ------------------------------------------------------------------ tables */
  function head2(first, groups, cols) {
    return "<thead><tr><th></th>" + groups.map(function (g) { return '<th colspan="' + cols.length + '" style="text-align:center">' + esc(g) + "</th>"; }).join("") +
      "</tr><tr><th>" + esc(first) + "</th>" + groups.map(function () { return cols.map(function (c) { return "<th>" + esc(c) + "</th>"; }).join(""); }).join("") + "</tr></thead>";
  }
  function tables() {
    var R = D.results, G = R.order, h = "";
    h += '<div class="tbl"><table class="res"><caption>Violation detection on the test set (Table I of the paper)</caption>' +
      head2("Method", G, ["Acc.", "FAR", "FRR", "Abst."]) + "<tbody>" + R.detection.map(function (r) {
        return "<tr" + (r[0] === "EduAssetVerify" ? ' class="ours"' : "") + "><td>" + esc(r[0]) + "</td>" +
          r[1].map(function (cells) { return cells.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join(""); }).join("") + "</tr>";
      }).join("") + "</tbody></table><div class='fn'>Standard deviation over passes at most " + R.max_sd + " points. CLIPScore uses no backbone; " +
      "parsed constraints: the parser's constraint sets instead of the gold ones.</div></div>";
    var task = "";
    h += '<div class="tbl"><table class="res"><caption>False acceptance by error type (%)</caption>' +
      head2("Error", G, ["Direct", "CoT", "Structured", "Ours"]) + "<tbody>" + R.operators.map(function (r) {
        var g = r[0] !== task ? '<tr><td class="grp" colspan="9">' + esc(r[0]) + "</td></tr>" : "";
        task = r[0];
        return g + "<tr><td>" + esc(r[1]) + "</td>" + r[2].map(function (cells) { return cells.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join(""); }).join("") + "</tr>";
      }).join("") + "</tbody></table><div class='fn'>Of the " + R.errors.fa_judges_both_backbones + " false acceptances of all judges under both backbones, " +
      R.errors.fa_measured_operators_only + " involve only part counts, colored counts, unequal partitions, or broken symmetries. Ours: EduAssetVerify.</div></div>";
    h += '<div class="tbl"><table class="res"><caption>Pair accuracy by test condition (%)</caption>' +
      head2("Condition", G, ["Direct", "CoT", "Ours"]) + "<tbody>" + R.conditions.map(function (r) {
        return "<tr><td>" + esc(r[0]) + "</td>" + r[1].map(function (cells) { return cells.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join(""); }).join("") + "</tr>";
      }).join("") + "</tbody></table><div class='fn'>Pairs whose correct image is judged valid and violated image invalid; abstentions count as errors. " +
      "Style invariance: unseen-style images whose verdict matches that of the same scene in its base style.</div></div>";
    h += '<div class="tbl"><table class="res"><caption>Component ablation (Table II of the paper, %)</caption>' +
      head2("Configuration", G, ["FAR", "FRR", "Abst."]) + "<tbody>" + R.ablation.map(function (r, i) {
        return "<tr" + (i === 0 ? ' class="ours"' : "") + "><td>" + esc(r[0]) + "</td>" + r[1].map(function (cells) { return cells.map(function (c) { return "<td>" + esc(c) + "</td>"; }).join(""); }).join("") + "</tr>";
      }).join("") + "</tbody></table><div class='fn'>Variants reuse the full method's readings; without rule engine, the VLM decides from the same evidence.</div></div>";
    $("#tables").innerHTML = h;
  }

  /* ------------------------------------------------------------------ start */
  function fromHash() {
    var hsh = (location.hash || "").replace(/^#/, ""), q = {};
    if (hsh.indexOf("=") < 0) return null;
    hsh.split("&").forEach(function (kv) { var p = kv.split("="); q[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || ""); });
    ["b", "show", "dm", "sp", "op", "y"].forEach(function (k) { if (q[k]) S[k] = q[k]; });
    if (q.n) S.n = q.n === "all" ? D.items.length : parseInt(q.n, 10) || PAGE;
    return q;
  }
  var q = fromHash();
  overview(); walkthrough(); controls(); grid(); pairs(); tables();
  bindBrowser(); bindModal();
  if (q) {
    if (q.only) [].forEach.call(document.querySelectorAll("main > section"), function (sec) { if (sec.id !== q.only) sec.hidden = true; });
    if (q.item) openItem(q.item, q.b || S.b);
    else if (q.only) return;
    else document.getElementById(q.at || "browser").scrollIntoView({ block: "start", behavior: "instant" });
  }
})();
