"""RQ5 (code plan v1.2): run-level data set, noise, splits and operating points."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dqk.ml.dataset import CORE, FEATURES, META, add_noise, frame_path
from dqk.ml.risk_model import (
    DIMENSIONS,
    _threshold,
    _youden,
    design,
    split_frames,
)


def _checks(**over) -> pd.DataFrame:
    rows = {
        c: {"dimension": "completeness", "in_dq_score": True, "warn_share": 0.0,
            "fail_share_thr": 0.01, "clean_share": 0.0, "clean_status": "pass"}
        for c in CORE
    }
    for c, d in over.items():
        rows[c] |= d
    return pd.DataFrame.from_dict(rows, orient="index")


def _runs(shares: dict[str, list[float]]) -> pd.DataFrame:
    n = len(next(iter(shares.values())))
    df = pd.DataFrame({f"s_{c}": [0.0] * n for c in CORE})
    for c, v in shares.items():
        df[f"s_{c}"] = v
    return df


def test_add_noise_rules_and_features():
    checks = _checks(C03={"clean_share": 0.001, "clean_status": "warn", "warn_share": 0.0,
                          "fail_share_thr": 0.002})
    dev = pd.DataFrame(0.0, index=[0, 1], columns=CORE)
    runs = _runs({"C03": [0.001, 0.003], "C05": [0.0, 0.02]})
    out = add_noise(runs, checks, dev, np.array([0, 1]), 0)
    # C03 already warns on clean data: only a move to fail counts (decision D3)
    assert out["w_C03"].tolist() == [False, True]
    assert out["w_C05"].tolist() == [False, True]
    assert out["detected"].tolist() == [0.0, 1.0]
    assert out["n_worsened"].tolist() == [0, 2]
    assert out.loc[1, "d_C05"] == pytest.approx(0.02)
    assert out.loc[0, "dq_drop"] == pytest.approx(0.0)
    assert out.loc[1, "dq_drop"] == pytest.approx((0.002 + 0.02) / 20)


def test_add_noise_uses_given_trials_and_clips():
    checks = _checks()
    dev = pd.DataFrame(0.0, index=range(4), columns=CORE)
    dev["C07"] = [-0.5, 0.0, 0.1, 0.2]
    runs = _runs({"C07": [0.0, 0.0, 0.0]})
    out = add_noise(runs, checks, dev, np.arange(4), 0, pick=np.array([0, 2, 3]))
    assert out["noise_trial"].tolist() == [0, 2, 3]
    assert out["n_C07"].tolist() == pytest.approx([0.0, 0.1, 0.2])  # clipped at 0


def test_youden_midpoint_and_quantile_threshold():
    y = np.array([0, 0, 0, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.9999, 0.9999])
    t = _youden(s, y)
    assert 0.3 < t < 0.9999  # midpoint, not the edge of the saturated cluster
    assert (s[y == 1] >= t).all() and not (s[y == 0] >= t).any()
    neg = np.linspace(0, 1, 101)
    thr = _threshold(np.r_[neg, [2.0]], np.r_[np.zeros(101), [1]], 0.05)
    assert (neg > thr).mean() <= 0.05


def test_fit_predict_threshold_matches_scores():
    """Separable data: every positive test run alarms, no negative one does, although the
    probabilities saturate near 1 (the case that broke a refit-on-all-data threshold)."""
    from dqk.ml.dataset import ml_config
    from dqk.ml.risk_model import fit_predict

    cfg = ml_config()["rq5"]
    rng = np.random.default_rng(0)
    n = 600
    cells = np.repeat(np.arange(12), n // 12)
    y = (cells % 2).astype(int)
    X = pd.DataFrame({"a": y * 0.5 + rng.normal(0, 0.01, n), "b": rng.normal(0, 1, n)})
    tr, te = cells < 9, cells >= 9
    s, thr, thr_j = fit_predict("gb", cfg, X[tr], y[tr], X[te], cells[tr])
    assert ((s >= thr_j) == (y[te] == 1)).all()
    assert ((s > thr) == (y[te] == 1)).all()


def test_design_feature_sets_hide_check_identity():
    meta = pd.DataFrame({"dimension": ["uniqueness"] * 20, "tol": 0.0}, index=CORE)
    meta.loc["C18", "dimension"] = "reconciliation"
    df = pd.DataFrame(0.0, index=[0, 1], columns=FEATURES)
    df.loc[1, "d_C18"] = 0.3
    df.loc[1, "d_C05"] = 0.1
    agn = design(df, FEATURES, "agnostic", meta)
    assert not any(c.startswith("d_") for c in agn)
    assert set(agn) == {"a_n_up", "a_max", "a_sum"} | {f"dim_{d}" for d in DIMENSIONS}
    assert agn.loc[1, "a_n_up"] == 2 and agn.loc[1, "a_max"] == pytest.approx(0.3)
    assert agn.loc[1, "dim_reconciliation"] == pytest.approx(0.3)
    hyb = design(df, FEATURES, "hybrid", meta)
    assert set(FEATURES) <= set(hyb) and "a_max" in hyb
    assert design(df, FEATURES, "check", meta).columns.tolist() == FEATURES


@pytest.fixture(scope="module")
def frame():
    p = frame_path(True)
    if not p.exists():
        pytest.skip("run python -m dqk.ml.dataset first")
    return pd.read_parquet(p)


@pytest.mark.slow
def test_frame_features_never_include_meta(frame):
    assert not set(META) & set(FEATURES)
    assert frame.groupby(["dataset", "grid"]).size().to_dict() == {
        ("olist", "clean"): 100, ("olist", "main"): 13000, ("olist", "rekeyed"): 2000,
        ("olist", "variants"): 2600, ("retail", "clean"): 100, ("retail", "retail"): 6000,
    }


@pytest.mark.slow
def test_noise_trials_never_reused(frame):
    for _ds, d in frame.groupby("dataset"):
        clean = d[d["code"] == "E0"]["noise_trial"]
        aug = d[d["code"] != "E0"]["noise_trial"]
        assert clean.is_unique and clean.min() >= 100
        assert aug.max() < 100


@pytest.mark.slow
def test_splits_hold_out_groups(frame):
    for _f, tr, te, _feats in split_frames(frame, "cell"):
        assert not set(frame.loc[tr, "cell_id"]) & set(frame.loc[te, "cell_id"])
    for code, tr, te, _feats in split_frames(frame, "loeo"):
        assert set(frame.loc[te, "code"]) == {code}
        assert code not in set(frame.loc[tr, "code"])
    (_n, tr, te, _feats), = split_frames(frame, "variants")
    assert set(frame.loc[te, "grid"]) == {"variants", "rekeyed"}
    assert set(frame.loc[tr, "grid"]) == {"main", "clean"}
    (_n, tr, te, feats), = split_frames(frame, "retail")
    assert set(frame.loc[tr, "dataset"]) == {"olist"} and set(frame.loc[te, "dataset"]) == {
        "retail"}
    assert frame.loc[te, feats].notna().all().all()


@pytest.mark.slow
def test_noiseless_frame_reproduces_stored_detection():
    """Without added noise, the rules recomputed from stored shares equal the stored flags."""
    p = frame_path(False)
    if not p.exists():
        pytest.skip("run python -m dqk.ml.dataset first")
    from dqk.analysis.stats import load_results
    from dqk.ml.dataset import RUNS

    f = pd.read_parquet(p)
    st = load_results(RUNS / "main").runs
    m = f[f["grid"] == "main"].merge(st, on=["cell_id", "seed"], suffixes=("", "_st"))
    assert len(m) == 13000
    assert (m["detected"] == m["detected_st"]).all()
    assert (m["material"] == m["material_0_01"]).all()
    assert (m["n_worsened"] == m["n_worsened_st"]).all()
    assert np.allclose(m["dq_drop"], m["dq_drop_st"])
