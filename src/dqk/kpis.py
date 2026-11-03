"""Compute every KPI of the spec on a mart, in long format."""

from __future__ import annotations

import pandas as pd

from dqk.config import KpiSpec, load_kpi_spec
from dqk.db import connect, run_sql_file
from dqk.tables import Mart


def compute_kpis(mart: Mart, spec: KpiSpec | None = None, use_alt: bool = False) -> pd.DataFrame:
    """Return columns kpi_id, item, value, rank; one row per KPI (scalar) or per item.

    With ``use_alt`` the alternative definitions are computed instead of the main ones
    for KPIs that have them (robustness, code plan 4.6).
    """
    spec = spec or load_kpi_spec()
    params = spec.params.model_dump()
    con = connect(mart.as_tables())
    parts = []
    for k in spec.kpis:
        defs = (
            [(a.id, a.sql) for a in k.alt_definitions]
            if use_alt and k.alt_definitions
            else [(k.id, k.sql)]
        )
        for kpi_id, sql in defs:
            df = run_sql_file(con, sql, params)
            df.insert(0, "kpi_id", kpi_id)
            parts.append(df)
    con.close()
    out = pd.concat(parts, ignore_index=True)
    out["rank"] = out["rank"].astype("Int64")
    return out
