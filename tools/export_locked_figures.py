"""Export locked paper figures from reports/plot_ready (no estimand recomputation).

Targets ACM sigconf dual-column. Each figure pairs a primary result with the diagnostic
that explains it, so a reader never has to hold one panel in mind while turning a page:

  - fig_E_units.pdf     : (a) the 15 locked item contrasts, (b) the 90-cell response
                          surface those contrasts are computed from
  - fig_N_structure.pdf : (a) the 8 locked seed means, (b) the direction-by-seed structure
                          underneath the overall estimand
  - fig_mechanism.pdf   : rebuilt from hand-authored PNG when present

Panels (a) come from the sealed analysis; panels (b) come from secondary_diagnostics.json,
recomputed over the same ledger by a module outside the sealed hash set. The captions carry
that split.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "reports" / "plot_ready"
DIAG = ROOT / "reports" / "secondary_diagnostics.json"
OUT = ROOT / "paper" / "figures"

PAD = {"P": "#415489", "A": "#4987a0", "D": "#62b3a3"}
#: One warm accent against an otherwise cool figure, reserved for the locked estimand and
#: for nothing else. Colour carries category in the data; annotation stays neutral or accent.
ACCENT = "#c2705a"
GREY, INK, MUTE = "#7a7a7a", "#2b2b2b", "#8a8a8a"
N_BLUE = "#3f6f8c"
HALO = dict(facecolor="white", edgecolor="none", pad=1.0, alpha=0.92)
# ACM textwidth ≈ 7.0in; keep all full-width figures at the same canvas width.
FULL_W = 7.0
#: ACM sigconf \columnwidth, measured from the compiled log (241.15pt).
COL_W = 241.15 / 72.27
#: Smallest base font size any figure may use. Mathtext sets sub/superscripts at 0.7x the
#: base, and the wider of the two canvases is placed at only about 1.07x natural size, so
#: 8.6 pt is the floor that still leaves a subscript clear of the 6 pt print minimum
#: enforced by tools.r7_gate row 7. Nothing in these figures may go below it, math or not.
MIN_PT = 8.6

#: Colour used for the profiles that never leave the CS = 1.0 ceiling. They carry most of the
#: probes but none of the signal, so they must recede behind the PAD hues.
CEIL_GREY = "#b9c2cc"
#: Sequential, single-hue, monotone in lightness: n_hk is non-negative and bounded, so a
#: diverging scale would have spent half its range on values the data cannot take.
N_CMAP = LinearSegmentedColormap.from_list(
    "csai_n", ["#f5f8f9", "#c6d9e2", "#7ba6bc", "#3f6f8c", "#28495d"]
)
STATE_ORDER = ("negative", "origin", "positive")
BLOCK_ORDER = ("affect", "placebo")


def _setup() -> None:
    sns.set_style("whitegrid")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial"],
            "mathtext.fontset": "dejavusans",
            "font.size": MIN_PT,
            "axes.labelsize": MIN_PT,
            "axes.titlesize": 8.6,
            "xtick.labelsize": MIN_PT,
            "ytick.labelsize": MIN_PT,
            "axes.linewidth": 0.6,
            "axes.edgecolor": "#8d8d8d",
            "grid.color": "#d5d5d5",
            "grid.linewidth": 0.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
        }
    )


def _save(fig: mpl.figure.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf")
    fig.savefig(OUT / f"{stem}.png", dpi=300)
    plt.close(fig)


def _response_surface() -> pd.Series:
    """The 90 locked E cells, indexed by (probe_id, block, state)."""
    d = json.loads(DIAG.read_text(encoding="utf-8"))
    df = pd.DataFrame(d["D1_e_response_surface"])
    return df.set_index(["probe_id", "block", "state"])["cs"]


def export_e_units(C: dict) -> None:
    e = pd.read_csv(UP / "01_fig_E_units.csv")
    e["axis"] = pd.Categorical(e["axis"], ["P", "A", "D"], ordered=True)
    e = e.sort_values(["axis", "probe_id"]).reset_index(drop=True)
    mes, th_e = float(C["MES"]), float(C["theta_E"])

    ys, blocks, y = [], {}, 0.0
    for a_ in ["P", "A", "D"]:
        n_ = int((e["axis"] == a_).sum())
        blocks[a_] = (y, y + n_ - 1)
        ys += list(y + np.arange(n_))
        y += n_ + 1.3
    e["y"] = ys
    foot = float(e["y"].max()) + 1.25

    # Height is free to compress: main.tex places this at width=\textwidth, so the printed
    # scale, and therefore every glyph size row 7 checks, is fixed by FULL_W alone.
    fig = plt.figure(figsize=(FULL_W, 2.32))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.05, 1.30], wspace=0.17)
    ax = fig.add_subplot(gs[0, 0])
    gsb = gs[0, 1].subgridspec(1, 2, wspace=0.13)
    axA = fig.add_subplot(gsb[0, 0])
    axP = fig.add_subplot(gsb[0, 1], sharey=axA)

    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", ls="-", lw=0.5)
    sns.despine(ax=ax)
    for name, (y0, y1) in blocks.items():
        ax.axhspan(y0 - 0.6, y1 + 0.6, color=PAD[name], alpha=0.07, lw=0, zorder=0)
    ax.axvline(0, color="#b0b0b0", lw=0.7, zorder=1)
    ax.axvline(mes, color=GREY, lw=1.0, ls=(0, (4, 2.2)), zorder=2)
    ax.axvline(th_e, color=ACCENT, lw=1.3, zorder=2)

    for _, r in e.iterrows():
        col, zero = PAD[r["axis"]], float(r["e_dj"]) == 0.0
        ax.plot([0, r["e_dj"]], [r["y"]] * 2, color=col, lw=1.1, alpha=0.75, solid_capstyle="round", zorder=3)
        ax.plot(r["e_dj"], r["y"], "o", ms=5.0, zorder=4, mfc=("white" if zero else col), mec=col, mew=1.1)

    ax.set_yticks(e["y"])
    ax.set_yticklabels(e["probe_id"])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(-0.035, 0.95)
    ax.set_ylim(foot + 0.55, -0.75)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_xlabel(r"$e_{d,j}$: affect $-$ placebo slope (CS / rendered-$z$ span)")
    ax.set_title("(a) Experiment E — 15 locked item units", loc="left", pad=4, color=INK)
    ax.text(mes - 0.012, foot, f"MES {mes:.2f}", fontsize=MIN_PT, color=GREY, ha="right", va="center", zorder=6, bbox=HALO)
    ax.text(th_e + 0.014, foot, rf"$\theta_E$ {th_e:.4f}", fontsize=MIN_PT, color=ACCENT, ha="left", va="center")
    # (b) The same 90 cells, but drawn as the slopes panel (a) summarises rather than as a
    # sparse table. Only eight distinct state profiles exist, so each is drawn once and
    # carries its multiplicity. That is what makes the decisive fact legible: every placebo
    # profile is horizontal, so the whole of e_dj comes from the affect block.
    surf = _response_surface()
    prof: dict[tuple[str, tuple[float, ...]], list[str]] = {}
    for _, r in e.iterrows():
        for block in BLOCK_ORDER:
            key = tuple(float(surf.loc[(r["probe_id"], block, s)]) for s in STATE_ORDER)
            prof.setdefault((block, key), []).append(str(r["axis"]))

    ceil_key = (1.0,) * len(STATE_ORDER)
    for axb, block, name in ((axA, "affect", "Affect"), (axP, "placebo", "Placebo")):
        axb.set_axisbelow(True)
        axb.grid(axis="x", visible=False)
        axb.grid(axis="y", ls="-", lw=0.5)
        sns.despine(ax=axb, left=True)
        starts: dict[float, int] = {}
        # ceiling profiles first so the coloured departures sit on top of them
        for (blk, key), members in sorted(prof.items(), key=lambda kv: kv[0][1] != ceil_key):
            if blk != block:
                continue
            at_ceiling = key == ceil_key
            col = CEIL_GREY if at_ceiling else PAD[members[0]]
            z = 2 if at_ceiling else 3
            axb.plot(range(len(key)), key, color=col, lw=1.5, alpha=0.9,
                     solid_capstyle="round", zorder=z)
            axb.plot(range(len(key)), key, "o", ms=3.4, mfc=col, mec="white", mew=0.6, zorder=z)
            starts[key[0]] = starts.get(key[0], 0) + len(members)
        for y0, cnt in starts.items():
            axb.text(-0.3, y0, rf"$\times${cnt}", ha="right", va="center",
                     fontsize=MIN_PT, color=MUTE)
        axb.set_xlim(-0.92, 2.22)
        axb.set_ylim(-0.17, 1.17)
        axb.set_xticks(range(len(STATE_ORDER)), ["\u2212", "0", "+"])
        axb.tick_params(length=0)
        axb.text(0.5, -0.115, name, transform=axb.transAxes, ha="center", va="top",
                 fontsize=MIN_PT, color=INK)
    axA.set_yticks([0.0, 0.5, 1.0], ["0", ".5", "1"])
    axA.set_ylabel("choice score", labelpad=1)
    axP.tick_params(labelleft=False)
    axP.text(2.22, 1.09, "CS = 1.0 ceiling", ha="right", va="center", fontsize=MIN_PT, color=MUTE)
    axA.set_title("(b) Response profile across the three states", loc="left", pad=4, color=INK)
    _save(fig, "fig_E_units")


def export_n_structure(C: dict) -> None:
    """Single full-width figure: (a) seed units, (b) direction×seed heatmap."""
    n = pd.read_csv(UP / "02_fig_N_units.csv")
    seed_order = list(C["seed_order"])
    n["seed"] = pd.Categorical(n["seed"], seed_order, ordered=True)
    n = n.sort_values("seed").reset_index(drop=True)
    mes, th_n = float(C["MES"]), float(C["theta_N"])
    lo_n, hi_n = C["bootstrap_N"]

    h = pd.read_csv(UP / "03_fig_N_heatmap_cells.csv")
    dir_order = list(C["direction_row_order"])
    M = h.pivot(index="direction", columns="seed", values="n_hk_mean").reindex(index=dir_order, columns=seed_order)
    V = M.to_numpy(dtype=float)
    vmax = float(np.nanmax(V))
    shares = {r["direction"]: r["share_of_theta_N"]
              for r in json.loads(DIAG.read_text(encoding="utf-8"))["D4_n_direction_decomposition"]["per_direction"]}

    fig = plt.figure(figsize=(FULL_W, 2.20))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.55], wspace=0.22)
    ax = fig.add_subplot(gs[0, 0])
    axh = fig.add_subplot(gs[0, 1])

    # (a) N units
    ax.set_axisbelow(True)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", ls="-", lw=0.5)
    sns.despine(ax=ax)
    ax.axvspan(lo_n, hi_n, color=ACCENT, alpha=0.09, lw=0, zorder=0)
    ax.axvline(0, color="#b0b0b0", lw=0.7, zorder=1)
    ax.axvline(mes, color=GREY, lw=1.0, ls=(0, (4, 2.2)), zorder=2)
    ax.axvline(th_n, color=ACCENT, lw=1.3, zorder=2)
    base = N_BLUE
    for i, r in n.iterrows():
        clears = float(r["N_k"]) >= mes
        ax.plot([0, r["N_k"]], [i] * 2, color=base, lw=1.1, alpha=0.7, solid_capstyle="round", zorder=3)
        ax.plot(r["N_k"], i, "o", ms=5.2, zorder=4, mfc=(base if clears else "white"), mec=base, mew=1.1)
    ax.set_yticks(range(len(n)))
    ax.set_yticklabels([f"seed {s}" for s in n["seed"]])
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(len(n) - 0.05, -0.95)
    ax.set_xlim(-0.006, 0.228)
    ax.set_xticks([0, 0.05, 0.10, 0.15, 0.20])
    ax.set_xlabel(r"$N_k$: signed full $-$ zero mean")
    ax.set_title("(a) Eight locked seed units", loc="left", pad=4, color=INK)
    # MES and theta_N sit within 0.005 of each other, so they share the top row only by
    # anchoring away from their own rule; the open-marker note drops to the free bottom row.
    ax.text(mes - 0.004, -0.6, f"MES {mes:.2f}", fontsize=MIN_PT, color=GREY, ha="right", va="center", zorder=6, bbox=HALO)
    ax.text(th_n + 0.005, -0.6, rf"$\theta_N$ {th_n:.4f}", fontsize=MIN_PT, color=ACCENT, ha="left", va="center")
    ax.text(0.225, len(n) - 0.45, "open: $N_k<$MES", fontsize=MIN_PT, color=MUTE, ha="right", va="center")

    # (b) Thirty of these 48 cells are exactly zero and none is negative. The panel is small
    # enough that every non-zero cell can carry its exact value, so the colour ramp only has
    # to make the row structure findable, not to be read off against a key.
    ykey = -1.15
    axh.imshow(V, cmap=N_CMAP, vmin=0.0, vmax=vmax, aspect="auto", zorder=2,
               interpolation="nearest")
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            v = float(V[i, j])
            if v > 0:
                axh.text(j, i, f"{v:.2f}".lstrip("0"), ha="center", va="center",
                         fontsize=MIN_PT, zorder=4,
                         color=("white" if v > 0.55 * vmax else "#23404f"))
    axh.set_xticks(np.arange(-0.5, V.shape[1], 1.0), minor=True)
    axh.set_yticks(np.arange(-0.5, V.shape[0], 1.0), minor=True)
    axh.grid(which="major", visible=False)
    axh.grid(which="minor", color="white", lw=1.0, zorder=3)
    axh.tick_params(which="minor", length=0)
    sns.despine(ax=axh, left=True, bottom=True)
    nx, ny = V.shape[1] - 0.5, V.shape[0] - 0.5
    for k in (1.5, 3.5):                     # P / A / D group separators
        axh.plot([-0.5, nx], [k, k], color="#94a0a8", lw=0.8, zorder=5)
    # the zero cells are near-white, so the matrix needs its own outline against the page
    axh.plot([-0.5, nx, nx, -0.5, -0.5], [-0.5, -0.5, ny, ny, -0.5],
             color="#c3ccd2", lw=0.8, zorder=5)
    axh.set_xticks(range(len(seed_order)), [str(s) for s in seed_order])
    axh.set_yticks(range(len(dir_order)), dir_order)
    axh.tick_params(length=0)
    axh.set_xlim(-0.75, len(seed_order) + 1.6)
    axh.set_ylim(len(dir_order) - 0.4, -1.75)
    axh.set_xlabel("History seed")
    axh.set_title(r"(b) Mean $\bar{n}_{h,k}$ by direction (secondary)", loc="left", pad=4, color=INK)

    # One annotation band above the grid: what an unlabelled cell means on the left, the
    # header of the share column on the right. Neither needs a row of its own.
    axh.text(-0.5, ykey, "unlabelled cell $=$ exactly 0 (30/48)", ha="left", va="center",
             fontsize=MIN_PT, color=MUTE)
    xshare = len(seed_order) + 0.5
    axh.text(xshare, ykey, r"% of $\theta_N$", ha="center", va="center", fontsize=MIN_PT, color=MUTE)
    for i, name in enumerate(dir_order):
        pct = 100.0 * shares[name]
        axh.text(xshare, i, "0" if pct == 0 else f"{pct:.1f}", ha="center", va="center",
                 fontsize=MIN_PT, color=(MUTE if pct == 0 else INK))

    # also write legacy single-panel names for any old includes
    _save(fig, "fig_N_structure")
    # Keep fig_N_units / fig_n_heatmap as aliases of the same canvas for checklist tools.
    for stem in ("fig_N_units", "fig_n_heatmap"):
        import shutil

        shutil.copyfile(OUT / "fig_N_structure.pdf", OUT / f"{stem}.pdf")
        shutil.copyfile(OUT / "fig_N_structure.png", OUT / f"{stem}.png")


#: Hand-authored figures, and the printed width each is placed at in main.tex. The PDF is
#: written with a resolution that makes its natural size equal that printed width, so the
#: page never rescales the raster and tools.r7_gate sees a placement scale of one.
AUTHORED = {
    "fig_mechanism": COL_W,
    "fig_E_items": COL_W,
    "fig_N_seeds": COL_W,
    "fig_E_grid": COL_W,
    "fig_E_split": COL_W,
    "fig_N_dirseed": COL_W,
}


def export_authored() -> list[str]:
    """Wrap each hand-authored PNG in a PDF sized to its placement width."""
    from PIL import Image

    written = []
    for stem, width_in in AUTHORED.items():
        src = OUT / f"{stem}.png"
        if not src.is_file():
            continue
        img = Image.open(src).convert("RGB")
        img.save(OUT / f"{stem}.pdf", "PDF", resolution=img.width / width_in)
        written.append(f"{stem}.pdf")
    return written


def main() -> int:
    _setup()
    C = json.loads((UP / "00_constants.json").read_text(encoding="utf-8"))
    export_e_units(C)
    export_n_structure(C)
    authored = export_authored()
    meta = {
        "source": "reports/plot_ready",
        "figures": authored + ["fig_E_units.pdf", "fig_N_structure.pdf"],
        "canvas_width_in": FULL_W,
        "theta_E": C["theta_E"],
        "theta_N": C["theta_N"],
    }
    (OUT / "figure_export_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("exported", meta["figures"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
