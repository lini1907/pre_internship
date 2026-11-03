"""Pipeline stages. Stage A1 covers the raw layer; staging and mart follow in A2."""

from __future__ import annotations

from pathlib import Path

import duckdb

from dqk.io import OLIST_DIR, OLIST_FILES
from dqk.tables import Tables


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


def write_raw(raw: Tables, con: duckdb.DuckDBPyConnection) -> None:
    """Persist the raw layer into schema ``raw`` of the warehouse."""
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for name, df in raw:
        con.register("_tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE raw.{name} AS SELECT * FROM _tmp")
        con.unregister("_tmp")
