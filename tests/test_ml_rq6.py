"""RQ6 (code plan v1.2): ML detectors M01-M03, leakage control, harness integration."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from dqk.ml.detectors import APPLIES, bundle_path, product_fold


def test_product_fold_stable_and_balanced():
    ids = pd.Series([f"p{i:05d}" for i in range(5000)])
    a, b = product_fold(ids, 5), product_fold(ids, 5)
    assert (a == b).all() and set(a) == {0, 1, 2, 3, 4}
    share = np.bincount(a) / len(a)
    assert share.min() > 0.17 and share.max() < 0.23


@pytest.fixture(scope="module")
def olist():
    if not bundle_path("olist").exists():
        pytest.skip("run python -m dqk.ml.detectors build --dataset olist first")
    from dqk.experiment.runner import load_clean_mart
    from dqk.ml.detectors import load_bundle

    return load_bundle("olist"), load_clean_mart()


@pytest.mark.slow
def test_crossfit_is_out_of_fold(olist):
    """A model that had seen each product would recover its label almost always; the
    out-of-fold accuracy must stay well below that."""
    b, _ = olist
    assert 0.3 < b.card["m01_top1"] < 0.95
    assert b.card["m02_r2"] < 0.95


@pytest.mark.slow
def test_clean_load_reuses_cache(olist):
    from dqk.ml.detectors import score_lines

    b, mart = olist
    f = score_lines(b, mart)
    assert len(f) == len(b.cache)
    assert np.allclose(f["resid"].to_numpy(), b.cache.loc[f["sig"], "resid"].to_numpy())


@pytest.mark.slow
def test_changed_price_rescored_by_same_fold_model(olist):
    """Price is not an M02 feature, so x100 on one line moves its residual by ln(100)
    exactly, provided the line is re-scored by the fold model that made the cached score."""
    from dqk.ml.detectors import score_lines

    b, mart = olist
    i = mart.fact_order_items.copy()
    k = int(np.flatnonzero(i["price"].astype(float).to_numpy() > 1)[123])
    i.loc[k, "price"] = float(i.loc[k, "price"]) * 100
    f0 = score_lines(b, mart).set_index("key")
    f1 = score_lines(b, replace(mart, fact_order_items=i)).set_index("key")
    key = i.loc[k, "order_id"] + "|" + str(i.loc[k, "order_item_id"]).zfill(3)
    assert f1.loc[key, "resid"] - f0.loc[key, "resid"] == pytest.approx(np.log(100), abs=1e-6)
    other = f1.index != key
    assert np.allclose(f1.loc[other, "resid"], f0.loc[other, "resid"])


@pytest.mark.slow
def test_unseen_label_flagged_by_m01(olist):
    from dqk.ml.detectors import flags

    b, mart = olist
    p = mart.dim_product.copy()
    pid = mart.fact_order_items["product_id"].iloc[0]
    p.loc[p["product_id"] == pid, "category_en"] = "BED_BATH_TABLE"
    fl = flags(b, replace(mart, dim_product=p))
    assert fl["M01"].loc[pid] and fl["M01_unseen_label"].loc[pid]


@pytest.mark.slow
def test_suites_core_unchanged_ml_adds_rows(olist):
    from dqk.experiment.runner import make_baseline

    _, mart = olist
    core = make_baseline(mart, suite="core")
    ml = make_baseline(mart, suite="ml")
    assert not core.dq["check_id"].str.startswith("M").any()
    m = ml.dq[ml.dq["check_id"].str.startswith("M")]
    assert m["check_id"].tolist() == list(APPLIES["olist"])
    assert (m["dimension"] == "ml").all() and not m["in_dq_score"].any()
    same = core.dq.merge(ml.dq, on="check_id", suffixes=("", "_ml"))
    assert np.allclose(same["fail_share"], same["fail_share_ml"], equal_nan=True)
    if ml.ml.thresholds:
        assert (m["status"] == "pass").all()
