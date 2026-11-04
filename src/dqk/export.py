"""Write mart tables, KPIs and DQ results to exports/ for the dashboard.

CSV for Looker Studio, Parquet for Power BI (code plan 3.7). docs/dashboard.md maps
every page of the dashboard to these files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from dqk import ROOT
from dqk.tables import Mart

EXPORT_DIR = ROOT / "exports"


def export_all(
    mart: Mart, kpis: pd.DataFrame, dq: pd.DataFrame, out: Path = EXPORT_DIR
) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    frames = dict(mart.as_tables()) | {"kpis_clean": kpis, "dq_results": dq}
    written = []
    for name, df in frames.items():
        df.to_parquet(out / f"{name}.parquet", index=False)
        df.to_csv(out / f"{name}.csv", index=False)
        written += [out / f"{name}.parquet", out / f"{name}.csv"]
    return written
