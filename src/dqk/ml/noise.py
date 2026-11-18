"""Natural variation of the core checks on clean data (code plan v1.2, RQ5).

In the experiment every injected run is compared with the same clean mart, so a check's
fail_share moves only because of the injected error: a delta of 1e-6 is a perfect signal.
A real load also differs from the last one by sampling noise. A model trained on noiseless
deltas would learn that perfect signal and look better than it can be.

This module measures that noise on clean data only. Orders are split at random into two
halves (the split_half pairs of dqk.analysis.false_alarms, same seeds), the core checks run
on half B, and dev = fail_share(B) - fail_share(full clean mart) per check. Volume checks
compare with a known reference count, which a half-load misses by 50 %, so their dev is set
to 0 (config/ml.yaml, noise.zero_dims).

    python -m dqk.ml.noise --dataset olist|retail [--n-trials 200]

Writes results/ml/clean_variation_<dataset>.parquet: dataset, trial, check_id, dimension,
in_dq_score, warn_share, fail_share_thr, clean_share, clean_status, half_share, dev.
"""

from __future__ import annotations

import argparse
import time

import pandas as pd
import yaml

from dqk.analysis.false_alarms import pairs_split_half
from dqk.dq import run_dq_checks
from dqk.experiment.runner import dataset_setup, load_clean_mart
from dqk.ml import ML_CONFIG, ML_DIR


def noise_path(dataset: str):
    return ML_DIR / f"clean_variation_{dataset}.parquet"


def clean_variation(dataset: str, n_trials: int, zero_dims=("volume",)) -> pd.DataFrame:
    path, _spec, cfg = dataset_setup(dataset, "core")
    mart = load_clean_mart(path)
    clean = run_dq_checks(mart.as_tables(), "mart", cfg).set_index("check_id")
    thr = {c.id: (c.warn_share, c.fail_share) for c in cfg.checks}
    rows = []
    t0 = time.perf_counter()
    for n, (trial, _a, b) in enumerate(pairs_split_half(mart, n_trials)):
        r = run_dq_checks(b.as_tables(), "mart", cfg)
        for x in r.itertuples():
            c = clean.loc[x.check_id]
            dev = 0.0 if x.dimension in zero_dims else x.fail_share - c["fail_share"]
            rows.append(
                {
                    "dataset": dataset,
                    "trial": n,
                    "trial_name": trial,
                    "check_id": x.check_id,
                    "dimension": x.dimension,
                    "in_dq_score": bool(x.in_dq_score),
                    "warn_share": thr[x.check_id][0],
                    "fail_share_thr": thr[x.check_id][1],
                    "clean_share": c["fail_share"],
                    "clean_status": c["status"],
                    "half_share": x.fail_share,
                    "dev": dev,
                }
            )
        if (n + 1) % 20 == 0:
            print(f"{dataset}: {n + 1}/{n_trials} trials, {time.perf_counter() - t0:.0f}s")
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    cfg = yaml.safe_load(ML_CONFIG.read_text(encoding="utf-8"))["rq5"]["noise"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["olist", "retail"], required=True)
    ap.add_argument("--n-trials", type=int, default=cfg["n_trials"])
    a = ap.parse_args(argv)
    out = clean_variation(a.dataset, a.n_trials, tuple(cfg["zero_dims"]))
    ML_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(noise_path(a.dataset), index=False)
    print(f"wrote {noise_path(a.dataset)} ({len(out)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
