"""E5 unit / scale errors on price. Unit: order item with price > 0.

price_x100    price * 100 (centavos loaded as reais)
price_div100  price / 100, rounded to 2 decimals (reais loaded as centavos)
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from dqk.inject._common import item_key, item_units
from dqk.tables import Mart

VARIANTS = ("price_x100", "price_div100")


def units(mart: Mart, variant: str) -> pd.DataFrame:
    return item_units(mart, mart.fact_order_items["price"] > 0)


def apply(mart: Mart, variant: str, ids, rng) -> Mart:
    i = mart.fact_order_items.copy()
    mask = item_key(i).isin(ids).to_numpy()
    factor = 100.0 if variant == "price_x100" else 0.01
    i.loc[mask, "price"] = (i.loc[mask, "price"] * factor).round(2)
    return replace(mart, fact_order_items=i)
