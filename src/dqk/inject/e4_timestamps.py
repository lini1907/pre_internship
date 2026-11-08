"""E4 timestamp errors. Unit: order.

tz_shift_3h     every timestamp of the order is +3 h (the source wrote UTC, the warehouse
                assumes Brasilia time, UTC-3). estimated_delivery_date is a date and stays.
day_month_swap  purchase_ts has day and month swapped (dd/mm read as mm/dd). Units are only
                orders whose purchase day is <= 12 and differs from the month, so every
                selected order really changes.
fact_order_items.purchase_date_key follows the new purchase_ts.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from dqk.inject._common import order_units, recompute_date_key
from dqk.tables import Mart

VARIANTS = ("tz_shift_3h", "day_month_swap")
TS_COLS = ["purchase_ts", "approved_ts", "delivered_carrier_ts", "delivered_customer_ts"]


def units(mart: Mart, variant: str) -> pd.DataFrame:
    ts = mart.fact_orders["purchase_ts"]
    if variant == "tz_shift_3h":
        return order_units(mart, ts.notna())
    return order_units(mart, ts.notna() & (ts.dt.day <= 12) & (ts.dt.day != ts.dt.month))


def apply(mart: Mart, variant: str, ids, rng) -> Mart:
    o = mart.fact_orders.copy()
    mask = o["order_id"].isin(ids)
    if variant == "tz_shift_3h":
        for c in TS_COLS:
            o.loc[mask, c] = o.loc[mask, c] + pd.Timedelta(hours=3)
    else:
        ts = o.loc[mask, "purchase_ts"]
        swapped = pd.to_datetime(
            pd.DataFrame({"year": ts.dt.year, "month": ts.dt.day, "day": ts.dt.month})
        ) + (ts - ts.dt.normalize())
        o.loc[mask, "purchase_ts"] = swapped.astype(o["purchase_ts"].dtype)
    i = recompute_date_key(mart.fact_order_items.copy(), o, ids)
    return replace(mart, fact_orders=o, fact_order_items=i)
