"""A hand-built mart of five orders. Expected KPI values are worked out in test_kpis.py."""

import pandas as pd
import pytest

from dqk.tables import Mart


def _ts(s):
    return pd.Timestamp(s) if s else pd.NaT


@pytest.fixture
def mini_mart() -> Mart:
    orders = [
        # order, customer, status, purchase, delivered, estimated, review
        ("O1", "A", "delivered", "2017-03-01", "2017-03-05", "2017-03-10", 5),
        ("O2", "A", "delivered", "2017-04-01", "2017-04-11", "2017-04-08", 1),
        ("O3", "B", "delivered", "2017-04-15", None, "2017-04-30", 4),
        ("O4", "C", "canceled", "2017-05-01", None, "2017-05-20", 2),
        ("O5", "D", "delivered", "2016-10-01", "2016-10-03", "2016-10-10", 3),  # outside window
    ]
    fact_orders = pd.DataFrame(
        {
            "order_id": [o[0] for o in orders],
            "customer_unique_id": [o[1] for o in orders],
            "status": [o[2] for o in orders],
            "purchase_ts": [_ts(o[3]) for o in orders],
            "approved_ts": [_ts(o[3]) for o in orders],
            "delivered_carrier_ts": pd.NaT,
            "delivered_customer_ts": [_ts(o[4]) for o in orders],
            "estimated_delivery_date": [pd.Timestamp(o[5]).date() for o in orders],
            "payment_total": 0.0,
            "review_score": pd.array([o[6] for o in orders], dtype="Int64"),
            "is_delivered": [o[2] == "delivered" for o in orders],
        }
    )
    items = [
        ("O1", 1, "P1", "S1", 100.0, 10.0),
        ("O1", 2, "P2", "S2", 50.0, 5.0),
        ("O2", 1, "P1", "S1", 200.0, 20.0),
        ("O3", 1, "PX", "S1", 30.0, 3.0),  # PX is an orphan product
        ("O4", 1, "P2", "S2", 40.0, 4.0),
        ("O5", 1, "P1", "S1", 999.0, 9.0),
    ]
    fact_order_items = pd.DataFrame(
        items,
        columns=["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
    )
    fact_order_items["purchase_date_key"] = 0
    return Mart(
        fact_orders=fact_orders,
        fact_order_items=fact_order_items,
        dim_customer=pd.DataFrame(
            {
                "customer_key": [1, 2, 3, 4],
                "customer_unique_id": list("ABCD"),
                "state": ["SP", "RJ", "MG", "SP"],
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
            {"date_key": [], "date": [], "year": [], "month": [], "year_month": []}
        ),
    )
