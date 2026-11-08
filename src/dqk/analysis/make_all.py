"""Rebuild every result table and figure from results/runs/ in one command.

    python -m dqk.analysis.make_all                # main grid + robustness (if present)
    python -m dqk.analysis.make_all --n-boot 200   # quick check

Writes results/tables/*.csv, results/tables/summary.md and results/figures/*.png.
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


def run(n_boot: int = 2000) -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    md, main = main_grid(RUNS / "main", n_boot)
    if (RUNS / "robustness").exists():
        md += robustness(RUNS / "robustness", main, n_boot)
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
