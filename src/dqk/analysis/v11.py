"""v1.1 analyses (code plan v1.1: N1 RQ4, N2 KPI-weighted DQ score, N3 low rates).

    python -m dqk.analysis.v11 --n-boot 2000

Reads results/runs/main (N2) and results/runs/extended/* (N1, N3) and writes, without
touching any v1.0 table:
  results/tables/t3c_rq2_kpi_weighted.csv        N2: rho of four detection measures
  results/tables/t6_rq4_silent_core_vs_ext.csv   N1: silent rate, core vs extended suite
  results/tables/t6b_rq4_detecting_checks.csv    N1: share of runs each check reacts
  results/tables/t7_lowrate.csv                  N3: dose-response 0.1 % .. 20 %
  results/figures/fig8_rq4_silent_before_after.png, fig9_rq2_score_variants.png,
  fig10_dose_response.png
  results/tables/summary_v11.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats
from statsmodels.stats.multitest import multipletests

from dqk import CONFIG_DIR, RESULTS_DIR
from dqk.analysis import figures as F
from dqk.analysis.stats import (
    GROUP_ORDER,
    group_distortion,
    load_results,
    wilson,
)
from dqk.config import load_kpi_spec

RUNS, TABLES, FIGS = RESULTS_DIR / "runs", RESULTS_DIR / "tables", RESULTS_DIR / "figures"
TRACEABILITY = CONFIG_DIR / "traceability.yaml"
CORE = [f"C{i:02d}" for i in range(1, 21)]
EXT = [f"C{i:02d}" for i in range(21, 25)]
MEASURES = {
    "dq_drop": "overall DQ score drop (v1.0)",
    "score_drop_g": "drop of the score over the group's guarding checks",
    "max_g": "largest fail_share increase among guarding checks",
    "n_worsened_g": "guarding checks that worsened",
}


# ---------------------------------------------------------------- N2


def group_checks(path: Path = TRACEABILITY) -> dict[str, list[str]]:
    """KPI group (kpi_type) -> union of the checks guarding its KPIs (Table 3.7)."""
    tr = yaml.safe_load(path.read_text(encoding="utf-8"))["kpis"]
    out: dict[str, set[str]] = {}
    for k in load_kpi_spec().kpis:
        out.setdefault(k.type, set()).update(tr[k.id])
    return {g: sorted(c) for g, c in out.items()}


def clean_shares(path: Path = RESULTS_DIR / "stage_a" / "dq_results.csv") -> pd.Series:
    d = pd.read_csv(path)
    return d[d["layer"] == "mart"].set_index("check_id")["fail_share"]


def kpi_weighted_dq(
    dq: pd.DataFrame, groups: dict[str, list[str]], clean: pd.Series
) -> pd.DataFrame:
    """Per run x KPI group: score_drop_g, max_g, n_worsened_g over the group's checks."""
    d = dq[["cell_id", "seed", "check_id", "fail_share", "worsened"]].copy()
    fs = d["fail_share"].clip(upper=1)
    d["delta"] = fs - d["check_id"].map(clean).clip(upper=1)
    d["worsened"] = d["worsened"].astype(float)
    parts = []
    for g, checks in groups.items():
        s = d[d["check_id"].isin(checks)]
        a = s.groupby(["cell_id", "seed"]).agg(
            score_drop_g=("delta", "mean"),
            max_g=("delta", "max"),
            n_worsened_g=("worsened", "sum"),
        )
        parts.append(a.assign(group=g).reset_index())
    return pd.concat(parts, ignore_index=True)


def _spearman(x, y) -> float:
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan
    return float(stats.spearmanr(x, y).statistic)


def _rho_boot(x, y, cells, rng, n_boot) -> tuple[float, float, float, float]:
    rho = _spearman(x, y)
    if np.isnan(rho):
        return rho, np.nan, np.nan, np.nan
    uniq, inv = np.unique(cells, return_inverse=True)
    idx = [np.flatnonzero(inv == i) for i in range(len(uniq))]
    b = []
    for _ in range(n_boot):
        ii = np.concatenate([idx[i] for i in rng.integers(0, len(uniq), len(uniq))])
        b.append(_spearman(x[ii], y[ii]))
    b = np.array(b, float)
    fb = b[np.isfinite(b)]
    if not fb.size:
        return rho, np.nan, np.nan, np.nan
    lo, hi = np.quantile(fb, [0.025, 0.975])
    p = min(1.0, max(2 * min((fb <= 0).mean(), (fb >= 0).mean()), 1 / fb.size))
    return rho, float(lo), float(hi), float(p)


def rq2_alternatives(
    runs: pd.DataFrame, kpi: pd.DataFrame, weighted: pd.DataFrame, n_boot: int = 2000, seed=0
) -> pd.DataFrame:
    """Spearman rho between each detection measure and group distortion, per KPI group,
    cluster-bootstrap CI and p (cells resampled), Holm across groups within a measure."""
    gd = group_distortion(kpi).merge(runs[["cell_id", "seed", "dq_drop"]], on=["cell_id", "seed"])
    gd = gd.merge(weighted, on=["cell_id", "seed", "group"], how="left")
    rng = np.random.default_rng(seed)
    rows = []
    for m in MEASURES:
        for g in [x for x in GROUP_ORDER if x in set(gd["group"])]:
            d = gd[gd["group"] == g].dropna(subset=["distortion", m])
            rho, lo, hi, p = _rho_boot(
                d[m].to_numpy(float), d["distortion"].to_numpy(float),
                d["cell_id"].to_numpy(), rng, n_boot,
            )
            rows.append({"measure": m, "group": g, "n_runs": len(d), "rho": rho,
                         "ci_lo": lo, "ci_hi": hi, "p": p})
    out = pd.DataFrame(rows)
    out["p_holm"] = np.nan
    for _m, idx in out.groupby("measure").groups.items():
        ok = out.loc[idx, "p"].notna()
        if ok.any():
            ii = ok[ok].index
            out.loc[ii, "p_holm"] = multipletests(out.loc[ii, "p"], method="holm")[1]
    return out


def fig9(t: pd.DataFrame, out: Path = FIGS) -> Path:
    import matplotlib.pyplot as plt

    groups = [g for g in GROUP_ORDER if g in set(t["group"])]
    ms = list(MEASURES)
    colors = ["#898781", "#2a78d6", "#eb6834", "#1baf7a"]
    markers = ["o", "s", "D", "^"]
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    w = 0.18
    for j, m in enumerate(ms):
        d = t[t["measure"] == m].set_index("group").reindex(groups)
        x = np.arange(len(groups)) + (j - 1.5) * w
        ax.errorbar(x, d["rho"], yerr=[d["rho"] - d["ci_lo"], d["ci_hi"] - d["rho"]],
                    fmt=markers[j], color=colors[j], ms=5, lw=1, capsize=2, label=MEASURES[m])
    ax.axhline(0, color=F.AXIS, lw=0.8)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylabel("Spearman ρ with group distortion (95 % CI)")
    ax.set_ylim(-1, 1)
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    return F._save(fig, out, "fig9_rq2_score_variants", t)


# ---------------------------------------------------------------- N1 / N3


def detected_by_suite(dq: pd.DataFrame) -> pd.DataFrame:
    """Per run: detected_core (any of C01-C20 worsened) and detected_ext (C01-C24)."""
    d = dq.assign(core=dq["check_id"].isin(CORE) & dq["worsened"], any=dq["worsened"])
    return (
        d.groupby(["cell_id", "seed"])
        .agg(detected_core=("core", "any"), detected_ext=("any", "any"))
        .reset_index()
    )


def load_extended(name: str) -> pd.DataFrame | None:
    folder = RUNS / "extended" / name
    if not any(folder.glob("*.runs.parquet")):
        return None
    r = load_results(folder, with_dq=True)
    runs = r.runs.merge(detected_by_suite(r.dq), on=["cell_id", "seed"])
    runs["dataset"] = "retail" if name.startswith("retail") else "olist"
    runs["scenario"] = name
    # cell ids repeat across datasets (E5 cells exist in both): carry the dataset
    return runs, r.dq.assign(dataset=runs["dataset"].iloc[0])


def rq4_silent(runs: pd.DataFrame, tau: float = 0.01) -> pd.DataFrame:
    """Silent share per (dataset, error, mechanism, rate) under each suite, Wilson CI."""
    mat = f"material_{tau:g}".replace(".", "_")
    rows = []
    keys = ["dataset", "code", "variant", "mechanism", "rate"]
    for key, d in runs.groupby(keys, sort=True):
        n = len(d)
        row = dict(zip(keys, key, strict=True)) | {"tau": tau, "n_runs": n,
                                                   "material_rate": d[mat].mean()}
        for suite in ("core", "ext"):
            k = int(((d[mat] > 0) & ~d[f"detected_{suite}"]).sum())
            lo, hi = wilson(k, n)
            row |= {f"silent_{suite}": k / n, f"silent_{suite}_lo": lo,
                    f"silent_{suite}_hi": hi,
                    f"detected_{suite}": float(d[f"detected_{suite}"].mean())}
        rows.append(row)
    return pd.DataFrame(rows)


def rq4_checks(runs: pd.DataFrame, dq: pd.DataFrame) -> pd.DataFrame:
    """Share of runs in which each extended check worsened, per error x mechanism x rate."""
    keys = ["code", "variant", "mechanism", "rate"]
    d = dq[dq["check_id"].isin(EXT)].merge(runs[["cell_id", "seed", "dataset"] + keys],
                                           on=["cell_id", "seed", "dataset"])
    if len(d) != dq["check_id"].isin(EXT).sum():
        raise RuntimeError("rq4_checks: runs and dq do not match one to one")
    t = d.pivot_table(index=["dataset"] + keys, columns="check_id", values="worsened",
                      aggfunc="mean")
    return t.reset_index()


def consistency_with_main(ext_runs: pd.DataFrame, main_runs: pd.DataFrame) -> pd.DataFrame:
    """For cells in both grids: detected_core vs main 'detected', material vs main."""
    m = main_runs[["cell_id", "seed", "detected", "material_0_01"]]
    j = ext_runs.merge(m, on=["cell_id", "seed"], suffixes=("", "_main"))
    return pd.DataFrame(
        {
            "n_runs": [len(j)],
            "n_cells": [j["cell_id"].nunique()],
            "detected_mismatch": [int((j["detected_core"] != (j["detected_main"] > 0)).sum())],
            "material_mismatch": [int((j["material_0_01"] != j["material_0_01_main"]).sum())],
        }
    )


def fig8(t6: pd.DataFrame, out: Path = FIGS) -> Path:
    import matplotlib.pyplot as plt

    panels = [
        ("olist", "E6", "category_reassign", "MCAR", "Olist: E6 category reassignment (MCAR)"),
        ("olist", "E5", "price_x100", "MCAR", "Olist: E5 price × 100 (MCAR)"),
        ("retail", "E5", "price_x100", "MCAR", "Online Retail II: E5 price × 100 (MCAR)"),
        ("retail", "E3", "missing_customer_id", "MCAR", "Online Retail II: E3 missing customer"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(12.5, 3.4), sharey=True)
    for ax, (ds, code, var, mech, title) in zip(axes, panels, strict=True):
        d = t6[(t6["dataset"] == ds) & (t6["code"] == code) & (t6["variant"] == var)
               & (t6["mechanism"] == mech)].sort_values("rate")
        if d.empty:
            ax.set_title(title + "\n(no runs yet)", fontsize=8.5, loc="left")
            continue
        x = np.arange(len(d))
        for off, suite, color, lab in ((-0.19, "core", "#898781", "core C01–C20"),
                                       (0.19, "ext", "#2a78d6", "extended C01–C24")):
            v = d[f"silent_{suite}"].to_numpy() * 100
            ax.bar(x + off, v, width=0.38, color=color, label=lab)
            for xi, vi in zip(x + off, v, strict=True):
                ax.text(xi, vi + 1.5, f"{vi:.0f}", ha="center", fontsize=7, color=F.INK2)
        ax.set_xticks(x, [f"{r:.0%}" for r in d["rate"]])
        ax.set_title(title, fontsize=8.5, loc="left")
        ax.set_xlabel("error rate")
    axes[0].set_ylabel("silent runs, % (material at τ = 1 %, not detected)")
    axes[0].set_ylim(0, 110)
    axes[0].legend(loc="upper left", fontsize=8)
    return F._save(fig, out, "fig8_rq4_silent_before_after", t6)


def lowrate_table(low: pd.DataFrame, ext: pd.DataFrame) -> pd.DataFrame:
    """Dose-response for E6 reassign and E5 x100 from 0.1 % to 20 %: material share at
    tau = 1 % and of the decision / ranking KPIs, silent share under each suite."""
    keep = ["E6-category_reassign", "E5-price_x100"]
    cols = ["cell_id", "seed", "code", "variant", "mechanism", "rate", "material_0_01",
            "detected_core", "detected_ext"]
    hi = ext[ext["cell_id"].str.startswith(tuple(keep))][cols]
    lo = low[cols]
    d = pd.concat([lo, hi], ignore_index=True)
    rows = []
    for key, g in d.groupby(["code", "variant", "mechanism", "rate"]):
        n = len(g)
        mat = g["material_0_01"] > 0
        rows.append(
            dict(zip(["code", "variant", "mechanism", "rate"], key, strict=True))
            | {
                "n_runs": n,
                "material_rate": mat.mean(),
                "silent_core": float((mat & ~g["detected_core"]).mean()),
                "silent_ext": float((mat & ~g["detected_ext"]).mean()),
                "detected_core": float(g["detected_core"].mean()),
                "detected_ext": float(g["detected_ext"].mean()),
            }
        )
    return pd.DataFrame(rows)


def kpi_flips(folder: Path) -> pd.DataFrame:
    """Per cell: share of runs where K15 flips / K11 top-10 changes, and median GMV error."""
    rows = []
    for f in sorted(folder.glob("*.kpi.parquet")):
        k = pd.read_parquet(f)
        cell = f.name.removesuffix(".kpi.parquet")
        g = k.set_index(["seed", "kpi_id"])
        rows.append(
            {
                "cell_id": cell,
                "k15_flip": float(g.xs("K15", level="kpi_id")["decision_flip"].mean()),
                "k11_changed": float(g.xs("K11", level="kpi_id")["topk_changed"].mean()),
                "k1_rel_error_median": float(g.xs("K1", level="kpi_id")["rel_error"].median()),
                "k1_rel_error_p95": float(g.xs("K1", level="kpi_id")["rel_error"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def fig10(t7: pd.DataFrame, out: Path = FIGS) -> Path:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, (code, var, title) in zip(
        axes, [("E6", "category_reassign", "E6 category reassignment"),
               ("E5", "price_x100", "E5 price × 100")], strict=True
    ):
        for mech, ls in (("MCAR", "-"), ("MAR", "--"), ("MNAR", ":")):
            d = t7[(t7["code"] == code) & (t7["variant"] == var) & (t7["mechanism"] == mech)]
            if d.empty:
                continue
            d = d.sort_values("rate")
            c = F.CODE_COLOR[code]
            ax.plot(d["rate"] * 100, d["material_rate"] * 100, ls=ls, color=c, marker="o",
                    ms=4, label=f"material ({mech})")
            ax.plot(d["rate"] * 100, d["silent_core"] * 100, ls=ls, color="#898781",
                    marker="s", ms=4, label=f"silent, core ({mech})")
            ax.plot(d["rate"] * 100, d["silent_ext"] * 100, ls=ls, color="#0d366b",
                    marker="^", ms=4, label=f"silent, extended ({mech})")
        ax.set_xscale("log")
        ax.set_xticks([0.1, 0.25, 0.5, 1, 2, 5, 10, 20], ["0.1", "0.25", "0.5", "1", "2", "5",
                                                           "10", "20"])
        ax.set_xlabel("error rate, % (log scale)")
        ax.set_title(title, loc="left")
    axes[0].set_ylabel("share of runs, %")
    axes[0].set_ylim(-3, 103)
    # one legend per panel: E6 runs MCAR/MAR, E5 runs MCAR/MNAR
    axes[0].legend(fontsize=7, loc="center right")
    axes[1].legend(fontsize=7, loc="center right")
    return F._save(fig, out, "fig10_dose_response", t7)


# ---------------------------------------------------------------- run


def _md(df: pd.DataFrame, fmt: str = ".3g") -> str:
    from dqk.analysis.make_all import _md as md

    return md(df, fmt)


def run(n_boot: int = 2000) -> Path:
    TABLES.mkdir(parents=True, exist_ok=True)
    md = ["# v1.1 results (N1 RQ4, N2, N3)", ""]
    main = load_results(RUNS / "main", with_dq=True)

    # N2
    w = kpi_weighted_dq(main.dq, group_checks(), clean_shares())
    t3c = rq2_alternatives(main.runs, main.kpi, w, n_boot=n_boot)
    t3c.to_csv(TABLES / "t3c_rq2_kpi_weighted.csv", index=False)
    fig9(t3c)
    md += ["## N2 - KPI-weighted DQ score (main grid, RQ2)", "",
           "Measures: " + "; ".join(f"`{k}` = {v}" for k, v in MEASURES.items()), "",
           _md(t3c), ""]

    # N1
    parts = [x for x in (load_extended(n) for n in ("olist_ext", "retail_ext")) if x]
    if parts:
        runs = pd.concat([p[0] for p in parts], ignore_index=True)
        dq = pd.concat([p[1] for p in parts], ignore_index=True)
        t6 = rq4_silent(runs)
        t6.to_csv(TABLES / "t6_rq4_silent_core_vs_ext.csv", index=False)
        t6b = rq4_checks(runs, dq)
        t6b.to_csv(TABLES / "t6b_rq4_detecting_checks.csv", index=False)
        fig8(t6)
        olist = runs[runs["dataset"] == "olist"]
        cons = consistency_with_main(olist, main.runs)
        cons.to_csv(TABLES / "t6c_rq4_consistency_with_main.csv", index=False)
        md += ["## N1 - RQ4: extended checks (core vs extended suite)", "",
               "Consistency with the main grid (cells in both grids, same seeds):", "",
               _md(cons), "", _md(t6), "", "Extended checks reacting (share of runs):", "",
               _md(t6b), ""]
        fa = TABLES / "f1_false_alarms.csv"
        if fa.exists():
            md += ["False alarms on clean data:", "", _md(pd.read_csv(fa)), ""]

    # N3
    low = load_extended("olist_lowrate")
    if low and parts:
        ext_olist = runs[runs["dataset"] == "olist"]
        t7 = lowrate_table(low[0], ext_olist)
        flips = pd.concat(
            [kpi_flips(RUNS / "extended" / "olist_lowrate"),
             kpi_flips(RUNS / "extended" / "olist_ext")], ignore_index=True
        )
        t7 = t7.assign(cell_id=lambda d: d["code"] + "-" + d["variant"] + "-" + d["mechanism"]
                       + "-" + d["rate"].map(lambda r: f"{r:g}"))
        t7 = t7.merge(flips, on="cell_id", how="left")
        t7.to_csv(TABLES / "t7_lowrate.csv", index=False)
        fig10(t7)
        md += ["## N3 - low error rates (dose-response)", "", _md(t7), ""]

    out = TABLES / "summary_v11.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args(argv)
    print(f"wrote {run(args.n_boot)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

