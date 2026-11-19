"""RQ6: run-level thresholds and false alarms of M01-M03 on clean data only (code plan
v1.2, L6). Mirrors dqk.analysis.false_alarms for C21-C24.

split_half         orders split at random into halves A and B (same 200 seeds as for
                   C23/C24); fail_share of each detector on half B, from the item flags of
                   the cross-fitted models. Thresholds: warn = 99th percentile rounded up
                   at the fourth decimal, fail = 2 x warn. Written to config/ml_thresholds.yaml
                   with --freeze, BEFORE the ML grid is run.
split_half_refit   20 seeds: models re-fitted on half A without the products of half B
                   (cold start), half B scored. Checks that the cheap version above is not
                   optimistic.
month_vs_past      every month of the KPI window: models fitted on all earlier orders
                   without the products sold in the month, the month scored. Real drift.

Item-level rules (tau_1, MAD, IsolationForest threshold) stay those of the clean
cross-fit; only the models are re-fitted, as when a production model is retrained.

    python -m dqk.ml.calibrate --dataset olist|retail [--freeze] [--skip-months]

Writes results/tables/f2_ml_false_alarms.csv and f2b_ml_false_alarm_shares.csv.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import time
from dataclasses import replace

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest

from dqk import RESULTS_DIR, ROOT
from dqk.analysis.false_alarms import WINDOWS, pairs_split_half, subset
from dqk.analysis.stats import wilson
from dqk.dq import status_of
from dqk.ml.detectors import (
    APPLIES,
    THRESHOLDS,
    MlBundle,
    flags,
    item_frame,
    load_bundle,
    m01_fit_score,
    m02_features,
    m03_features,
    product_frame,
    rq6_config,
)
from dqk.tables import Mart

TABLES = RESULTS_DIR / "tables"
N_SEEDS = 200
N_REFIT = 20


def _ceil4(x: float) -> float:
    return float(np.ceil(x * 1e4 - 1e-9) / 1e4)


def _shares(fl: dict[str, pd.Series], cur: Mart, checks) -> dict[str, tuple[int, int]]:
    """(n_failed, n_total) per detector restricted to the lines / products of ``cur``."""
    from dqk.ml.detectors import item_key

    i = cur.fact_order_items
    keys = item_key(i[i["price"].astype(float) > 0])
    out = {}
    for cid in checks:
        s = fl[cid]
        if cid == "M01":
            s = s[s.index.isin(set(i["product_id"]))]
        else:
            s = s.reindex(keys).dropna()
        out[cid] = (int(s.sum()), len(s))
    return out


# ---------------------------------------------------------------- refit on a subset


def refit_flags(b: MlBundle, ref: Mart, cur: Mart, seed: int) -> dict[str, pd.Series]:
    """Fit M01-M03 on ``ref`` without the products sold in ``cur`` (cold start), score
    ``cur`` with the frozen item-level rules of the bundle."""
    cfg = rq6_config()
    cur_products = set(cur.fact_order_items["product_id"])
    keep = ~ref.fact_order_items["product_id"].isin(cur_products)
    ref = replace(ref, fact_order_items=ref.fact_order_items[keep].reset_index(drop=True))
    out = {}
    if "M01" in APPLIES[b.dataset]:
        pr = product_frame(ref, b.ctx)
        pc = product_frame(cur, b.ctx)
        p = pd.concat([pr, pc], ignore_index=True)
        train = np.r_[np.ones(len(pr), bool), np.zeros(len(pc), bool)]
        P = m01_fit_score(p, train, ~train, b.cats, cfg, seed)
        lab = pc["category_en"].to_numpy()
        known = np.isin(lab, b.cats)
        cols = np.array([b.cats.index(c) if k else 0 for c, k in zip(lab, known, strict=True)])
        prob = np.where(known, P[np.arange(len(pc)), cols], 0.0)
        out["M01"] = pd.Series((~known) | (prob < b.tau1), index=pc["product_id"].to_numpy())
    fr = item_frame(ref, b.ctx, b.cats)
    fc = item_frame(cur, b.ctx, b.cats)
    f2, f3 = m02_features(b.dataset), m03_features(b.dataset)
    if len(fr) > cfg["max_train_rows"]:
        fr = fr.sample(cfg["max_train_rows"], random_state=seed)
    cat_idx = [f2.index("cat")] if "cat" in f2 else None
    r = HistGradientBoostingRegressor(random_state=seed, categorical_features=cat_idx,
                                      **cfg["models"]["m02"]).fit(fr[f2], fr["lp"])
    resid = fc["lp"].to_numpy() - r.predict(fc[f2])
    out["M02"] = pd.Series(np.abs(resid - b.m02_center) > cfg["m02_k"] * b.m02_mad,
                           index=fc["key"].to_numpy())
    med = fr[f3].median()
    iso = IsolationForest(random_state=seed, **cfg["models"]["m03"]).fit(fr[f3].fillna(med))
    out["M03"] = pd.Series(iso.score_samples(fc[f3].fillna(med)) < b.m03_thr,
                           index=fc["key"].to_numpy())
    return out


# ---------------------------------------------------------------- the three methods


def run(dataset: str, skip_months: bool = False) -> pd.DataFrame:
    from dqk.experiment.runner import dataset_setup, load_clean_mart

    b = load_bundle(dataset)
    mart = load_clean_mart(dataset_setup(dataset)[0])
    checks = APPLIES[dataset]
    rows = []
    t0 = time.perf_counter()
    fl = flags(b, mart)
    for trial, _a, cur in pairs_split_half(mart, N_SEEDS):
        for cid, (nf, nt) in _shares(fl, cur, checks).items():
            rows.append({"dataset": dataset, "method": "split_half", "trial": trial,
                         "check_id": cid, "n_failed": nf, "n_total": nt})
    print(f"{dataset} split_half: {time.perf_counter() - t0:.0f}s")
    if dataset == "olist":
        for n, (trial, ref, cur) in enumerate(pairs_split_half(mart, N_REFIT)):
            for cid, s in refit_flags(b, ref, cur, rq6_config()["seed"] + n).items():
                rows.append({"dataset": dataset, "method": "split_half_refit", "trial": trial,
                             "check_id": cid, "n_failed": int(s.sum()), "n_total": len(s)})
        print(f"{dataset} split_half_refit: {time.perf_counter() - t0:.0f}s")
    if not skip_months:
        o = mart.fact_orders
        month = o["purchase_ts"].dt.to_period("M")
        start, end = WINDOWS[dataset]
        for m in pd.period_range(start, end, freq="M")[:-1]:
            if not (month < m).any():
                continue  # first month of the data: no past to train on
            ref = subset(mart, o.loc[month < m, "order_id"])
            cur = subset(mart, o.loc[month == m, "order_id"])
            for cid, s in refit_flags(b, ref, cur, rq6_config()["seed"]).items():
                rows.append({"dataset": dataset, "method": "month_vs_past", "trial": str(m),
                             "check_id": cid, "n_failed": int(s.sum()), "n_total": len(s)})
            print(f"{dataset} {m}: {time.perf_counter() - t0:.0f}s")
    sh = pd.DataFrame(rows)
    sh["fail_share"] = sh["n_failed"] / sh["n_total"].where(sh["n_total"] > 0)
    return sh


def thresholds_from(sh: pd.DataFrame, q: float = 0.99) -> dict[str, list[float]]:
    s = sh[sh["method"] == "split_half"]
    out = {}
    for cid, d in s.groupby("check_id"):
        w = _ceil4(float(np.quantile(d["fail_share"], q)))
        out[cid] = [w, _ceil4(2 * w)]
    return out


def alarm_table(sh: pd.DataFrame, thr: dict[str, list[float]]) -> pd.DataFrame:
    rows = []
    for (ds, method, cid), d in sh.groupby(["dataset", "method", "check_id"], sort=False):
        w, f = thr[cid]
        st = d["fail_share"].map(lambda x, w=w, f=f: status_of(x, w, f))
        k, n = int((st != "pass").sum()), len(d)
        lo, hi = wilson(k, n)
        rows.append({"dataset": ds, "check_id": cid, "method": method, "trials": n,
                     "alarms": k, "fails": int((st == "fail").sum()), "rate": k / n,
                     "ci_lo": lo, "ci_hi": hi, "warn_share": w, "fail_share": f,
                     "median_share": float(d["fail_share"].median())})
    return pd.DataFrame(rows)


def freeze(thr_by_dataset: dict) -> None:
    old = {}
    if THRESHOLDS.exists():
        old = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8")).get("thresholds", {})
    old.update(thr_by_dataset)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    doc = {
        "version": 1,
        "note": "Run-level warn/fail thresholds of M01-M03, from 200 clean split halves "
                "(99th percentile, fail = 2 x warn). Frozen before the ML grid was run; "
                "do not change after looking at injected runs.",
        "frozen_at": dt.datetime.now().isoformat(timespec="seconds"),
        "code_commit": commit,
        "thresholds": old,
    }
    THRESHOLDS.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["olist", "retail"], required=True)
    ap.add_argument("--freeze", action="store_true", help="write config/ml_thresholds.yaml")
    ap.add_argument("--skip-months", action="store_true")
    a = ap.parse_args(argv)
    sh = run(a.dataset, a.skip_months)
    thr = thresholds_from(sh)
    print("thresholds:", thr)
    if a.freeze:
        if THRESHOLDS.exists() and a.dataset in (yaml.safe_load(
                THRESHOLDS.read_text(encoding="utf-8")).get("thresholds") or {}):
            raise SystemExit(f"thresholds for {a.dataset} already frozen; refusing to change")
        freeze({a.dataset: thr})
    else:
        from dqk.ml.detectors import load_thresholds

        thr = load_thresholds().get(a.dataset, thr)
    tab = alarm_table(sh, thr)
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, df in (("f2b_ml_false_alarm_shares", sh), ("f2_ml_false_alarms", tab)):
        p = TABLES / f"{name}.csv"
        if p.exists():
            prev = pd.read_csv(p)
            df = pd.concat([prev[prev["dataset"] != a.dataset], df], ignore_index=True)
        df.to_csv(p, index=False)
    print(tab.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
