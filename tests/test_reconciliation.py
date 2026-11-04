"""Acceptance criterion 5.6: five KPIs recomputed with independent SQL on the raw CSV files
match the pipeline. The raw queries cast and filter on their own and do not reuse any
staging or mart SQL."""

import duckdb
import pandas as pd
import pytest

from dqk.config import load_kpi_spec
from dqk.io import OLIST_DIR, OLIST_FILES
from dqk.kpis import compute_kpis
from dqk.pipeline import build_mart, load_raw

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not all((OLIST_DIR / f).exists() for f in OLIST_FILES.values()),
        reason="Olist data not downloaded (python run_pipeline.py)",
    ),
]

DELIVERED = """
    SELECT order_id, customer_id,
           CAST(order_purchase_timestamp AS TIMESTAMP) AS purchased,
           CAST(order_delivered_customer_date AS TIMESTAMP) AS delivered,
           CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated
    FROM orders
    WHERE order_status = 'delivered'
      AND CAST(order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '{start}'
      AND CAST(order_purchase_timestamp AS TIMESTAMP) <  TIMESTAMP '{end}'
"""

RAW_SQL = {
    "K1": """SELECT sum(CAST(i.price AS DOUBLE))
             FROM order_items i WHERE i.order_id IN (SELECT order_id FROM delivered)""",
    "K2": "SELECT count(*) FROM delivered",
    "K5": """SELECT count(*) FILTER (WHERE delivered::DATE <= estimated::DATE) / count(*)
             FROM delivered WHERE delivered IS NOT NULL""",
    # One review per order: the latest answer; among reviews answered at that same
    # moment, the smallest review_id.
    "K7": """
        WITH w AS (
            SELECT order_id FROM orders
            WHERE CAST(order_purchase_timestamp AS TIMESTAMP) >= TIMESTAMP '{start}'
              AND CAST(order_purchase_timestamp AS TIMESTAMP) <  TIMESTAMP '{end}'
        ),
        last_answer AS (
            SELECT order_id, max(CAST(review_answer_timestamp AS TIMESTAMP)) AS t
            FROM order_reviews GROUP BY 1
        ),
        chosen AS (
            SELECT r.order_id, min(r.review_id) AS review_id
            FROM order_reviews r JOIN last_answer a
              ON a.order_id = r.order_id AND CAST(r.review_answer_timestamp AS TIMESTAMP) = a.t
            GROUP BY 1
        )
        SELECT avg(CAST(r.review_score AS DOUBLE))
        FROM chosen c
        JOIN order_reviews r USING (order_id, review_id)
        WHERE c.order_id IN (SELECT order_id FROM w)""",
    "K10": """SELECT count(DISTINCT c.customer_unique_id)
              FROM delivered d JOIN customers c USING (customer_id)""",
}


@pytest.fixture(scope="module")
def raw():
    return load_raw()


@pytest.fixture(scope="module")
def pipeline_kpis(raw):
    return compute_kpis(build_mart(raw)).set_index("kpi_id")


@pytest.fixture(scope="module")
def con(raw):
    p = load_kpi_spec().params
    con = duckdb.connect()
    for name, df in raw:
        con.register(name, df)
    con.execute(
        "CREATE VIEW delivered AS " + DELIVERED.format(start=p.window_start, end=p.window_end)
    )
    return con


@pytest.mark.parametrize("kpi_id", list(RAW_SQL))
def test_kpi_matches_independent_raw_query(con, pipeline_kpis, kpi_id):
    p = load_kpi_spec().params
    expected = con.execute(RAW_SQL[kpi_id].format(start=p.window_start, end=p.window_end))
    expected = expected.fetchone()[0]
    got = pipeline_kpis.loc[kpi_id, "value"]
    assert got == pytest.approx(expected, rel=1e-9), f"{kpi_id}: pipeline {got} vs raw {expected}"


def test_build_is_deterministic(raw):
    """Two builds give the same rows in the same order: Stage B samples rows by position."""
    a, b = build_mart(raw), build_mart(raw)
    for (name, x), (_, y) in zip(a.as_tables(), b.as_tables(), strict=True):
        pd.testing.assert_frame_equal(x, y, obj=name)
