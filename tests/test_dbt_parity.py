"""dbt models (code plan v1.1, M1): in sync with sql/, and the dbt mart equals the
pipeline mart row for row. The second test needs dbt (requirements-dbt.txt, e.g. in
.venv-dbt) and warehouse/olist.duckdb; it is skipped otherwise."""

import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from dqk import ROOT
from dqk.pipeline import MART_TABLES, STAGING_TABLES

DBT_DIR = ROOT / "dbt"
DBT_DB = ROOT / "warehouse" / "olist_dbt.duckdb"
PIPE_DB = ROOT / "warehouse" / "olist.duckdb"


def dbt_executable() -> str | None:
    venv = ROOT / ".venv-dbt" / ("Scripts" if sys.platform == "win32" else "bin") / "dbt"
    for cand in (venv.with_suffix(".exe"), venv):
        if cand.exists():
            return str(cand)
    return shutil.which("dbt")


def test_dbt_models_in_sync_with_sql():
    out = subprocess.run(
        [sys.executable, str(DBT_DIR / "sync_models.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout


@pytest.mark.slow
@pytest.mark.skipif(dbt_executable() is None, reason="dbt not installed")
@pytest.mark.skipif(not PIPE_DB.exists(), reason="needs warehouse/olist.duckdb")
def test_dbt_mart_equals_pipeline_mart():
    run = subprocess.run(
        [dbt_executable(), "build", "--profiles-dir", "."],
        cwd=DBT_DIR,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout[-3000:]
    con = duckdb.connect()
    con.execute(f"ATTACH '{Path(PIPE_DB).as_posix()}' AS p (READ_ONLY)")
    con.execute(f"ATTACH '{Path(DBT_DB).as_posix()}' AS d (READ_ONLY)")
    for schema, names in (("staging", STAGING_TABLES), ("mart", MART_TABLES)):
        for name in names:
            a, b = f"p.{schema}.{name}", f"d.{schema}.{name}"
            cols_a = [d[0] for d in con.execute(f"SELECT * FROM {a} LIMIT 0").description]
            cols_b = [d[0] for d in con.execute(f"SELECT * FROM {b} LIMIT 0").description]
            assert cols_a == cols_b, name
            n_a = con.execute(f"SELECT count(*) FROM {a}").fetchone()[0]
            n_b = con.execute(f"SELECT count(*) FROM {b}").fetchone()[0]
            assert n_a == n_b, (name, n_a, n_b)
            for x, y in ((a, b), (b, a)):
                sql = f"SELECT count(*) FROM (FROM {x} EXCEPT ALL FROM {y})"
                diff = con.execute(sql).fetchone()
                assert diff[0] == 0, (name, x, diff[0])
    con.close()
