"""Stage A: rebuild everything with one command (code plan 3.8).

    python run_pipeline.py                 # download (if missing) -> raw -> DQ raw -> staging
                                           # -> DQ staging -> mart -> DQ mart -> KPI -> export
    python run_pipeline.py --skip-download --no-export
    python run_pipeline.py --suite extended --accept   # v1.1: C21-C24, then store this
                                                       # load as the reference snapshot

Writes warehouse/olist.duckdb, results/stage_a/{dq_results,kpis_clean}.csv and run_meta.json.
The raw data contracts (contracts/*.yaml) are checked first; the run stops on a violation
(--no-contracts skips them). With --suite extended the core results are unchanged and
C21-C24 are added; C22-C24 compare with warehouse/reference/ (the last load accepted with
--accept) and are reported as skipped when there is none. --suite extended writes its
results to results/stage_a/dq_results_extended.csv, so dq_results.csv stays the core
baseline. Exits 1 if a mart check fails, unless --allow-fail.
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

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from dqk import RESULTS_DIR, __version__  # noqa: E402
from dqk.config import KPI_LOCK, check_lock  # noqa: E402
from dqk.contracts import ContractError, enforce  # noqa: E402
from dqk.dq import (  # noqa: E402
    dq_score,
    load_dq_config,
    run_dq_checks,
    write_catalogue,
)
from dqk.export import export_all  # noqa: E402
from dqk.io import OLIST_DIR, ensure_olist, verify_manifest  # noqa: E402
from dqk.kpis import compute_kpis  # noqa: E402
from dqk.pipeline import (  # noqa: E402
    build_mart_from_staging,
    build_staging,
    load_raw,
    load_reference,
    save_reference,
    write_schema,
)

WAREHOUSE = ROOT / "warehouse" / "olist.duckdb"
OUT = RESULTS_DIR / "stage_a"


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _meta(seconds: float, counts: dict) -> dict:
    import numpy
    import pyarrow

    return {
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(seconds, 1),
        "git_commit": _git_commit(),
        "kpi_spec_hash": json.loads(KPI_LOCK.read_text(encoding="utf-8"))["spec_hash"],
        "kpi_spec_matches_lock": not check_lock(),
        "versions": {
            "dqk": __version__,
            "python": sys.version.split()[0],
            "duckdb": duckdb.__version__,
            "pandas": pd.__version__,
            "numpy": numpy.__version__,
            "pyarrow": pyarrow.__version__,
        },
        "rows": counts,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--skip-download", action="store_true", help="use the files already in data/")
    ap.add_argument("--no-export", action="store_true", help="do not write exports/")
    ap.add_argument("--allow-fail", action="store_true", help="exit 0 even if a mart check fails")
    ap.add_argument("--suite", choices=["core", "extended"], default="core")
    ap.add_argument(
        "--accept", action="store_true", help="store this mart as the reference snapshot"
    )
    ap.add_argument("--no-contracts", action="store_true", help="skip the raw data contracts")
    args = ap.parse_args(argv)

    t0 = time.perf_counter()
    if args.skip_download:
        verify_manifest()
    else:
        ensure_olist()
    raw = load_raw(OLIST_DIR)
    if not args.no_contracts:
        try:
            enforce(raw)
        except ContractError as e:
            print(f"Load stopped by the raw data contracts: {e}", file=sys.stderr)
            return 2
    dq = [run_dq_checks(raw, "raw")]
    staging = build_staging(raw)
    dq.append(run_dq_checks(staging, "staging"))
    mart = build_mart_from_staging(staging)
    dq.append(run_dq_checks(mart.as_tables(), "mart"))
    dq = pd.concat(dq, ignore_index=True)
    dq_ext = None
    if args.suite == "extended":
        ref = load_reference()
        if ref is None:
            print("No reference snapshot yet: C22-C24 skipped (run once with --accept)")
        r = run_dq_checks(mart.as_tables(), "mart", load_dq_config(suite="extended"), ref)
        dq_ext = r[r["check_id"] > "C20"]
    kpis = compute_kpis(mart)

    OUT.mkdir(parents=True, exist_ok=True)
    dq.to_csv(OUT / "dq_results.csv", index=False)
    kpis.to_csv(OUT / "kpis_clean.csv", index=False)
    write_catalogue(OUT / "dq_results.csv")
    if dq_ext is not None:
        dq_ext.to_csv(OUT / "dq_results_extended.csv", index=False)
        dq = pd.concat([dq, dq_ext], ignore_index=True)

    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(WAREHOUSE)) as con:
        write_schema(raw, "raw", con)
        write_schema(staging, "staging", con)
        write_schema(mart.as_tables(), "mart", con)
        con.execute("CREATE SCHEMA IF NOT EXISTS results")
        for name, df in {"kpis_clean": kpis, "dq_results": dq}.items():
            con.register("_tmp", df)
            con.execute(f"CREATE OR REPLACE TABLE results.{name} AS SELECT * FROM _tmp")
            con.unregister("_tmp")
    if not args.no_export:
        export_all(mart, kpis, dq)

    counts = {
        layer: {name: len(df) for name, df in tables}
        for layer, tables in [("raw", raw), ("staging", staging), ("mart", mart.as_tables())]
    }
    seconds = time.perf_counter() - t0
    (OUT / "run_meta.json").write_text(
        json.dumps(_meta(seconds, counts), indent=2), "utf-8", newline="\n"
    )

    print("Rows per layer:")
    for layer, c in counts.items():
        print(f"  {layer:8s} " + ", ".join(f"{n}={v:,}" for n, v in c.items()))
    print("DQ checks:")
    for layer, g in dq.groupby("layer", sort=False):
        s = g["status"].value_counts()
        line = (
            f"  {layer:8s} pass={s.get('pass', 0)} warn={s.get('warn', 0)} fail={s.get('fail', 0)}"
        )
        if layer != "raw":
            line += f"  dq_score={dq_score(g):.4f}"
        bad = g[g["status"] != "pass"]
        if len(bad):
            line += "  (" + ", ".join(f"{r.check_id} {r.status}" for r in bad.itertuples()) + ")"
        print(line)
    print(f"KPIs: {kpis['kpi_id'].nunique()} computed, {len(kpis)} rows")
    print(f"Done in {seconds:.1f} s -> {WAREHOUSE.relative_to(ROOT)}, {OUT.relative_to(ROOT)}/")

    mart_fail = dq[(dq["layer"] == "mart") & (dq["status"] == "fail")]
    if len(mart_fail) and not args.allow_fail:
        print("Mart check(s) failed: " + ", ".join(mart_fail["check_id"]), file=sys.stderr)
        return 1
    if args.accept:
        if len(mart_fail):
            print("Not accepted: a mart check failed", file=sys.stderr)
            return 1
        saved = save_reference(mart)
        print(f"Accepted as reference: {', '.join(p.name for p in saved)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
