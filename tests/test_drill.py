"""Incident drill (code plan v1.1, P1): scenarios touch exactly the units chosen by rule
and are deterministic."""

import pandas as pd
import pytest

from dqk.drill import (
    WEEK,
    corrupt,
    run_drill,
    summarise,
    target_category,
    target_seller,
    units_category_migration,
    units_double_load,
    units_price_in_cents,
)


@pytest.fixture(scope="module")
def mart():
    from conftest import make_synth_mart

    return make_synth_mart(n_orders=3000, seed=7)


def test_double_load_duplicates_one_week(mart):
    ids = units_double_load(mart)
    o = mart.fact_orders
    in_week = ((o["purchase_ts"] >= WEEK[0]) & (o["purchase_ts"] < WEEK[1])).sum()
    assert len(ids) == in_week > 0
    m, n, _ = corrupt(mart, "double_load")
    assert n == in_week
    assert len(m.fact_orders) == len(o) + in_week
    n_items = mart.fact_order_items["order_id"].isin(ids).sum()
    assert len(m.fact_order_items) == len(mart.fact_order_items) + n_items


def test_price_in_cents_hits_one_seller(mart):
    seller = target_seller(mart)
    m, n, _ = corrupt(mart, "price_in_cents")
    i0, i1 = mart.fact_order_items, m.fact_order_items
    hit = i0["seller_id"] == seller
    assert n == hit.sum() == len(units_price_in_cents(mart))
    assert (i1.loc[hit, "price"] == (i0.loc[hit, "price"] * 100).round(2)).all()
    assert (i1.loc[~hit, "price"] == i0.loc[~hit, "price"]).all()


def test_category_migration_moves_3pct_of_largest_category(mart):
    cat = target_category(mart)
    ids = units_category_migration(mart)
    n_cat = (mart.dim_product["category_en"] == cat).sum()
    assert len(ids) == round(0.03 * n_cat)
    m, _, _ = corrupt(mart, "category_migration")
    p0 = mart.dim_product.set_index("product_id")["category_en"]
    p1 = m.dim_product.set_index("product_id")["category_en"]
    changed = p0.index[p0 != p1]
    assert set(changed) == set(ids)


def test_drill_is_deterministic(mart):
    a = summarise(run_drill(mart), None)
    b = summarise(run_drill(mart), None)
    pd.testing.assert_frame_equal(a[0], b[0])
    pd.testing.assert_frame_equal(a[1], b[1])
    s = a[0].set_index("scenario")
    assert s.loc["double_load", "detected_core"]  # C05 / C06 react to duplicate keys
    assert "C22" in s.loc["category_migration", "extended_checks_reacting"] or len(
        units_category_migration(mart)
    ) == 0
