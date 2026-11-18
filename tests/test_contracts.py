"""Raw data contracts (code plan v1.1, M3): a dropped, renamed or retyped column is caught."""

import pandas as pd
import pytest

from dqk.contracts import ContractError, enforce, load_contracts, validate_all
from dqk.tables import Tables


def _raw() -> Tables:
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "customer_id": ["c1", "c2"],
            "order_status": ["delivered", "shipped"],
            "order_purchase_timestamp": ["2017-10-02 10:56:33", "2018-07-24 20:41:37"],
            "order_approved_at": ["2017-10-02 11:07:15", ""],
            "order_delivered_carrier_date": ["2017-10-04 19:55:00", None],
            "order_delivered_customer_date": ["2017-10-10 21:25:13", None],
            "order_estimated_delivery_date": ["2017-10-18 00:00:00", "2018-08-13 00:00:00"],
        }
    )
    items = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "order_item_id": ["1", "1"],
            "product_id": ["p1", "p2"],
            "seller_id": ["s1", "s2"],
            "shipping_limit_date": ["2017-09-19 09:45:35", "2017-05-03 11:05:13"],
            "price": ["58.90", "239.90"],
            "freight_value": ["13.29", "19.93"],
        }
    )
    return Tables({"orders": orders, "order_items": items})


def _kinds(raw):
    return {(v.table, v.column, v.kind, v.severity) for v in validate_all(raw)}


def test_two_contracts_and_clean_fixture_passes():
    assert {c["id"] for c in load_contracts()} == {"olist-orders", "olist-order-items"}
    assert validate_all(_raw()) == []


def test_dropped_required_column_is_an_error():
    raw = _raw()
    raw.frames["order_items"] = raw["order_items"].drop(columns="freight_value")
    assert ("order_items", "freight_value", "missing_column", "error") in _kinds(raw)
    with pytest.raises(ContractError):
        enforce(raw, echo=lambda s: None)


def test_renamed_column_is_missing_plus_extra():
    raw = _raw()
    raw.frames["order_items"] = raw["order_items"].rename(columns={"price": "unit_price"})
    k = _kinds(raw)
    assert ("order_items", "price", "missing_column", "error") in k
    assert ("order_items", "unit_price", "extra_column", "warning") in k


def test_retyped_column_is_unparseable():
    raw = _raw()
    raw.frames["order_items"]["price"] = ["58,90", "239,90"]  # decimal comma
    assert ("order_items", "price", "unparseable", "error") in _kinds(raw)


def test_dropped_optional_column_is_a_warning_only():
    raw = _raw()
    raw.frames["orders"] = raw["orders"].drop(columns="order_approved_at")
    k = _kinds(raw)
    assert ("orders", "order_approved_at", "missing_column", "warning") in k
    enforce(raw, echo=lambda s: None)  # does not raise


def test_missing_table_is_an_error():
    raw = Tables({"orders": _raw()["orders"]})
    assert ("order_items", None, "missing_table", "error") in _kinds(raw)
