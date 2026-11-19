"""RQ6: machine-learning detectors for silent errors (code plan v1.2, L3-L5).

M01  category consistency (Olist only). Random forest over product attributes from the
     product master (raw.products), reference price and freight, and the seller's category
     profile. A product is flagged when its observed category has probability below tau_1,
     or is a label the model has never seen (reported separately: that part is a rule).
M02  price residual. Gradient-boosting regression of log price from item features; a line
     is flagged when |residual - median| > k x MAD of the clean residuals.
M03  price anomaly. IsolationForest (unsupervised) on log price and a few item features; a
     line is flagged when its score is below the q-quantile of clean scores.

Leakage control (code plan 3.2). Products are split into folds by a stable hash of their id;
every product, and every line of it, is scored by a model that did not see that product.
The detectors therefore model the case "new product / no snapshot", where C22 cannot help.

A detector returns one row in the format of a DQ check (check_id, layer, dimension="ml",
n_failed, n_total, fail_share, status, in_dq_score=False), so the experiment's "worsened",
"detected" and "silent" measures apply unchanged.

    python -m dqk.ml.detectors build --dataset olist|retail     # fit, cache, model card
"""

from __future__ import annotations

import argparse
import hashlib
import time
from dataclasses import dataclass, field

import duckdb
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    IsolationForest,
    RandomForestClassifier,
)

from dqk import CONFIG_DIR
from dqk.dq import status_of
from dqk.ml import ML_DIR
from dqk.ml.dataset import ml_config
from dqk.tables import Mart

CHECK_IDS = ("M01", "M02", "M03")
APPLIES = {"olist": ("M01", "M02", "M03"), "retail": ("M02", "M03")}
THRESHOLDS = CONFIG_DIR / "ml_thresholds.yaml"
MODELS_DIR = ML_DIR / "models"
OLIST_MASTER = ["w", "l", "h", "wd", "ph", "nl", "dl"]


def rq6_config() -> dict:
    return ml_config()["rq6"]


def product_fold(ids: pd.Series, n_folds: int) -> np.ndarray:
    """Stable fold of a product id (same in every process and run)."""
    return np.array(
        [int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16) % n_folds for s in ids], int
    )


def item_key(items: pd.DataFrame) -> pd.Series:
    return items["order_id"] + "|" + items["order_item_id"].astype(str).str.zfill(3)


# ---------------------------------------------------------------- context (product master)


@dataclass
class Context:
    dataset: str
    master: pd.DataFrame  # index product_id: product attributes (Olist) or text SVD (Retail)
    quantity: pd.Series | None = None  # Retail: item key -> quantity
    n_folds: int = 5


def load_context(dataset: str, cfg: dict | None = None) -> Context:
    cfg = cfg or rq6_config()
    from dqk.experiment.runner import dataset_setup

    con = duckdb.connect(str(dataset_setup(dataset)[0]), read_only=True)
    if dataset == "olist":
        m = con.sql(
            """SELECT product_id,
                      try_cast(product_weight_g AS DOUBLE) AS w,
                      try_cast(product_length_cm AS DOUBLE) AS l,
                      try_cast(product_height_cm AS DOUBLE) AS h,
                      try_cast(product_width_cm AS DOUBLE) AS wd,
                      try_cast(product_photos_qty AS DOUBLE) AS ph,
                      try_cast(product_name_lenght AS DOUBLE) AS nl,
                      try_cast(product_description_lenght AS DOUBLE) AS dl
               FROM raw.products"""
        ).df().set_index("product_id")
        con.close()
        return Context(dataset, m, None, cfg["n_folds"])
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer

    d = con.sql("SELECT product_id, category_pt AS description FROM mart.dim_product").df()
    q = con.sql(
        """SELECT invoice AS order_id,
                  CAST(row_number() OVER (PARTITION BY invoice ORDER BY src_row) AS INTEGER)
                      AS order_item_id,
                  quantity
           FROM staging.stg_retail_lines"""
    ).df()
    con.close()
    # Unsupervised text features of the product master (no labels, no prices).
    hv = HashingVectorizer(n_features=2**12, ngram_range=(1, 2), alternate_sign=False)
    tf = TfidfTransformer().fit_transform(hv.transform(d["description"].fillna("")))
    k = cfg["retail_text_dims"]
    z = TruncatedSVD(k, random_state=cfg["seed"]).fit_transform(tf)
    m = pd.DataFrame(z, index=d["product_id"], columns=[f"t{i}" for i in range(k)])
    quantity = pd.Series(q["quantity"].to_numpy(float), index=item_key(q))
    return Context(dataset, m, quantity, cfg["n_folds"])


# ---------------------------------------------------------------- features


def item_frame(mart: Mart, ctx: Context, cats: list[str] | None = None) -> pd.DataFrame:
    """One row per order line with price > 0: key, product_id, fold, lp (log price) and the
    features of M02 / M03."""
    i = mart.fact_order_items
    i = i[i["price"].astype(float) > 0]
    f = pd.DataFrame(
        {
            "key": item_key(i).to_numpy(),
            "product_id": i["product_id"].to_numpy(),
            "lp": np.log(i["price"].astype(float).to_numpy()),
        }
    )
    f["fold"] = product_fold(f["product_id"], ctx.n_folds)
    if ctx.dataset == "olist":
        f = f.join(ctx.master[OLIST_MASTER], on="product_id")
        f["lfreight"] = np.log1p(i["freight_value"].astype(float).to_numpy())
        cat = mart.dim_product.set_index("product_id")["category_en"]
        code = {c: n for n, c in enumerate(cats or [])}
        f["cat"] = f["product_id"].map(cat).map(code).astype(float)
        f["lw"] = np.log1p(f["w"])
        f["lvol"] = np.log1p(f["l"] * f["h"] * f["wd"])
        f["sig"] = (
            f["key"] + "|" + f["product_id"] + "|" + i["price"].astype(str).to_numpy() + "|"
            + i["freight_value"].astype(str).to_numpy() + "|" + f["cat"].astype(str)
        )
    else:
        f["lqty"] = np.log(f["key"].map(ctx.quantity).to_numpy(float))
        f = f.join(ctx.master, on="product_id")
        f["sig"] = f["key"] + "|" + f["product_id"] + "|" + i["price"].astype(str).to_numpy()
    return f


def m02_features(dataset: str) -> list[str]:
    if dataset == "olist":
        return OLIST_MASTER + ["lfreight", "cat"]
    return ["lqty"] + [f"t{i}" for i in range(rq6_config()["retail_text_dims"])]


def m03_features(dataset: str) -> list[str]:
    return ["lp", "lfreight", "lw", "lvol"] if dataset == "olist" else ["lp", "lqty"]


def product_frame(mart: Mart, ctx: Context) -> pd.DataFrame:
    """Olist products with a category: label, master attributes, reference price/freight/
    volume and main seller (from the order lines of ``mart``)."""
    p = mart.dim_product[mart.dim_product["category_en"].notna()][["product_id", "category_en"]]
    i = mart.fact_order_items
    agg = i.assign(price=i["price"].astype(float), fr=i["freight_value"].astype(float)).groupby(
        "product_id").agg(mp=("price", "median"), mf=("fr", "median"), n=("price", "size"),
                          seller=("seller_id", lambda s: s.mode().iat[0]))
    p = p.join(ctx.master[OLIST_MASTER], on="product_id").join(agg, on="product_id")
    p = p[p["n"].notna()].reset_index(drop=True)
    p["fold"] = product_fold(p["product_id"], ctx.n_folds)
    return p


# ---------------------------------------------------------------- M01


def _m01_X(p: pd.DataFrame, train: np.ndarray, cats: list[str]) -> np.ndarray:
    """Numeric attributes + the seller's category profile computed from training products
    only (so a product's own label never enters its features)."""
    t = p[train]
    cnt = pd.crosstab(t["seller"], t["category_en"]).reindex(columns=cats, fill_value=0)
    prof = cnt.div(cnt.sum(axis=1), axis=0).reindex(p["seller"]).to_numpy()
    base = p[OLIST_MASTER + ["mp", "mf", "n"]].to_numpy(float)
    return np.nan_to_num(np.c_[base, prof], nan=-1.0)


def m01_fit_score(p: pd.DataFrame, train: np.ndarray, score: np.ndarray, cats, cfg, seed):
    """Fit on products ``train``, return P (len(score) x len(cats)) for products ``score``."""
    X = _m01_X(p, train, cats)
    rf = RandomForestClassifier(random_state=seed, **cfg["models"]["m01"])
    rf.fit(X[train], p.loc[train, "category_en"])
    out = np.zeros((int(score.sum()), len(cats)), np.float32)
    cols = [cats.index(c) for c in rf.classes_]
    out[:, cols] = rf.predict_proba(X[score])
    return out


# ---------------------------------------------------------------- bundle


@dataclass
class MlBundle:
    dataset: str
    ctx: Context
    cats: list[str]
    P: pd.DataFrame | None  # product x category, out-of-fold (Olist)
    tau1: float | None
    m02: list  # one regressor per fold
    m02_center: float
    m02_mad: float
    m03: list
    m03_thr: float
    cache: pd.DataFrame  # clean lines: sig -> resid, iso (out-of-fold)
    thresholds: dict = field(default_factory=dict)
    card: dict = field(default_factory=dict)


def _fit_items(f: pd.DataFrame, dataset: str, cfg: dict, seed: int):
    """Fold models of M02 and M03 and their out-of-fold scores on the clean lines."""
    feats2, feats3 = m02_features(dataset), m03_features(dataset)
    cat_idx = [feats2.index("cat")] if "cat" in feats2 else None
    m02, m03 = [], []
    resid = np.full(len(f), np.nan)
    iso = np.full(len(f), np.nan)
    rng = np.random.default_rng(seed)
    for k in range(cfg["n_folds"]):
        tr = np.flatnonzero(f["fold"].to_numpy() != k)
        te = f["fold"].to_numpy() == k
        if len(tr) > cfg["max_train_rows"]:
            tr = np.sort(rng.choice(tr, cfg["max_train_rows"], replace=False))
        r = HistGradientBoostingRegressor(
            random_state=seed, categorical_features=cat_idx, **cfg["models"]["m02"]
        ).fit(f.iloc[tr][feats2], f.iloc[tr]["lp"])
        resid[te] = f.loc[te, "lp"].to_numpy() - r.predict(f.loc[te, feats2])
        m02.append(r)
        x3 = f.iloc[tr][feats3].fillna(f[feats3].median())
        iforest = IsolationForest(random_state=seed, **cfg["models"]["m03"]).fit(x3)
        iso[te] = iforest.score_samples(f.loc[te, feats3].fillna(f[feats3].median()))
        m03.append(iforest)
    return m02, m03, resid, iso


def build_bundle(dataset: str, mart: Mart | None = None, verbose: bool = True) -> MlBundle:
    from dqk.experiment.runner import dataset_setup, load_clean_mart

    cfg = rq6_config()
    seed = cfg["seed"]
    t0 = time.perf_counter()
    ctx = load_context(dataset, cfg)
    mart = mart if mart is not None else load_clean_mart(dataset_setup(dataset)[0])
    cats, P, tau1, card = [], None, None, {}
    if dataset == "olist":
        p = product_frame(mart, ctx)
        cats = sorted(p["category_en"].unique())
        Pm = np.zeros((len(p), len(cats)), np.float32)
        for k in range(cfg["n_folds"]):
            te = p["fold"].to_numpy() == k
            Pm[te] = m01_fit_score(p, ~te, te, cats, cfg, seed)
        P = pd.DataFrame(Pm, index=p["product_id"], columns=cats)
        yi = np.array([cats.index(c) for c in p["category_en"]])
        p_true = Pm[np.arange(len(p)), yi]
        tau1 = float(np.quantile(p_true, cfg["m01_tau_quantile"]))
        card["m01_top1"] = float((Pm.argmax(axis=1) == yi).mean())
        top5 = np.argsort(-Pm, axis=1)[:, :5]
        card["m01_top5"] = float((top5 == yi[:, None]).any(axis=1).mean())
        card["m01_tau1"] = tau1
        card["m01_products"] = len(p)
        if verbose:
            print(f"M01: top1 {card['m01_top1']:.3f}  {time.perf_counter() - t0:.0f}s")
    f = item_frame(mart, ctx, cats)
    m02, m03, resid, iso = _fit_items(f, dataset, cfg, seed)
    center = float(np.median(resid))
    mad = float(np.median(np.abs(resid - center)))
    thr3 = float(np.quantile(iso, cfg["m03_quantile"]))
    card |= {
        "lines": len(f),
        "m02_mae": float(np.mean(np.abs(resid))),
        "m02_r2": float(1 - np.var(resid) / np.var(f["lp"])),
        "m02_mad": mad,
        "m03_threshold": thr3,
    }
    if verbose:
        print(f"M02: MAE {card['m02_mae']:.3f} R2 {card['m02_r2']:.3f}  "
              f"{time.perf_counter() - t0:.0f}s")
    cache = pd.DataFrame({"resid": resid, "iso": iso}, index=f["sig"].to_numpy())
    cache = cache[~cache.index.duplicated()]
    b = MlBundle(dataset, ctx, cats, P, tau1, m02, center, mad, m03, thr3, cache, {}, card)
    b.thresholds = load_thresholds().get(dataset, {})
    return b


def bundle_path(dataset: str):
    return MODELS_DIR / f"{dataset}_bundle.joblib"


def load_bundle(dataset: str) -> MlBundle:
    """Cached bundle (fit once with `build`); thresholds always re-read from the YAML."""
    import joblib

    p = bundle_path(dataset)
    b = joblib.load(p) if p.exists() else build_bundle(dataset, verbose=False)
    b.thresholds = load_thresholds().get(dataset, {})
    return b


def load_thresholds() -> dict:
    if not THRESHOLDS.exists():
        return {}
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8")).get("thresholds", {})


# ---------------------------------------------------------------- scoring a load


def score_lines(b: MlBundle, mart: Mart) -> pd.DataFrame:
    """Lines of ``mart`` with resid (M02) and iso (M03). Lines identical to a clean line
    reuse its cached out-of-fold score; changed or new lines are scored by the model of
    their product's fold (the same model that produced the cached scores)."""
    f = item_frame(mart, b.ctx, b.cats)
    f["resid"] = f["sig"].map(b.cache["resid"])
    f["iso"] = f["sig"].map(b.cache["iso"])
    todo = f["resid"].isna().to_numpy()
    if todo.any():
        feats2, feats3 = m02_features(b.dataset), m03_features(b.dataset)
        med3 = f[feats3].median()
        for k in range(b.ctx.n_folds):
            m = todo & (f["fold"].to_numpy() == k)
            if not m.any():
                continue
            f.loc[m, "resid"] = f.loc[m, "lp"] - b.m02[k].predict(f.loc[m, feats2])
            f.loc[m, "iso"] = b.m03[k].score_samples(f.loc[m, feats3].fillna(med3))
    return f


def flags(b: MlBundle, mart: Mart, lines: pd.DataFrame | None = None) -> dict[str, pd.Series]:
    """Item-level flags per detector (index = line or product)."""
    cfg = rq6_config()
    out = {}
    if "M01" in APPLIES[b.dataset]:
        sold = set(mart.fact_order_items["product_id"])
        p = mart.dim_product[mart.dim_product["category_en"].notna()]
        p = p[p["product_id"].isin(sold) & p["product_id"].isin(b.P.index)]
        lab = p["category_en"].to_numpy()
        known = np.isin(lab, b.cats)
        prob = np.zeros(len(p))
        rows = b.P.index.get_indexer(p["product_id"])
        cols = np.array([b.cats.index(c) if k else 0 for c, k in zip(lab, known, strict=True)])
        prob[known] = b.P.to_numpy()[rows[known], cols[known]]
        out["M01"] = pd.Series((~known) | (prob < b.tau1), index=p["product_id"].to_numpy())
        out["M01_unseen_label"] = pd.Series(~known, index=p["product_id"].to_numpy())
    f = lines if lines is not None else score_lines(b, mart)
    out["M02"] = pd.Series(
        np.abs(f["resid"].to_numpy() - b.m02_center) > cfg["m02_k"] * b.m02_mad,
        index=f["key"].to_numpy(),
    )
    out["M03"] = pd.Series(f["iso"].to_numpy() < b.m03_thr, index=f["key"].to_numpy())
    return out


def run_ml_checks(mart: Mart, b: MlBundle) -> pd.DataFrame:
    """One row per detector, in the format of dqk.dq.run_dq_checks."""
    fl = flags(b, mart)
    rows = []
    for cid in APPLIES[b.dataset]:
        s = fl[cid]
        n_failed, n_total = int(s.sum()), len(s)
        share = n_failed / n_total if n_total else 0.0
        warn, fail = b.thresholds.get(cid, (np.inf, np.inf))
        rows.append({"check_id": cid, "layer": "mart", "dimension": "ml",
                     "n_failed": n_failed, "n_total": n_total, "fail_share": share,
                     "status": status_of(share, warn, fail), "in_dq_score": False})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- CLI


def main(argv=None) -> int:
    import joblib

    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["build"])
    ap.add_argument("--dataset", choices=["olist", "retail"], required=True)
    a = ap.parse_args(argv)
    # Import through the package, so the pickle refers to dqk.ml.detectors.MlBundle and
    # not to __main__.MlBundle (python -m runs this file as __main__).
    from dqk.ml import detectors

    b = detectors.build_bundle(a.dataset)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(b, bundle_path(a.dataset), compress=3)
    card = pd.Series(b.card)
    card.to_csv(ML_DIR / f"model_card_{a.dataset}.csv", header=["value"])
    print(card.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
