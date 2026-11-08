"""Distortion measures on small examples with known answers (code plan 4.4, 4.8)."""

import math

import pandas as pd
import pytest

from dqk import CONFIG_DIR
from dqk.config import load_kpi_spec
from dqk.dq import run_dq_checks
from dqk.experiment.grid import Cell, expand, load_grid
from dqk.experiment.measures import (
    dq_measures,
    kpi_measures,
    ranking_measures,
    rel_error,
    run_summary,
    series_mapd,
)
from dqk.experiment.runner import make_baseline, run_cell, run_once
from dqk.inject.spec import ErrorSpec


def _rank(items, values):
    df = pd.DataFrame({"item": items, "value": values})
    df["rank"] = df["value"].rank(ascending=False, method="first").astype("Int64")
    return df


def test_rel_error():
    assert rel_error(100.0, 110.0) == pytest.approx(0.1)
    assert rel_error(100.0, 90.0) == pytest.approx(0.1)
    assert rel_error(0.0, 0.0) == 0.0
    assert math.isinf(rel_error(0.0, 1.0))
    assert math.isinf(rel_error(1.0, math.nan))


def test_ranking_identical():
    a = _rank(list("abcde"), [5, 4, 3, 2, 1])
    m = ranking_measures(a, a, k=3)
    assert m == {"kendall_tau_b": 1.0, "topk_overlap": 1.0, "top1_flip": 0.0, "topk_changed": 0.0}


def test_ranking_swap_and_new_entry():
    clean = _rank(list("abcde"), [5, 4, 3, 2, 1])
    corr = _rank(list("abcdeX"), [5, 3, 4, 2, 1, 4.5])  # X enters at rank 2, b and c swap
    m = ranking_measures(clean, corr, k=3)
    # top3 clean {a,b,c}; corr a, X, c -> overlap 2/3
    assert m["topk_overlap"] == pytest.approx(2 / 3)
    assert m["top1_flip"] == 0.0 and m["topk_changed"] == 1.0
    # union a,b,c,X: clean (5,4,3,0), corr (5,3,4,4.5) -> tau-b by hand
    from scipy.stats import kendalltau

    assert m["kendall_tau_b"] == pytest.approx(kendalltau([5, 4, 3, 0], [5, 3, 4, 4.5]).statistic)


def test_series_mapd():
    clean = pd.DataFrame({"item": ["2017-01", "2017-02"], "value": [100.0, 200.0]})
    corr = pd.DataFrame({"item": ["2017-01", "2017-03"], "value": [110.0, 50.0]})
    # Jan 10 %, Feb missing -> 100 %; Mar ignored
    assert series_mapd(clean, corr) == pytest.approx(0.55)


def test_kpi_measures_identical_is_zero(mini_mart):
    from dqk.kpis import compute_kpis

    spec = load_kpi_spec()
    k = compute_kpis(mini_mart, spec)
    m = kpi_measures(k, k, spec)
    assert len(m) == len(spec.kpis)
    assert (m["rel_error"].dropna() == 0).all()
    assert m.filter(like="material_").fillna(0).to_numpy().sum() == 0


def test_run_once_rate_zero_and_detection(synth_mart, tmp_path):
    base = make_baseline(synth_mart)
    km, dm, run = run_once(base, Cell(ErrorSpec("E5", "price_x100", "MCAR", 0.0)), seed=0)
    assert run["n_selected"] == 0 and run["detected"] == 0 and run["dq_drop"] == 0
    assert (km["rel_error"].dropna() == 0).all()

    km, dm, run = run_once(base, Cell(ErrorSpec("E1", "duplicate_order", "MCAR", 0.05)), seed=0)
    assert run["detected"] == 1 and "C05" in run["worsened_checks"]
    assert run["material_0_01"] == 1

    cell = Cell(ErrorSpec("E6", "category_spelling", "MCAR", 0.2))
    runs = run_cell(base, cell, [0, 1], tmp_path)
    assert len(runs) == 2 and (tmp_path / f"{cell.cell_id}.runs.parquet").exists()
    assert (runs["detected"] == 0).all()  # no check looks at spelling: silent candidate


def test_dq_measures_and_summary(synth_mart):
    dq = run_dq_checks(synth_mart.as_tables(), "mart")
    dm = dq_measures(dq, dq)
    assert not dm["worsened"].any()
    km = pd.DataFrame({"material_0_01": [0.0, 1.0]})
    s = run_summary(km, dm, dq, taus=(0.01,))
    assert s["material_0_01"] == 1 and s["silent_0_01"] == 1 and s["dq_drop"] == 0


def test_main_grid_has_65_cells():
    cells = expand(load_grid(CONFIG_DIR / "grid_main.yaml"))
    assert len(cells) == 65
    assert len({(c.spec.code, c.spec.mechanism) for c in cells}) == 13
