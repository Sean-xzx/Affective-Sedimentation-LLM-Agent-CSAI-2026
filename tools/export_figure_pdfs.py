"""Export paper data figures from locked formal analysis (need-based).

Paper inventory:
  - fig_mechanism.pdf : non-data flowchart (unchanged here if already present)
  - fig_primary.pdf   : (a) E item units e_dj  (b) N seed units N_k
  - fig_n_heatmap.pdf : direction x seed mean signed contrasts

Tables carry design / gates / axis summaries; do not duplicate them as extra plots.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from tools.analysis_core import (
    DIMS,
    _formal_records,
    compute_e_effects,
    compute_n_effects,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "final_results.json"
FIG_DIR = ROOT / "paper" / "figures"
MES = 0.10
SEEDS = [14, 24, 5, 18, 22, 13, 1, 26]

C_MEAN = "#2b2b2b"
C_BOX = "#f7f5f8"
C_EDGE = "#3a3a3a"
C_ARROW = "#6a6a6a"
C_MUTED = "#7a7a7a"
C_GRID = "#d9d5dc"
C_MES: str
C_POS: str
DIM_COLORS: dict[str, tuple]
HEAT_CMAP = None


def _setup() -> None:
    global C_MES, C_POS, DIM_COLORS, HEAT_CMAP
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.linewidth": 0.8,
            "axes.edgecolor": C_EDGE,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": C_GRID,
            "grid.linewidth": 0.6,
            "figure.dpi": 200,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
        }
    )
    muted = sns.color_palette("muted", n_colors=6)
    light_m = sns.color_palette("light:m_r", n_colors=8)
    dim = sns.color_palette("ch:rot=-.25,hue=1,light=.65", n_colors=3)
    DIM_COLORS = {"P": dim[0], "A": dim[1], "D": dim[2]}
    C_POS = muted[0]
    C_MES = light_m[6]
    HEAT_CMAP = sns.diverging_palette(220, 12, s=55, l=58, center="light", as_cmap=True)


def _savefig(fig, out: Path) -> None:
    fmt = out.suffix.lstrip(".").lower() or "pdf"
    fig.savefig(out, format=fmt)


def _box(ax, xy, w, h, text, *, fontsize=7.2) -> None:
    x, y = xy
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.0, edgecolor=C_EDGE, facecolor=C_BOX,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, color=C_EDGE)


def _arrow(ax, p0, p1) -> None:
    ax.add_patch(
        FancyArrowPatch(
            p0, p1, arrowstyle="-|>", mutation_scale=9,
            linewidth=1.0, color=C_ARROW, shrinkA=1, shrinkB=1,
        )
    )


def mechanism_figure(out: Path) -> None:
    """Non-data overview (protocol figure 1).

    Prefer the hand-authored flowchart PNG when present; do not overwrite it
    with the legacy matplotlib schematic.
    """
    hand = out.with_suffix(".png")
    if hand.is_file():
        from PIL import Image

        Image.open(hand).convert("RGB").save(out, "PDF", resolution=150.0)
        return

    fig, ax = plt.subplots(figsize=(7.0, 3.15))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6.1)
    ax.axis("off")
    _box(ax, (0.25, 4.35), 2.35, 1.15, "Frozen history H\n(200 events / seed)")
    _box(ax, (3.1, 4.35), 2.5, 1.15, "Deterministic\ncontroller\neps -> m -> s")
    _box(ax, (6.15, 4.35), 2.4, 1.15, "Rendered state\nR[z] text block")
    _box(ax, (9.1, 4.35), 2.15, 1.15, "Probe +\nAB/BA options")
    _box(ax, (11.75, 4.35), 1.95, 1.15, "JSON choice\n-> CS")
    for p0, p1 in [
        ((2.6, 4.92), (3.1, 4.92)), ((5.6, 4.92), (6.15, 4.92)),
        ((8.55, 4.92), (9.1, 4.92)), ((11.25, 4.92), (11.75, 4.92)),
    ]:
        _arrow(ax, p0, p1)
    ax.text(4.35, 5.7, "Gate D: engineering assertion", ha="center", fontsize=7, color=C_MUTED)
    ax.text(11.7, 5.7, "Behavioral evidence", ha="center", fontsize=7, color=C_MUTED)
    _box(ax, (1.0, 2.15), 5.4, 1.4,
         "Experiment E (180)\nAffect labels vs active placebo\nMatched numbers; no EVENT_MEMORY", fontsize=7.1)
    _box(ax, (7.4, 2.15), 5.6, 1.4,
         "Experiment N (576)\nFull R1[z(s_200(H))] vs R1[(0,0,0)]\nIdentical EVENT_MEMORY M(H)", fontsize=7.1)
    ax.plot([7.35, 7.35], [4.35, 3.85], color=C_ARROW, lw=1.0)
    ax.plot([3.7, 10.2], [3.85, 3.85], color=C_ARROW, lw=1.0)
    _arrow(ax, (3.7, 3.85), (3.7, 3.55))
    _arrow(ax, (10.2, 3.85), (10.2, 3.55))
    _box(ax, (3.2, 0.3), 7.4, 1.2,
         "Primary gates (order D -> E -> N): MES=0.10, exact sign-flip,\n"
         "pair completeness, discordance caps, blind integrity QC", fontsize=7.1)
    _arrow(ax, (3.7, 2.15), (5.5, 1.5))
    _arrow(ax, (10.2, 2.15), (8.3, 1.5))
    _savefig(fig, out)
    plt.close(fig)


def primary_figure(effects: dict[str, float], n_k: dict, theta_e: float, theta_n: float, out: Path) -> None:
    """Two-panel primary: E item units + N seed units (sign-flip analysis units)."""
    df_e = pd.DataFrame(
        [{"probe": p, "axis": p.split("-", 1)[0], "effect": float(v)}
         for p, v in effects.items() if v is not None]
    )
    df_n = pd.DataFrame(
        {"seed": [str(s) for s in SEEDS],
         "effect": [float(n_k[s] if s in n_k else n_k[str(s)]) for s in SEEDS],
         "unit": "seed $N_k$"}
    )

    fig, (ax_e, ax_n) = plt.subplots(1, 2, figsize=(7.0, 2.75), gridspec_kw={"width_ratios": [1.35, 1.0]})

    sns.stripplot(
        data=df_e, x="effect", y="axis", hue="axis",
        palette=DIM_COLORS, order=list(DIMS), hue_order=list(DIMS),
        jitter=0.18, size=6.5, alpha=0.55, legend=False, linewidth=0, ax=ax_e,
    )
    sns.pointplot(
        data=df_e, x="effect", y="axis", order=list(DIMS),
        color=C_MEAN, errorbar=None, markers="D", markersize=4.5, linestyle="none", ax=ax_e,
    )
    ax_e.axvline(0.0, color=C_MUTED, lw=0.7)
    ax_e.axvline(MES, color=C_MES, ls="--", lw=1.0, label=f"MES={MES:.2f}")
    ax_e.axvline(theta_e, color=C_MEAN, ls=":", lw=1.0, label=rf"$\theta_E$={theta_e:.4f}")
    ax_e.set_xlabel(r"$e_{d,j}$ (CS / rendered-$z$)")
    ax_e.set_ylabel("")
    ax_e.set_title("(a) Experiment E: item-level units", fontsize=8)
    ax_e.legend(loc="lower right", frameon=False, fontsize=6.0)
    sns.despine(ax=ax_e, left=True)

    sns.stripplot(
        data=df_n, x="effect", y="unit",
        color=C_POS, jitter=0.12, size=7.5, alpha=0.55, linewidth=0, ax=ax_n,
    )
    sns.pointplot(
        data=df_n, x="effect", y="unit",
        color=C_MEAN, errorbar=None, markers="D", markersize=5, linestyle="none", ax=ax_n,
    )
    ax_n.axvline(0.0, color=C_MUTED, lw=0.7)
    ax_n.axvline(MES, color=C_MES, ls="--", lw=1.0, label=f"MES={MES:.2f}")
    ax_n.axvline(theta_n, color=C_MEAN, ls=":", lw=1.0, label=rf"$\theta_N$={theta_n:.4f}")
    ax_n.set_xlabel(r"$N_k$ (dir.-corrected CS)")
    ax_n.set_ylabel("")
    ax_n.set_title("(b) Experiment N: seed-level units", fontsize=8)
    ax_n.legend(loc="lower right", frameon=False, fontsize=6.0)
    sns.despine(ax=ax_n, left=True)

    fig.tight_layout(w_pad=1.2)
    _savefig(fig, out)
    plt.close(fig)


def n_heatmap_figure(n_hj: dict, out: Path) -> None:
    """Annotated direction x seed heatmap (secondary: where theta_N comes from)."""
    dirs = ["P-", "P+", "A-", "A+", "D-", "D+"]
    acc: dict[tuple, list[float]] = {}
    for (h, s, _p), v in n_hj.items():
        acc.setdefault((h, s), []).append(float(v))
    M = pd.DataFrame(np.nan, index=dirs, columns=[str(s) for s in SEEDS])
    for h in dirs:
        for s in SEEDS:
            vals = acc.get((h, s), [])
            if vals:
                M.loc[h, str(s)] = float(np.mean(vals))

    fig, ax = plt.subplots(figsize=(3.55, 3.05))
    sns.despine(fig)
    ax.set_facecolor("white")
    vmax = max(0.2, float(np.nanmax(np.abs(M.to_numpy()))))
    sns.heatmap(
        M, annot=True, fmt=".2f", linewidths=0.5, linecolor="white",
        cmap=HEAT_CMAP, center=0.0, vmin=-vmax, vmax=vmax, ax=ax,
        cbar_kws={"label": "Signed CS contrast", "shrink": 0.85},
        annot_kws={"size": 6.2, "color": C_EDGE},
    )
    ax.set_xlabel("History seed $k$")
    ax.set_ylabel("History direction")
    ax.set_title("Experiment N: mean $n_{h,k}$", fontsize=8)
    ax.tick_params(labelsize=7)
    _savefig(fig, out)
    plt.close(fig)


def main() -> int:
    _setup()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    from tools.rand_manifest import RAW_PATH
    from sprint.runner import load_records

    records = _formal_records(load_records(RAW_PATH))
    e = compute_e_effects(records)
    n = compute_n_effects(records)
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    if abs(e["theta_E"] - results["theta_E"]) > 1e-12 or abs(n["theta_N"] - results["theta_N"]) > 1e-12:
        raise SystemExit("theta mismatch vs final_results.json")

    mechanism_figure(FIG_DIR / "fig_mechanism.pdf")
    primary_figure(
        e["effects"], n["N_k"], float(e["theta_E"]), float(n["theta_N"]),
        FIG_DIR / "fig_primary.pdf",
    )
    n_heatmap_figure(n["n_hj"], FIG_DIR / "fig_n_heatmap.pdf")

    meta = {
        "theta_E": e["theta_E"],
        "theta_N": n["theta_N"],
        "figures": ["fig_mechanism.pdf", "fig_primary.pdf", "fig_n_heatmap.pdf"],
        "data_figures": ["fig_primary.pdf", "fig_n_heatmap.pdf"],
        "need": {
            "fig_primary": "sign-flip analysis units e_dj and N_k",
            "fig_n_heatmap": "direction x seed support for theta_N (not in axis table)",
        },
    }
    (FIG_DIR / "figure_export_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote figures under {FIG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
