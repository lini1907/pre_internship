"""Unit selection (code plan 4.2, 4.8): exact counts, nesting, reproducibility, MAR bias."""

import numpy as np
import pandas as pd
import pytest

from dqk.inject.sampling import mnar_weights, n_to_select, rng_streams, select_units
from dqk.inject.spec import ErrorSpec

RATES = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 1.0]


def _units(n=1000):
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "unit_id": [f"u{j:05d}" for j in range(n)],
            "grp": rng.choice(["A", "B", "C", "D"], n),
            "x": rng.normal(size=n),
        }
    )


def _select(units, rate, seed=0, mech="MCAR", params=None, code="E1", variant="duplicate_order"):
    spec = ErrorSpec(code, variant, mech, rate, params or {})
    rng, _ = rng_streams(seed, code, variant)
    return set(select_units(units, spec, rng))


MAR = {"by": "grp", "groups": ["A"], "weight": 5}
MNAR = {"by_value": "x", "strength": 1.0}


def test_n_to_select_rounds_half_up():
    assert n_to_select(0.05, 10) == 1  # 0.5 -> 1, not banker's 0
    assert n_to_select(0.01, 99441) == 994
    assert n_to_select(0.0, 100) == 0


@pytest.mark.parametrize("mech,params", [("MCAR", {}), ("MAR", MAR), ("MNAR", MNAR)])
@pytest.mark.parametrize("rate", RATES)
def test_exact_count(rate, mech, params):
    u = _units()
    assert len(_select(u, rate, mech=mech, params=params)) == n_to_select(rate, len(u))


@pytest.mark.parametrize("mech,params", [("MCAR", {}), ("MAR", MAR), ("MNAR", MNAR)])
def test_nested_across_rates(mech, params):
    u = _units()
    sets = [_select(u, r, seed=7, mech=mech, params=params) for r in RATES]
    for small, big in zip(sets, sets[1:], strict=False):
        assert small <= big


def test_same_seed_same_units_different_seed_different_units():
    u = _units()
    assert _select(u, 0.05, seed=3) == _select(u, 0.05, seed=3)
    assert _select(u, 0.05, seed=3) != _select(u, 0.05, seed=4)


def test_streams_depend_on_code_and_variant():
    u = _units()
    a = _select(u, 0.05, code="E1", variant="duplicate_order")
    b = _select(u, 0.05, code="E5", variant="price_x100")
    assert a != b


def test_mechanisms_share_random_numbers():
    """MAR with weight 1 for everyone is exactly MCAR (common random numbers)."""
    u = _units()
    flat = {"by": "grp", "groups": ["A"], "weight": 1}
    assert _select(u, 0.1, seed=5, mech="MAR", params=flat) == _select(u, 0.1, seed=5)


def test_mar_oversamples_weighted_group():
    """Over 1000 seeds, group A (25 % of units, weight 5) gets far more than 25 % of hits."""
    u = _units(400)
    in_a = set(u.loc[u["grp"] == "A", "unit_id"])
    share_a = len(in_a) / len(u)
    shares_mar, shares_mcar = [], []
    for seed in range(1000):
        s = _select(u, 0.05, seed=seed, mech="MAR", params=MAR)
        shares_mar.append(len(s & in_a) / len(s))
        s = _select(u, 0.05, seed=seed)
        shares_mcar.append(len(s & in_a) / len(s))
    assert abs(np.mean(shares_mcar) - share_a) < 0.02
    assert np.mean(shares_mar) > share_a + 0.3  # theory: about 5*0.25/(5*0.25+0.75) = 0.62


def test_mnar_prefers_large_values():
    u = _units()
    hits = [
        u.set_index("unit_id")
        .loc[list(_select(u, 0.05, seed=s, mech="MNAR", params=MNAR)), "x"]
        .mean()
        for s in range(200)
    ]
    assert np.mean(hits) > 0.5


def test_mnar_weights_handle_missing_and_log():
    w = mnar_weights(pd.Series([1.0, None, 100.0]), strength=1.0, log=True)
    assert w[1] == 1.0 and w[2] > w[0]
