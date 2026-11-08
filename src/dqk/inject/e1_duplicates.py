"""E1 duplicate records. Unit: order.

duplicate_order          re-insert the order and all its items with the same order_id
duplicate_order_rekeyed  same, but the copy gets a new order_id (a reload that mints new
                         keys); uniqueness checks cannot see it
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from dqk.inject._common import new_hex_ids, order_units
from dqk.tables import Mart

VARIANTS = ("duplicate_order", "duplicate_order_rekeyed")


def units(mart: Mart, variant: str) -> pd.DataFrame:
    return order_units(mart)


def apply(mart: Mart, variant: str, ids, rng) -> Mart:
    o, i = mart.fact_orders, mart.fact_order_items
    dup_o = o[o["order_id"].isin(ids)].copy()
    dup_i = i[i["order_id"].isin(ids)].copy()
    if variant == "duplicate_order_rekeyed":
        new = new_hex_ids(rng, len(dup_o), set(o["order_id"]))
        mapping = dict(zip(dup_o["order_id"], new, strict=True))
        dup_o["order_id"] = dup_o["order_id"].map(mapping)
        dup_i["order_id"] = dup_i["order_id"].map(mapping)
    return replace(
        mart,
        fact_orders=pd.concat([o, dup_o], ignore_index=True),
        fact_order_items=pd.concat([i, dup_i], ignore_index=True),
    )
