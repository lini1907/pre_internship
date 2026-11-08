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


CATEGORIES = ["bed_bath_table", "health_beauty", "sports_leisure", "toys", "auto", "books"]
STATES = ["SP", "RJ", "MG", "BA", "RS"]


def make_synth_mart(n_orders: int = 300, seed: int = 0) -> Mart:
    """A random but valid mart (window 2017-2018) for Stage B sampling / injection tests."""
    import numpy as np

    rng = np.random.default_rng(seed)
    n_cust, n_prod, n_sell = n_orders // 2, 40, 10
    cust = [f"c{j:04d}" for j in range(n_cust)]
    prod = [f"p{j:04d}" for j in range(n_prod)]
    sell = [f"s{j:03d}" for j in range(n_sell)]
    purchase = pd.Timestamp("2017-01-01") + pd.to_timedelta(
        rng.integers(0, 600 * 24 * 60, n_orders), unit="min"
    )
    delivered_days = rng.uniform(2, 30, n_orders)
    delivered = purchase + pd.to_timedelta(delivered_days, unit="D")
    estimated = (purchase + pd.to_timedelta(rng.uniform(5, 25, n_orders), unit="D")).normalize()
    status = np.where(rng.random(n_orders) < 0.9, "delivered", "shipped")
    delivered = pd.Series(delivered).where(status == "delivered")
    order_ids = [f"o{j:05d}" for j in range(n_orders)]
    score = pd.array(rng.integers(1, 6, n_orders), dtype="Int32")
    score[rng.random(n_orders) < 0.05] = pd.NA
    n_items = rng.integers(1, 4, n_orders)
    items = pd.DataFrame(
        {
            "order_id": np.repeat(order_ids, n_items),
            "order_item_id": np.concatenate([np.arange(1, k + 1) for k in n_items]).astype("int32"),
            "product_id": rng.choice(prod, n_items.sum()),
            "seller_id": rng.choice(sell, n_items.sum()),
            "price": np.round(np.exp(rng.normal(4, 1, n_items.sum())), 2),
            "freight_value": np.round(rng.uniform(5, 40, n_items.sum()), 2),
        }
    )
    pts = pd.Series(purchase, index=order_ids)
    items["purchase_date_key"] = (
        items["order_id"].map(pts).dt.strftime("%Y%m%d").astype("int32")
    )
    pay = items.assign(a=items.price + items.freight_value).groupby("order_id")["a"].sum()
    orders = pd.DataFrame(
        {
            "order_id": order_ids,
            "customer_unique_id": rng.choice(cust, n_orders),
            "status": status,
            "purchase_ts": purchase.astype("datetime64[us]"),
            "approved_ts": (purchase + pd.Timedelta(hours=1)).astype("datetime64[us]"),
            "delivered_carrier_ts": (purchase + pd.Timedelta(days=1)).astype("datetime64[us]"),
            "delivered_customer_ts": delivered.to_numpy().astype("datetime64[us]"),
            "estimated_delivery_date": estimated.astype("datetime64[us]"),
            "payment_total": pd.Series(order_ids).map(pay).round(2).to_numpy(),
            "review_id": [f"r{j:05d}" if s is not pd.NA else None for j, s in enumerate(score)],
            "review_score": score,
            "is_delivered": status == "delivered",
        }
    )
    cats = rng.choice(CATEGORIES, n_prod)
    return Mart(
        fact_orders=orders,
        fact_order_items=items,
        dim_customer=pd.DataFrame(
            {"customer_key": range(n_cust), "customer_unique_id": cust,
             "state": rng.choice(STATES, n_cust)}
        ),
        dim_product=pd.DataFrame(
            {"product_key": range(n_prod), "product_id": prod,
             "category_pt": [c + "_pt" for c in cats], "category_en": cats}
        ),
        dim_seller=pd.DataFrame(
            {"seller_key": range(n_sell), "seller_id": sell, "state": rng.choice(STATES, n_sell)}
        ),
        dim_date=pd.DataFrame(
            {"date_key": pd.Series(dtype="int32"), "date": pd.Series(dtype="datetime64[us]"),
             "year": pd.Series(dtype="int32"), "month": pd.Series(dtype="int32"),
             "year_month": pd.Series(dtype=str)}
        ),
    )


@pytest.fixture(scope="session")
def synth_mart() -> Mart:
    return make_synth_mart()
