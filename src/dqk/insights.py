"""Business analyses on the clean mart (code plan v1.1, P3 and P4).

    python -m dqk.insights                 # CSVs + figures
    python -m dqk.insights --report-figs   # also copy figures to ../../hinh/en/p2_*.png

Same population as the KPI spec: delivered orders (A01-A03) or all orders with a review
(A04, A05) purchased in [window_start, window_end) of config/kpi_spec.yaml.

  a01_cohort_retention     results/insights/cohort.csv     docs/figures/insight_cohort.png
  a02_customer_segments    results/insights/segments.csv   docs/figures/insight_segments.png
  a03_seller_pareto        results/insights/pareto.csv     docs/figures/insight_pareto.png
  a04_late_delivery_whatif results/insights/whatif_late.csv
  a05_late_by_state        results/insights/late_by_state.csv
plus results/insights/summary.json (headline numbers quoted in the report).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dqk import DOCS_DIR, RESULTS_DIR, ROOT  # noqa: E402
from dqk.config import load_kpi_spec  # noqa: E402
from dqk.db import connect, run_sql_file  # noqa: E402
from dqk.tables import Mart  # noqa: E402

OUT_DIR = RESULTS_DIR / "insights"
FIG_DIR = DOCS_DIR / "figures"
REPORT_FIG_DIR = ROOT.parents[1] / "hinh" / "en"
QUERIES = {
    "cohort": "a01_cohort_retention",
    "segments": "a02_customer_segments",
    "pareto": "a03_seller_pareto",
    "whatif_late": "a04_late_delivery_whatif",
    "late_by_state": "a05_late_by_state",
}
BLUE, RED, GREY = "#2563EB", "#DC2626", "#6B7280"


def run_insights(mart: Mart, params: dict | None = None) -> dict[str, pd.DataFrame]:
    params = params or load_kpi_spec().params.model_dump()
    con = connect(mart.as_tables())
    out = {k: run_sql_file(con, f"analysis/{q}.sql", params) for k, q in QUERIES.items()}
    con.close()
    return out


def pareto_share(pareto: pd.DataFrame, dimension: str, top: float) -> float:
    """GMV share of the top ``top`` share of entities (e.g. 0.2 = top 20 % of sellers)."""
    p = pareto[pareto["dimension"] == dimension]
    k = max(1, int(np.ceil(top * len(p))))
    return float(p.loc[p["rank"] <= k, "gmv"].sum() / p["gmv"].sum())


def summary(r: dict[str, pd.DataFrame]) -> dict:
    c = r["cohort"]
    full = c[~c["censored"]]
    pooled = full.groupby("horizon_days")[["n_repeat", "n_customers"]].sum()
    seg = r["segments"]
    w = r["whatif_late"].set_index("scenario")
    st = r["late_by_state"]
    sellers = r["pareto"][r["pareto"]["dimension"] == "seller"]
    return {
        "customers": int(c.loc[c["horizon_days"] == 30, "n_customers"].sum()),
        "repeat_rate_by_horizon_uncensored": {
            int(h): float(x.n_repeat / x.n_customers) for h, x in pooled.iterrows()
        },
        "repeat_share_all": float(
            (seg["repeat_share"] * seg["n_customers"]).sum() / seg["n_customers"].sum()
        ),
        "gmv_share_top_m_quintile": float(
            seg.loc[seg["m_quintile"] == 5, "gmv"].sum() / seg["gmv"].sum()
        ),
        "n_sellers": int(len(sellers)),
        "gmv_share_top_1pct_sellers": pareto_share(r["pareto"], "seller", 0.01),
        "gmv_share_top_10pct_sellers": pareto_share(r["pareto"], "seller", 0.10),
        "gmv_share_top_20pct_sellers": pareto_share(r["pareto"], "seller", 0.20),
        "gmv_share_top_5_categories": float(
            r["pareto"].query("dimension == 'category' and rank <= 5")["gmv"].sum()
            / r["pareto"].query("dimension == 'category'")["gmv"].sum()
        ),
        "late_share": float(w.loc["current", "late_share"]),
        "avg_review_current": float(w.loc["current", "avg_review_score"]),
        "avg_review_if_0pct_late": float(w.loc["0 %", "avg_review_score"]),
        "negative_share_current": float(w.loc["current", "negative_share"]),
        "negative_share_if_0pct_late": float(w.loc["0 %", "negative_share"]),
        "worst_states_on_time": st.head(3)[["state", "on_time_rate"]].to_dict("records"),
        "sp_share_of_late": float(st.loc[st["state"] == "SP", "share_of_late"].iloc[0]),
        "rj_share_of_late": float(st.loc[st["state"] == "RJ", "share_of_late"].iloc[0]),
    }


def _style():
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def fig_cohort(c: pd.DataFrame, path: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    labels = {30: "within 1 month", 91: "within 3 months", 182: "within 6 months",
              365: "within 12 months"}
    colors = {30: "#93C5FD", 91: "#60A5FA", 182: BLUE, 365: "#1E3A8A"}
    for h, g in c.groupby("horizon_days"):
        g = g[~g["censored"]]
        ax.plot(g["cohort"], g["repeat_rate"] * 100, marker="o", ms=3.5, lw=1.5,
                color=colors[int(h)], label=labels[int(h)])
    ax.set_ylabel("Customers with a second order, %")
    ax.set_xlabel("Cohort (month of first delivered order)")
    cohorts = sorted(c["cohort"].unique())
    ax.set_xticks(cohorts[::2])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    ax.text(0.99, 0.02, "Censored cohort-horizon cells (window ends 2018-08) not shown",
            transform=ax.transAxes, ha="right", fontsize=9, color=GREY)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def fig_segments(s: pd.DataFrame, path: Path) -> Path:
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    panels = [
        ("repeat_share", "Customers with 2+ orders, %", lambda v: v * 100, "{:.1f}"),
        ("gmv", "GMV (million BRL)", lambda v: v / 1e6, "{:.2f}"),
    ]
    for ax, (col, title, f, fmt) in zip(axes, panels, strict=True):
        m = s.pivot(index="r_quintile", columns="m_quintile", values=col)
        m = m.sort_index(ascending=False)
        v = f(m.to_numpy(float))
        im = ax.imshow(v, cmap="Blues")
        for (i, j), x in np.ndenumerate(v):
            ax.text(j, i, fmt.format(x), ha="center", va="center", fontsize=9,
                    color="white" if x > v.max() * 0.6 else "black")
        ax.set_xticks(range(5), [f"M{q}" for q in m.columns])
        ax.set_yticks(range(5), [f"R{q}" for q in m.index])
        ax.set_xlabel("Monetary quintile (M5 = highest value)")
        ax.set_ylabel("Recency quintile (R5 = most recent)")
        ax.set_title(title, fontsize=11)
        for sp in ax.spines.values():
            sp.set_visible(False)
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def fig_pareto(p: pd.DataFrame, path: Path) -> Path:
    _style()
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for dim, color in (("seller", BLUE), ("category", RED)):
        g = p[p["dimension"] == dim]
        x = np.r_[0, g["cum_share_entities"].to_numpy() * 100]
        y = np.r_[0, g["cum_share_gmv"].to_numpy() * 100]
        name = {"seller": "Sellers", "category": "Categories"}[dim]
        ax.plot(x, y, color=color, lw=1.8, label=f"{name} (n = {len(g):,})")
    ax.plot([0, 100], [0, 100], color=GREY, lw=0.8, ls="--", label="Equal shares")
    share = pareto_share(p, "seller", 0.2) * 100
    ax.axvline(20, color=GREY, lw=0.6, ls=":")
    ax.annotate(f"Top 20 % of sellers: {share:.1f} % of GMV", xy=(20, share),
                xytext=(32, share - 18), arrowprops={"arrowstyle": "->", "color": GREY},
                fontsize=10)
    ax.set_xlabel("Cumulative share of sellers / categories (sorted by GMV), %")
    ax.set_ylabel("Cumulative share of GMV, %")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 101)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def write_all(r: dict[str, pd.DataFrame], report_figs: bool = False) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in r.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False, lineterminator="\n")
    s = summary(r)
    (OUT_DIR / "summary.json").write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    figs = {
        "cohort": fig_cohort(r["cohort"], FIG_DIR / "insight_cohort.png"),
        "segments": fig_segments(r["segments"], FIG_DIR / "insight_segments.png"),
        "pareto": fig_pareto(r["pareto"], FIG_DIR / "insight_pareto.png"),
    }
    if report_figs and REPORT_FIG_DIR.exists():
        for name, f in figs.items():
            shutil.copyfile(f, REPORT_FIG_DIR / f"p2_insight_{name}.png")
    return s


def main(argv=None) -> int:
    from dqk.experiment.runner import load_clean_mart

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-figs", action="store_true")
    args = ap.parse_args(argv)
    s = write_all(run_insights(load_clean_mart()), args.report_figs)
    print(json.dumps(s, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
