"""Pipeline stages: raw -> staging -> mart, each a set of DataFrames."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from dqk import CONFIG_DIR, SQL_DIR
from dqk.db import connect, read_sql
from dqk.io import OLIST_DIR, OLIST_FILES
from dqk.tables import MART_SCHEMA, Mart, Tables

TRANSLATION_EXTRA = CONFIG_DIR / "category_translation_extra.csv"

# Build order matters: dim_customer and dim_date read stg_orders, facts read several.
STAGING_TABLES = [
    "stg_orders",
    "stg_order_items",
    "stg_order_payments",
    "stg_order_reviews",
    "stg_customers",
    "stg_sellers",
    "stg_products",
]
MART_TABLES = list(MART_SCHEMA)


def load_raw(src: Path = OLIST_DIR) -> Tables:
    """Read every source CSV with all columns as VARCHAR, so raw keeps values as-is."""
    return Tables(
        {
            table: duckdb.sql(
                f"SELECT * FROM read_csv('{(src / fname).as_posix()}', all_varchar=true)"
            ).df()
            for table, fname in OLIST_FILES.items()
        }
    )


def load_translation_extra(path: Path = TRANSLATION_EXTRA) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def _build(con: duckdb.DuckDBPyConnection, names: list[str], folder: str) -> Tables:
    """Materialise sql/<folder>/<name>.sql as tables, in order, and return them."""
    for name in names:
        con.execute(
            f"CREATE OR REPLACE TABLE {name} AS {read_sql(SQL_DIR / folder / f'{name}.sql')}"
        )
    return Tables({name: con.execute(f"SELECT * FROM {name}").df() for name in names})


def build_staging(raw: Tables) -> Tables:
    con = connect(raw)
    con.register("category_translation_extra", load_translation_extra())
    staging = _build(con, STAGING_TABLES, "staging")
    con.close()
    return staging


def build_mart_from_staging(staging: Tables) -> Mart:
    con = connect(staging)
    mart = _build(con, MART_TABLES, "mart")
    con.close()
    for name, cols in MART_SCHEMA.items():
        if list(mart[name].columns) != list(cols):
            raise RuntimeError(f"{name}: columns {list(mart[name].columns)} != {list(cols)}")
    return Mart(**mart.frames)


def build_mart(raw: Tables) -> Mart:
    return build_mart_from_staging(build_staging(raw))


def write_schema(tables: Tables, schema: str, con: duckdb.DuckDBPyConnection) -> None:
    """Persist a layer into one schema of the warehouse."""
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    for name, df in tables:
        con.register("_tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE {schema}.{name} AS SELECT * FROM _tmp")
        con.unregister("_tmp")


def write_raw(raw: Tables, con: duckdb.DuckDBPyConnection) -> None:
    write_schema(raw, "raw", con)
