"""RQ5: a learned KPI-risk score from the outputs of the DQ checks (code plan v1.2, L2).

Question. Given only what a pipeline observes after a load (the fail_share of each core
check), can a model tell whether the load distorts a KPI, better than the aggregate DQ score
and the rule "any check worse than before", and for error types it has never seen?

Methods (scores: higher = more risk)
  rules     detected (any check worse; binary), n_worsened, dq_drop (aggregate score of RQ2),
            and per KPI group the KPI-weighted measures of RQ2 (max_<g>, n_worsened_<g>)
  models    logreg, rf, gb on d_C01..d_C20 (config/ml.yaml, fixed hyperparameters)

Splits (every run is predicted by a model that never saw its group)
  cell      GroupKFold(5) over cells, Olist main grid + clean runs (in-distribution)
  loeo      leave one error type out (E0 clean, E1..E6), Olist main grid + clean runs
  variants  train Olist main + clean, test the unseen error variants and re-keyed duplicates
  retail    train all Olist runs on the 10 checks that also exist on Online Retail II,
            test Online Retail II runs + its clean runs

Operating point. A model's (or a continuous rule's) alarm threshold is the (1 - alarm_rate)
quantile of the scores of the non-material runs in the training folds, from an inner
GroupKFold(3) over cells, so the test fold never sets it.

    python -m dqk.ml.risk_model [--quick]

Writes results/tables/t8_rq5_*.csv and results/ml/rq5_oof.parquet.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dqk import RESULTS_DIR
from dqk.analysis.v11 import group_checks
from dqk.ml import ML_DIR
from dqk.ml.dataset import CORE, FEATURES, GROUPS, frame_path, ml_config

TABLES = RESULTS_DIR / "tables"
RETAIL_CHECKS = ["C01", "C02", "C05", "C06", "C08", "C10", "C11", "C17", "C19", "C20"]
# name -> (estimator, feature set). Feature sets:
#   check     d_<check> of every check (the check identity is visible to the model)
#   agnostic  summaries that do not name a check: number of checks above their noise
#             level, largest and summed increase, largest increase per DQ dimension
#   hybrid    check + agnostic
# gb_mono_* use monotone increasing constraints (a check that gets worse never lowers the
# risk). The agnostic and hybrid variants were added after the quick run showed that
# check-level models do not generalise to unseen error types (exploratory, reported so).
MODELS = {
    "logreg": ("logreg", "check"),
    "rf": ("rf", "check"),
    "gb": ("gb", "check"),
    "gb_mono_hybrid": ("gb_mono", "hybrid"),
    "gb_mono_agnostic": ("gb_mono", "agnostic"),
}
DIMENSIONS = ["completeness", "uniqueness", "referential_integrity", "validity", "temporal",
              "reconciliation", "volume"]


# ---------------------------------------------------------------- models


def make_model(name: str, cfg: dict, seed: int, n_features: int | None = None):
    if name == "gb_mono":
        return HistGradientBoostingClassifier(
            random_state=seed, monotonic_cst=[1] * n_features, **cfg["models"]["gb"]
        )
    p = cfg["models"][name]
    if name == "logreg":
        return make_pipeline(
            SimpleImputer(strategy="constant", fill_value=0.0),
            StandardScaler(),
            LogisticRegression(C=p["C"], max_iter=p["max_iter"]),
        )
    if name == "rf":
        return make_pipeline(
            SimpleImputer(strategy="constant", fill_value=0.0),
            RandomForestClassifier(random_state=seed, **p),
        )
    if name == "gb":
        return HistGradientBoostingClassifier(random_state=seed, **p)
    raise ValueError(name)


def make_regressor(cfg: dict, seed: int):
    return HistGradientBoostingRegressor(random_state=seed, **cfg["models"]["gb"])


# ---------------------------------------------------------------- feature sets


def check_meta() -> pd.DataFrame:
    """dimension and noise tolerance (3 x sd of the clean split-half deviation) per check."""
    from dqk.ml.dataset import load_noise

    checks, dev = load_noise("olist")
    return pd.DataFrame({"dimension": checks["dimension"], "tol": 3 * dev.std()})


def design(df: pd.DataFrame, feats: list[str], kind: str, meta: pd.DataFrame) -> pd.DataFrame:
    """Model input for a feature set, computed over the checks in ``feats`` only (so the
    retail split uses the same 10 checks on both sides)."""
    X = df[feats]
    if kind == "check":
        return X
    ids = [f[2:] for f in feats]
    d = np.nan_to_num(X.to_numpy(float), nan=0.0)
    tol = meta["tol"].reindex(ids).fillna(0).to_numpy()
    pos = np.clip(d, 0, None)
    a = pd.DataFrame(
        {"a_n_up": (d > tol).sum(axis=1), "a_max": pos.max(axis=1), "a_sum": pos.sum(axis=1)},
        index=df.index,
    )
    dims = meta["dimension"].reindex(ids).to_numpy()
    for dim in DIMENSIONS:
        cols = dims == dim
        a[f"dim_{dim}"] = pos[:, cols].max(axis=1) if cols.any() else 0.0
    return a if kind == "agnostic" else pd.concat([X, a], axis=1)


def fit_predict(name, cfg, Xtr, ytr, Xte, cells):
    """(test scores, threshold at the configured alarm rate, threshold at Youden's J).

    Both thresholds come from inner cross-validated scores on the training data, and the
    test score is the mean of the same inner-fold models. A single refit on all training
    data would put its probabilities on a slightly different scale, which near saturation
    (0.9997 vs 0.99985) is enough to move whole error types across a threshold."""
    est, _ = MODELS[name]
    model = make_model(est, cfg, cfg["seed"], Xtr.shape[1])
    inner, fitted = _inner_scores(model, Xtr, ytr, cells, return_models=True)
    s = np.mean(
        [m.predict_proba(Xte)[:, 1] if hasattr(m, "predict_proba") else np.full(len(Xte), m)
         for m in fitted],
        axis=0,
    )
    return s, _threshold(inner, ytr, cfg["alarm_rate"]), _youden(inner, ytr)


# ---------------------------------------------------------------- splits


def split_frames(df: pd.DataFrame, split: str):
    """Yield (name, train_index, test_index, features) per fold."""
    olist = df[df["dataset"] == "olist"]
    core = olist[olist["grid"].isin(["main", "clean"])]
    if split in ("cell", "loeo"):
        groups = core["cell_id"] if split == "cell" else core["code"]
        if split == "cell":
            folds = GroupKFold(n_splits=5).split(core, groups=groups)
            for k, (tr, te) in enumerate(folds):
                yield f"fold{k}", core.index[tr], core.index[te], FEATURES
        else:
            for code in sorted(groups.unique()):
                te = core.index[groups == code]
                tr = core.index[groups != code]
                yield code, tr, te, FEATURES
    elif split == "variants":
        te = olist.index[olist["grid"].isin(["variants", "rekeyed"])]
        yield "variants", core.index, te, FEATURES
    elif split == "retail":
        retail = df[df["dataset"] == "retail"]
        yield "retail", olist.index, retail.index, [f"d_{c}" for c in RETAIL_CHECKS]
    else:
        raise ValueError(split)


# ---------------------------------------------------------------- fitting


def _threshold(scores: np.ndarray, y: np.ndarray, alarm_rate: float) -> float:
    neg = scores[y == 0]
    return float(np.quantile(neg, 1 - alarm_rate)) if neg.size else float("inf")


def _youden(scores: np.ndarray, y: np.ndarray) -> float:
    """Threshold maximising TPR - FPR (Youden's J); an alarm is score >= threshold.

    The threshold is the midpoint between the chosen score and the next lower distinct
    score, not the chosen score itself: probabilities of a boosted model saturate near 1,
    and a refit on more data can put the same runs a hair below a threshold taken at the
    edge of that cluster."""
    from sklearn.metrics import roc_curve

    if len(np.unique(y)) < 2:
        return 0.5
    fpr, tpr, thr = roc_curve(y, scores)
    t = float(thr[np.argmax(tpr - fpr)])
    lower = scores[scores < t]
    return (t + float(lower.max())) / 2 if lower.size else t


def _inner_scores(
    model, X: pd.DataFrame, y: np.ndarray, cells: np.ndarray, return_models: bool = False
):
    """Inner cross-validated scores on the training data (GroupKFold(3) over cells), and
    optionally the fitted inner models (a constant for a fold with one class)."""
    out = np.full(len(y), np.nan)
    models = []
    n = min(3, len(np.unique(cells)))
    for tr, te in GroupKFold(n_splits=n).split(X, groups=cells):
        if len(np.unique(y[tr])) < 2:
            out[te] = float(y[tr][0])
            models.append(float(y[tr][0]))
            continue
        m = clone(model).fit(X.iloc[tr], y[tr])
        out[te] = m.predict_proba(X.iloc[te])[:, 1]
        models.append(m)
    return (out, models) if return_models else out


def oof(
    df: pd.DataFrame, target: str, split: str, cfg: dict, models=tuple(MODELS)
) -> pd.DataFrame:
    """Out-of-fold scores and alarms of every model and rule for one target and split.
    One row per test run x method."""
    rate = cfg["alarm_rate"]
    meta = check_meta()
    rules = ["detected", "n_worsened", "dq_drop"]
    g = target.removeprefix("material_") if target != "material" else None
    if g:
        rules += [c for c in (f"max_{g}", f"n_worsened_{g}") if c in df]
    rows = []
    for fold, tr, te, feats in split_frames(df, split):
        dtr = df.loc[tr].dropna(subset=[target])
        dte = df.loc[te].dropna(subset=[target])
        if dte.empty:
            continue
        ytr = dtr[target].to_numpy(int)
        base = {
            "split": split, "target": target, "fold": fold,
            "cell_id": dte["cell_id"].to_numpy(), "seed": dte["seed"].to_numpy(),
            "code": dte["code"].to_numpy(), "variant": dte["variant"].to_numpy(),
            "dataset": dte["dataset"].to_numpy(), "y": dte[target].to_numpy(int),
        }
        for r in rules:
            if r not in dte or dtr[r].isna().all():
                continue
            s_tr = dtr[r].fillna(0).to_numpy(float)
            s_te = dte[r].fillna(0).to_numpy(float)
            if r == "detected":
                thr = thr_j = 0.5
            else:
                thr, thr_j = _threshold(s_tr, ytr, rate), _youden(s_tr, ytr)
            rows.append(pd.DataFrame(base | {"method": r, "score": s_te, "alarm": s_te > thr,
                                             "alarm_j": s_te >= thr_j}))
        if len(np.unique(ytr)) < 2:
            continue
        for name in models:
            kind = MODELS[name][1]
            s_te, thr, thr_j = fit_predict(
                name, cfg, design(dtr, feats, kind, meta), ytr,
                design(dte, feats, kind, meta), dtr["cell_id"].to_numpy(),
            )
            rows.append(pd.DataFrame(base | {"method": name, "score": s_te, "alarm": s_te > thr,
                                             "alarm_j": s_te >= thr_j}))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ---------------------------------------------------------------- metrics


def _auc(y, s) -> float:
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else np.nan


def _cluster_index(cells: np.ndarray):
    uniq, inv = np.unique(cells, return_inverse=True)
    return [np.flatnonzero(inv == i) for i in range(len(uniq))]


def summarise(o: pd.DataFrame, n_boot: int, seed: int) -> pd.DataFrame:
    """Per split x target x method: AUROC (cluster-bootstrap CI), AUPRC, Brier, and at the
    operating point: alarm rate on non-material runs, recall on material runs, silent rate
    (material and no alarm, over all runs)."""
    rng = np.random.default_rng(seed)
    rows = []
    for (split, target, method), d in o.groupby(["split", "target", "method"], sort=False):
        y, s, a = d["y"].to_numpy(), d["score"].to_numpy(float), d["alarm"].to_numpy(bool)
        aj = d["alarm_j"].to_numpy(bool)
        auc = _auc(y, s)
        lo = hi = np.nan
        if n_boot and not np.isnan(auc):
            idx = _cluster_index(d["cell_id"].to_numpy())
            b = []
            for _ in range(n_boot):
                ii = np.concatenate([idx[i] for i in rng.integers(0, len(idx), len(idx))])
                b.append(_auc(y[ii], s[ii]))
            b = np.array(b, float)
            if np.isfinite(b).any():
                lo, hi = np.nanquantile(b, [0.025, 0.975])
        prob = method in MODELS
        rows.append(
            {
                "split": split, "target": target, "method": method,
                "n": len(y), "n_material": int(y.sum()),
                "auroc": auc, "auroc_lo": lo, "auroc_hi": hi,
                "auprc": float(average_precision_score(y, s)) if 0 < y.sum() else np.nan,
                "brier": float(brier_score_loss(y, s)) if prob else np.nan,
                "alarm_rate_nonmaterial": float(a[y == 0].mean()) if (y == 0).any() else np.nan,
                "recall_material": float(a[y == 1].mean()) if (y == 1).any() else np.nan,
                "silent_rate": float(((y == 1) & ~a).mean()),
                "alarm_rate_nonmaterial_j": float(aj[y == 0].mean()) if (y == 0).any()
                else np.nan,
                "recall_material_j": float(aj[y == 1].mean()) if (y == 1).any() else np.nan,
                "silent_rate_j": float(((y == 1) & ~aj).mean()),
            }
        )
    return pd.DataFrame(rows)


def auc_difference(o: pd.DataFrame, a: str, b: str, n_boot: int, seed: int) -> pd.DataFrame:
    """AUROC(a) - AUROC(b) on the same runs, cluster-bootstrap CI and two-sided p."""
    rng = np.random.default_rng(seed)
    rows = []
    for (split, target), d in o.groupby(["split", "target"], sort=False):
        da = d[d["method"] == a].set_index(["cell_id", "seed", "fold"])
        db = d[d["method"] == b].set_index(["cell_id", "seed", "fold"])
        if da.empty or db.empty:
            continue
        j = da.join(db[["score"]], rsuffix="_b", how="inner")
        y, sa, sb = j["y"].to_numpy(), j["score"].to_numpy(float), j["score_b"].to_numpy(float)
        diff = _auc(y, sa) - _auc(y, sb)
        if np.isnan(diff):
            continue
        idx = _cluster_index(j.index.get_level_values("cell_id").to_numpy())
        bs = []
        for _ in range(n_boot):
            ii = np.concatenate([idx[i] for i in rng.integers(0, len(idx), len(idx))])
            bs.append(_auc(y[ii], sa[ii]) - _auc(y[ii], sb[ii]))
        bs = np.array(bs, float)
        bs = bs[np.isfinite(bs)]
        p = min(1.0, max(2 * min((bs <= 0).mean(), (bs >= 0).mean()), 1 / bs.size))
        lo, hi = np.quantile(bs, [0.025, 0.975])
        rows.append({"split": split, "target": target, "a": a, "b": b, "diff": diff,
                     "ci_lo": lo, "ci_hi": hi, "p": p})
    return pd.DataFrame(rows)


def by_code(o: pd.DataFrame) -> pd.DataFrame:
    """Per split x method x error code (and variant): material share, recall, alarms, silent."""
    keys = ["split", "target", "method", "dataset", "code", "variant"]
    g = o.groupby(keys, sort=False)
    return g.apply(
        lambda d: pd.Series(
            {
                "n": len(d),
                "material": d["y"].mean(),
                "recall_material": d.loc[d["y"] == 1, "alarm"].mean() if (d["y"] == 1).any()
                else np.nan,
                "alarm_rate_nonmaterial": d.loc[d["y"] == 0, "alarm"].mean()
                if (d["y"] == 0).any() else np.nan,
                "silent_rate": ((d["y"] == 1) & ~d["alarm"]).mean(),
                "recall_material_j": d.loc[d["y"] == 1, "alarm_j"].mean()
                if (d["y"] == 1).any() else np.nan,
                "alarm_rate_nonmaterial_j": d.loc[d["y"] == 0, "alarm_j"].mean()
                if (d["y"] == 0).any() else np.nan,
                "silent_rate_j": ((d["y"] == 1) & ~d["alarm_j"]).mean(),
            }
        ),
        include_groups=False,
    ).reset_index()


# ---------------------------------------------------------------- magnitude (regression)


def magnitude(df: pd.DataFrame, cfg: dict, n_boot: int) -> pd.DataFrame:
    """Spearman rho between predicted and true distortion per KPI group (out-of-fold, splits
    cell and loeo), next to dq_drop and the KPI-weighted measure max_<g> of RQ2."""
    from dqk.analysis.v11 import _rho_boot

    rng = np.random.default_rng(cfg["seed"])
    rows = []
    for split in ("cell", "loeo"):
        for g in GROUPS:
            t = f"dist_{g}"
            if t not in df:
                continue
            pred = pd.Series(np.nan, index=df.index)
            for _fold, tr, te, feats in split_frames(df, split):
                dtr = df.loc[tr].dropna(subset=[t])
                dtr = dtr[np.isfinite(dtr[t])]
                if dtr.empty or dtr[t].nunique() < 2:
                    continue
                m = make_regressor(cfg, cfg["seed"]).fit(dtr[feats], np.log1p(dtr[t]))
                pred.loc[te] = m.predict(df.loc[te, feats])
            d = df.assign(pred=pred).dropna(subset=[t, "pred"])
            d = d[np.isfinite(d[t])]
            for method in ("pred", "dq_drop", f"max_{g}"):
                if method not in d:
                    continue
                rho, lo, hi, p = _rho_boot(
                    d[method].fillna(0).to_numpy(float), d[t].to_numpy(float),
                    d["cell_id"].to_numpy(), rng, n_boot,
                )
                rows.append({"split": split, "group": g,
                             "method": "gb_regressor" if method == "pred" else method,
                             "n": len(d), "rho": rho, "ci_lo": lo, "ci_hi": hi, "p": p})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- explanation


def importance(df: pd.DataFrame, cfg: dict, targets) -> pd.DataFrame:
    """Permutation importance (drop in AUROC) of each check for the gb model, on the test
    folds of the cell split, averaged over folds. Compared with the checks that guard each
    KPI group in the traceability matrix of Part 2 (config/traceability.yaml)."""
    guard = group_checks()
    rows = []
    for target in targets:
        g = target.removeprefix("material_") if target != "material" else None
        imps = []
        for _fold, tr, te, feats in split_frames(df, "cell"):
            dtr, dte = df.loc[tr].dropna(subset=[target]), df.loc[te].dropna(subset=[target])
            if dtr[target].nunique() < 2 or dte[target].nunique() < 2:
                continue
            m = make_model("gb", cfg, cfg["seed"]).fit(dtr[feats], dtr[target].astype(int))
            r = permutation_importance(
                m, dte[feats], dte[target].astype(int), scoring="roc_auc", n_repeats=5,
                random_state=cfg["seed"], n_jobs=-1,
            )
            imps.append(pd.Series(r.importances_mean, index=[f[2:] for f in feats]))
        if not imps:
            continue
        imp = pd.concat(imps, axis=1).mean(axis=1)
        for c in CORE:
            rows.append({"target": target, "group": g or "any", "check_id": c,
                         "importance": float(imp.get(c, 0.0)),
                         "guards": bool(g and c in guard.get(g, []))})
    return pd.DataFrame(rows)


def traceability_overlap(imp: pd.DataFrame) -> pd.DataFrame:
    """Per KPI group: do the most important checks coincide with the guarding checks?
    top-k with k = number of guarding checks; Jaccard and share of total importance."""
    guard = group_checks()
    rows = []
    for g, d in imp[imp["group"] != "any"].groupby("group"):
        gs = set(guard.get(g, []))
        pos = d[d["importance"] > 0].sort_values("importance", ascending=False)
        top = set(pos["check_id"].head(len(gs)))
        tot = pos["importance"].sum()
        rows.append({
            "group": g, "guarding": ",".join(sorted(gs)), "top_k": ",".join(
                pos["check_id"].head(len(gs))),
            "jaccard": len(top & gs) / len(top | gs) if (top | gs) else np.nan,
            "share_on_guarding": float(pos.loc[pos["check_id"].isin(gs), "importance"].sum()
                                       / tot) if tot > 0 else np.nan,
            "n_important": int((d["importance"] > 0.005).sum()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main


def run(quick: bool = False, noise: bool = True) -> dict[str, pd.DataFrame]:
    cfg = ml_config()["rq5"]
    n_boot = 100 if quick else cfg["n_boot"]
    df = pd.read_parquet(frame_path(noise))
    targets = ["material"] + [f"material_{g}" for g in GROUPS if f"material_{g}" in df]
    splits = ("cell", "loeo", "variants", "retail")
    parts = []
    t0 = time.perf_counter()
    for split in splits:
        for target in targets:
            if quick:
                models = ("gb", "gb_mono_agnostic")
            elif target == "material":
                models = tuple(MODELS)
            else:
                models = ("gb", "gb_mono_hybrid", "gb_mono_agnostic")
            o = oof(df, target, split, cfg, models)
            if not o.empty:
                parts.append(o)
        print(f"oof {split}: {time.perf_counter() - t0:.0f}s")
    o = pd.concat(parts, ignore_index=True)
    out = {
        "oof": o,
        "auc": summarise(o, n_boot, cfg["seed"]),
        "diff": pd.concat(
            [auc_difference(o, a, b, n_boot, cfg["seed"])
             for a in ("gb", "gb_mono_hybrid", "gb_mono_agnostic")
             for b in ("dq_drop", "detected")],
            ignore_index=True,
        ),
        "by_code": by_code(o[o["target"] == "material"]),
    }
    print(f"metrics: {time.perf_counter() - t0:.0f}s")
    out["magnitude"] = magnitude(df, cfg, n_boot)
    print(f"magnitude: {time.perf_counter() - t0:.0f}s")
    out["importance"] = importance(df, cfg, targets)
    out["overlap"] = traceability_overlap(out["importance"])
    print(f"importance: {time.perf_counter() - t0:.0f}s")
    return out


def write(out: dict[str, pd.DataFrame], suffix: str = "") -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    ML_DIR.mkdir(parents=True, exist_ok=True)
    out["oof"].to_parquet(ML_DIR / f"rq5_oof{suffix}.parquet", index=False)
    names = {"auc": "t8_rq5_auc", "diff": "t8a_rq5_auc_diff", "by_code": "t8b_rq5_by_code",
             "magnitude": "t8c_rq5_spearman", "importance": "t8d_rq5_importance",
             "overlap": "t8e_rq5_traceability"}
    for k, n in names.items():
        out[k].to_csv(TABLES / f"{n}{suffix}.csv", index=False)
        print(f"wrote {n}{suffix}.csv")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="gb only, 100 bootstrap draws")
    ap.add_argument("--noiseless", action="store_true", help="sensitivity: no natural noise")
    a = ap.parse_args(argv)
    out = run(a.quick, noise=not a.noiseless)
    write(out, ("_noiseless" if a.noiseless else "") + ("_quick" if a.quick else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
