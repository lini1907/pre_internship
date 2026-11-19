"""The ML grid repeats the extended grid with the same seeds: adding M01-M03 must not
change the injections, the KPIs or the SQL checks (code plan v1.2, 3.7)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dqk import RESULTS_DIR

RUNS = RESULTS_DIR / "runs"
PAIRS = [("ml/olist_ml", "extended/olist_ext"), ("ml/olist_ml_lowrate", "extended/olist_lowrate"),
         ("ml/retail_ml", "extended/retail_ext")]


@pytest.mark.slow
@pytest.mark.parametrize("ml, ext", PAIRS)
def test_ml_grid_matches_extended(ml, ext):
    a, b = RUNS / ml, RUNS / ext
    if not a.exists() or not b.exists():
        pytest.skip("ML grid not run")
    cells = sorted(f.name.removesuffix(".runs.parquet") for f in a.glob("*.runs.parquet"))
    assert cells
    for c in cells:
        ra = pd.read_parquet(a / f"{c}.runs.parquet")
        rb = pd.read_parquet(b / f"{c}.runs.parquet")
        cols = ["seed", "n_selected", "achieved_rate", "material_0_01", "dq_score"]
        pd.testing.assert_frame_equal(ra[cols], rb[cols])
        ka = pd.read_parquet(a / f"{c}.kpi.parquet")
        kb = pd.read_parquet(b / f"{c}.kpi.parquet")
        assert np.allclose(ka["value"], kb["value"], equal_nan=True)
        da = pd.read_parquet(a / f"{c}.dq.parquet")
        db = pd.read_parquet(b / f"{c}.dq.parquet")
        da = da[~da["check_id"].str.startswith("M")].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            da[["seed", "check_id", "fail_share", "status", "worsened"]],
            db[["seed", "check_id", "fail_share", "status", "worsened"]],
        )
