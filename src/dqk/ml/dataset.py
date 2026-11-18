"""Run-level data set for RQ5 (code plan v1.2, L1).

One row per run of a stored grid (results/runs/...), nothing is re-run:

meta      dataset, grid, cell_id, code, variant, mechanism, rate, seed
features  d_C01 .. d_C20: fail_share of each core check minus its clean fail_share, after
          adding natural load-to-load variation (see below); NaN where a check does not
          apply (Online Retail II has 10 of the 20 core checks). Only these columns are fed
          to the models; meta never is.
labels    material: any KPI distorted (tau = 1 %, as in RQ3);
          material_<group>, dist_<group> per KPI group (dqk.analysis.stats.GROUP_ORDER
          without "count", which never changes).
rules     the v1.0/v1.1 detection measures recomputed on the same noisy shares, so rules and
          models see the same data: detected (any check worse than its clean status),
          n_worsened, dq_drop (aggregate score) and the KPI-weighted measures of RQ2
          (max_<group>, n_worsened_<group> over the checks that guard the group).

Natural variation. The stored shares are noiseless: the experiment compares every run with
one fixed clean mart. Each run gets the deviation vector of one clean split-half trial
(dqk.ml.noise), centred per check, so that a model cannot learn "any change at all = error".
Trials 0..n_aug-1 are used for this; trials n_aug.. become clean runs (code E0, all labels 0),
so a noise vector is never used twice. noise=False gives the noiseless variant (sensitivity).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from dqk import RESULTS_DIR
from dqk.analysis.stats import GROUP_ORDER, group_distortion, load_results
from dqk.analysis.v11 import group_checks
from dqk.dq import STATUS_ORDER
from dqk.ml import ML_CONFIG, ML_DIR
from dqk.ml.noise import noise_path

CORE = [f"C{i:02d}" for i in range(1, 21)]
FEATURES = [f"d_{c}" for c in CORE]
GROUPS = [g for g in GROUP_ORDER if g != "count"]
META = ["dataset", "grid", "cell_id", "code", "variant", "mechanism", "rate", "seed"]
RUNS = RESULTS_DIR / "runs"

# (folder under results/runs, dataset, grid label)
SOURCES = {
    "main": ("main", "olist", "main"),
    "variants": ("robustness/variants", "olist", "variants"),
    "rekeyed": ("robustness/rekeyed", "olist", "rekeyed"),
    "retail": ("retail", "retail", "retail"),
}


def ml_config() -> dict:
    return yaml.safe_load(ML_CONFIG.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- clean reference + noise


def load_noise(dataset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(checks, dev): checks = one row per check with clean_share, clean_status, warn_share,
    fail_share_thr, in_dq_score, dimension; dev = trial x check, centred per check."""
    n = pd.read_parquet(noise_path(dataset))
    checks = (
        n.drop_duplicates("check_id")
        .set_index("check_id")[
            ["dimension", "in_dq_score", "warn_share", "fail_share_thr", "clean_share",
             "clean_status"]
        ]
    )
    dev = n.pivot(index="trial", columns="check_id", values="dev")
    dev = dev - dev.mean()
    return checks, dev


# ---------------------------------------------------------------- stored runs -> one row per run


def _labels(kpi: pd.DataFrame, tau_col: str) -> pd.DataFrame:
    """material, material_<group>, dist_<group> per (cell_id, seed)."""
    m = (
        kpi.assign(m=kpi[tau_col].fillna(0))
        .groupby(["cell_id", "seed", "kpi_type"])["m"].max()
        .unstack("kpi_type")
    )
    out = pd.DataFrame(index=m.index)
    out["material"] = m.max(axis=1)
    for g in GROUPS:
        if g in m:
            out[f"material_{g}"] = m[g]
    gd = group_distortion(kpi).pivot_table(
        index=["cell_id", "seed"], columns="group", values="distortion"
    )
    for g in GROUPS:
        if g in gd:
            out[f"dist_{g}"] = gd[g]
    return out.reset_index()


def load_source(name: str, tau: float = 0.01) -> pd.DataFrame:
    """Stored runs of one grid: meta, labels and the raw (noiseless) share per check."""
    folder, dataset, grid = SOURCES[name]
    gr = load_results(RUNS / folder, with_dq=True)
    tau_col = f"material_{tau:g}".replace(".", "_")
    runs = gr.runs[["cell_id", "code", "variant", "mechanism", "rate", "seed"]].copy()
    runs.insert(0, "grid", grid)
    runs.insert(0, "dataset", dataset)
    shares = gr.dq.pivot(index=["cell_id", "seed"], columns="check_id", values="fail_share")
    shares.columns = [f"s_{c}" for c in shares.columns]
    out = runs.merge(_labels(gr.kpi, tau_col), on=["cell_id", "seed"], how="left")
    return out.merge(shares.reset_index(), on=["cell_id", "seed"], how="left")


def clean_runs(dataset: str, checks: pd.DataFrame, n: int) -> pd.DataFrame:
    """n clean runs (code E0): raw shares equal the clean shares, all labels 0. Their
    natural variation is added by add_noise from the trials reserved for clean runs."""
    rows = pd.DataFrame(
        {
            "dataset": dataset,
            "grid": "clean",
            "cell_id": f"E0-clean-{dataset}",
            "code": "E0",
            "variant": "clean",
            "mechanism": "none",
            "rate": 0.0,
            "seed": np.arange(n),
            "material": 0.0,
        }
    )
    for c in checks.index:
        rows[f"s_{c}"] = checks.loc[c, "clean_share"]
    return rows


# ---------------------------------------------------------------- noise, features, rule measures


def add_noise(
    df: pd.DataFrame,
    checks: pd.DataFrame,
    dev: pd.DataFrame,
    trials: np.ndarray,
    seed: int,
    pick: np.ndarray | None = None,
) -> pd.DataFrame:
    """Add one clean deviation vector, drawn from ``trials`` (or given row by row in
    ``pick``), to every run; then compute features d_<check> and the rule-based measures
    on the noisy shares."""
    if pick is None:
        pick = np.random.default_rng(seed).choice(trials, size=len(df), replace=True)
    out = df.copy()
    out["noise_trial"] = pick
    applies = [c for c in CORE if c in checks.index]
    worse = np.zeros((len(df), len(applies)), dtype=bool)
    for j, c in enumerate(applies):
        clean = float(checks.loc[c, "clean_share"])
        s = out[f"s_{c}"].to_numpy(float) + dev[c].reindex(pick).to_numpy(float)
        s = np.clip(s, 0.0, 1.0)
        out[f"n_{c}"] = s
        out[f"d_{c}"] = s - clean
        warn, fail = checks.loc[c, ["warn_share", "fail_share_thr"]]
        status = np.where(s > fail, 2, np.where(s > warn, 1, 0))
        worse[:, j] = status > STATUS_ORDER[checks.loc[c, "clean_status"]]
        out[f"w_{c}"] = worse[:, j]
    for c in CORE:
        if c not in applies:
            out[f"d_{c}"] = np.nan
    out["detected"] = worse.any(axis=1).astype(float)
    out["n_worsened"] = worse.sum(axis=1)
    score_checks = [c for c in applies if checks.loc[c, "in_dq_score"]]
    out["dq_drop"] = out[[f"d_{c}" for c in score_checks]].clip(lower=-1).mean(axis=1)
    for g, guard in group_checks().items():
        if g not in GROUPS:
            continue
        gc = [c for c in guard if c in applies]
        if gc:
            out[f"max_{g}"] = out[[f"d_{c}" for c in gc]].max(axis=1)
            out[f"n_worsened_{g}"] = out[[f"w_{c}" for c in gc]].sum(axis=1)
    return out


def build_frame(
    sources=("main", "variants", "rekeyed", "retail"), noise: bool = True
) -> pd.DataFrame:
    """The RQ5 frame: stored runs of ``sources`` plus clean runs per dataset."""
    cfg = ml_config()["rq5"]
    n_aug = cfg["noise"]["n_aug"]
    parts = []
    for dataset in sorted({SOURCES[s][1] for s in sources}):
        checks, dev = load_noise(dataset)
        if not noise:
            dev = dev * 0.0
        n_trials = len(dev)
        runs = pd.concat(
            [load_source(s, cfg["tau"]) for s in sources if SOURCES[s][1] == dataset],
            ignore_index=True,
        )
        seed = cfg["seed"] + (0 if dataset == "olist" else 1)
        parts.append(add_noise(runs, checks, dev, np.arange(n_aug), seed))
        clean = clean_runs(dataset, checks, n_trials - n_aug)
        # one clean run per reserved trial, no repeats
        t = np.arange(n_aug, n_trials)
        parts.append(add_noise(clean, checks, dev, t, 0, pick=t))
    out = pd.concat(parts, ignore_index=True)
    lab = ["material"] + [f"material_{g}" for g in GROUPS] + [f"dist_{g}" for g in GROUPS]
    clean_mask = out["code"] == "E0"
    for c in lab:
        if c in out:
            out.loc[clean_mask, c] = out.loc[clean_mask, c].fillna(0.0)
    return out


def frame_path(noise: bool = True) -> Path:
    return ML_DIR / ("rq5_frame.parquet" if noise else "rq5_frame_noiseless.parquet")


def main(argv=None) -> int:
    ML_DIR.mkdir(parents=True, exist_ok=True)
    for noise in (True, False):
        f = build_frame(noise=noise)
        f.to_parquet(frame_path(noise), index=False)
        print(f"wrote {frame_path(noise)}: {len(f)} runs")
        print(f.groupby(["dataset", "grid"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
