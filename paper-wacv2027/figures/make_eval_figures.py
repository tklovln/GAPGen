"""Generate evaluation figures for the GAPGen paper from existing result files.

Sources (no re-generation, no API calls):
  paper/results/auto_eval.json        GPT-4o proxy eval + DINOv2 cohesion (fruit B0-B3)
  paper/results/ablation_seeds.csv    Fruit B0-B3 x 3 seeds (pass / needs_review / iters ...)
  paper/results/ablation_multi_theme.csv  Pet / Ocean B1-B3

Outputs (PNG, 200 dpi) -> paper/figures/eval_*.png

Run:  python paper/figures/make_eval_figures.py
Self-check: python paper/figures/make_eval_figures.py --check
"""
from __future__ import annotations

import csv
import json
import pathlib
import statistics as st
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
RESULTS = ROOT / "paper" / "results"
FIGS = ROOT / "paper" / "figures"
CONDS = ["B0", "B1", "B2", "B3"]
# Consistent, colorblind-friendly palette across all figures.
CMAP = {"B0": "#bdbdbd", "B1": "#6baed6", "B2": "#fd8d3c", "B3": "#31a354"}
plt.rcParams.update({"font.size": 11, "savefig.dpi": 200, "figure.autolayout": True})


def _load_auto() -> dict:
    return json.loads((RESULTS / "auto_eval.json").read_text())["themes"]["fruit"]


def _load_seeds() -> dict[str, dict[str, list[float]]]:
    """condition -> metric -> [per-seed values]."""
    out: dict[str, dict[str, list[float]]] = {}
    with (RESULTS / "ablation_seeds.csv").open() as f:
        for row in csv.DictReader(f):
            c = row["condition"]
            d = out.setdefault(c, {})
            for m in ("pass_rate", "needs_review_rate", "mean_iters",
                      "mean_style", "mean_function", "mean_cohesion", "mean_progression"):
                if row.get(m):  # quality dims are only populated for B3
                    d.setdefault(m, []).append(float(row[m]))
    return out


def _mean_std(vals: list[float]) -> tuple[float, float]:
    return (st.mean(vals), st.pstdev(vals) if len(vals) > 1 else 0.0)


def _load_critic_progression() -> dict[str, tuple[float, float]]:
    """condition -> (progression_mean, progression_std) on the critic 0-10 scale.

    B0-B2 come from the backfill file; B3 from its seed rows in ablation_seeds.csv.
    """
    out: dict[str, tuple[float, float]] = {}
    bf = json.loads((RESULTS / "critic_backfill.json").read_text())
    for c, d in bf.items():
        out[c] = (d["progression_mean"], d["progression_std"])
    b3 = [float(r["mean_progression"]) for r in csv.DictReader((RESULTS / "ablation_seeds.csv").open())
          if r["condition"] == "B3" and r["mean_progression"]]
    if b3:
        out["B3"] = _mean_std(b3)
    return out


# --------------------------------------------------------------------------- #
# CORE: role accuracy + DINOv2 cohesion + critic stage progression (3 panels)
# --------------------------------------------------------------------------- #
def fig_core(auto: dict) -> pathlib.Path:
    role = [auto[c]["role_recognition"]["accuracy"] for c in CONDS]
    colors = [CMAP[c] for c in CONDS]
    fams = ["elements", "powerups", "crate"]
    prog = _load_critic_progression()

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(12.4, 3.4))

    # Left: role recognition accuracy.
    bars = ax1.bar(CONDS, role, color=colors, edgecolor="black", linewidth=0.5)
    ax1.set_title("Role recognition accuracy")
    ax1.set_ylabel("Accuracy (GPT-4o judge)")
    ax1.set_ylim(0, 1.0)
    ax1.spines[["top", "right"]].set_visible(False)
    for b, v in zip(bars, role):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}",
                 ha="center", va="bottom", fontsize=9)

    # Middle: DINOv2 cohesion, grouped by asset family (elements/powerups/crate).
    x = np.arange(len(fams))
    w = 0.2
    for i, c in enumerate(CONDS):
        vals = [auto[c]["cohesion"]["families"][f]["mean_sim"] for f in fams]
        ax2.bar(x + (i - 1.5) * w, vals, w, label=c, color=CMAP[c],
                edgecolor="black", linewidth=0.4)
    ax2.set_xticks(x, fams)
    ax2.set_title("Intra-family cohesion")
    ax2.set_ylabel("DINOv2 mean cosine sim")
    ax2.set_ylim(0, 1.0)
    ax2.legend(title="Condition", ncol=4, fontsize=8, loc="upper center",
               bbox_to_anchor=(0.5, 1.0), frameon=False, columnspacing=1.0)
    ax2.spines[["top", "right"]].set_visible(False)

    # Right: critic stage-progression score (0-10); B0-B2 backfilled, mean +/- sd.
    pmeans = [prog[c][0] for c in CONDS]
    pstds = [prog[c][1] for c in CONDS]
    pbars = ax3.bar(CONDS, pmeans, yerr=pstds, color=colors, edgecolor="black",
                    linewidth=0.5, capsize=4, error_kw={"elinewidth": 1})
    ax3.set_title("Critic stage progression")
    ax3.set_ylabel("Progression score (0-10, 3 seeds)")
    ax3.set_ylim(0, 10.5)
    ax3.spines[["top", "right"]].set_visible(False)
    for b, v in zip(pbars, pmeans):
        ax3.text(b.get_x() + b.get_width() / 2, v + 0.15, f"{v:.1f}",
                 ha="center", va="bottom", fontsize=9)

    out = FIGS / "eval_core.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# CORE: pairwise win-rate heatmap (row beats column)
# --------------------------------------------------------------------------- #
def fig_pairwise(auto: dict) -> pathlib.Path:
    n = len(CONDS)
    idx = {c: i for i, c in enumerate(CONDS)}
    M = np.full((n, n), np.nan)
    for pw in auto["pairwise"]:
        a, b = pw["compare"].split("_vs_")  # a_vs_b
        # win rate is stored keyed on the "later" condition; recover both.
        key = next(k for k in pw if k.endswith("_win_rate"))
        winner = key.split("_win_rate")[0]
        wr = pw[key]  # win rate of `winner` over the other
        other = b if winner == a else a
        M[idx[winner], idx[other]] = wr
        M[idx[other], idx[winner]] = 1 - wr

    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(n), CONDS)
    ax.set_yticks(range(n), CONDS)
    ax.set_xlabel("vs. (column)")
    ax.set_ylabel("row condition")
    ax.set_title("Pairwise win rate (row beats column)")
    for i in range(n):
        for j in range(n):
            if not np.isnan(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=10)
            elif i == j:
                ax.text(j, i, "-", ha="center", va="center", color="gray")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="win rate")
    out = FIGS / "eval_pairwise.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# ABLATION: needs_review + mean_iters with per-seed error bars
# --------------------------------------------------------------------------- #
def fig_ablation(seeds: dict) -> pathlib.Path:
    conds = [c for c in CONDS if c in seeds]
    x = np.arange(len(conds))
    colors = [CMAP[c] for c in conds]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 3.4))
    for ax, metric, title, ylab in (
        (ax1, "needs_review_rate", "Needs-review rate\n(only B3 has a VLM critic)", "fraction (mean $\\pm$ sd, 3 seeds)"),
        (ax2, "mean_iters", "Mean critic iterations\n(only B3 has a VLM critic)", "iterations (mean $\\pm$ sd, 3 seeds)"),
    ):
        means, stds = zip(*(_mean_std(seeds[c][metric]) for c in conds))
        ax.bar(x, means, yerr=stds, color=colors, edgecolor="black", linewidth=0.5,
               capsize=4, error_kw={"elinewidth": 1})
        ax.set_xticks(x, conds)
        ax.set_title(title)
        ax.set_ylabel(ylab)
        ax.spines[["top", "right"]].set_visible(False)
        for xi, m in zip(x, means):
            ax.text(xi, m + (max(means) * 0.03 + 0.005), f"{m:.2f}",
                    ha="center", va="bottom", fontsize=9)
    out = FIGS / "eval_ablation.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# APPENDIX: per-family cohesion grouped bar (elements / powerups / crate)
# --------------------------------------------------------------------------- #
def fig_family_cohesion(auto: dict) -> pathlib.Path:
    fams = ["elements", "powerups", "crate"]
    x = np.arange(len(fams))
    w = 0.2
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for i, c in enumerate(CONDS):
        vals = [auto[c]["cohesion"]["families"][f]["mean_sim"] for f in fams]
        ax.bar(x + (i - 1.5) * w, vals, w, label=c, color=CMAP[c],
               edgecolor="black", linewidth=0.4)
    ax.set_xticks(x, fams)
    ax.set_ylabel("DINOv2 mean cosine sim")
    ax.set_ylim(0, 1.0)
    ax.legend(title="Condition", ncol=4, fontsize=9, loc="upper left", frameon=True)
    ax.spines[["top", "right"]].set_visible(False)
    out = FIGS / "eval_family_cohesion.png"
    fig.savefig(out)
    plt.close(fig)
    return out


# --------------------------------------------------------------------------- #
# APPENDIX: B3 critic quality across themes (Fruit / Pet / Ocean)
# --------------------------------------------------------------------------- #
def fig_multi_theme(seeds: dict) -> pathlib.Path:
    dims = ["mean_style", "mean_function", "mean_cohesion", "mean_progression"]
    dim_labels = ["style", "function", "cohesion", "progression"]

    # Fruit B3: mean over 3 seeds; Pet/Ocean B3: single run from the multi-theme CSV.
    scores: dict[str, list[float]] = {
        "Fruit": [_mean_std(seeds["B3"][d])[0] for d in dims],
    }
    with (RESULTS / "ablation_multi_theme.csv").open() as f:
        for r in csv.DictReader(f):
            if r["condition"] == "B3":
                scores[r["theme"]] = [float(r[d]) for d in dims]

    themes = list(scores)
    theme_colors = {"Fruit": "#e6550d", "Pet": "#756bb1", "Ocean": "#3182bd"}
    x = np.arange(len(dims))
    w = 0.8 / len(themes)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for i, t in enumerate(themes):
        off = (i - (len(themes) - 1) / 2) * w
        bars = ax.bar(x + off, scores[t], w, label=t,
                      color=theme_colors.get(t, "#999999"),
                      edgecolor="black", linewidth=0.4)
        for b, v in zip(bars, scores[t]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.1, f"{v:.1f}",
                    ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(x, dim_labels)
    ax.set_ylabel("Critic score (0-10)")
    ax.set_ylim(0, 11)
    ax.set_title("Full-system (B3) pack quality across themes")
    ax.legend(title="Theme", ncol=len(themes), fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    out = FIGS / "eval_multi_theme.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def build_all() -> list[pathlib.Path]:
    auto = _load_auto()
    seeds = _load_seeds()
    return [
        fig_core(auto),
        fig_pairwise(auto),
        fig_ablation(seeds),
        fig_family_cohesion(auto),
        fig_multi_theme(seeds),
    ]


def self_check() -> None:
    """Offline sanity: data loads, pairwise matrix is antisymmetric, files land."""
    auto = _load_auto()
    assert set(CONDS) <= set(auto), "missing conditions in auto_eval.json"
    # role accuracy is monotone non-decreasing B0->B3 (the headline claim)
    acc = [auto[c]["role_recognition"]["accuracy"] for c in CONDS]
    assert acc == sorted(acc), f"role accuracy not monotone: {acc}"
    seeds = _load_seeds()
    assert all(len(seeds[c]["pass_rate"]) == 3 for c in CONDS), "expected 3 seeds each"
    prog = _load_critic_progression()
    assert set(CONDS) <= set(prog), f"missing progression conds: {set(CONDS) - set(prog)}"
    outs = build_all()
    for p in outs:
        assert p.exists() and p.stat().st_size > 1000, f"bad output {p}"
    print("self_check OK:", ", ".join(p.name for p in outs))


if __name__ == "__main__":
    if "--check" in sys.argv:
        self_check()
    else:
        for p in build_all():
            print("wrote", p.relative_to(ROOT))
