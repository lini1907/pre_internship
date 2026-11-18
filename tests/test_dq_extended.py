"""Extended checks C21-C24 (code plan v1.1, section 2.4)."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from dqk import RESULTS_DIR
from dqk.dq import load_dq_config, run_dq_checks
from dqk.experiment.runner import WAREHOUSE, load_clean_mart

EXT = ["C21", "C22", "C23", "C24"]


@pytest.fixture(scope="module")
def ext_config():
    return load_dq_config(suite="extended")


def _ext(mart, cfg, reference):
    r = run_dq_checks(mart.as_tables(), "mart", cfg, reference=reference.as_tables())
    return r.set_index("check_id").loc[EXT]


def test_suites_have_20_and_24_checks():
    core = load_dq_config()
    ext = load_dq_config(suite="extended")
    assert [c.id for c in core.checks] == [f"C{i:02d}" for i in range(1, 21)]
    assert [c.id for c in ext.checks] == [f"C{i:02d}" for i in range(1, 25)]
    assert not any(c.in_dq_score for c in ext.checks[20:])
    # the core part of the extended config is the core config
    assert ext.checks[:20] == core.checks
    with pytest.raises(ValueError):
        load_dq_config(suite="nope")


def test_clean_mart_against_itself_passes(synth_mart, ext_config):
    r = _ext(synth_mart, ext_config, synth_mart)
    assert (r["status"] == "pass").all(), r
    assert r.loc[["C21", "C22", "C23"], "n_failed"].eq(0).all()


def test_missing_reference_is_skipped(synth_mart, ext_config):
    r = run_dq_checks(synth_mart.as_tables(), "mart", ext_config).set_index("check_id")
    assert list(r.index[-4:]) == EXT
    assert r.loc["C21", "status"] == "pass"
    assert (r.loc[["C22", "C23", "C24"], "status"] == "skipped").all()
    assert r.loc[["C22", "C23", "C24"], "fail_share"].isna().all()


def test_core_suite_unchanged_by_reference(synth_mart):
    core = load_dq_config()
    a = run_dq_checks(synth_mart.as_tables(), "mart", core)
    b = run_dq_checks(synth_mart.as_tables(), "mart", core, reference=synth_mart.as_tables())
    pd.testing.assert_frame_equal(a, b)


def test_c21_counts_missing_customer_keys(synth_mart, ext_config):
    o = synth_mart.fact_orders.copy()
    o.loc[o.index[:7], "customer_unique_id"] = None
    r = _ext(replace(synth_mart, fact_orders=o), ext_config, synth_mart)
    assert r.loc["C21", "n_failed"] == 7
    assert r.loc["C21", "n_total"] == len(o)
    assert r.loc["C21", "status"] == "fail"


def test_c22_counts_changed_categories(synth_mart, ext_config):
    p = synth_mart.dim_product.copy()
    p.loc[0, "category_en"] = "something_else"
    p.loc[1, "category_en"] = p.loc[1, "category_en"].upper()  # spelling
    p.loc[2, "category_en"] = None  # NULL vs value counts too
    r = _ext(replace(synth_mart, dim_product=p), ext_config, synth_mart)
    assert r.loc["C22", "n_failed"] == 3
    assert r.loc["C22", "n_total"] == len(p)


def test_c23_flags_a_shifted_category(ext_config):
    from conftest import make_synth_mart

    m = make_synth_mart(n_orders=3000, seed=1)
    p = m.dim_product.copy()
    big = m.fact_order_items.merge(p, on="product_id")["category_en"].value_counts().index[0]
    # move every product of the largest category into a brand new one
    p.loc[p["category_en"] == big, "category_en"] = "new_category"
    r = _ext(replace(m, dim_product=p), ext_config, m)
    # two categories drift (the emptied one and the new one), out of n + 1 in the union
    n_cat = m.dim_product["category_en"].nunique()
    assert r.loc["C23", "n_failed"] == 2
    assert r.loc["C23", "n_total"] == n_cat + 1


def test_c23_ignores_a_proportional_sample(ext_config):
    from conftest import make_synth_mart

    m = make_synth_mart(n_orders=3000, seed=2)
    keep = m.fact_orders["order_id"].iloc[::2]
    half = replace(
        m,
        fact_orders=m.fact_orders[m.fact_orders["order_id"].isin(keep)],
        fact_order_items=m.fact_order_items[m.fact_order_items["order_id"].isin(keep)],
    )
    assert _ext(half, ext_config, m).loc["C23", "n_failed"] == 0


def test_c24_counts_prices_off_by_100(synth_mart, ext_config):
    i = synth_mart.fact_order_items.copy()
    base = _ext(synth_mart, ext_config, synth_mart).loc["C24", "n_failed"]
    rng = np.random.default_rng(0)
    rows = rng.choice(i.index, 20, replace=False)
    i.loc[rows, "price"] = i.loc[rows, "price"] * 100
    r = _ext(replace(synth_mart, fact_order_items=i), ext_config, synth_mart)
    assert r.loc["C24", "n_failed"] >= base + 18  # x100 = +4.6 in log; a few were already out
    assert r.loc["C24", "n_total"] == (i["price"] > 0).sum()


def test_c24_hand_computed():
    """Global fallback (categories under price_min_items): median and MAD by hand."""
    from conftest import make_synth_mart

    m = make_synth_mart(n_orders=20, seed=3)
    cfg = load_dq_config(suite="extended")
    lp = np.log(m.fact_order_items["price"].astype(float))
    med = np.median(lp)
    mad = np.median(np.abs(lp - med))
    expected = int((np.abs(lp - med) > cfg.params.price_k * mad).sum())
    cats = m.fact_order_items.merge(m.dim_product, on="product_id")["category_en"]
    assert cats.value_counts().max() < cfg.params.price_min_items  # all use global stats
    assert _ext(m, cfg, m).loc["C24", "n_failed"] == expected


@pytest.mark.slow
@pytest.mark.skipif(not WAREHOUSE.exists(), reason="needs warehouse/olist.duckdb")
def test_core_suite_matches_stage_a_on_real_mart():
    csv = RESULTS_DIR / "stage_a" / "dq_results.csv"
    base = pd.read_csv(csv)
    base = base[base["layer"] == "mart"].reset_index(drop=True)
    mart = load_clean_mart()
    for suite in ("core", "extended"):
        cfg = load_dq_config(suite=suite)
        r = run_dq_checks(mart.as_tables(), "mart", cfg, reference=mart.as_tables())
        r = r.iloc[:20].reset_index(drop=True)
        assert list(r["check_id"]) == list(base["check_id"])
        assert (r["n_failed"].to_numpy() == base["n_failed"].to_numpy()).all()
        assert (r["status"].to_numpy() == base["status"].to_numpy()).all()



def test_retail_extended_config():
    from dqk.retail.adapter import retail_dq_config

    core = retail_dq_config()
    ext = retail_dq_config(suite="extended")
    assert len(core.checks) == 10
    assert [c.id for c in ext.checks] == [c.id for c in core.checks] + ["C21", "C24"]
    c24 = ext.checks[-1]
    assert (c24.warn_share, c24.fail_share) == (0.0268, 0.0535)
    # the Olist C24 thresholds are untouched
    olist_c24 = load_dq_config(suite="extended").checks[-1]
    assert (olist_c24.warn_share, olist_c24.fail_share) == (0.0192, 0.0383)


def test_reference_snapshot_roundtrip(synth_mart, ext_config, tmp_path):
    from dqk.pipeline import load_reference, save_reference

    assert load_reference(tmp_path) is None
    save_reference(synth_mart, tmp_path)
    ref = load_reference(tmp_path)
    assert ref.names() == ["dim_product", "fact_order_items"]
    r = run_dq_checks(synth_mart.as_tables(), "mart", ext_config, reference=ref)
    assert (r.set_index("check_id").loc[EXT, "status"] == "pass").all()
