"""Containers for the tables passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field, fields

import pandas as pd

# Column types of the mart (section 3.3 of the code plan). Used to build empty
# schemas for SQL compile tests and, in Stage A2, to check the mart output.
MART_SCHEMA: dict[str, dict[str, str]] = {
    "dim_customer": {
        "customer_key": "INTEGER",
        "customer_unique_id": "VARCHAR",
        "state": "VARCHAR",
    },
    "dim_product": {
        "product_key": "INTEGER",
        "product_id": "VARCHAR",
        "category_pt": "VARCHAR",
        "category_en": "VARCHAR",
    },
    "dim_seller": {
        "seller_key": "INTEGER",
        "seller_id": "VARCHAR",
        "state": "VARCHAR",
    },
    "dim_date": {
        "date_key": "INTEGER",
        "date": "DATE",
        "year": "INTEGER",
        "month": "INTEGER",
        "year_month": "VARCHAR",
    },
    "fact_order_items": {
        "order_id": "VARCHAR",
        "order_item_id": "INTEGER",
        "product_id": "VARCHAR",
        "seller_id": "VARCHAR",
        "price": "DECIMAL(12,2)",
        "freight_value": "DECIMAL(12,2)",
        "purchase_date_key": "INTEGER",
    },
    "fact_orders": {
        "order_id": "VARCHAR",
        "customer_unique_id": "VARCHAR",
        "status": "VARCHAR",
        "purchase_ts": "TIMESTAMP",
        "approved_ts": "TIMESTAMP",
        "delivered_carrier_ts": "TIMESTAMP",
        "delivered_customer_ts": "TIMESTAMP",
        "estimated_delivery_date": "DATE",
        "payment_total": "DECIMAL(12,2)",
        "review_score": "INTEGER",
        "is_delivered": "BOOLEAN",
    },
}


@dataclass
class Tables:
    """A named set of DataFrames, e.g. one layer (raw, staging) of the warehouse."""

    frames: dict[str, pd.DataFrame] = field(default_factory=dict)

    def __getitem__(self, name: str) -> pd.DataFrame:
        return self.frames[name]

    def __iter__(self):
        return iter(self.frames.items())

    def names(self) -> list[str]:
        return list(self.frames)


@dataclass
class Mart:
    """The star schema. Fact tables keep natural keys so orphan keys can be injected."""

    fact_orders: pd.DataFrame
    fact_order_items: pd.DataFrame
    dim_customer: pd.DataFrame
    dim_product: pd.DataFrame
    dim_seller: pd.DataFrame
    dim_date: pd.DataFrame

    def as_tables(self) -> Tables:
        return Tables({f.name: getattr(self, f.name) for f in fields(self)})
