"""E2 orphan foreign keys. Unit: order item.

orphan_product  product_id replaced by a fresh id that is not in dim_product
orphan_seller   seller_id replaced by a fresh id that is not in dim_seller
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from dqk.inject._common import item_key, item_units, new_hex_ids
from dqk.tables import Mart

VARIANTS = ("orphan_product", "orphan_seller")
_TARGET = {
    "orphan_product": ("product_id", "dim_product"),
    "orphan_seller": ("seller_id", "dim_seller"),
}


def units(mart: Mart, variant: str) -> pd.DataFrame:
    return item_units(mart)


def apply(mart: Mart, variant: str, ids, rng) -> Mart:
    col, dim = _TARGET[variant]
    i = mart.fact_order_items.copy()
    mask = item_key(i).isin(ids).to_numpy()
    taken = set(getattr(mart, dim)[col]) | set(i[col])
    i.loc[mask, col] = new_hex_ids(rng, int(mask.sum()), taken)
    return replace(mart, fact_order_items=i)
