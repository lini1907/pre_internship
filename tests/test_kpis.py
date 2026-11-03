import duckdb
import pytest

from dqk.config import load_kpi_spec
from dqk.db import read_sql, run_sql
from dqk.kpis import compute_kpis
from dqk.tables import MART_SCHEMA

# Hand-computed on the mini mart (conftest.py). O4 is canceled, O5 is outside the window.
EXPECTED_SCALARS = {
    "K1": 380.0,  # 100 + 50 + 200 + 30
    "K2": 3,  # O1, O2, O3
    "K3": 380.0 / 3,
    "K4": 38.0 / 380.0,
    "K5": 0.5,  # O1 on time, O2 late, O3 has no delivery date
    "K6": 7.0,  # (4 + 10) / 2 days
    "K7": 3.0,  # O1..O4: (5 + 1 + 4 + 2) / 4
    "K8": 0.5,  # O2, O4
    "K9": 0.5,  # A has 2 delivered orders, B has 1
    "K10": 2,
}


@pytest.fixture
def kpis(mini_mart):
    return compute_kpis(mini_mart)


@pytest.mark.parametrize("kpi_id,expected", EXPECTED_SCALARS.items())
def test_scalar_kpis(kpis, kpi_id, expected):
    row = kpis[kpis.kpi_id == kpi_id]
    assert len(row) == 1
    assert row["item"].isna().all()
    assert row["value"].iloc[0] == pytest.approx(expected)


def _ranking(kpis, kpi_id):
    df = kpis[kpis.kpi_id == kpi_id]
    return {
        r.item: (r.value, None if r.rank is None or str(r.rank) == "<NA>" else int(r.rank))
        for r in df.itertuples()
    }


def test_k11_orphan_goes_to_unknown_without_rank(kpis):
    assert _ranking(kpis, "K11") == {
        "toys": (300.0, 1),
        "books": (50.0, 2),
        "unknown": (30.0, None),
    }


def test_k12_k13(kpis):
    assert _ranking(kpis, "K12") == {"S1": (330.0, 1), "S2": (50.0, 2)}
    assert _ranking(kpis, "K13") == {"SP": (350.0, 1), "RJ": (30.0, 2)}


def test_k14_monthly(kpis):
    df = kpis[kpis.kpi_id == "K14"]
    assert dict(zip(df["item"], df["value"], strict=True)) == {"2017-03": 150.0, "2017-04": 230.0}


def test_k15_threshold_and_decision(mini_mart):
    spec = load_kpi_spec()
    assert compute_kpis(mini_mart, spec).query("kpi_id == 'K15'").empty  # < 100 reviews
    spec.params.min_reviews = 1
    df = compute_kpis(mini_mart, spec).query("kpi_id == 'K15'")
    # toys: O1 (5), O2 (1) -> 3.0; books: O1 (5), O4 (2) -> 3.5
    assert list(df["item"]) == ["toys", "books"]
    assert df["value"].tolist() == pytest.approx([3.0, 3.5])


def test_alt_definition(mini_mart):
    df = compute_kpis(mini_mart, use_alt=True)
    assert "K5_all_orders" in set(df.kpi_id) and "K5" not in set(df.kpi_id)
    # O1 on time; O2 late; O3 no date; O4 canceled -> 1 / 4
    assert df.query("kpi_id == 'K5_all_orders'")["value"].iloc[0] == pytest.approx(0.25)


def test_every_kpi_sql_compiles_on_typed_empty_mart():
    """Every KPI file runs against empty tables with the exact mart column types."""
    spec = load_kpi_spec()
    con = duckdb.connect()
    for table, cols in MART_SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({', '.join(f'{c} {t}' for c, t in cols.items())})")
    for path in spec.sql_files():
        df = run_sql(con, read_sql(path), spec.params.model_dump())
        assert list(df.columns) == ["item", "value", "rank"], path
