"""DuckDB helpers: register DataFrames as views and run SQL files with parameters."""

from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
import pandas as pd

from dqk import SQL_DIR
from dqk.tables import Tables

_PARAM = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def connect(tables: Tables | None = None, database: str = ":memory:") -> duckdb.DuckDBPyConnection:
    """Open a connection and expose each DataFrame as a view with the same name.

    DQK_DUCKDB_THREADS caps DuckDB's threads per connection. The parallel experiment runner
    sets it to 1 in each worker so N workers do not start N x n_cores threads."""
    config = {}
    if os.environ.get("DQK_DUCKDB_THREADS"):
        config = {"threads": int(os.environ["DQK_DUCKDB_THREADS"])}
    con = duckdb.connect(database, config=config)
    if config:
        con.execute("SET enable_progress_bar = false")
    if tables is not None:
        for name, df in tables:
            con.register(name, df)
    return con


def read_sql(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = SQL_DIR / p
    return p.read_text(encoding="utf-8")


def run_sql(con: duckdb.DuckDBPyConnection, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run a query, passing only the named ``$params`` that the query actually uses."""
    used = set(_PARAM.findall(sql))
    given = {k: v for k, v in (params or {}).items() if k in used}
    missing = used - given.keys()
    if missing:
        raise KeyError(f"SQL needs parameters not supplied: {sorted(missing)}")
    return con.execute(sql, given).df() if given else con.execute(sql).df()


def run_sql_file(
    con: duckdb.DuckDBPyConnection, path: str | Path, params: dict | None = None
) -> pd.DataFrame:
    return run_sql(con, read_sql(path), params)
