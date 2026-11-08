"""Online Retail II adapter (code plan 4.7): cleaning rules, mapping onto the Olist mart
schema, and the KPI / DQ subsets of kpi_map.yaml."""

import pandas as pd
import pytest

from dqk.dq import run_dq_checks
from dqk.experiment.grid import expand, load_grid
from dqk.kpis import compute_kpis
from dqk.retail.adapter import build_retail, load_kpi_map, retail_dq_config, retail_kpi_spec
from dqk.tables import MART_SCHEMA

COLS = [
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
]


@pytest.fixture
def raw() -> pd.DataFrame:
    rows = [
        # kept: invoice 100001, two lines, customer 1 in France then Germany
        ("100001", "10001", "MUG", 2, "2010-01-05 10:00", 1.5, 1.0, "France"),
        ("100001", "10002a", "CUP", 1, "2010-01-05 10:00", 4.0, 1.0, "France"),
        ("100001", "10002a", "CUP", 1, "2010-01-05 10:00", 4.0, 1.0, "France"),  # R1 dup
        ("100002", "10001", "MUG", 10, "2010-02-01 09:00", 1.25, 1.0, "Germany"),
        ("100003", "10003", "PLATE", 3, "2010-02-02 09:00", 2.0, 2.0, "United Kingdom"),
        ("A00004", "10001", "ADJUST", 1, "2010-02-03 09:00", 9.0, 2.0, "United Kingdom"),  # R2
        ("100005", "10003", "PLATE", 50, "2010-03-01 09:00", 2.0, 2.0, "United Kingdom"),  # R4
        ("C100006", "10003", "PLATE", -50, "2010-03-02 09:00", 2.0, 2.0, "United Kingdom"),  # R3
        ("100007", "POST", "POSTAGE", 1, "2010-03-03 09:00", 18.0, 2.0, "United Kingdom"),  # R5
        ("100008", "10001", "MUG", 0, "2010-03-04 09:00", 1.5, 2.0, "United Kingdom"),  # R6
        ("100009", "10001", "MUG", 1, "2010-03-05 09:00", 1.5, None, "United Kingdom"),  # R7
    ]
    df = pd.DataFrame(rows, columns=COLS)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["Customer ID"] = df["Customer ID"].astype(float)
    df.insert(0, "src_row", range(1, len(df) + 1))
    df["sheet"] = "s"
    return df


def test_cleaning_rules_remove_one_row_each(raw):
    _, _, rules = build_retail(raw)
    assert rules["rule"].tolist() == [f"R{i}" for i in range(8)]
    assert rules["removed"].tolist() == [0, 1, 1, 1, 1, 1, 1, 1]
    assert rules["rows_left"].iloc[-1] == 4


def test_mart_mapping(raw):
    _, mart, _ = build_retail(raw)
    for name, cols in MART_SCHEMA.items():
        assert list(getattr(mart, name).columns) == list(cols)
    o, i = mart.fact_orders, mart.fact_order_items
    assert o["order_id"].tolist() == ["100001", "100002", "100003"]
    assert o["is_delivered"].all() and o["delivered_customer_ts"].isna().all()
    assert i["price"].astype(float).tolist() == [3.0, 4.0, 12.5, 6.0]  # Quantity x Price
    assert i.loc[i["order_id"] == "100001", "order_item_id"].tolist() == [1, 2]
    assert (i["freight_value"] == 0).all() and i["seller_id"].nunique() == 1
    p = mart.dim_product.set_index("product_id")
    assert "10002A" in p.index  # StockCode upper-cased
    assert (p["category_en"] == p.index).all()
    c = mart.dim_customer.set_index("customer_unique_id")["state"]
    assert c.to_dict() == {"1": "Germany", "2": "United Kingdom"}  # latest country


def test_kpi_subset_runs_on_retail_mart(raw):
    _, mart, _ = build_retail(raw)
    spec = retail_kpi_spec()
    assert [k.id for k in spec.kpis] == [k["id"] for k in load_kpi_map()["kpis"]]
    assert str(spec.params.window_start) == "2009-12-01"
    k = compute_kpis(mart, spec).set_index("kpi_id")
    assert k.loc["K1", "value"] == pytest.approx(25.5)
    assert k.loc["K2", "value"] == 3
    assert k.loc["K10", "value"] == 2
    assert k.loc["K9", "value"] == pytest.approx(0.5)  # customer 1 has two invoices
    top = k.loc["K13"].sort_values("rank")
    assert top["item"].tolist() == ["Germany", "United Kingdom"]


def test_dq_subset_passes_on_clean_retail_mart(raw):
    _, mart, _ = build_retail(raw)
    cfg = retail_dq_config()
    kmap = load_kpi_map()["dq"]
    assert [c.id for c in cfg.checks] == kmap["checks"]
    cfg = cfg.model_copy(update={"reference_rows": {"mart": {"orders": 3, "items": 4}}})
    dq = run_dq_checks(mart.as_tables(), "mart", cfg)
    assert (dq["status"] == "pass").all()


def test_grid_retail_has_no_e6():
    grid = load_grid("config/grid_retail.yaml")
    assert grid.dataset == "retail"
    cells = expand(grid)
    assert {c.spec.code for c in cells} == {"E1", "E2", "E3", "E4", "E5"}
    assert len(cells) == 6 * len(grid.rates)
