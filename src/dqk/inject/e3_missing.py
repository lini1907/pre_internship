"""E3 missing values. Unit: a row whose target column is not null.

missing_delivery_date  fact_orders.delivered_customer_ts -> NULL   (unit: order)
missing_review_score   fact_orders.review_score -> NULL            (unit: order)
missing_category       dim_product.category_pt/category_en -> NULL (unit: product)
missing_customer_id    fact_orders.customer_unique_id -> NULL      (unit: order; used on
                       Online Retail II, which has no delivery dates)
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from dqk.inject._common import order_units
from dqk.tables import Mart

VARIANTS = (
    "missing_delivery_date",
    "missing_review_score",
    "missing_category",
    "missing_customer_id",
)
_ORDER_COL = {
    "missing_delivery_date": "delivered_customer_ts",
    "missing_review_score": "review_score",
    "missing_customer_id": "customer_unique_id",
}


def units(mart: Mart, variant: str) -> pd.DataFrame:
    if variant in _ORDER_COL:
        return order_units(mart, mart.fact_orders[_ORDER_COL[variant]].notna())
    p = mart.dim_product[mart.dim_product["category_en"].notna()]
    return pd.DataFrame(
        {"unit_id": p["product_id"].to_numpy(), "category": p["category_en"].to_numpy()}
    )


def apply(mart: Mart, variant: str, ids, rng) -> Mart:
    if variant in _ORDER_COL:
        o = mart.fact_orders.copy()
        o.loc[o["order_id"].isin(ids), _ORDER_COL[variant]] = None
        return replace(mart, fact_orders=o)
    p = mart.dim_product.copy()
    mask = p["product_id"].isin(ids)
    p.loc[mask, ["category_pt", "category_en"]] = None
    return replace(mart, dim_product=p)
