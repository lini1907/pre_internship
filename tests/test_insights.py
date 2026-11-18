"""Business analyses (code plan v1.1, P3/P4): hand-checked cases and consistency with
the frozen KPIs on a synthetic mart."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from dqk.config import load_kpi_spec
from dqk.insights import pareto_share, run_insights
from dqk.kpis import compute_kpis


@pytest.fixture(scope="module")
def synth():
    from conftest import make_synth_mart

    return (make_synth_mart(n_orders=2000, seed=5),)


@pytest.fixture(scope="module")
def results(synth):
    return run_insights(synth[0])


def kpi(m, kid):
    k = compute_kpis(m)
    return float(k.loc[k["kpi_id"] == kid, "value"].iloc[0])


def test_whatif_current_row_reproduces_k5_k7_k8(synth, results):
    m = synth[0]
    w = results["whatif_late"].set_index("scenario")
    assert w.loc["current", "on_time_share"] == pytest.approx(kpi(m, "K5"))
    assert w.loc["current", "avg_review_score"] == pytest.approx(kpi(m, "K7"))
    assert w.loc["current", "negative_share"] == pytest.approx(kpi(m, "K8"))
    assert w.loc["current", "moved_reviews"] == 0
    # fewer late orders move the score towards the on-time mean, monotone in the target
    s = w.loc[["current", "5 %", "3 %", "0 %"], "avg_review_score"]
    if w.loc["current", "late_share"] > 0.05:
        if w.loc["current", "mean_on_time"] > w.loc["current", "mean_late"]:
            assert s.is_monotonic_increasing
        else:
            assert s.is_monotonic_decreasing


def test_segments_repeat_share_is_k9(synth, results):
    seg = results["segments"]
    rate = (seg["repeat_share"] * seg["n_customers"]).sum() / seg["n_customers"].sum()
    assert rate == pytest.approx(kpi(synth[0], "K9"))
    assert seg["n_customers"].sum() == kpi(synth[0], "K10")


def test_pareto_total_is_k1_and_curve_ends_at_one(synth, results):
    p = results["pareto"]
    for _dim, g in p.groupby("dimension"):
        assert g["gmv"].sum() == pytest.approx(kpi(synth[0], "K1"))
        assert g["cum_share_gmv"].iloc[-1] == pytest.approx(1.0)
        assert g["cum_share_entities"].iloc[-1] == pytest.approx(1.0)
        assert g["gmv"].is_monotonic_decreasing


def test_pareto_share_by_hand():
    p = pd.DataFrame(
        {"dimension": "seller", "rank": [1, 2, 3, 4, 5], "gmv": [50.0, 20, 15, 10, 5]}
    )
    assert pareto_share(p, "seller", 0.2) == pytest.approx(0.5)  # 1 of 5
    assert pareto_share(p, "seller", 0.4) == pytest.approx(0.7)
    assert pareto_share(p, "seller", 0.01) == pytest.approx(0.5)  # at least one


def test_cohort_by_hand(synth):
    """Customer A: first order 2017-03-01, second 2017-03-20 (19 days) -> repeat at every
    horizon. Customer B: 2017-03-05 and 2017-08-01 (149 days) -> only 182 and 365."""
    m = synth[0]
    o = m.fact_orders.copy()
    i = m.fact_order_items.copy()
    extra = pd.DataFrame(
        {
            "order_id": ["xa1", "xa2", "xb1", "xb2"],
            "customer_unique_id": ["cA", "cA", "cB", "cB"],
            "purchase_ts": pd.to_datetime(
                ["2017-03-01", "2017-03-20", "2017-03-05", "2017-08-01"]
            ).astype("datetime64[us]"),
        }
    )
    tmpl = o.iloc[[0] * 4].reset_index(drop=True)
    for c in extra.columns:
        tmpl[c] = extra[c]
    tmpl["status"] = "delivered"
    tmpl["is_delivered"] = True
    # keep only the hand-built customers
    m2 = replace(m, fact_orders=tmpl, fact_order_items=i.iloc[0:0])
    c = run_insights(m2)["cohort"]
    c = c[c["cohort"] == "2017-03"].set_index("horizon_days")
    assert (c["n_customers"] == 2).all()
    assert c.loc[30, "n_repeat"] == 1
    assert c.loc[91, "n_repeat"] == 1
    assert c.loc[182, "n_repeat"] == 2
    assert c.loc[365, "n_repeat"] == 2
    assert not c["censored"].any()


def test_late_by_state_shares_sum_to_one(results):
    st = results["late_by_state"]
    assert st["share_of_late"].sum() == pytest.approx(1.0)
    assert st["share_of_delivered"].sum() == pytest.approx(1.0)
    assert st["on_time_rate"].is_monotonic_increasing
    assert np.isfinite(st["negative_share"]).all()


def test_spec_window_is_used(results):
    p = load_kpi_spec().params
    cohorts = results["cohort"]["cohort"]
    assert cohorts.min() >= str(p.window_start)[:7]
    assert cohorts.max() < str(p.window_end)[:7]
