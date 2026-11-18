"""Run the experiment: one run, one cell, many cells in parallel with resume (code plan 4.3).

Per cell three Parquet files are written to results/runs/<grid>/:
  <cell_id>.kpi.parquet   run x KPI   (kpi_measures + seed)
  <cell_id>.dq.parquet    run x check (dq_measures + seed)
  <cell_id>.runs.parquet  run         (injection log summary, run_summary, timing)
The .runs file is written last, so its presence marks a finished cell (--resume).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, replace
from pathlib import Path

import duckdb
import pandas as pd

from dqk import ROOT
from dqk.config import KpiSpec, load_kpi_spec
from dqk.dq import DqConfig, load_dq_config, run_dq_checks
from dqk.experiment.grid import BaselineOptions, Cell
from dqk.experiment.measures import dq_measures, kpi_measures, run_summary
from dqk.inject import inject_errors, unit_table
from dqk.kpis import compute_kpis
from dqk.tables import MART_SCHEMA, Mart

WAREHOUSE = ROOT / "warehouse" / "olist.duckdb"


def dataset_setup(
    dataset: str = "olist", suite: str = "core"
) -> tuple[Path, KpiSpec, DqConfig]:
    """(warehouse file, KPI spec, DQ config) of a dataset. Online Retail II uses the
    subsets of src/dqk/retail/kpi_map.yaml on the same KPI and DQ SQL files.
    suite="extended" adds C21-C24 (v1.1)."""
    if dataset == "olist":
        return WAREHOUSE, load_kpi_spec(), load_dq_config(suite=suite)
    if dataset == "retail":
        from dqk.retail.adapter import RETAIL_WAREHOUSE, retail_dq_config, retail_kpi_spec

        return RETAIL_WAREHOUSE, retail_kpi_spec(), retail_dq_config(suite=suite)
    raise ValueError(f"unknown dataset {dataset}")


@dataclass
class Baseline:
    """The clean mart and everything measured on it, computed once per worker.

    reference: the mart that reference-based checks (C22-C24) compare with; the clean
    mart itself in the extended suite, None in the core suite."""

    mart: Mart
    kpis: pd.DataFrame
    dq: pd.DataFrame
    kpi_spec: KpiSpec
    dq_config: DqConfig
    options: BaselineOptions | None = None
    reference: Mart | None = None

    def ref_tables(self):
        return self.reference.as_tables() if self.reference is not None else None

    def compute_kpis(self, mart: Mart) -> pd.DataFrame:
        return kpis_for(mart, self.kpi_spec, bool(self.options and self.options.use_alt_kpis))


def kpis_for(mart: Mart, spec: KpiSpec, use_alt: bool = False) -> pd.DataFrame:
    """compute_kpis; with use_alt each alternative definition is reported under the id of
    the KPI it replaces, so the measures compare like with like."""
    out = compute_kpis(mart, spec, use_alt=use_alt)
    if use_alt:
        multi = [k.id for k in spec.kpis if len(k.alt_definitions) > 1]
        if multi:
            raise ValueError(f"KPIs with several alt definitions: {multi}")
        parent = {a.id: k.id for k in spec.kpis for a in k.alt_definitions}
        out["kpi_id"] = out["kpi_id"].replace(parent)
    return out


def filter_mart(mart: Mart, opt: BaselineOptions | None) -> Mart:
    """Apply the baseline filters of a robustness scenario to the clean mart.
    Only the fact tables are filtered; dimensions stay complete."""
    if opt is None:
        return mart
    o, i = mart.fact_orders, mart.fact_order_items
    keep = pd.Series(True, index=o.index)
    if opt.period is not None:
        keep &= o["purchase_ts"].dt.year == opt.period
    if opt.exclude_top_value_orders:
        value = i.groupby("order_id")["price"].sum().astype(float)
        value = o["order_id"].map(value).fillna(0.0)
        k = round(opt.exclude_top_value_orders * len(o))
        top = value.sort_values(ascending=False, kind="stable").index[:k]
        keep &= ~o.index.isin(top)
    if keep.all():
        return mart
    o = o[keep].reset_index(drop=True)
    i = i[i["order_id"].isin(o["order_id"])].reset_index(drop=True)
    return replace(mart, fact_orders=o, fact_order_items=i)


def load_clean_mart(path: Path = WAREHOUSE) -> Mart:
    con = duckdb.connect(str(path), read_only=True)
    mart = Mart(**{n: con.sql(f"SELECT * FROM mart.{n}").df() for n in MART_SCHEMA})
    con.close()
    return mart


def make_baseline(
    mart: Mart | None = None,
    options: BaselineOptions | None = None,
    dataset: str = "olist",
    suite: str = "core",
) -> Baseline:
    path, spec, cfg = dataset_setup(dataset, suite)
    mart = filter_mart(mart if mart is not None else load_clean_mart(path), options)
    base = Baseline(
        mart=mart,
        kpis=kpis_for(mart, spec, bool(options and options.use_alt_kpis)),
        dq=pd.DataFrame(),
        kpi_spec=spec,
        dq_config=cfg,
        options=options,
        reference=mart if suite == "extended" else None,
    )
    base.dq = run_dq_checks(mart.as_tables(), "mart", cfg, reference=base.ref_tables())
    return base


def run_once(
    base: Baseline, cell: Cell, seed: int, units=None
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    t0 = time.perf_counter()
    corrupted, log = inject_errors(base.mart, cell.spec, seed, units)
    t1 = time.perf_counter()
    kpis = base.compute_kpis(corrupted)
    dq = run_dq_checks(
        corrupted.as_tables(), "mart", base.dq_config, reference=base.ref_tables()
    )
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


_WORKER_MARTS: dict[str, Mart] = {}
_WORKER_BASES: dict[tuple[str, str, str], Baseline] = {}


def _worker_cell(
    cell: Cell,
    seeds: list[int],
    out_dir: str,
    options: BaselineOptions | None = None,
    duckdb_threads: int | None = None,
    dataset: str = "olist",
    suite: str = "core",
) -> str:
    """joblib entry point: each worker process loads each clean mart once, builds one
    baseline per (dataset, options) and reuses them."""
    if duckdb_threads:
        os.environ["DQK_DUCKDB_THREADS"] = str(duckdb_threads)
    key = (dataset, options.key() if options else "", suite)
    if key not in _WORKER_BASES:
        if dataset not in _WORKER_MARTS:
            _WORKER_MARTS[dataset] = load_clean_mart(dataset_setup(dataset)[0])
        _WORKER_BASES[key] = make_baseline(_WORKER_MARTS[dataset], options, dataset, suite)
    run_cell(_WORKER_BASES[key], cell, seeds, Path(out_dir))
    return cell.cell_id


def run_cells(
    cells: list[Cell],
    seeds: list[int],
    out_dir: Path,
    workers: int = 1,
    resume: bool = False,
    progress=print,
    options: BaselineOptions | None = None,
    dataset: str = "olist",
    suite: str = "core",
) -> list[str]:
    todo = [c for c in cells if not (resume and cell_paths(out_dir, c)["runs"].exists())]
    if len(todo) < len(cells):
        progress(f"resume: skipping {len(cells) - len(todo)} finished cells")
    if workers <= 1:
        done = []
        for n, c in enumerate(todo, 1):
            t = time.perf_counter()
            done.append(
                _worker_cell(c, seeds, str(out_dir), options, dataset=dataset, suite=suite)
            )
            progress(f"[{n}/{len(todo)}] {c.cell_id}  {time.perf_counter() - t:.1f}s")
        return done
    from joblib import Parallel, delayed

    return Parallel(n_jobs=workers, verbose=10)(
        delayed(_worker_cell)(c, seeds, str(out_dir), options, 1, dataset, suite)
        for c in todo
    )
