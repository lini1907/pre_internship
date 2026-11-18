"""False alarms of the extended checks on clean data only (code plan v1.1, section 2.3).

    python -m dqk.analysis.false_alarms               # 200 split-half seeds + 20 months
    python -m dqk.analysis.false_alarms --calibrate   # also print the thresholds to freeze

Two ways to pair a "reference" with a "current" load, neither containing injected errors:

split_half   orders split at random into halves A (reference) and B (current), 200 seeds.
             Measures sampling noise only. Thresholds of C23 and C24 are set from it:
             warn = 99th percentile of fail_share, fail = 2 x warn.
month_vs_past  for every month of the KPI window (2017-01 .. 2018-08): reference = all
             orders purchased before that month, current = orders of that month. A harder
             test: it includes real drift over time (new products, seasonality).

Fact tables are filtered by order; dimensions stay complete, as in a real incremental load.
Both datasets by default (--dataset olist|retail to restrict). Online Retail II has
only C21 and C24 (kpi_map.yaml); its C24 thresholds are calibrated on its own clean data.
Writes results/tables/f1_false_alarms.csv and results/tables/f1b_false_alarm_shares.csv.
"""

from __future__ import annotations

import argparse
from dataclasses import replace

import numpy as np
import pandas as pd

from dqk import RESULTS_DIR
from dqk.analysis.stats import wilson
from dqk.dq import load_dq_config, run_dq_checks, status_of
from dqk.tables import Mart

CHECKS = ("C21", "C22", "C23", "C24")
N_SEEDS = 200
# Months tested by month_vs_past: the KPI window of each dataset.
WINDOWS = {"olist": ("2017-01-01", "2018-09-01"), "retail": ("2009-12-01", "2011-12-01")}


def subset(mart: Mart, order_ids) -> Mart:
    o = mart.fact_orders[mart.fact_orders["order_id"].isin(order_ids)].reset_index(drop=True)
    i = mart.fact_order_items[mart.fact_order_items["order_id"].isin(order_ids)]
    return replace(mart, fact_orders=o, fact_order_items=i.reset_index(drop=True))


def pairs_split_half(mart: Mart, n_seeds: int = N_SEEDS):
    ids = mart.fact_orders["order_id"].sort_values().to_numpy()
    for seed in range(n_seeds):
        rng = np.random.default_rng(np.random.SeedSequence([20261117, seed]))
        a = rng.random(len(ids)) < 0.5
        yield f"seed{seed}", subset(mart, ids[a]), subset(mart, ids[~a])


def pairs_month_vs_past(mart: Mart, dataset: str = "olist"):
    o = mart.fact_orders
    month = o["purchase_ts"].dt.to_period("M")
    start, end = WINDOWS[dataset]
    for m in pd.period_range(start, end, freq="M")[:-1]:
        ref = o.loc[month < m, "order_id"]
        cur = o.loc[month == m, "order_id"]
        yield str(m), subset(mart, ref), subset(mart, cur)


def shares(
    mart: Mart, method: str, cfg=None, n_seeds: int = N_SEEDS, dataset: str = "olist"
) -> pd.DataFrame:
    """fail_share of C21-C24 per trial (one row per trial x check)."""
    cfg = cfg or load_dq_config(suite="extended")
    if method == "split_half":
        pairs = pairs_split_half(mart, n_seeds)
    else:
        pairs = pairs_month_vs_past(mart, dataset)
    rows = []
    for trial, ref, cur in pairs:
        r = run_dq_checks(cur.as_tables(), "mart", cfg, reference=ref.as_tables())
        r = r[r["check_id"].isin(CHECKS)]
        for x in r.itertuples():
            rows.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "trial": trial,
                    "check_id": x.check_id,
                    "n_failed": x.n_failed,
                    "n_total": x.n_total,
                    "fail_share": x.fail_share,
                }
            )
    return pd.DataFrame(rows)


def _ceil4(x: float) -> float:
    """Round up to 4 decimals, so a share equal to the quantile still passes."""
    return float(np.ceil(x * 1e4 - 1e-9) / 1e4)


def calibrate(split: pd.DataFrame, q: float = 0.99) -> dict[str, tuple[float, float]]:
    """(warn_share, fail_share) of C23 and C24: warn = q-quantile, fail = 2 x warn.
    If the quantile is 0, warn = 0 and fail = the smallest non-zero share possible."""
    out = {}
    for cid in sorted({"C23", "C24"} & set(split["check_id"])):
        s = split.loc[split["check_id"] == cid]
        p = float(np.quantile(s["fail_share"], q))
        if p == 0:
            p_fail = float((1 / s["n_total"]).min())
            out[cid] = (0.0, p_fail)
        else:
            out[cid] = (_ceil4(p), _ceil4(2 * p))
    return out


def dataset_config(dataset: str):
    if dataset == "retail":
        from dqk.retail.adapter import retail_dq_config

        return retail_dq_config(suite="extended")
    return load_dq_config(suite="extended")


def alarm_table(sh: pd.DataFrame) -> pd.DataFrame:
    """Per (dataset, check, method): trials, alarms (status warn or fail), rate and Wilson
    95 % CI, with the thresholds currently configured for the dataset."""
    th = {
        (ds, c.id): (c.warn_share, c.fail_share)
        for ds in sh["dataset"].unique()
        for c in dataset_config(ds).checks
    }
    sh = sh.assign(
        status=[
            status_of(s, *th[(d, c)])
            for s, d, c in zip(sh["fail_share"], sh["dataset"], sh["check_id"], strict=True)
        ]
    )
    rows = []
    for (dataset, cid, method), g in sh.groupby(["dataset", "check_id", "method"], sort=True):
        k = int((g["status"] != "pass").sum())
        n = len(g)
        lo, hi = wilson(k, n)
        rows.append(
            {
                "dataset": dataset,
                "check_id": cid,
                "method": method,
                "warn_share": th[(dataset, cid)][0],
                "fail_share": th[(dataset, cid)][1],
                "n_trials": n,
                "n_alarms": k,
                "n_fail": int((g["status"] == "fail").sum()),
                "alarm_rate": k / n,
                "ci_low": lo,
                "ci_high": hi,
                "share_median": float(g["fail_share"].median()),
                "share_p99": float(np.quantile(g["fail_share"], 0.99)),
            }
        )
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    from dqk.experiment.runner import dataset_setup, load_clean_mart

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibrate", action="store_true", help="print thresholds to freeze")
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    ap.add_argument("--dataset", action="append", choices=["olist", "retail"])
    args = ap.parse_args(argv)

    parts = []
    for ds in args.dataset or ["olist", "retail"]:
        mart = load_clean_mart(dataset_setup(ds)[0])
        cfg = dataset_config(ds)
        split = shares(mart, "split_half", cfg, args.seeds, ds)
        if args.calibrate:
            for cid, (w, f) in calibrate(split).items():
                print(f"{ds} {cid}: warn_share {w:g}, fail_share {f:g}")
        parts += [split, shares(mart, "month_vs_past", cfg, dataset=ds)]
        del mart
    sh = pd.concat(parts, ignore_index=True)
    out = RESULTS_DIR / "tables"
    sh.to_csv(out / "f1b_false_alarm_shares.csv", index=False)
    tab = alarm_table(sh)
    tab.to_csv(out / "f1_false_alarms.csv", index=False)
    print(tab.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
