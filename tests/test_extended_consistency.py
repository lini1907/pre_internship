"""v1.1 N1: the extended grid reproduces the main grid on shared cells. Same seeds give
the same injections, so detected_core (any of C01-C20 worsened) and material_0_01 must
equal the main grid's 'detected' and 'material_0_01' run by run."""

import pytest

from dqk import RESULTS_DIR

MAIN = RESULTS_DIR / "runs" / "main"
EXT = RESULTS_DIR / "runs" / "extended" / "olist_ext"


@pytest.mark.slow
@pytest.mark.skipif(
    not (any(MAIN.glob("*.runs.parquet")) and any(EXT.glob("*.runs.parquet"))),
    reason="needs results/runs/main and results/runs/extended/olist_ext",
)
def test_detected_core_and_material_match_main_grid():
    from dqk.analysis.stats import load_results
    from dqk.analysis.v11 import consistency_with_main, detected_by_suite

    ext = load_results(EXT, with_dq=True)
    runs = ext.runs.merge(detected_by_suite(ext.dq), on=["cell_id", "seed"])
    shared = set(runs["cell_id"]) & {f.name.removesuffix(".runs.parquet")
                                     for f in MAIN.glob("*.runs.parquet")}
    assert shared, "no shared cells"
    main = load_results(MAIN)
    c = consistency_with_main(runs[runs["cell_id"].isin(shared)], main.runs).iloc[0]
    assert c["n_runs"] == 200 * len(shared)
    assert c["detected_mismatch"] == 0
    assert c["material_mismatch"] == 0
