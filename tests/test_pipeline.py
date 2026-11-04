"""Staging and mart rules on a tiny raw layer (all VARCHAR, as read from the CSV files)."""

import pandas as pd
import pytest

from dqk.dq import run_dq_checks
from dqk.pipeline import STAGING_TABLES, build_mart_from_staging, build_staging
from dqk.tables import MART_SCHEMA, Tables


def _df(cols, rows):
    return pd.DataFrame([dict(zip(cols.split(), r, strict=True)) for r in rows], dtype=object)


@pytest.fixture
def raw() -> Tables:
    return Tables(
        {
            "orders": _df(
                "order_id customer_id order_status order_purchase_timestamp order_approved_at "
                "order_delivered_carrier_date order_delivered_customer_date "
                "order_estimated_delivery_date",
                [
                    (
                        "O1",
                        "c1",
                        "delivered",
                        "2017-03-01 10:00:00",
                        "2017-03-01 11:00:00",
                        "2017-03-02 08:00:00",
                        "2017-03-05 12:00:00",
                        "2017-03-10 00:00:00",
                    ),
                    (
                        "O2",
                        "c2",
                        " Delivered ",
                        "2017-04-01 09:00:00",
                        "2017-04-01 10:00:00",
                        "2017-04-02 09:00:00",
                        "2017-04-11 09:00:00",
                        "2017-04-08 00:00:00",
                    ),
                    (
                        "O3",
                        "c3",
                        "canceled",
                        "2017-05-01 08:00:00",
                        None,
                        None,
                        None,
                        "2017-05-20 00:00:00",
                    ),
                ],
            ),
            "order_items": _df(
                "order_id order_item_id product_id seller_id shipping_limit_date price "
                "freight_value",
                [
                    ("O1", "1", "P1", "S1", "2017-03-03 00:00:00", "100.00", "10.00"),
                    ("O1", "2", "P2", "S2", "2017-03-03 00:00:00", "50.50", "5.00"),
                    ("O2", "1", "P3", "S1", "2017-04-03 00:00:00", "200.00", "20.00"),
                ],
            ),
            "order_payments": _df(
                "order_id payment_sequential payment_type payment_installments payment_value",
                [
                    ("O1", "1", "credit_card", "2", "100.00"),
                    ("O1", "2", "voucher", "1", "65.50"),
                    ("O2", "1", "boleto", "1", "220.00"),
                ],
            ),
            "order_reviews": _df(
                "review_id order_id review_score review_comment_title review_comment_message "
                "review_creation_date review_answer_timestamp",
                [
                    ("R1", "O1", "3", None, None, "2017-03-06 00:00:00", "2017-03-07 00:00:00"),
                    ("R1b", "O1", "5", None, None, "2017-03-08 00:00:00", "2017-03-09 00:00:00"),
                    ("R2", "O2", "1", None, None, "2017-04-12 00:00:00", "2017-04-13 00:00:00"),
                ],
            ),
            "customers": _df(
                "customer_id customer_unique_id customer_zip_code_prefix customer_city "
                "customer_state",
                [
                    ("c1", "A", "01000", "Sao Paulo", "sp"),
                    ("c2", "A", "20000", "Rio", "RJ "),
                    ("c3", "B", "30000", "BH", "MG"),
                ],
            ),
            "sellers": _df(
                "seller_id seller_zip_code_prefix seller_city seller_state",
                [("S1", "01000", "sao paulo", "SP"), ("S2", "80000", "curitiba", "PR")],
            ),
            "products": _df(
                "product_id product_category_name product_name_lenght "
                "product_description_lenght product_photos_qty product_weight_g "
                "product_length_cm product_height_cm product_width_cm",
                [
                    ("P1", "brinquedos", "40", "300", "1", "500", "10", "10", "10"),
                    ("P2", "pc_gamer", "35", "200", "2", "900", "20", "5", "15"),
                    ("P3", None, None, None, None, "100", "5", "5", "5"),
                ],
            ),
            "product_category_name_translation": _df(
                "product_category_name product_category_name_english", [("brinquedos", "toys")]
            ),
        }
    )


@pytest.fixture
def staging(raw):
    return build_staging(raw)


def test_staging_tables_and_casts(staging):
    assert staging.names() == STAGING_TABLES
    o = staging["stg_orders"].set_index("order_id")
    assert o.loc["O2", "status"] == "delivered"  # trimmed and lower-cased
    assert o.loc["O1", "purchase_ts"] == pd.Timestamp("2017-03-01 10:00")
    assert pd.isna(o.loc["O3", "approved_ts"])
    assert staging["stg_order_items"]["price"].tolist() == [100.0, 50.5, 200.0]
    assert "product_name_length" in staging["stg_products"].columns  # source typo fixed


def test_one_review_per_order_latest_answer(staging):
    r = staging["stg_order_reviews"].set_index("order_id")
    assert len(r) == 2
    assert r.loc["O1", "review_id"] == "R1b"
    assert r.loc["O1", "review_score"] == 5


def test_category_translation_with_extra_seed(staging):
    p = staging["stg_products"].set_index("product_id")["category_en"]
    assert p["P1"] == "toys"
    assert p["P2"] == "pc_gamer"  # from config/category_translation_extra.csv
    assert pd.isna(p["P3"])  # missing category stays NULL; KPIs label it unknown


def test_mart(staging):
    m = build_mart_from_staging(staging)
    for name, cols in MART_SCHEMA.items():
        assert list(getattr(m, name).columns) == list(cols)
    fo = m.fact_orders.set_index("order_id")
    assert fo.loc["O1", "customer_unique_id"] == "A"
    assert fo.loc["O1", "payment_total"] == pytest.approx(165.5)
    assert pd.isna(fo.loc["O3", "payment_total"])
    assert fo["is_delivered"].tolist() == [True, True, False]
    assert fo.loc["O1", "review_score"] == 5
    # A ordered from SP (O1) then RJ (O2): the latest order's state wins.
    c = m.dim_customer.set_index("customer_unique_id")["state"]
    assert c.to_dict() == {"A": "RJ", "B": "MG"}
    assert m.fact_order_items["purchase_date_key"].tolist() == [20170301, 20170301, 20170401]
    d = m.dim_date
    assert d["date_key"].iloc[0] == 20170301 and d["date_key"].iloc[-1] == 20170501
    assert len(d) == 62  # 2017-03-01 .. 2017-05-01


def test_dq_runs_on_every_layer(raw, staging):
    m = build_mart_from_staging(staging)
    for layer, tables in [("raw", raw), ("staging", staging), ("mart", m.as_tables())]:
        r = run_dq_checks(tables, layer)
        assert len(r) and (r["n_total"] >= 0).all(), layer
    # O2 pays 220 for 220 of goods; O1 pays 165.5 for 165.5. Nothing to reconcile.
    r = run_dq_checks(m.as_tables(), "mart").set_index("check_id")
    assert r.loc["C18", "n_failed"] == 0
    assert r.loc["C02", "n_failed"] == 1  # P3
