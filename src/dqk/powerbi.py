"""Generate the Power BI project (PBIP: TMDL semantic model + PBIR report) for the dashboard.

Usage: python -m dqk.powerbi   -> powerbi/Olist.pbip, Olist.SemanticModel/, Olist.Report/

The model imports exports/*.parquet (run_pipeline.py first) through the parameter
ExportsFolder. KPI cards read kpis_clean, so the dashboard shows exactly the pipeline's
numbers; charts that slice by month, state or status use the mart with the KPI spec's
window (docs/dashboard.md).
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from dqk import CONFIG_DIR, ROOT
from dqk.config import load_kpi_spec
from dqk.export import EXPORT_DIR

OUT_DIR = ROOT / "powerbi"
NAME = "Olist"
_NS = uuid.UUID("6f1c2a52-6d0e-4c8e-9a51-0b7c6e1f4d10")
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
# Power BI's own base theme, copied from the Desktop install (bin/.../BaseThemes).
BASE_THEME = CONFIG_DIR / "powerbi" / "CY26SU10.json"


def _tag(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "/".join(parts)))


# ---------------------------------------------------------------- semantic model

# table -> [(column, TMDL dataType, M type)]
COLUMNS: dict[str, list[tuple[str, str, str]]] = {
    "fact_orders": [
        ("order_id", "string", "type text"),
        ("customer_unique_id", "string", "type text"),
        ("status", "string", "type text"),
        ("purchase_ts", "dateTime", "type datetime"),
        ("delivered_customer_ts", "dateTime", "type datetime"),
        ("estimated_delivery_date", "dateTime", "type datetime"),
        ("payment_total", "double", "type number"),
        ("review_score", "int64", "Int64.Type"),
        ("is_delivered", "boolean", "type logical"),
        # derived in Power Query
        ("purchase_date_key", "int64", "Int64.Type"),
        ("in_window", "boolean", "type logical"),
        ("on_time", "int64", "Int64.Type"),
        ("delivery_days", "double", "type number"),
    ],
    "fact_order_items": [
        ("order_id", "string", "type text"),
        ("order_item_id", "int64", "Int64.Type"),
        ("product_id", "string", "type text"),
        ("seller_id", "string", "type text"),
        ("price", "double", "type number"),
        ("freight_value", "double", "type number"),
    ],
    "dim_customer": [
        ("customer_unique_id", "string", "type text"),
        ("state", "string", "type text"),
    ],
    "dim_product": [
        ("product_id", "string", "type text"),
        ("category_pt", "string", "type text"),
        ("category_en", "string", "type text"),
    ],
    "dim_seller": [("seller_id", "string", "type text"), ("state", "string", "type text")],
    "dim_date": [
        ("date_key", "int64", "Int64.Type"),
        ("date", "dateTime", "type datetime"),
        ("year", "int64", "Int64.Type"),
        ("month", "int64", "Int64.Type"),
        ("year_month", "string", "type text"),
    ],
    "kpis_clean": [
        ("kpi_id", "string", "type text"),
        ("item", "string", "type text"),
        ("value", "double", "type number"),
        ("rank", "int64", "Int64.Type"),
    ],
    "dq_results": [
        ("check_id", "string", "type text"),
        ("layer", "string", "type text"),
        ("dimension", "string", "type text"),
        ("n_failed", "int64", "Int64.Type"),
        ("n_total", "int64", "Int64.Type"),
        ("fail_share", "double", "type number"),
        ("status", "string", "type text"),
        ("in_dq_score", "boolean", "type logical"),
    ],
}
# Ranking and series KPIs as small tables, so charts need no visual-level filters.
KPI_TABLES = {
    "k11_top_categories": ("K11", 10),
    "k12_top_sellers": ("K12", 20),
    "k13_top_states": ("K13", 5),
    "k14_monthly_gmv": ("K14", None),
    "k15_categories": ("K15", None),
}
for _t in KPI_TABLES:
    COLUMNS[_t] = COLUMNS["kpis_clean"]

FORMATS = {
    "price": "#,0.00",
    "freight_value": "#,0.00",
    "payment_total": "#,0.00",
    "value": "#,0.00",
    "fail_share": "0.000%",
    "delivery_days": "0.0",
}


def _m_list(names: list[str]) -> str:
    return "{" + ", ".join(f'"{n}"' for n in names) + "}"


def _m_source(table: str, window: tuple[str, str]) -> str:
    """Power Query (M) for one table."""
    types = ", ".join(f'{{"{c}", {m}}}' for c, _, m in COLUMNS[table])
    if table in KPI_TABLES:
        kpi, top = KPI_TABLES[table]
        cond = f'[kpi_id] = "{kpi}"' + (f" and [rank] <> null and [rank] <= {top}" if top else "")
        steps = [
            'Source = Parquet.Document(File.Contents(ExportsFolder & "kpis_clean.parquet"))',
            f"Selected = Table.SelectRows(Source, each {cond})",
            f"Typed = Table.TransformColumnTypes(Selected, {{{types}}})",
        ]
    elif table == "fact_orders":
        start = "#datetime({}, {}, {}, 0, 0, 0)".format(*map(int, window[0].split("-")))
        end = "#datetime({}, {}, {}, 0, 0, 0)".format(*map(int, window[1].split("-")))
        base = [c for c, _, _ in COLUMNS[table][:9]]
        steps = [
            'Source = Parquet.Document(File.Contents(ExportsFolder & "fact_orders.parquet"))',
            f"Kept = Table.SelectColumns(Source, {_m_list(base)})",
            'DateKey = Table.AddColumn(Kept, "purchase_date_key", each '
            "if [purchase_ts] = null then null else Number.From(DateTime.ToText([purchase_ts], "
            '"yyyyMMdd")))',
            f'InWindow = Table.AddColumn(DateKey, "in_window", each [purchase_ts] <> null and '
            f"[purchase_ts] >= {start} and [purchase_ts] < {end})",
            'OnTime = Table.AddColumn(InWindow, "on_time", each if [delivered_customer_ts] = null '
            "then null else if Date.From([delivered_customer_ts]) <= "
            "Date.From([estimated_delivery_date]) then 1 else 0)",
            'Days = Table.AddColumn(OnTime, "delivery_days", each if [delivered_customer_ts] = '
            "null then null else Duration.TotalDays([delivered_customer_ts] - [purchase_ts]))",
            f"Typed = Table.TransformColumnTypes(Days, {{{types}}})",
        ]
    else:
        cols = _m_list([c for c, _, _ in COLUMNS[table]])
        steps = [
            f'Source = Parquet.Document(File.Contents(ExportsFolder & "{table}.parquet"))',
            f"Kept = Table.SelectColumns(Source, {cols})",
            f"Typed = Table.TransformColumnTypes(Kept, {{{types}}})",
        ]
    body = ",\n".join("\t\t\t\t    " + s for s in steps)
    return "\t\t\t\tlet\n" + body + "\n\t\t\t\tin\n\t\t\t\t    Typed"


WINDOW = "CALCULATE({expr}, fact_orders[in_window] = TRUE(), fact_orders[is_delivered] = TRUE())"
# table that holds the measure -> [(name, DAX, format)]
MEASURES: dict[str, list[tuple[str, str, str]]] = {
    "kpis_clean": [
        ("K1 GMV", 'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K1")', "#,0"),
        (
            "K2 Delivered orders",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K2")',
            "#,0",
        ),
        ("K3 AOV", 'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K3")', "#,0.00"),
        (
            "K4 Freight ratio",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K4")',
            "0.0%",
        ),
        ("K5 On-time rate", 'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K5")', "0.0%"),
        (
            "K6 Mean delivery days",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K6")',
            "0.00",
        ),
        (
            "K7 Avg review score",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K7")',
            "0.000",
        ),
        (
            "K8 Negative review share",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K8")',
            "0.0%",
        ),
        (
            "K9 Repeat customer rate",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K9")',
            "0.00%",
        ),
        (
            "K10 Active customers",
            'CALCULATE(SUM(kpis_clean[value]), kpis_clean[kpi_id] = "K10")',
            "#,0",
        ),
        (
            "K15 Worst-rated category",
            'CALCULATE(MIN(kpis_clean[item]), kpis_clean[kpi_id] = "K15", kpis_clean[rank] = 1)',
            "",
        ),
    ],
    "fact_orders": [
        ("On-time rate", WINDOW.format(expr="AVERAGE(fact_orders[on_time])"), "0.0%"),
        ("Mean delivery days", WINDOW.format(expr="AVERAGE(fact_orders[delivery_days])"), "0.0"),
        (
            "Avg review score",
            "CALCULATE(AVERAGE(fact_orders[review_score]), fact_orders[in_window] = TRUE())",
            "0.00",
        ),
        (
            "Reviewed orders",
            "CALCULATE(COUNTROWS(fact_orders), fact_orders[in_window] = TRUE(), "
            "KEEPFILTERS(NOT ISBLANK(fact_orders[review_score])))",
            "#,0",
        ),
        ("Delivered orders (mart)", WINDOW.format(expr="COUNTROWS(fact_orders)"), "#,0"),
    ],
    "fact_order_items": [
        ("GMV (mart)", WINDOW.format(expr="SUM(fact_order_items[price])"), "#,0"),
        (
            "GMV all statuses",
            "CALCULATE(SUM(fact_order_items[price]), fact_orders[in_window] = TRUE())",
            "#,0",
        ),
    ],
    "dq_results": [
        (
            "DQ score (mart)",
            'CALCULATE(1 - AVERAGE(dq_results[fail_share]), dq_results[layer] = "mart", '
            "dq_results[in_dq_score] = TRUE())",
            "0.00%",
        ),
        (
            "Mart checks pass",
            'CALCULATE(COUNTROWS(dq_results), dq_results[layer] = "mart", '
            'dq_results[status] = "pass") + 0',
            "0",
        ),
        (
            "Mart checks warn",
            'CALCULATE(COUNTROWS(dq_results), dq_results[layer] = "mart", '
            'dq_results[status] = "warn") + 0',
            "0",
        ),
        (
            "Mart checks fail",
            'CALCULATE(COUNTROWS(dq_results), dq_results[layer] = "mart", '
            'dq_results[status] = "fail") + 0',
            "0",
        ),
    ],
}

RELATIONSHIPS = [
    ("fact_order_items", "order_id", "fact_orders", "order_id"),
    ("fact_order_items", "product_id", "dim_product", "product_id"),
    ("fact_order_items", "seller_id", "dim_seller", "seller_id"),
    ("fact_orders", "customer_unique_id", "dim_customer", "customer_unique_id"),
    ("fact_orders", "purchase_date_key", "dim_date", "date_key"),
]


def _q(name: str) -> str:
    """Quote a TMDL object name when it is not a plain identifier."""
    return name if name.replace("_", "").isalnum() else f"'{name}'"


def table_tmdl(table: str, window: tuple[str, str]) -> str:
    out = [f"table {table}", f"\tlineageTag: {_tag('t', table)}", ""]
    for name, dax, fmt in MEASURES.get(table, []):
        out.append(f"\tmeasure {_q(name)} = {dax}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out += [f"\t\tlineageTag: {_tag('m', table, name)}", ""]
    for col, dtype, _ in COLUMNS[table]:
        numeric = dtype in ("int64", "double")
        summarize = "sum" if numeric and col in ("price", "freight_value", "value") else "none"
        out.append(f"\tcolumn {col}")
        out.append(f"\t\tdataType: {dtype}")
        if col in FORMATS:
            out.append(f"\t\tformatString: {FORMATS[col]}")
        out += [
            f"\t\tlineageTag: {_tag('c', table, col)}",
            f"\t\tsummarizeBy: {summarize}",
            f"\t\tsourceColumn: {col}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            "",
        ]
    out += [
        f"\tpartition {table} = m",
        "\t\tmode: import",
        "\t\tsource =",
        _m_source(table, window),
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(out)


def write_model(root: Path, exports: Path) -> None:
    spec = load_kpi_spec()
    window = (str(spec.params.window_start), str(spec.params.window_end))
    sm = root / f"{NAME}.SemanticModel"
    d = sm / "definition"
    (d / "tables").mkdir(parents=True)
    _json(
        sm / "definition.pbism",
        {
            "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "settings": {},
        },
    )
    _platform(sm, "SemanticModel")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n\n", "utf-8")
    tables = list(COLUMNS)
    model = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(['ExportsFolder', *tables])}",
        "",
        *[f"ref table {t}" for t in tables],
        "",
    ]
    (d / "model.tmdl").write_text("\n".join(model), "utf-8")
    folder = str(exports.resolve()).rstrip("\\/") + "\\"
    (d / "expressions.tmdl").write_text(
        f'expression ExportsFolder = "{folder}" meta [IsParameterQuery=true, Type="Text", '
        "IsParameterQueryRequired=true]\n"
        f"\tlineageTag: {_tag('e', 'ExportsFolder')}\n\n"
        "\tannotation PBI_ResultType = Text\n\n",
        "utf-8",
    )
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [
            f"relationship {_tag('r', ft, fc, tt)}",
            f"\tfromColumn: {ft}.{fc}",
            f"\ttoColumn: {tt}.{tc}",
            "",
        ]
    (d / "relationships.tmdl").write_text("\n".join(rel), "utf-8")
    for t in tables:
        (d / "tables" / f"{t}.tmdl").write_text(table_tmdl(t, window), "utf-8")


# ---------------------------------------------------------------- report

W, H = 1280, 720


def _col(table, col):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": col}}


def _meas(table, name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def _sum(table, col):
    return {"Aggregation": {"Expression": _col(table, col), "Function": 0}}


def _proj(field) -> dict:
    if "Aggregation" in field:
        inner = field["Aggregation"]["Expression"]["Column"]
        ref = f"Sum({inner['Expression']['SourceRef']['Entity']}.{inner['Property']})"
        native = f"Sum of {inner['Property']}"
    else:
        kind = next(iter(field))
        ref = f"{field[kind]['Expression']['SourceRef']['Entity']}.{field[kind]['Property']}"
        native = field[kind]["Property"]
    return {"field": field, "queryRef": ref, "nativeQueryRef": native}


def _lit(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


def visual(name, vtype, x, y, w, h, buckets, title=None, sort=None, z=0):
    v = {
        "visualType": vtype,
        "query": {
            "queryState": {
                b: {"projections": [_proj(f) for f in fields]} for b, fields in buckets.items()
            }
        },
        "drillFilterOtherVisuals": True,
    }
    if sort is not None:
        field, direction = sort
        v["query"]["sortDefinition"] = {
            "sort": [{"field": field, "direction": direction}],
            "isDefaultSort": True,
        }
    if title:
        v["visualContainerObjects"] = {
            "title": [{"properties": {"show": _lit("true"), "text": _lit(f"'{title}'")}}]
        }
    return {
        "$schema": f"{SCHEMA}/item/report/definition/visualContainer/1.0.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
        "visual": v,
    }


def _cards(prefix, measures, y=16, h=110):
    n = len(measures)
    gap = 16
    w = (W - gap * (n + 1)) // n
    cards = [
        visual(
            f"{prefix}card{i}", "card", gap + i * (w + gap), y, w, h, {"Values": [_meas(t, m)]}, z=i
        )
        for i, (t, m) in enumerate(measures)
    ]
    for c in cards:  # full numbers, not "13M"
        c["visual"]["objects"] = {"labels": [{"properties": {"labelDisplayUnits": _lit("1D")}}]}
    return cards


def pages() -> list[tuple[str, str, list[dict]]]:
    K = "kpis_clean"
    month = _col("dim_date", "year_month")
    sales = _cards(
        "s", [(K, "K1 GMV"), (K, "K2 Delivered orders"), (K, "K3 AOV"), (K, "K4 Freight ratio")]
    ) + [
        visual(
            "s_k14",
            "lineChart",
            16,
            142,
            824,
            562,
            {
                "Category": [_col("k14_monthly_gmv", "item")],
                "Y": [_sum("k14_monthly_gmv", "value")],
            },
            "K14 Monthly GMV (BRL)",
            (_col("k14_monthly_gmv", "item"), "Ascending"),
            10,
        ),
        visual(
            "s_status",
            "clusteredBarChart",
            856,
            142,
            408,
            562,
            {
                "Category": [_col("fact_orders", "status")],
                "Y": [_meas("fact_order_items", "GMV all statuses")],
            },
            "GMV by order status (all statuses, window)",
            z=11,
        ),
    ]
    delivery = _cards("d", [(K, "K5 On-time rate"), (K, "K6 Mean delivery days")]) + [
        visual(
            "d_ontime",
            "lineChart",
            16,
            142,
            616,
            276,
            {"Category": [month], "Y": [_meas("fact_orders", "On-time rate")]},
            "On-time rate by purchase month",
            (month, "Ascending"),
            10,
        ),
        visual(
            "d_days",
            "clusteredColumnChart",
            648,
            142,
            616,
            276,
            {"Category": [month], "Y": [_meas("fact_orders", "Mean delivery days")]},
            "Mean delivery days by purchase month",
            (month, "Ascending"),
            11,
        ),
        visual(
            "d_state",
            "clusteredColumnChart",
            16,
            434,
            1248,
            270,
            {
                "Category": [_col("dim_customer", "state")],
                "Y": [_meas("fact_orders", "On-time rate")],
            },
            "On-time rate by customer state",
            z=12,
        ),
    ]
    satisfaction = _cards(
        "q",
        [
            (K, "K7 Avg review score"),
            (K, "K8 Negative review share"),
            (K, "K15 Worst-rated category"),
        ],
    ) + [
        visual(
            "q_dist",
            "clusteredColumnChart",
            16,
            142,
            408,
            562,
            {
                "Category": [_col("fact_orders", "review_score")],
                "Y": [_meas("fact_orders", "Reviewed orders")],
            },
            "Review score distribution (window)",
            (_col("fact_orders", "review_score"), "Ascending"),
            10,
        ),
        visual(
            "q_month",
            "lineChart",
            440,
            142,
            824,
            270,
            {"Category": [month], "Y": [_meas("fact_orders", "Avg review score")]},
            "Average review score by purchase month",
            (month, "Ascending"),
            11,
        ),
        visual(
            "q_k15",
            "tableEx",
            440,
            428,
            824,
            276,
            {
                "Values": [
                    _col("k15_categories", "rank"),
                    _col("k15_categories", "item"),
                    _sum("k15_categories", "value"),
                ]
            },
            "K15 Eligible categories (>= 100 reviewed orders), worst first",
            (_col("k15_categories", "rank"), "Ascending"),
            12,
        ),
    ]
    customers = _cards("c", [(K, "K9 Repeat customer rate"), (K, "K10 Active customers")]) + [
        visual(
            "c_k11",
            "clusteredBarChart",
            16,
            142,
            400,
            562,
            {
                "Category": [_col("k11_top_categories", "item")],
                "Y": [_sum("k11_top_categories", "value")],
            },
            "K11 Top-10 categories by GMV",
            sort=(_sum("k11_top_categories", "value"), "Descending"),
            z=10,
        ),
        visual(
            "c_k12",
            "clusteredBarChart",
            432,
            142,
            416,
            562,
            {
                "Category": [_col("k12_top_sellers", "item")],
                "Y": [_sum("k12_top_sellers", "value")],
            },
            "K12 Top-20 sellers by GMV",
            sort=(_sum("k12_top_sellers", "value"), "Descending"),
            z=11,
        ),
        visual(
            "c_k13",
            "clusteredBarChart",
            864,
            142,
            400,
            562,
            {"Category": [_col("k13_top_states", "item")], "Y": [_sum("k13_top_states", "value")]},
            "K13 Top-5 customer states by GMV",
            sort=(_sum("k13_top_states", "value"), "Descending"),
            z=12,
        ),
    ]
    dq = _cards(
        "q",
        [
            ("dq_results", "DQ score (mart)"),
            ("dq_results", "Mart checks pass"),
            ("dq_results", "Mart checks warn"),
            ("dq_results", "Mart checks fail"),
        ],
    ) + [
        visual(
            "q_table",
            "tableEx",
            16,
            142,
            760,
            562,
            {
                "Values": [
                    _col("dq_results", c)
                    for c in (
                        "check_id",
                        "layer",
                        "dimension",
                        "n_failed",
                        "n_total",
                        "fail_share",
                        "status",
                    )
                ]
            },
            "DQ check results (clean build)",
            (_col("dq_results", "check_id"), "Ascending"),
            10,
        ),
        visual(
            "q_share",
            "clusteredBarChart",
            792,
            142,
            472,
            562,
            {
                "Category": [_col("dq_results", "check_id")],
                "Y": [_sum("dq_results", "fail_share")],
                "Series": [_col("dq_results", "layer")],
            },
            "Failure share by check and layer",
            z=11,
        ),
    ]
    return [
        ("p1sales", "1. Sales", sales),
        ("p2delivery", "2. Delivery", delivery),
        ("p3satisfaction", "3. Satisfaction", satisfaction),
        ("p4customers", "4. Customers & sellers", customers),
        ("p5dataquality", "5. Data quality", dq),
    ]


def write_report(root: Path) -> None:
    rp = root / f"{NAME}.Report"
    d = rp / "definition"
    d.mkdir(parents=True)
    _json(
        rp / "definition.pbir",
        {
            "$schema": f"{SCHEMA}/item/report/definitionProperties/1.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
        },
    )
    _platform(rp, "Report")
    _json(
        d / "version.json",
        {
            "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
            "version": "2.0.0",
        },
    )
    themes = rp / "StaticResources" / "SharedResources" / "BaseThemes"
    themes.mkdir(parents=True)
    shutil.copy(BASE_THEME, themes / BASE_THEME.name)
    _json(
        d / "report.json",
        {
            "$schema": f"{SCHEMA}/item/report/definition/report/1.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": BASE_THEME.stem,
                    "reportVersionAtImport": "5.68",
                    "type": "SharedResources",
                }
            },
            "layoutOptimization": "None",
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": BASE_THEME.stem,
                            "path": f"BaseThemes/{BASE_THEME.name}",
                            "type": "BaseTheme",
                        }
                    ],
                }
            ],
        },
    )
    ps = pages()
    _json(
        d / "pages" / "pages.json",
        {
            "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p for p, _, _ in ps],
            "activePageName": ps[0][0],
        },
    )
    for pid, display, visuals in ps:
        _json(
            d / "pages" / pid / "page.json",
            {
                "$schema": f"{SCHEMA}/item/report/definition/page/1.0.0/schema.json",
                "name": pid,
                "displayName": display,
                "displayOption": "FitToPage",
                "height": H,
                "width": W,
            },
        )
        for v in visuals:
            _json(d / "pages" / pid / "visuals" / v["name"] / "visual.json", v)


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", "utf-8")


def _platform(folder: Path, kind: str) -> None:
    _json(
        folder / ".platform",
        {
            "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": kind, "displayName": NAME},
            "config": {"version": "2.0", "logicalId": _tag("platform", kind)},
        },
    )


def write_project(out: Path = OUT_DIR, exports: Path = EXPORT_DIR) -> Path:
    for p in (out / f"{NAME}.SemanticModel", out / f"{NAME}.Report"):
        if p.exists():
            shutil.rmtree(p)
    out.mkdir(parents=True, exist_ok=True)
    write_model(out, exports)
    write_report(out)
    _json(
        out / f"{NAME}.pbip",
        {
            "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    return out / f"{NAME}.pbip"


if __name__ == "__main__":
    print(f"Wrote {write_project()}")
