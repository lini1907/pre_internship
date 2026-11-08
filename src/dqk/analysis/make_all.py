"""Rebuild every result table and figure from results/runs/ in one command.

    python -m dqk.analysis.make_all                # main + robustness + retail (if present)
    python -m dqk.analysis.make_all --n-boot 200   # quick check

Writes results/tables/*.csv, results/tables/summary.md, results/tables/paper_tables.md
and results/figures/*.png. Table prefixes: t = main grid, r = robustness, x = Online
Retail II, p = summary tables for the paper.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from dqk import RESULTS_DIR
from dqk.analysis import figures as F
from dqk.analysis.stats import (
    RQ1_KPIS,
    describe_cells,
    detecting_checks,
    load_results,
    rq1_friedman,
    rq2_spearman,
    rq3_silent,
)
from dqk.experiment.measures import TAUS

RUNS, TABLES, FIGS = RESULTS_DIR / "runs", RESULTS_DIR / "tables", RESULTS_DIR / "figures"


def _md(df: pd.DataFrame, floatfmt: str = ".3g") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = [
            format(v, floatfmt) if isinstance(v, float) and np.isfinite(v) else str(v) for v in r
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main_grid(folder: Path, n_boot: int) -> list[str]:
    r = load_results(folder)
    md = [
        "# Stage B results: main grid\n",
        f"{r.runs['cell_id'].nunique()} cells, {len(r.runs)} runs, "
        f"seeds per cell {r.runs.groupby('cell_id').size().min()}–"
        f"{r.runs.groupby('cell_id').size().max()}. "
        f"Max |achieved − target rate| = "
        f"{(r.runs['achieved_rate'] - r.runs['rate']).abs().max():.2e}.\n",
    ]

    desc = describe_cells(r.kpi)
    desc.to_csv(TABLES / "t1_describe_main.csv", index=False)

    rq1 = rq1_friedman(r.kpi)
    rq1["tests"].to_csv(TABLES / "t2_rq1_friedman.csv", index=False)
    rq1["ranks"].to_csv(TABLES / "t2_rq1_mean_ranks.csv", index=False)
    rq1["nemenyi"].to_csv(TABLES / "t2_rq1_nemenyi.csv")
    rq1["blocks"].reset_index().to_csv(TABLES / "t2_rq1_blocks.csv", index=False)
    md += [
        "## RQ1: which error type distorts KPIs most (MCAR, Friedman)\n",
        "Blocks = KPI (K1–K10, K14) × rate; value = cell median distortion.",
        f" Blocks where all error types tie: {rq1['n_blocks_all_tied']}.\n",
        _md(rq1["tests"]),
        "\nMean rank (1 = least distortion):\n",
        _md(rq1["ranks"]),
        "\nNemenyi p-values:\n",
        _md(rq1["nemenyi"].reset_index()),
        "",
    ]

    rq2 = rq2_spearman(r.runs, r.kpi, n_boot=n_boot)
    rq2.to_csv(TABLES / "t3_rq2_spearman.csv", index=False)
    rq2n = rq2_spearman(r.runs, r.kpi, n_boot=n_boot, detection="n_worsened")
    rq2n.to_csv(TABLES / "t3b_rq2_spearman_n_worsened.csv", index=False)
    md += [
        "## RQ2: Spearman ρ between DQ score drop and KPI distortion\n",
        "All runs; 95 % CI and p from a bootstrap that resamples cells (p floor 1/n_boot);"
        " p_holm across groups; p_naive treats runs as independent (reference only).\n",
        _md(rq2),
        "\nSame with the number of worsened checks as detection signal:\n",
        _md(rq2n),
        "",
    ]

    rq3 = rq3_silent(r.runs, by=("code", "rate"), tau=0.01)
    rq3.to_csv(TABLES / "t4_rq3_silent_code_rate.csv", index=False)
    rq3m = rq3_silent(r.runs, by=("code", "variant", "mechanism", "rate"), tau=0.01)
    rq3m.to_csv(TABLES / "t4b_rq3_silent_cell.csv", index=False)
    rq3t = pd.concat([rq3_silent(r.runs, by=("code",), tau=t) for t in TAUS])
    rq3t.to_csv(TABLES / "t4c_rq3_silent_tau.csv", index=False)
    md += [
        "## RQ3: silent errors (τ = 0.01, mechanisms pooled)\n",
        _md(
            rq3[
                [
                    "code",
                    "rate",
                    "n_runs",
                    "silent_rate",
                    "silent_lo",
                    "silent_hi",
                    "material_rate",
                    "detected_rate",
                ]
            ]
        ),
        "\nMateriality threshold sensitivity (all rates pooled):\n",
        _md(rq3t[["code", "tau", "silent_rate", "silent_lo", "silent_hi", "material_rate"]]),
        "",
    ]

    det = detecting_checks(r.runs)
    det.reset_index().to_csv(TABLES / "t5_detecting_checks.csv", index=False)
    md += [
        "## Which checks react to which error (share of runs)\n",
        _md(det.reset_index(), ".2f"),
        "",
    ]

    figs = [
        F.fig_heatmap(desc, FIGS, 0.05),
        F.fig_heatmap(desc, FIGS, 0.20),
        F.fig_rate_lines(r.kpi, FIGS),
        F.fig_dq_vs_distortion(r.runs, r.kpi, rq2, FIGS),
        F.fig_silent(rq3, FIGS),
    ]
    md += ["## Figures\n"] + [f"- `{p.relative_to(RESULTS_DIR.parent).as_posix()}`" for p in figs]
    return md, r


def rq1_sensitivity(main, rk) -> pd.DataFrame:
    """RQ1 under the design choices left open (D6 and the ranking KPIs):
    E1 as duplicate_order or duplicate_order_rekeyed; KPI set K1-K10+K14 or also K11-K13+K15;
    ranking distortion as 1 - top-k overlap or 1 - Kendall tau_b."""
    rekeyed = pd.concat([main.kpi[main.kpi["code"] != "E1"], rk.kpi], ignore_index=True)
    all_kpis = RQ1_KPIS + ["K11", "K12", "K13", "K15"]

    def by_tau(k: pd.DataFrame) -> pd.DataFrame:
        k = k.copy()
        r = k["kpi_type"] == "ranking"
        k.loc[r, "distortion"] = 1.0 - k.loc[r, "kendall_tau_b"]
        return k

    variants = [
        ("main: E1 same key, 11 KPIs", main.kpi, RQ1_KPIS),
        ("E1 same key, 15 KPIs, overlap", main.kpi, all_kpis),
        ("E1 same key, 15 KPIs, Kendall tau", by_tau(main.kpi), all_kpis),
        ("E1 re-keyed, 11 KPIs", rekeyed, RQ1_KPIS),
        ("E1 re-keyed, 15 KPIs, overlap", rekeyed, all_kpis),
        ("E1 re-keyed, 15 KPIs, Kendall tau", by_tau(rekeyed), all_kpis),
    ]
    rows = []
    for name, k, kpis in variants:
        r = rq1_friedman(k, kpis=kpis)
        t = r["tests"].iloc[0]
        rows.append(
            r["ranks"].assign(
                variant=name,
                n_blocks=int(t["n_blocks"]),
                n_tied=r["n_blocks_all_tied"],
                kendall_w=t["kendall_w"],
                p=t["p"],
            )
        )
    return pd.concat(rows, ignore_index=True)


def robustness(root: Path, main, n_boot: int) -> list[str]:
    scen = sorted(p for p in root.iterdir() if p.is_dir() and any(p.glob("*.runs.parquet")))
    if not scen:
        return []
    md = ["\n# Robustness (proposal 6.5)\n"]
    silent, rho, ranks, kpi_cmp = [], [], [], []
    main_desc = describe_cells(main.kpi).set_index(
        ["code", "variant", "mechanism", "rate", "kpi_id"]
    )["median"]
    for folder in [None, *scen]:
        r = main if folder is None else load_results(folder)
        name = "main" if folder is None else folder.name
        rates = sorted(r.runs["rate"].unique()) if folder else [0.05, 0.10]
        runs = r.runs[r.runs["rate"].isin(rates)]
        kpi = r.kpi[r.kpi["rate"].isin(rates)]
        s = rq3_silent(runs, by=("code", "variant", "rate"), tau=0.01)
        silent.append(s.assign(scenario=name))
        rho.append(rq2_spearman(runs, kpi, n_boot=n_boot).assign(scenario=name))
        if runs.groupby("code")["variant"].nunique().max() == 1 and runs["code"].nunique() == 6:
            rk = rq1_friedman(kpi)
            ranks.append(
                rk["ranks"].assign(
                    scenario=name,
                    kendall_w=rk["tests"].iloc[0]["kendall_w"],
                    p=rk["tests"].iloc[0]["p"],
                )
            )
        if folder is not None:
            d = describe_cells(kpi)
            d["main_median"] = d.set_index(
                ["code", "variant", "mechanism", "rate", "kpi_id"]
            ).index.map(main_desc)
            kpi_cmp.append(d.assign(scenario=name))
    silent = pd.concat(silent)
    silent.to_csv(TABLES / "r1_silent_by_scenario.csv", index=False)
    rho = pd.concat(rho)
    rho.to_csv(TABLES / "r2_rq2_rho_by_scenario.csv", index=False)
    if ranks:
        ranks = pd.concat(ranks)
        ranks.to_csv(TABLES / "r3_rq1_ranks_by_scenario.csv", index=False)
        md += [
            "## RQ1 mean ranks per scenario (rates 5 % and 10 %, MCAR)\n",
            _md(
                ranks.pivot_table(
                    index="code", columns="scenario", values="mean_rank"
                ).reset_index()
            ),
            "\nKendall's W: "
            + ", ".join(
                f"{s} {w:.2f}" for s, w in ranks.groupby("scenario")["kendall_w"].first().items()
            ),
            "",
        ]
    if kpi_cmp:
        pd.concat(kpi_cmp).to_csv(TABLES / "r4_kpi_median_vs_main.csv", index=False)
    md += [
        "## RQ2 ρ per scenario\n",
        _md(rho.pivot_table(index="group", columns="scenario", values="rho").reset_index()),
        "\n## RQ3 silent rate per scenario (τ = 0.01)\n",
        _md(
            silent.pivot_table(
                index=["code", "variant", "rate"], columns="scenario", values="silent_rate"
            ).reset_index()
        ),
        "",
    ]
    if "rekeyed" in {p.name for p in scen}:
        rk = load_results(root / "rekeyed")
        sens = rq1_sensitivity(main, rk)
        sens.to_csv(TABLES / "r6_rq1_sensitivity.csv", index=False)
        wide = sens.pivot_table(index="variant", columns="code", values="mean_rank", sort=False)
        meta = sens.groupby("variant", sort=False)[["n_blocks", "n_tied", "kendall_w", "p"]].first()
        md += [
            "## RQ1 sensitivity: E1 variant, KPI set, ranking measure (MCAR, all rates)\n",
            "Mean rank (1 = least distortion). Main result = first row.\n",
            _md(wide.join(meta).reset_index()),
            "",
        ]
        both = pd.concat([main.runs[main.runs["code"] == "E1"], rk.runs])
        s = rq3_silent(both, by=("code", "variant", "rate"), tau=0.01)
        s.to_csv(TABLES / "r5_rq3_rekeyed_vs_duplicate.csv", index=False)
        F.fig_silent(
            s.assign(code=s["code"]).query("variant == 'duplicate_order_rekeyed'"),
            FIGS,
            "fig5_silent_rekeyed",
        )
        md += [
            "## D6: re-keyed duplicates vs plain duplicates (silent rate, τ = 0.01)\n",
            _md(
                s[
                    [
                        "variant",
                        "rate",
                        "silent_rate",
                        "silent_lo",
                        "silent_hi",
                        "material_rate",
                        "detected_rate",
                    ]
                ]
            ),
            "",
        ]
    return md


# Online Retail II: KPIs it shares with Olist; for RQ1 the continuous ones (code plan 4.7).
RETAIL_RQ1_KPIS = ["K1", "K2", "K3", "K9", "K10", "K14"]
RETAIL_SHARED_KPIS = RETAIL_RQ1_KPIS + ["K11", "K13"]


def _ci(lo: float, hi: float) -> str:
    return f"[{lo:.2f}, {hi:.2f}]"


def retail(folder: Path, main, n_boot: int) -> tuple[list[str], dict]:
    """Online Retail II vs Olist: the same analyses, MCAR cells compared like for like."""
    r = load_results(folder)
    md = [
        "\n# Online Retail II (code plan 4.7)\n",
        f"{r.runs['cell_id'].nunique()} cells, {len(r.runs)} runs. KPIs "
        f"{', '.join(RETAIL_SHARED_KPIS)}; E3 = missing_customer_id (Olist main grid: "
        "missing_delivery_date); E6 not applicable. Mapping: `docs/retail_adapter.md`.\n",
    ]
    desc = describe_cells(r.kpi)
    desc.to_csv(TABLES / "x1_retail_describe.csv", index=False)

    keys = ["code", "rate", "kpi_id"]
    o = describe_cells(main.kpi)
    o = o[(o["mechanism"] == "MCAR") & o["kpi_id"].isin(RETAIL_SHARED_KPIS)]
    x = desc[desc["mechanism"] == "MCAR"]
    cmp = o[keys + ["variant", "median"]].merge(
        x[keys + ["variant", "median"]], on=keys, suffixes=("_olist", "_retail")
    )
    cmp = cmp.rename(columns={"median_olist": "olist_median", "median_retail": "retail_median"})
    cmp = cmp[
        [
            "code",
            "variant_olist",
            "variant_retail",
            "rate",
            "kpi_id",
            "olist_median",
            "retail_median",
        ]
    ]
    cmp.to_csv(TABLES / "x2_retail_vs_olist_kpi.csv", index=False)
    at5 = cmp[cmp["rate"] == 0.05].pivot_table(
        index="code", columns="kpi_id", values=["olist_median", "retail_median"]
    )
    at5.columns = [f"{k} {'O' if v.startswith('olist') else 'R'}" for v, k in at5.columns]
    at5 = at5[[c for k in RETAIL_SHARED_KPIS for c in (f"{k} O", f"{k} R") if c in at5]]

    rq1 = {
        "olist (E1-E5)": rq1_friedman(main.kpi[main.kpi["code"] != "E6"], kpis=RETAIL_RQ1_KPIS),
        "retail": rq1_friedman(r.kpi, kpis=RETAIL_RQ1_KPIS),
    }
    ranks = pd.concat(
        [
            v["ranks"].assign(
                dataset=k,
                kendall_w=v["tests"].iloc[0]["kendall_w"],
                p=v["tests"].iloc[0]["p"],
                n_blocks=int(v["tests"].iloc[0]["n_blocks"]),
                n_tied=v["n_blocks_all_tied"],
            )
            for k, v in rq1.items()
        ],
        ignore_index=True,
    )
    ranks.to_csv(TABLES / "x3_rq1_retail_vs_olist.csv", index=False)
    rq1["retail"]["tests"].to_csv(TABLES / "x3b_rq1_retail_friedman.csv", index=False)

    shared = main.kpi[main.kpi["kpi_id"].isin(RETAIL_SHARED_KPIS)]
    rho = pd.concat(
        [
            rq2_spearman(main.runs, shared, n_boot=n_boot).assign(dataset="olist"),
            rq2_spearman(r.runs, r.kpi, n_boot=n_boot).assign(dataset="retail"),
        ],
        ignore_index=True,
    )
    rho.to_csv(TABLES / "x4_rq2_retail_vs_olist.csv", index=False)

    silent = pd.concat(
        [
            rq3_silent(
                d[d["mechanism"] == "MCAR"].assign(dataset=name),
                by=("dataset", "code", "rate"),
                tau=0.01,
            )
            for name, d in (("olist", main.runs), ("retail", r.runs))
        ],
        ignore_index=True,
    )
    silent.to_csv(TABLES / "x5_rq3_silent_retail_vs_olist.csv", index=False)
    det = detecting_checks(r.runs)
    det.reset_index().to_csv(TABLES / "x6_retail_detecting_checks.csv", index=False)

    figs = [
        F.fig_silent(
            rq3_silent(r.runs, by=("code", "rate"), tau=0.01),
            FIGS,
            "fig6_silent_retail",
            "Online Retail II, RQ3: material KPI change (τ = 0.01) that no DQ check flags "
            "(mechanisms pooled, Wilson 95 % CI)",
        ),
        F.fig_dataset_compare(cmp, FIGS),
    ]
    w = ", ".join(
        f"{k} {v['tests'].iloc[0]['kendall_w']:.2f} (p = {v['tests'].iloc[0]['p']:.2g})"
        for k, v in rq1.items()
    )
    md += [
        "## Median distortion at 5 % (MCAR), Olist (O) vs Online Retail II (R)\n",
        "Scalar: relative error; K14: MAPD; K11/K13: 1 − top-k overlap.\n",
        _md(at5.reset_index()),
        "\n## RQ1 on the KPIs both datasets share (MCAR, E1–E5)\n",
        _md(ranks.pivot_table(index="code", columns="dataset", values="mean_rank").reset_index()),
        f"\nKendall's W: {w}\n",
        "## RQ2 ρ (DQ score drop vs distortion), shared KPIs\n",
        _md(rho.pivot_table(index="group", columns="dataset", values="rho").reset_index()),
        "\n## RQ3 silent rate (MCAR, τ = 0.01)\n",
        _md(
            silent.pivot_table(
                index=["code", "rate"], columns="dataset", values="silent_rate"
            ).reset_index()
        ),
        "\n## Which checks react on Online Retail II (share of runs)\n",
        _md(det.reset_index(), ".2f"),
        "\n## Figures\n",
    ]
    md += [f"- `{p.relative_to(RESULTS_DIR.parent).as_posix()}`" for p in figs] + [""]
    return md, {"runs": r.runs, "rq1": rq1, "rho": rho}


def _per_code(runs: pd.DataFrame, ranks: pd.DataFrame, name: str) -> pd.DataFrame:
    s = rq3_silent(runs[runs["mechanism"] == "MCAR"], by=("code",), tau=0.01).set_index("code")
    return pd.DataFrame(
        {
            f"{name}_rq1_rank": ranks.set_index("code")["mean_rank"],
            f"{name}_detected": s["detected_rate"],
            f"{name}_material": s["material_rate"],
            f"{name}_silent": s["silent_rate"],
            f"{name}_silent_lo": s["silent_lo"],
            f"{name}_silent_hi": s["silent_hi"],
        }
    )


def paper_tables(main, ret: dict | None) -> list[str]:
    """Compact tables for the paper (P1 error types, P2 RQ2), written as CSV and Markdown.
    Built from tables written earlier in the same make_all run."""
    p1 = _per_code(main.runs, pd.read_csv(TABLES / "t2_rq1_mean_ranks.csv"), "olist")
    if ret is not None:
        p1 = p1.join(_per_code(ret["runs"], ret["rq1"]["retail"]["ranks"], "retail"))
    p1 = p1.reset_index()
    p1.to_csv(TABLES / "p1_error_summary.csv", index=False)

    cols = ["group", "rho", "ci_lo", "ci_hi", "p_holm"]
    p2 = pd.read_csv(TABLES / "t3_rq2_spearman.csv")[cols].add_prefix("olist_")
    p2 = p2.rename(columns={"olist_group": "group"})
    if ret is not None:
        rr = ret["rho"][ret["rho"]["dataset"] == "retail"][cols].add_prefix("retail_")
        p2 = p2.merge(rr.rename(columns={"retail_group": "group"}), on="group", how="left")
    p2.to_csv(TABLES / "p2_rq2_summary.csv", index=False)

    show1, show2 = p1.copy(), p2.copy()
    for d in ("olist", "retail"):
        if f"{d}_silent" in show1:
            show1[f"{d}_silent"] = [
                f"{s:.2f} {_ci(lo, hi)}"
                for s, lo, hi in show1[
                    [f"{d}_silent", f"{d}_silent_lo", f"{d}_silent_hi"]
                ].itertuples(index=False)
            ]
            show1 = show1.drop(columns=[f"{d}_silent_lo", f"{d}_silent_hi"])
        if f"{d}_rho" in show2:
            show2[f"{d}_rho"] = [
                f"{x:.2f} {_ci(lo, hi)}" if np.isfinite(x) else "n/a"
                for x, lo, hi in show2[[f"{d}_rho", f"{d}_ci_lo", f"{d}_ci_hi"]].itertuples(
                    index=False
                )
            ]
            show2 = show2.drop(columns=[f"{d}_ci_lo", f"{d}_ci_hi"])
    return [
        "# Summary tables for the paper\n",
        "Generated by `python -m dqk.analysis.make_all`. Do not edit.\n",
        "## Table P1: error types (MCAR cells, all rates pooled, τ = 0.01)\n",
        "rq1_rank: Friedman mean rank, 1 = least distortion (Olist: K1–K10 + K14, E1–E6; "
        "Online Retail II: K1–K3, K9, K10, K14, E1–E5). detected / material / silent: share "
        "of runs; silent with Wilson 95 % CI.\n",
        _md(show1, ".2f"),
        "\n## Table P2: RQ2, Spearman ρ between DQ score drop and distortion per KPI group\n",
        "All runs of each dataset (Olist: all 15 KPIs); 95 % cluster-bootstrap CI (cells "
        "resampled); p Holm-adjusted; n/a = constant input (no ρ). Online Retail II has no "
        "duration, score or decision KPIs; its rate group is K9 only.\n",
        _md(show2, ".3g"),
        "",
    ]


def run(n_boot: int = 2000) -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    md, main = main_grid(RUNS / "main", n_boot)
    if (RUNS / "robustness").exists():
        md += robustness(RUNS / "robustness", main, n_boot)
    ret = None
    if any((RUNS / "retail").glob("*.runs.parquet")):
        md_r, ret = retail(RUNS / "retail", main, n_boot)
        md += md_r
    (TABLES / "paper_tables.md").write_text(
        "\n".join(paper_tables(main, ret)) + "\n", encoding="utf-8"
    )
    out = TABLES / "summary.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args(argv)
    print(f"wrote {run(args.n_boot)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
