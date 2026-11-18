"""Stage B: run an error-injection grid on the clean mart (code plan 4.3).

    python run_experiment.py --grid config/grid_main.yaml --workers 8 --resume
    python run_experiment.py --grid config/grid_main.yaml \
        --cell E3-missing_delivery_date-MNAR-0.05 --seeds 5          # pilot

Needs warehouse/olist.duckdb (python run_pipeline.py). Writes results/runs/<grid name>/
(one set of Parquet files per cell, see dqk.experiment.runner) and _meta.json.
Refuses to run if the KPI spec changed since it was frozen, unless --allow-spec-change.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from dqk import RESULTS_DIR, __version__  # noqa: E402
from dqk.config import KPI_LOCK, check_lock  # noqa: E402
from dqk.experiment.grid import expand, load_grids  # noqa: E402
from dqk.experiment.runner import dataset_setup, run_cells  # noqa: E402
from dqk.retail.adapter import kpi_map_hash  # noqa: E402


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _versions() -> dict:
    import duckdb
    import numpy
    import pandas
    import pyarrow
    import scipy

    return {
        "dqk": __version__,
        "python": sys.version.split()[0],
        "duckdb": duckdb.__version__,
        "pandas": pandas.__version__,
        "numpy": numpy.__version__,
        "pyarrow": pyarrow.__version__,
        "scipy": scipy.__version__,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--grid", required=True, help="grid YAML, e.g. config/grid_main.yaml")
    ap.add_argument("--cell", action="append", help="run only this cell id (repeatable)")
    ap.add_argument("--seeds", type=int, help="number of seeds (default: n_seeds of the grid)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--resume", action="store_true", help="skip cells that already have output")
    ap.add_argument("--out", type=Path, help="output folder (default results/runs/<grid name>)")
    ap.add_argument("--allow-spec-change", action="store_true")
    ap.add_argument(
        "--only", action="append", help="run only this scenario of a scenarios file (repeatable)"
    )
    args = ap.parse_args(argv)

    changed = check_lock()
    if changed and not args.allow_spec_change:
        print("KPI spec changed since freeze (re-run old results if you continue):")
        print("  " + "\n  ".join(changed))
        return 1
    grids = load_grids(args.grid)
    if args.only:
        names = {g.name.split("/", 1)[-1]: g for g in grids}
        unknown = [s for s in args.only if s not in names]
        if unknown:
            print(f"unknown scenario(s): {unknown}; known: {sorted(names)}")
            return 2
        grids = [names[s] for s in args.only]
    for ds in {g.dataset for g in grids}:
        warehouse = dataset_setup(ds)[0]
        if not warehouse.exists():
            build = "python run_pipeline.py" if ds == "olist" else "python -m dqk.retail.adapter"
            print(f"{warehouse} not found: run {build} first")
            return 1

    if args.out and len(grids) > 1:
        print("--out needs a single-grid file (this one has scenarios)")
        return 2
    for grid in grids:
        cells = expand(grid)
        if args.cell:
            known = {c.cell_id: c for c in cells}
            unknown = [c for c in args.cell if c not in known]
            if unknown:
                print(f"unknown cell(s) in {grid.name}: {unknown}")
                return 2
            cells = [known[c] for c in args.cell]
        seeds = list(range(args.seeds if args.seeds else grid.n_seeds))
        out = args.out or RESULTS_DIR / "runs" / grid.name

        print(f"grid {grid.name}: {len(cells)} cells x {len(seeds)} seeds -> {out}")
        t = time.perf_counter()
        run_cells(
            cells,
            seeds,
            out,
            workers=args.workers,
            resume=args.resume,
            options=grid.baseline,
            dataset=grid.dataset,
            suite=grid.dq_suite,
        )
        seconds = time.perf_counter() - t

        out.mkdir(parents=True, exist_ok=True)
        meta = {
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "seconds": round(seconds, 1),
            "grid": str(args.grid),
            "grid_name": grid.name,
            "dataset": grid.dataset,
            "dq_suite": grid.dq_suite,
            "baseline": grid.baseline.model_dump(),
            "cells": [c.cell_id for c in cells],
            "n_seeds": len(seeds),
            "workers": args.workers,
            "git_commit": _git_commit(),
            "kpi_spec_hash": json.loads(KPI_LOCK.read_text(encoding="utf-8"))["spec_hash"],
            "kpi_spec_matches_lock": not changed,
            **({"kpi_map_hash": kpi_map_hash()} if grid.dataset == "retail" else {}),
            "versions": _versions(),
        }
        (out / "_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(f"{grid.name} done in {seconds:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
