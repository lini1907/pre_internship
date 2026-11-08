"""Error injectors E1-E6 (code plan 4.8): only logged units change, untouched rows stay
identical, the new values have the intended kind of error, and the clean mart is never
modified."""

from dataclasses import fields

import pandas as pd
import pytest

from dqk.dq import run_dq_checks, worsened
from dqk.inject import INJECTORS, inject_errors, unit_table
from dqk.inject._common import item_key
from dqk.inject.sampling import n_to_select
from dqk.inject.spec import ErrorSpec
from dqk.kpis import compute_kpis

ALL_VARIANTS = [(code, v) for code, mod in INJECTORS.items() for v in mod.VARIANTS]


def _snapshot(mart):
    return {f.name: getattr(mart, f.name).copy(deep=True) for f in fields(mart)}


def _inject(mart, code, variant, rate=0.1, seed=1):
    return inject_errors(mart, ErrorSpec(code, variant, "MCAR", rate), seed)


@pytest.mark.parametrize("code,variant", ALL_VARIANTS)
def test_clean_mart_untouched_and_count_exact(synth_mart, code, variant):
    before = _snapshot(synth_mart)
    _, log = _inject(synth_mart, code, variant)
    for name, df in before.items():
        pd.testing.assert_frame_equal(getattr(synth_mart, name), df)
    assert log.n_selected == n_to_select(0.1, log.n_units) > 0
    assert log.n_units == len(unit_table(synth_mart, code, variant))


@pytest.mark.parametrize("code,variant", ALL_VARIANTS)
def test_rate_zero_changes_nothing(synth_mart, code, variant):
    out, log = _inject(synth_mart, code, variant, rate=0.0)
    assert log.n_selected == 0
    clean = compute_kpis(synth_mart)
    pd.testing.assert_frame_equal(compute_kpis(out), clean)


def _assert_only_rows_changed(clean: pd.DataFrame, corr: pd.DataFrame, changed_mask, cols):
    assert len(clean) == len(corr)
    keep = ~changed_mask
    pd.testing.assert_frame_equal(clean[keep], corr[keep])
    diff = (clean.loc[changed_mask, cols] != corr.loc[changed_mask, cols]) & ~(
        clean.loc[changed_mask, cols].isna() & corr.loc[changed_mask, cols].isna()
    )
    assert diff.any(axis=1).all(), "every selected row must really change"


@pytest.mark.parametrize("variant", ["duplicate_order", "duplicate_order_rekeyed"])
def test_e1(synth_mart, variant):
    out, log = _inject(synth_mart, "E1", variant)
    o0, o1 = synth_mart.fact_orders, out.fact_orders
    i0, i1 = synth_mart.fact_order_items, out.fact_order_items
    pd.testing.assert_frame_equal(o1.iloc[: len(o0)], o0)
    pd.testing.assert_frame_equal(i1.iloc[: len(i0)], i0)
    assert len(o1) - len(o0) == log.n_selected
    assert len(i1) - len(i0) == i0["order_id"].isin(log.selected_ids).sum()
    dq0 = run_dq_checks(synth_mart.as_tables(), "mart")
    dq1 = run_dq_checks(out.as_tables(), "mart")
    c05 = dq1.set_index("check_id").loc["C05", "status"]
    if variant == "duplicate_order":
        assert c05 == "fail"
        assert set(o1["order_id"].iloc[len(o0) :]) == set(log.selected_ids)
    else:
        assert c05 == "pass"
        assert not set(o1["order_id"].iloc[len(o0) :]) & set(o0["order_id"])
    assert worsened(dq0, dq1).any() or variant == "duplicate_order_rekeyed"


@pytest.mark.parametrize(
    "variant,col,dim",
    [("orphan_product", "product_id", "dim_product"), ("orphan_seller", "seller_id", "dim_seller")],
)
def test_e2(synth_mart, variant, col, dim):
    out, log = _inject(synth_mart, "E2", variant)
    i0, i1 = synth_mart.fact_order_items, out.fact_order_items
    mask = item_key(i0).isin(log.selected_ids)
    _assert_only_rows_changed(i0, i1, mask, [col])
    assert not i1.loc[mask, col].isin(getattr(synth_mart, dim)[col]).any()
    assert i1.loc[mask, col].is_unique


@pytest.mark.parametrize(
    "variant,col",
    [("missing_delivery_date", "delivered_customer_ts"), ("missing_review_score", "review_score")],
)
def test_e3_orders(synth_mart, variant, col):
    out, log = _inject(synth_mart, "E3", variant)
    o0, o1 = synth_mart.fact_orders, out.fact_orders
    mask = o0["order_id"].isin(log.selected_ids)
    assert o0.loc[mask, col].notna().all()
    assert o1.loc[mask, col].isna().all()
    pd.testing.assert_frame_equal(o0[~mask], o1[~mask])
    pd.testing.assert_frame_equal(o0.drop(columns=col), o1.drop(columns=col))


def test_e3_category(synth_mart):
    out, log = _inject(synth_mart, "E3", "missing_category")
    p0, p1 = synth_mart.dim_product, out.dim_product
    mask = p0["product_id"].isin(log.selected_ids)
    assert p1.loc[mask, ["category_pt", "category_en"]].isna().all().all()
    pd.testing.assert_frame_equal(p0[~mask], p1[~mask])


def test_e4_tz_shift(synth_mart):
    out, log = _inject(synth_mart, "E4", "tz_shift_3h")
    o0, o1 = synth_mart.fact_orders, out.fact_orders
    mask = o0["order_id"].isin(log.selected_ids)
    pd.testing.assert_frame_equal(o0[~mask], o1[~mask])
    d = o1.loc[mask, "purchase_ts"] - o0.loc[mask, "purchase_ts"]
    assert (d == pd.Timedelta(hours=3)).all()
    assert (o1["estimated_delivery_date"] == o0["estimated_delivery_date"]).all()
    key = out.fact_order_items["order_id"].map(o1.set_index("order_id")["purchase_ts"])
    assert (
        key.dt.strftime("%Y%m%d").astype(int) == out.fact_order_items["purchase_date_key"]
    ).all()


def test_e4_day_month_swap(synth_mart):
    out, log = _inject(synth_mart, "E4", "day_month_swap")
    o0, o1 = synth_mart.fact_orders, out.fact_orders
    mask = o0["order_id"].isin(log.selected_ids)
    a, b = o0.loc[mask, "purchase_ts"], o1.loc[mask, "purchase_ts"]
    assert (a.dt.day == b.dt.month).all() and (a.dt.month == b.dt.day).all()
    assert (a.dt.time == b.dt.time).all() and (a != b).all()
    pd.testing.assert_frame_equal(o0[~mask], o1[~mask])


@pytest.mark.parametrize("variant,factor", [("price_x100", 100), ("price_div100", 0.01)])
def test_e5(synth_mart, variant, factor):
    out, log = _inject(synth_mart, "E5", variant)
    i0, i1 = synth_mart.fact_order_items, out.fact_order_items
    mask = item_key(i0).isin(log.selected_ids)
    _assert_only_rows_changed(i0, i1, mask, ["price"])
    assert (i1.loc[mask, "price"] - (i0.loc[mask, "price"] * factor).round(2)).abs().max() < 1e-9
    k0 = compute_kpis(synth_mart).set_index("kpi_id").loc["K1", "value"]
    k1 = compute_kpis(out).set_index("kpi_id").loc["K1", "value"]
    assert (k1 > k0) if factor > 1 else (k1 < k0)


def test_e6_reassign(synth_mart):
    out, log = _inject(synth_mart, "E6", "category_reassign")
    p0, p1 = synth_mart.dim_product, out.dim_product
    mask = p0["product_id"].isin(log.selected_ids)
    _assert_only_rows_changed(p0, p1, mask, ["category_en"])
    assert p1.loc[mask, "category_en"].isin(set(p0["category_en"])).all()
    pt = p0.drop_duplicates("category_en").set_index("category_en")["category_pt"]
    assert (
        p1.loc[mask, "category_pt"].to_numpy() == pt.reindex(p1.loc[mask, "category_en"]).to_numpy()
    ).all()


def test_e6_spelling(synth_mart):
    out, log = _inject(synth_mart, "E6", "category_spelling")
    p0, p1 = synth_mart.dim_product, out.dim_product
    mask = p0["product_id"].isin(log.selected_ids)
    _assert_only_rows_changed(p0, p1, mask, ["category_en"])
    norm = p1.loc[mask, "category_en"].str.strip().str.lower()
    assert (norm.to_numpy() == p0.loc[mask, "category_en"].to_numpy()).all()
    assert not p1.loc[mask, "category_en"].isin(set(p0["category_en"])).any()
