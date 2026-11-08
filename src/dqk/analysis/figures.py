"""Paper figures for RQ1-RQ3 (code plan 4.5). Static PNG (300 dpi) + matching CSV tables.

Error codes E1-E6 keep one colour and one marker each in every figure (colour follows the
entity). The palette passed the categorical colour checks (CVD and normal-vision
separation); three colours are below 3:1 contrast, so every series also has a distinct
marker and a legend, and each figure has a CSV with the plotted numbers.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

from dqk.analysis.stats import GROUP_ORDER, group_distortion  # noqa: E402

CODE_COLOR = {
    "E1": "#2a78d6",
    "E2": "#eb6834",
    "E3": "#1baf7a",
    "E4": "#eda100",
    "E5": "#e87ba4",
    "E6": "#008300",
}
CODE_MARKER = {"E1": "o", "E2": "s", "E3": "^", "E4": "D", "E5": "v", "E6": "P"}
CODE_NAME = {
    "E1": "E1 duplicates",
    "E2": "E2 orphan keys",
    "E3": "E3 missing values",
    "E4": "E4 timestamps",
    "E5": "E5 unit errors",
    "E6": "E6 category errors",
}
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SEQ = LinearSegmentedColormap.from_list(
    "seq_blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
)
KPI_ORDER = [f"K{i}" for i in range(1, 16)]

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.titlesize": 10,
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _save(fig, out: Path, name: str, table: pd.DataFrame | None = None) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.png"
    fig.savefig(p)
    plt.close(fig)
    if table is not None:
        table.to_csv(out / f"{name}.csv", index=False)
    return p


def _legend_codes(ax_or_fig, codes, **kw):
    handles = [
        plt.Line2D(
            [], [], color=CODE_COLOR[c], marker=CODE_MARKER[c], lw=2, ms=6, label=CODE_NAME[c]
        )
        for c in codes
    ]
    return ax_or_fig.legend(handles=handles, **kw)


# ------------------------------------------------------------ 1. heatmap


def fig_heatmap(desc: pd.DataFrame, out: Path, rate: float = 0.05) -> Path:
    """Median distortion: rows = error x mechanism, columns = KPI, at one rate."""
    d = desc[np.isclose(desc["rate"], rate)].copy()
    d["row"] = d["code"] + " " + d["variant"] + " · " + d["mechanism"]
    m = d.pivot_table(index="row", columns="kpi_id", values="median", aggfunc="first")
    m = m[[k for k in KPI_ORDER if k in m.columns]].sort_index()
    floor = 1e-4
    shown = m.clip(lower=floor).replace(np.inf, np.nan)
    fig, ax = plt.subplots(figsize=(9.5, 0.36 * len(m) + 1.6))
    im = ax.imshow(
        shown.to_numpy(float),
        cmap=SEQ,
        aspect="auto",
        norm=LogNorm(vmin=floor, vmax=max(1.0, float(np.nanmax(shown.to_numpy())))),
    )
    ax.set_xticks(range(m.shape[1]), m.columns)
    ax.set_yticks(range(m.shape[0]), m.index)
    ax.tick_params(axis="y", colors=INK2, labelsize=8)
    ax.tick_params(axis="x", colors=INK2)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.iat[i, j]
            if pd.isna(v) or v < 0.001:
                continue
            txt = (
                "∞"
                if np.isinf(v)
                else f"{v:.1%}"
                if v < 0.1
                else f"{v:.0%}"
                if v < 10
                else f"{v:.0f}×"
            )
            dark = np.isfinite(v) and v > 0.05
            ax.text(
                j, i, txt, ha="center", va="center", fontsize=6.5, color="white" if dark else INK
            )
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("median distortion (log scale)", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title(
        f"Median KPI distortion at error rate {rate:.0%} "
        "(scalar: relative error · K11–K13: 1 − top-k overlap · K14: MAPD · "
        "K15: flip share)",
        loc="left",
        fontsize=9,
    )
    table = m.reset_index()
    return _save(fig, out, f"fig1_heatmap_rate{int(round(rate * 100)):02d}", table)


# ------------------------------------------------------------ 2. lines vs rate


def fig_rate_lines(
    kpi: pd.DataFrame, out: Path, kpis=("K1", "K4", "K5", "K6", "K14"), mechanism: str = "MCAR"
) -> Path:
    """Distortion vs error rate with the 2.5-97.5 % band over seeds, one panel per KPI.
    Continuous KPIs only: ranking KPIs move in steps of 1/k and do not suit a log axis."""
    d = kpi[(kpi["mechanism"] == mechanism) & kpi["kpi_id"].isin(kpis)]
    q = (
        d.replace(np.inf, np.nan)
        .groupby(["kpi_id", "code", "rate"])["distortion"]
        .quantile([0.025, 0.5, 0.975])
        .unstack()
        .reset_index()
        .rename(columns={0.025: "q025", 0.5: "median", 0.975: "q975"})
    )
    fig, axes = plt.subplots(1, len(kpis), figsize=(2.8 * len(kpis), 3.6), sharex=True)
    floor = 1e-5
    for ax, k in zip(np.atleast_1d(axes), kpis, strict=True):
        qk = q[q["kpi_id"] == k]
        for c in sorted(qk["code"].unique()):
            s = qk[qk["code"] == c].sort_values("rate")
            if s["q975"].max() < floor:
                continue  # never moves this KPI
            ax.fill_between(
                s["rate"],
                s["q025"].clip(lower=floor),
                s["q975"].clip(lower=floor),
                color=CODE_COLOR[c],
                alpha=0.15,
                lw=0,
            )
            ax.plot(
                s["rate"],
                s["median"].clip(lower=floor),
                color=CODE_COLOR[c],
                lw=2,
                marker=CODE_MARKER[c],
                ms=5,
                mec="white",
                mew=1,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([0.01, 0.02, 0.05, 0.1, 0.2], ["1%", "2%", "5%", "10%", "20%"])
        ax.minorticks_off()
        ax.set_title(k, loc="left")
        ax.set_xlabel("error rate")
    np.atleast_1d(axes)[0].set_ylabel("distortion (median, 95 % band)")
    fig.suptitle(
        f"KPI distortion grows with the error rate ({mechanism}); errors that never "
        "move a KPI are omitted from its panel",
        x=0.01,
        ha="left",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.1, 1, 0.95), w_pad=1.5)
    _legend_codes(
        fig, sorted(q["code"].unique()), loc="lower center", ncol=6, bbox_to_anchor=(0.5, 0.0)
    )
    return _save(fig, out, "fig2_rate_lines", q)


# ------------------------------------------------------------ 3. RQ2 scatter


def fig_dq_vs_distortion(
    runs: pd.DataFrame, kpi: pd.DataFrame, rq2: pd.DataFrame, out: Path
) -> Path:
    """Cell medians of dq_drop vs group distortion, one panel per KPI group (RQ2)."""
    gd = group_distortion(kpi).merge(
        runs[["cell_id", "seed", "code", "mechanism", "rate", "dq_drop"]], on=["cell_id", "seed"]
    )
    cm = (
        gd.groupby(["group", "cell_id", "code", "mechanism", "rate"])[["dq_drop", "distortion"]]
        .median()
        .reset_index()
    )
    groups = [g for g in GROUP_ORDER if g in set(cm["group"])]
    ncol = 3
    nrow = int(np.ceil(len(groups) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(10, 2.9 * nrow), squeeze=False)
    rho = rq2.set_index("group")
    for ax, g in zip(axes.flat, groups, strict=False):
        s = cm[cm["group"] == g]
        for c in sorted(s["code"].unique()):
            t = s[s["code"] == c]
            ax.scatter(
                t["dq_drop"],
                t["distortion"],
                s=36,
                color=CODE_COLOR[c],
                marker=CODE_MARKER[c],
                edgecolors="white",
                linewidths=1,
                zorder=3,
            )
        ax.set_yscale("symlog", linthresh=1e-4)
        top = float(s["distortion"].replace(np.inf, np.nan).max())
        ax.set_ylim(0, max(top * 2 if np.isfinite(top) else 1.0, 1e-3))
        ax.set_title(g, loc="left")
        if g in rho.index and pd.notna(rho.at[g, "rho"]):
            r = rho.loc[g]
            ax.text(
                0.98,
                0.04,
                f"ρ = {r['rho']:.2f} [{r['ci_lo']:.2f}, {r['ci_hi']:.2f}]",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=8,
                color=INK2,
            )
        else:
            ax.text(
                0.98,
                0.04,
                "ρ undefined (no variation)",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=8,
                color=MUTED,
            )
    for ax in axes.flat[len(groups) :]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("DQ score drop")
    for ax in axes[:, 0]:
        ax.set_ylabel("distortion")
    _legend_codes(
        fig, sorted(cm["code"].unique()), loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.03)
    )
    fig.suptitle(
        "RQ2: DQ score drop vs KPI distortion (one point per cell, median over seeds; "
        "ρ over all runs, 95 % cluster-bootstrap CI)",
        x=0.01,
        ha="left",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    return _save(fig, out, "fig3_dq_vs_distortion", cm)


# ------------------------------------------------------------ 4. RQ3 silent rate


def fig_silent(
    rq3: pd.DataFrame, out: Path, name: str = "fig4_silent_rate", title: str | None = None
) -> Path:
    """Silent-error rate with Wilson 95 % CI per error type across rates (RQ3)."""
    fig, ax = plt.subplots(figsize=(7, 3.6))
    codes = sorted(rq3["code"].unique())
    offsets = np.linspace(-0.06, 0.06, len(codes))
    placed: list[dict] = []  # direct-label groups
    for off, c in zip(offsets, codes, strict=True):
        s = rq3[rq3["code"] == c].sort_values("rate")
        x = s["rate"] * np.exp(off)  # small horizontal dodge on the log axis
        ax.errorbar(
            x,
            s["silent_rate"],
            yerr=[  # clip: at a rate of 0 or 1 the Wilson bound can miss it by ~1e-16
                (s["silent_rate"] - s["silent_lo"]).clip(lower=0),
                (s["silent_hi"] - s["silent_rate"]).clip(lower=0),
            ],
            color=CODE_COLOR[c],
            marker=CODE_MARKER[c],
            ms=6,
            mec="white",
            mew=1,
            lw=2,
            capsize=2,
            elinewidth=1,
        )
        last = s.iloc[-1]
        for g in placed:  # series ending within 0.07 of each other share one label
            if abs(last["silent_rate"] - g["y"]) < 0.07:
                g["codes"].append(c)
                break
        else:
            placed.append({"y": last["silent_rate"], "x": last["rate"], "codes": [c]})
    for g in placed:
        label = CODE_NAME[g["codes"][0]] if len(g["codes"]) == 1 else ", ".join(g["codes"])
        ax.annotate(
            label,
            (g["x"] * np.exp(offsets[-1]), g["y"]),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=INK2,
        )
    ax.set_xscale("log")
    ax.set_xticks([0.01, 0.02, 0.05, 0.1, 0.2], ["1%", "2%", "5%", "10%", "20%"])
    ax.minorticks_off()
    ax.set_xlim(0.008, 0.45)
    ax.set_ylim(-0.03, 1.05)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("error rate")
    ax.set_ylabel("share of runs that are silent")
    tau = rq3["tau"].iloc[0]
    ax.set_title(
        title
        or f"RQ3: material KPI change (τ = {tau:g}) that no DQ check flags "
        "(mechanisms pooled, Wilson 95 % CI)",
        loc="left",
        fontsize=9.5,
    )
    _legend_codes(ax, codes, loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    return _save(fig, out, name, rq3)


# ------------------------------------------------------------ 5. Olist vs Online Retail II


def fig_dataset_compare(cmp: pd.DataFrame, out: Path, kpis=("K1", "K10", "K14")) -> Path:
    """Median distortion per error type and rate, Olist (solid) vs Online Retail II
    (dashed), MCAR. ``cmp`` is the x2 table of make_all (one row per code x rate x KPI)."""
    fig, axes = plt.subplots(1, len(kpis), figsize=(3.2 * len(kpis), 3.2), sharex=True)
    codes = sorted(cmp["code"].unique())
    for ax, k in zip(np.atleast_1d(axes), kpis, strict=True):
        d = cmp[cmp["kpi_id"] == k]
        for c in codes:
            s = d[d["code"] == c].sort_values("rate")
            for col, ls in (("olist_median", "-"), ("retail_median", "--")):
                y = s[col].clip(lower=1e-6)
                ax.plot(
                    s["rate"],
                    y,
                    ls=ls,
                    color=CODE_COLOR[c],
                    marker=CODE_MARKER[c],
                    ms=4,
                    lw=1.6,
                    mec="white",
                    mew=0.6,
                )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([0.01, 0.02, 0.05, 0.1, 0.2], ["1%", "2%", "5%", "10%", "20%"])
        ax.minorticks_off()
        ax.set_ylim(5e-7, None)
        ax.set_title(k, loc="left", fontsize=10)
        ax.set_xlabel("error rate")
    np.atleast_1d(axes)[0].set_ylabel("median distortion (log)")
    fig.suptitle(
        "Olist (solid) vs Online Retail II (dashed), MCAR; values ≤ 1e-6 drawn at 1e-6",
        x=0.01,
        ha="left",
        fontsize=9.5,
    )
    _legend_codes(fig, codes, loc="lower center", ncol=len(codes), bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    return _save(fig, out, "fig7_retail_vs_olist", cmp[cmp["kpi_id"].isin(kpis)])


__all__ = [
    "fig_dataset_compare",
    "fig_dq_vs_distortion",
    "fig_heatmap",
    "fig_rate_lines",
    "fig_silent",
]
