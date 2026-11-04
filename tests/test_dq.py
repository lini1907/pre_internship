"""Each mart check: n_failed = 0 on a clean hand-built mart, and exactly n on a copy with n
planted errors (code plan 3.9)."""

import copy

import duckdb
import pandas as pd
import pytest

from dqk.db import read_sql, run_sql
from dqk.dq import (
    detected,
    dq_score,
    load_dq_config,
    render_sql,
    run_dq_checks,
    status_of,
    worsened,
)
from dqk.tables import MART_SCHEMA, Mart


def _ts(s):
    return pd.Timestamp(s) if s else pd.NaT


def make_clean_mart() -> Mart:
    orders = [
        # order, customer, status, purchase, delivered, estimated, review_id, score, payment
        ("O1", "A", "delivered", "2017-03-01 10:00", "2017-03-05", "2017-03-10", "R1", 5, 165.0),
        ("O2", "A", "delivered", "2017-04-01 09:00", "2017-04-11", "2017-04-08", "R2", 1, 220.0),
        ("O3", "B", "delivered", "2017-04-15 12:00", "2017-04-20", "2017-04-30", None, None, 33.0),
        ("O4", "C", "canceled", "2017-05-01 08:00", None, "2017-05-20", "R4", 2, 44.0),
    ]
    fact_orders = pd.DataFrame(
        {
            "order_id": [o[0] for o in orders],
            "customer_unique_id": [o[1] for o in orders],
            "status": [o[2] for o in orders],
            "purchase_ts": [_ts(o[3]) for o in orders],
            "approved_ts": [_ts(o[3]) + pd.Timedelta(hours=1) for o in orders],
            "delivered_carrier_ts": [_ts(o[3]) + pd.Timedelta(days=1) for o in orders],
            "delivered_customer_ts": [_ts(o[4]) for o in orders],
            "estimated_delivery_date": [_ts(o[5]) for o in orders],
            "payment_total": [o[8] for o in orders],
            "review_id": [o[6] for o in orders],
            "review_score": pd.array([o[7] for o in orders], dtype="Int64"),
            "is_delivered": [o[2] == "delivered" for o in orders],
        }
    )
    items = [
        ("O1", 1, "P1", "S1", 100.0, 10.0),
        ("O1", 2, "P2", "S2", 50.0, 5.0),
        ("O2", 1, "P1", "S1", 200.0, 20.0),
        ("O3", 1, "P2", "S1", 30.0, 3.0),
        ("O4", 1, "P2", "S2", 40.0, 4.0),
    ]
    fact_order_items = pd.DataFrame(items, columns=list(MART_SCHEMA["fact_order_items"])[:6])
    fact_order_items["purchase_date_key"] = 20170301
    return Mart(
        fact_orders=fact_orders,
        fact_order_items=fact_order_items,
        dim_customer=pd.DataFrame(
            {
                "customer_key": [1, 2, 3],
                "customer_unique_id": list("ABC"),
                "state": ["SP", "RJ", "MG"],
            }
        ),
        dim_product=pd.DataFrame(
            {
                "product_key": [1, 2],
                "product_id": ["P1", "P2"],
                "category_pt": ["brinquedos", "livros"],
                "category_en": ["toys", "books"],
            }
        ),
        dim_seller=pd.DataFrame(
            {"seller_key": [1, 2], "seller_id": ["S1", "S2"], "state": ["SP", "RJ"]}
        ),
        dim_date=pd.DataFrame(
            {
                "date_key": [20170301],
                "date": [_ts("2017-03-01")],
                "year": [2017],
                "month": [3],
                "year_month": ["2017-03"],
            }
        ),
    )


@pytest.fixture
def config():
    """The repo config with reference row counts set to the clean fixture."""
    cfg = load_dq_config()
    cfg.reference_rows["mart"] = {"orders": 4, "items": 5}
    return cfg


def _check(mart: Mart, config, check_id: str) -> pd.Series:
    r = run_dq_checks(mart.as_tables(), "mart", config)
    return r.set_index("check_id").loc[check_id]


def test_clean_fixture_passes_every_mart_check(config):
    r = run_dq_checks(make_clean_mart().as_tables(), "mart", config)
    mart_checks = [c.id for c in config.checks if "mart" in c.layers]
    assert list(r["check_id"]) == mart_checks
    assert (r["n_failed"] == 0).all(), r[r["n_failed"] > 0]
    assert (r["status"] == "pass").all()
    assert dq_score(r) == 1.0


def _set(df, row, col, value):
    df.loc[row, col] = value


# check id -> (function that plants errors in a deep copy of the mart, expected n_failed)
PLANTS = {
    "C01": (lambda m: _set(m.fact_order_items, [0, 2], "product_id", None), 2),
    "C02": (lambda m: _set(m.dim_product, 0, "category_en", None), 1),
    "C03": (lambda m: _set(m.fact_orders, 2, "delivered_customer_ts", pd.NaT), 1),
    "C04": (lambda m: _set(m.fact_orders, 0, "review_score", pd.NA), 1),
    "C05": (
        lambda m: setattr(m, "fact_orders", pd.concat([m.fact_orders, m.fact_orders.iloc[[1]]])),
        2,
    ),
    "C06": (
        lambda m: setattr(
            m, "fact_order_items", pd.concat([m.fact_order_items, m.fact_order_items.iloc[[3]]])
        ),
        2,
    ),
    "C07": (lambda m: _set(m.fact_orders, 1, "review_id", "R1"), 2),
    "C08": (lambda m: _set(m.fact_order_items, 1, "product_id", "PX"), 1),
    "C09": (lambda m: _set(m.fact_order_items, [1, 4], "seller_id", "SX"), 2),
    "C10": (lambda m: _set(m.fact_order_items, 4, "order_id", "OX"), 1),
    "C11": (lambda m: _set(m.fact_order_items, 2, "price", 0.0), 1),
    "C12": (lambda m: _set(m.fact_order_items, 2, "freight_value", -1.0), 1),
    "C13": (lambda m: _set(m.fact_orders, 3, "review_score", 7), 1),
    "C14": (lambda m: _set(m.dim_customer, 2, "state", "XX"), 1),
    "C15": (
        lambda m: _set(m.fact_orders, 0, "approved_ts", _ts("2017-03-01 09:00")),
        1,
    ),
    "C16": (
        lambda m: _set(m.fact_orders, 1, "delivered_customer_ts", _ts("2017-03-31")),
        1,
    ),
    "C17": (lambda m: _set(m.fact_orders, 3, "purchase_ts", _ts("2019-05-01")), 1),
    "C18": (lambda m: _set(m.fact_orders, 0, "payment_total", 170.0), 1),
    "C19": (lambda m: setattr(m, "fact_orders", m.fact_orders.iloc[:3]), 1),
    "C20": (
        lambda m: setattr(
            m, "fact_order_items", pd.concat([m.fact_order_items, m.fact_order_items.iloc[[0]]])
        ),
        1,
    ),
}


def test_every_check_has_a_planted_error_test(config):
    assert set(PLANTS) == {c.id for c in config.checks}


@pytest.mark.parametrize("check_id", sorted(PLANTS))
def test_planted_errors_are_counted_exactly(config, check_id):
    plant, expected = PLANTS[check_id]
    mart = copy.deepcopy(make_clean_mart())
    plant(mart)
    row = _check(mart, config, check_id)
    assert row.n_failed == expected
    assert row.status != "pass"


def test_status_thresholds():
    assert status_of(0.0, 0.0, 0.001) == "pass"
    assert status_of(0.0005, 0.0, 0.001) == "warn"
    assert status_of(0.001, 0.0, 0.001) == "warn"  # boundary belongs to the lower status
    assert status_of(0.0011, 0.0, 0.001) == "fail"
    assert status_of(0.019, 0.02, 0.05) == "pass"


def test_detection_is_relative_to_baseline():
    base = pd.DataFrame({"check_id": ["C01", "C03"], "layer": "mart", "status": ["pass", "warn"]})
    same = base.copy()
    assert not detected(base, same)
    still_warn = base.assign(status=["pass", "warn"])
    assert not detected(base, still_warn)
    to_fail = base.assign(status=["pass", "fail"])
    assert detected(base, to_fail)
    assert worsened(base, to_fail).tolist() == [False, True]
    better = base.assign(status=["pass", "pass"])
    assert not detected(base, better)


def test_render_sql_replaces_every_placeholder():
    sql = "SELECT * FROM {{orders}} JOIN {{items}} USING (order_id)"
    assert render_sql(sql, {"orders": "fact_orders", "items": "fact_order_items"}) == (
        "SELECT * FROM fact_orders JOIN fact_order_items USING (order_id)"
    )
    with pytest.raises(KeyError):
        render_sql(sql, {"orders": "fact_orders"})


def test_config_defaults_and_layers():
    cfg = load_dq_config()
    assert [c.id for c in cfg.checks] == [f"C{i:02d}" for i in range(1, 21)]
    c01 = next(c for c in cfg.checks if c.id == "C01")
    assert (c01.warn_share, c01.fail_share) == (0.0, 0.001)
    assert {c.dimension for c in cfg.checks if c.in_dq_score} == {
        "completeness",
        "uniqueness",
        "validity",
    }
    assert all("mart" in c.layers for c in cfg.checks), "Stage B detects on the mart"


def test_every_check_sql_compiles_on_typed_empty_mart():
    cfg = load_dq_config()
    con = duckdb.connect()
    for table, cols in MART_SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({', '.join(f'{c} {t}' for c, t in cols.items())})")
    for c in cfg.checks:
        sql = render_sql(read_sql(c.sql), cfg.layers["mart"])
        df = run_sql(con, sql, cfg.layer_params("mart"))
        assert list(df.columns) == ["n_failed", "n_total"], c.id
