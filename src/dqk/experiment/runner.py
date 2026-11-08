"""Run the experiment: one run, one cell, many cells in parallel with resume (code plan 4.3).

Per cell three Parquet files are written to results/runs/<grid>/:
  <cell_id>.kpi.parquet   run x KPI   (kpi_measures + seed)
  <cell_id>.dq.parquet    run x check (dq_measures + seed)
  <cell_id>.runs.parquet  run         (injection log summary, run_summary, timing)
The .runs file is written last, so its presence marks a finished cell (--resume).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from dqk import ROOT
from dqk.config import KpiSpec, load_kpi_spec
from dqk.dq import DqConfig, load_dq_config, run_dq_checks
from dqk.experiment.grid import Cell
from dqk.experiment.measures import dq_measures, kpi_measures, run_summary
from dqk.inject import inject_errors, unit_table
from dqk.kpis import compute_kpis
from dqk.tables import MART_SCHEMA, Mart

WAREHOUSE = ROOT / "warehouse" / "olist.duckdb"


@dataclass
class Baseline:
    """The clean mart and everything measured on it, computed once per worker."""

    mart: Mart
    kpis: pd.DataFrame
    dq: pd.DataFrame
    kpi_spec: KpiSpec
    dq_config: DqConfig


def load_clean_mart(path: Path = WAREHOUSE) -> Mart:
    con = duckdb.connect(str(path), read_only=True)
    mart = Mart(**{n: con.sql(f"SELECT * FROM mart.{n}").df() for n in MART_SCHEMA})
    con.close()
    return mart


def make_baseline(mart: Mart | None = None) -> Baseline:
    mart = mart if mart is not None else load_clean_mart()
    spec, cfg = load_kpi_spec(), load_dq_config()
    return Baseline(
        mart=mart,
        kpis=compute_kpis(mart, spec),
        dq=run_dq_checks(mart.as_tables(), "mart", cfg),
        kpi_spec=spec,
        dq_config=cfg,
    )


def run_once(
    base: Baseline, cell: Cell, seed: int, units=None
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    t0 = time.perf_counter()
    corrupted, log = inject_errors(base.mart, cell.spec, seed, units)
    t1 = time.perf_counter()
    kpis = compute_kpis(corrupted, base.kpi_spec)
    dq = run_dq_checks(corrupted.as_tables(), "mart", base.dq_config)
    t2 = time.perf_counter()
    km = kpi_measures(base.kpis, kpis, base.kpi_spec)
    dm = dq_measures(base.dq, dq)
    run = {
        "cell_id": cell.cell_id,
        "code": log.code,
        "variant": log.variant,
        "mechanism": log.mechanism,
        "rate": log.rate,
        "seed": seed,
        "n_units": log.n_units,
        "n_selected": log.n_selected,
        "achieved_rate": log.achieved_rate,
        **run_summary(km, dm, base.dq),
        "t_inject": t1 - t0,
        "t_measure": t2 - t1,
        "t_total": time.perf_counter() - t0,
    }
    for df in (km, dm):
        df.insert(0, "seed", seed)
        df.insert(0, "cell_id", cell.cell_id)
    return km, dm, run


def cell_paths(out_dir: Path, cell: Cell) -> dict[str, Path]:
    return {k: out_dir / f"{cell.cell_id}.{k}.parquet" for k in ("kpi", "dq", "runs")}


def run_cell(base: Baseline, cell: Cell, seeds, out_dir: Path) -> pd.DataFrame:
    units = unit_table(base.mart, cell.spec.code, cell.spec.variant)
    kms, dms, runs = [], [], []
    for seed in seeds:
        km, dm, run = run_once(base, cell, seed, units)
        kms.append(km)
        dms.append(dm)
        runs.append(run)
    paths = cell_paths(out_dir, cell)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(kms, ignore_index=True).to_parquet(paths["kpi"], index=False)
    pd.concat(dms, ignore_index=True).to_parquet(paths["dq"], index=False)
    runs_df = pd.DataFrame(runs)
    runs_df.to_parquet(paths["runs"], index=False)
    return runs_df


_WORKER_BASE: Baseline | None = None


def _worker_cell(cell: Cell, seeds: list[int], out_dir: str) -> str:
    """joblib entry point: each worker process builds the baseline once and reuses it."""
    global _WORKER_BASE
    if _WORKER_BASE is None:
        _WORKER_BASE = make_baseline()
    run_cell(_WORKER_BASE, cell, seeds, Path(out_dir))
    return cell.cell_id


def run_cells(
    cells: list[Cell],
    seeds: list[int],
    out_dir: Path,
    workers: int = 1,
    resume: bool = False,
    progress=print,
) -> list[str]:
    todo = [c for c in cells if not (resume and cell_paths(out_dir, c)["runs"].exists())]
    if len(todo) < len(cells):
        progress(f"resume: skipping {len(cells) - len(todo)} finished cells")
    if workers <= 1:
        done = []
        for n, c in enumerate(todo, 1):
            t = time.perf_counter()
            done.append(_worker_cell(c, seeds, str(out_dir)))
            progress(f"[{n}/{len(todo)}] {c.cell_id}  {time.perf_counter() - t:.1f}s")
        return done
    from joblib import Parallel, delayed

    return Parallel(n_jobs=workers, verbose=10)(
        delayed(_worker_cell)(c, seeds, str(out_dir)) for c in todo
    )
