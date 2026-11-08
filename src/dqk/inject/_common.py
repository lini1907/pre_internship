"""Helpers shared by the error injectors.

Every injector module exposes
    VARIANTS: tuple of variant names it handles
    units(mart, variant) -> DataFrame with a string ``unit_id`` column (one row per unit
        that the rate is measured on) plus the attributes MAR / MNAR may weight by
    apply(mart, variant, ids, rng) -> Mart with the units in ``ids`` corrupted
``apply`` must copy every table it changes and leave the clean mart untouched.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dqk.tables import Mart


def item_key(items: pd.DataFrame) -> pd.Series:
    """String key of an order item: '<order_id>|<order_item_id, 3 digits>'."""
    return items["order_id"] + "|" + items["order_item_id"].astype(str).str.zfill(3)


def new_hex_ids(rng: np.random.Generator, n: int, taken: set[str]) -> list[str]:
    """n distinct 32-hex ids (Olist format) that are not in ``taken``."""
    out: list[str] = []
    seen = set(taken)
    while len(out) < n:
        a = rng.integers(0, 2**63, size=n - len(out), dtype=np.int64)
        b = rng.integers(0, 2**63, size=n - len(out), dtype=np.int64)
        for x, y in zip(a, b, strict=True):
            s = f"{x:016x}{y:016x}"
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def customer_state(mart: Mart) -> pd.Series:
    """State per order_id (from dim_customer)."""
    m = mart.fact_orders[["order_id", "customer_unique_id"]].merge(
        mart.dim_customer[["customer_unique_id", "state"]], on="customer_unique_id", how="left"
    )
    return m.set_index("order_id")["state"]


def first_seller_state(mart: Mart) -> pd.Series:
    """State of the seller of the first item, per order_id (NaN for orders without items)."""
    i = mart.fact_order_items.sort_values(["order_id", "order_item_id"])
    i = i.drop_duplicates("order_id")[["order_id", "seller_id"]]
    m = i.merge(mart.dim_seller[["seller_id", "state"]], on="seller_id", how="left")
    return m.set_index("order_id")["state"]


def item_category(mart: Mart) -> pd.Series:
    """category_en per order item, aligned with fact_order_items' index."""
    m = mart.fact_order_items[["product_id"]].merge(
        mart.dim_product[["product_id", "category_en"]], on="product_id", how="left"
    )
    return pd.Series(m["category_en"].to_numpy(), index=mart.fact_order_items.index)


def order_units(mart: Mart, mask: pd.Series | None = None) -> pd.DataFrame:
    """Orders as units, with customer_state, seller_state and delivery_delay_days."""
    o = mart.fact_orders if mask is None else mart.fact_orders[mask]
    cs, ss = customer_state(mart), first_seller_state(mart)
    est = pd.to_datetime(o["estimated_delivery_date"])
    delay = (o["delivered_customer_ts"] - est).dt.total_seconds() / 86400
    return pd.DataFrame(
        {
            "unit_id": o["order_id"].to_numpy(),
            "customer_state": o["order_id"].map(cs).to_numpy(),
            "seller_state": o["order_id"].map(ss).to_numpy(),
            "delivery_delay_days": delay.to_numpy(),
            "review_score": o["review_score"].astype("Float64").to_numpy(),
        }
    )


def item_units(mart: Mart, mask: pd.Series | None = None) -> pd.DataFrame:
    i = mart.fact_order_items
    cat = item_category(mart)
    sel = slice(None) if mask is None else mask.to_numpy()
    seller_state = i["seller_id"].map(mart.dim_seller.set_index("seller_id")["state"])
    return pd.DataFrame(
        {
            "unit_id": item_key(i).to_numpy()[sel],
            "category": cat.to_numpy()[sel],
            "seller_state": seller_state.to_numpy()[sel],
            "price": i["price"].to_numpy()[sel],
        }
    )


def recompute_date_key(items: pd.DataFrame, orders: pd.DataFrame, order_ids) -> pd.DataFrame:
    """Refresh fact_order_items.purchase_date_key (YYYYMMDD) for the given orders."""
    ts = orders.set_index("order_id")["purchase_ts"]
    mask = items["order_id"].isin(order_ids)
    if mask.any():
        new = items.loc[mask, "order_id"].map(ts).dt.strftime("%Y%m%d").astype("int32")
        items.loc[mask, "purchase_date_key"] = new.to_numpy()
    return items
