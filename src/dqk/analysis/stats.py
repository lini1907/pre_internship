"""Statistics for RQ1-RQ3 on the experiment output (code plan 4.5).

Input is the Parquet output of dqk.experiment.runner (one folder per grid). Every function
takes and returns DataFrames so the same code serves the main grid and the robustness grids.

distortion: one number per (run, KPI), 0 = unchanged
  scalar KPIs (K1-K10)  rel_error = |x_c - x_0| / |x_0|
  series (K14)          series_mapd
  ranking (K11-K13)     1 - topk_overlap
  decision (K15)        decision_flip (0/1)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

from dqk.experiment.measures import SCALAR_TYPES

RUN_KEYS = ["cell_id", "code", "variant", "mechanism", "rate"]
# RQ1 blocks: KPIs measured on a continuous scale (ranking / decision are too coarse).
RQ1_KPIS = ["K1", "K2", "K3", "K4", "K5", "K6", "K7", "K8", "K9", "K10", "K14"]
# KPI groups for RQ2 (kpi_type of kpi_spec.yaml).
GROUP_ORDER = [
    "monetary",
    "count",
    "ratio",
    "rate",
    "duration",
    "score",
    "ranking",
    "series",
    "decision",
]


@dataclass
class GridResults:
    name: str
    runs: pd.DataFrame  # one row per run
    kpi: pd.DataFrame  # one row per run x KPI, with distortion and the run keys
    dq: pd.DataFrame  # one row per run x check


def distortion(kpi: pd.DataFrame) -> pd.Series:
    """A grid without some KPI type (Online Retail II has no decision KPI) lacks that
    type's measure column; those rows simply do not occur."""
    t = kpi["kpi_type"]
    out = pd.Series(np.nan, index=kpi.index, dtype=float)
    for mask, col, f in (
        (t.isin(SCALAR_TYPES), "rel_error", lambda s: s),
        (t == "series", "series_mapd", lambda s: s),
        (t == "ranking", "topk_overlap", lambda s: 1.0 - s),
        (t == "decision", "decision_flip", lambda s: s),
    ):
        if mask.any():
            out[mask] = f(kpi.loc[mask, col])
    return out


def load_results(folder: str | Path, with_dq: bool = False) -> GridResults:
    folder = Path(folder)
    runs_files = sorted(folder.glob("*.runs.parquet"))
    if not runs_files:
        raise FileNotFoundError(f"no *.runs.parquet in {folder}")
    runs = pd.concat([pd.read_parquet(f) for f in runs_files], ignore_index=True)
    done = {f.name.removesuffix(".runs.parquet") for f in runs_files}
    kpi = pd.concat(
        [pd.read_parquet(folder / f"{c}.kpi.parquet") for c in sorted(done)], ignore_index=True
    )
    kpi = kpi.merge(runs[RUN_KEYS + ["seed"]], on=["cell_id", "seed"], how="left")
    kpi["distortion"] = distortion(kpi)
    dq = (
        pd.concat(
            [pd.read_parquet(folder / f"{c}.dq.parquet") for c in sorted(done)], ignore_index=True
        )
        if with_dq
        else pd.DataFrame()
    )
    return GridResults(folder.name, runs, kpi, dq)


def combo_label(df: pd.DataFrame) -> pd.Series:
    """'E1 duplicate_order MCAR' style label of an (error x mechanism) combination."""
    return df["code"] + " " + df["variant"] + " " + df["mechanism"]


# ---------------------------------------------------------------- descriptive


def describe_cells(kpi: pd.DataFrame) -> pd.DataFrame:
    """Per cell x KPI: n runs, median and 2.5-97.5 % quantiles of distortion, plus the mean
    of each binary flag."""
    g = kpi.groupby(RUN_KEYS + ["kpi_id", "kpi_type"], sort=False)["distortion"]
    out = g.agg(
        n="count",
        median="median",
        q025=lambda s: s.quantile(0.025),
        q975=lambda s: s.quantile(0.975),
        mean="mean",
    ).reset_index()
    tau = kpi.groupby(RUN_KEYS + ["kpi_id"], sort=False)["kendall_tau_b"].median()
    out["median_kendall_tau_b"] = out.set_index(RUN_KEYS + ["kpi_id"]).index.map(tau)
    return out


# ---------------------------------------------------------------- RQ1


def rq1_friedman(kpi: pd.DataFrame, mechanism: str = "MCAR", kpis=RQ1_KPIS) -> dict:
    """Which error type distorts KPIs most? Friedman test with blocks = KPI x rate,
    treatments = error codes, value = median distortion of the cell (code plan 4.5).

    Returns dict with the block table, test results overall and per rate (Holm-adjusted),
    mean ranks (1 = least distortion), Kendall's W and the Nemenyi p-value matrix."""
    import scikit_posthocs as sp

    d = kpi[(kpi["mechanism"] == mechanism) & kpi["kpi_id"].isin(kpis)]
    med = d.groupby(["kpi_id", "rate", "code"])["distortion"].median().unstack("code")
    med = med.dropna(axis=0, how="any")
    k = med.shape[1]

    def _test(block: pd.DataFrame) -> dict:
        chi2, p = stats.friedmanchisquare(*[block[c].to_numpy() for c in block.columns])
        n = len(block)
        return {"n_blocks": n, "k": k, "chi2": chi2, "p": p, "kendall_w": chi2 / (n * (k - 1))}

    overall = _test(med) | {"rate": "all"}
    per_rate = [
        _test(med.xs(r, level="rate")) | {"rate": r}
        for r in sorted(med.index.get_level_values("rate").unique())
    ]
    tests = pd.DataFrame([overall] + per_rate)
    tests["p_holm"] = np.nan
    tests.loc[tests["rate"] != "all", "p_holm"] = multipletests(
        tests.loc[tests["rate"] != "all", "p"], method="holm"
    )[1]
    ranks = med.rank(axis=1).mean().sort_values().rename("mean_rank").reset_index()
    nemenyi = sp.posthoc_nemenyi_friedman(med.to_numpy())
    nemenyi.index = nemenyi.columns = med.columns
    tied = int((med.nunique(axis=1) == 1).sum())
    return {
        "blocks": med,
        "tests": tests,
        "ranks": ranks,
        "nemenyi": nemenyi,
        "n_blocks_all_tied": tied,
    }


# ---------------------------------------------------------------- RQ2


def group_distortion(kpi: pd.DataFrame) -> pd.DataFrame:
    """Per run x KPI group: mean distortion over the KPIs of the group."""
    d = kpi.replace([np.inf], np.nan)
    return (
        d.groupby(["cell_id", "seed", "kpi_type"])["distortion"]
        .mean()
        .rename("distortion")
        .reset_index()
        .rename(columns={"kpi_type": "group"})
    )


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan
    return float(stats.spearmanr(x, y).statistic)


def rq2_spearman(
    runs: pd.DataFrame,
    kpi: pd.DataFrame,
    n_boot: int = 2000,
    seed: int = 0,
    detection: str = "dq_drop",
) -> pd.DataFrame:
    """Does the DQ score track KPI distortion? Spearman rho between ``detection`` (default
    dq_drop) and group distortion over all runs, per KPI group. 95 % CI by a cluster
    bootstrap that resamples cells (keeps the paired structure within a cell).
    p is the two-sided bootstrap p (Holm-adjusted across groups); p_naive is the asymptotic
    test that treats runs as independent, kept for reference only."""
    gd = group_distortion(kpi).merge(runs[["cell_id", "seed", detection]], on=["cell_id", "seed"])
    rng = np.random.default_rng(seed)
    rows = []
    for g in [x for x in GROUP_ORDER if x in set(gd["group"])]:
        d = gd[gd["group"] == g].dropna(subset=["distortion", detection])
        x, y = d[detection].to_numpy(float), d["distortion"].to_numpy(float)
        rho = _spearman(x, y)
        p_naive = float(stats.spearmanr(x, y).pvalue) if not np.isnan(rho) else np.nan
        cells = d["cell_id"].to_numpy()
        uniq, inv = np.unique(cells, return_inverse=True)
        idx_by_cell = [np.flatnonzero(inv == i) for i in range(len(uniq))]
        boots = []
        if not np.isnan(rho):
            for _ in range(n_boot):
                pick = rng.integers(0, len(uniq), len(uniq))
                ii = np.concatenate([idx_by_cell[i] for i in pick])
                boots.append(_spearman(x[ii], y[ii]))
        b = np.array(boots, dtype=float)
        lo, hi = (
            np.nanquantile(b, [0.025, 0.975])
            if b.size and np.isfinite(b).any()
            else (np.nan, np.nan)
        )
        # Two-sided cluster-bootstrap p for H0: rho = 0 (runs within a cell are not
        # independent, so the asymptotic p above is far too small). Floor 1 / n_boot.
        fb = b[np.isfinite(b)]
        p = (
            min(1.0, max(2 * min((fb <= 0).mean(), (fb >= 0).mean()), 1 / fb.size))
            if fb.size
            else np.nan
        )
        rows.append(
            {
                "group": g,
                "n_runs": len(d),
                "n_cells": len(uniq),
                "rho": rho,
                "ci_lo": lo,
                "ci_hi": hi,
                "p": p,
                "p_naive": p_naive,
            }
        )
    out = pd.DataFrame(rows)
    ok = out["p"].notna()
    out["p_holm"] = np.nan
    if ok.any():
        out.loc[ok, "p_holm"] = multipletests(out.loc[ok, "p"], method="holm")[1]
    return out


# ---------------------------------------------------------------- RQ3


def wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    lo, hi = proportion_confint(k, n, alpha=alpha, method="wilson")
    return float(lo), float(hi)


def rq3_silent(runs: pd.DataFrame, by=("code", "rate"), tau: float = 0.01) -> pd.DataFrame:
    """Share of runs with a material KPI change that no DQ check flags, with Wilson 95 % CI.
    Also the material and detected shares, and the share silent among material runs."""
    t = f"{tau:g}".replace(".", "_")
    mat, sil = f"material_{t}", f"silent_{t}"
    rows = []
    for key, d in runs.groupby(list(by), sort=True):
        key = key if isinstance(key, tuple) else (key,)
        n, k = len(d), int(d[sil].sum())
        n_mat = int(d[mat].sum())
        lo, hi = wilson(k, n)
        lo_m, hi_m = wilson(k, n_mat)
        rows.append(
            dict(zip(by, key, strict=True))
            | {
                "tau": tau,
                "n_runs": n,
                "n_silent": k,
                "silent_rate": k / n,
                "silent_lo": lo,
                "silent_hi": hi,
                "material_rate": n_mat / n,
                "detected_rate": float(d["detected"].mean()),
                "silent_given_material": k / n_mat if n_mat else np.nan,
                "sgm_lo": lo_m,
                "sgm_hi": hi_m,
            }
        )
    return pd.DataFrame(rows)


def detecting_checks(runs: pd.DataFrame, by=("code", "variant")) -> pd.DataFrame:
    """How often each DQ check flags each error (share of runs where it worsened)."""
    s = runs.assign(check=runs["worsened_checks"].fillna("").str.split(",")).explode("check")
    s = s[s["check"] != ""]
    n = runs.groupby(list(by)).size().rename("n_runs")
    c = s.groupby(list(by) + ["check"]).size().rename("n").reset_index()
    c = c.merge(n.reset_index(), on=list(by))
    c["share"] = c["n"] / c["n_runs"]
    # errors no check ever flags stay in the table as a row of zeros
    return c.pivot_table(index=list(by), columns="check", values="share", fill_value=0.0).reindex(
        n.index, fill_value=0.0
    )


__all__ = [
    "GridResults",
    "RQ1_KPIS",
    "GROUP_ORDER",
    "combo_label",
    "describe_cells",
    "detecting_checks",
    "distortion",
    "group_distortion",
    "load_results",
    "rq1_friedman",
    "rq2_spearman",
    "rq3_silent",
    "wilson",
]
