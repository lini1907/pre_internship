"""Online Retail II -> the Olist mart schema (code plan 4.7).

    python -m dqk.retail.adapter                  # download if needed, build, write docs
    python -m dqk.retail.adapter --skip-download

Writes data/retail/online_retail_ii.parquet (both Excel sheets, cached because reading the
.xlsx takes about a minute), data/retail/MANIFEST.json, warehouse/retail.duckdb (schemas
staging and mart) and docs/retail_adapter.md. KPI and DQ subsets: src/dqk/retail/kpi_map.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from dqk import DATA_DIR, DOCS_DIR, ROOT
from dqk.config import KpiSpec, load_kpi_spec
from dqk.db import connect, read_sql
from dqk.dq import DqConfig, load_dq_config, run_dq_checks
from dqk.io import sha256
from dqk.pipeline import write_schema
from dqk.tables import MART_SCHEMA, Mart, Tables

KPI_MAP = Path(__file__).with_name("kpi_map.yaml")
RETAIL_DIR = DATA_DIR / "retail"
ZIP_PATH = RETAIL_DIR / "online_retail_ii.zip"
PARQUET = RETAIL_DIR / "online_retail_ii.parquet"
MANIFEST = RETAIL_DIR / "MANIFEST.json"
RETAIL_WAREHOUSE = ROOT / "warehouse" / "retail.duckdb"

# Build order: facts first, the dimensions read stg_retail_lines / fact_orders.
STAGING = ["stg_retail_lines"]
MART = ["fact_orders", "fact_order_items", "dim_customer", "dim_product", "dim_seller", "dim_date"]
_DTYPES = {"Invoice": str, "StockCode": str, "Description": str, "Country": str}


def load_kpi_map(path: Path = KPI_MAP) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def kpi_map_hash(path: Path = KPI_MAP) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- KPI / DQ subsets


def retail_kpi_spec(spec: KpiSpec | None = None, kmap: dict | None = None) -> KpiSpec:
    """The frozen KPI spec restricted to the KPIs that apply, with the retail window."""
    spec = spec or load_kpi_spec()
    kmap = kmap or load_kpi_map()
    keep = [k["id"] for k in kmap["kpis"]]
    unknown = set(keep) - {k.id for k in spec.kpis}
    if unknown:
        raise ValueError(f"kpi_map lists unknown KPIs: {sorted(unknown)}")
    params = spec.params.model_copy(update=kmap["kpi_params"])
    return spec.model_copy(
        update={"params": params, "kpis": [k for k in spec.kpis if k.id in keep]}
    )


def retail_dq_config(
    cfg: DqConfig | None = None, kmap: dict | None = None, suite: str = "core"
) -> DqConfig:
    """dq_checks.yaml restricted to the checks that apply, with retail params and the
    retail reference row counts. Thresholds stay those of the Olist catalogue.
    suite="extended" adds dq.checks_extended of kpi_map.yaml (C21, C24), with the C24
    thresholds of dq.thresholds_extended (calibrated on clean Online Retail II)."""
    cfg = cfg or load_dq_config(suite=suite)
    dq = (kmap or load_kpi_map())["dq"]
    keep = list(dq["checks"]) + (list(dq.get("checks_extended", [])) if suite == "extended" else [])
    over = dq.get("thresholds_extended", {}) if suite == "extended" else {}
    unknown = set(keep) - {c.id for c in cfg.checks}
    if unknown:
        raise ValueError(f"kpi_map lists unknown checks: {sorted(unknown)}")
    params = cfg.params.model_copy(
        update={
            k: (pd.Timestamp(v).date() if k.startswith("data_") else v)
            for k, v in dq["params"].items()
        }
    )
    return cfg.model_copy(
        update={
            "params": params,
            "reference_rows": dq["reference_rows"],
            "checks": [
                c.model_copy(update=over.get(c.id, {})) for c in cfg.checks if c.id in keep
            ],
        }
    )


# ---------------------------------------------------------------- ingestion


def download_retail(url: str | None = None, dest: Path = ZIP_PATH) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = url or load_kpi_map()["source"]["url"]
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, dest)
    return dest


def read_xlsx(archive: Path = ZIP_PATH) -> pd.DataFrame:
    """Both sheets of the workbook, concatenated, with sheet name and source row number."""
    name = load_kpi_map()["source"]["file"]
    with zipfile.ZipFile(archive) as z, z.open(name) as f:
        sheets = pd.read_excel(f, sheet_name=None, dtype=_DTYPES)
    df = pd.concat([s.assign(sheet=k) for k, s in sheets.items()], ignore_index=True)
    df.insert(0, "src_row", range(1, len(df) + 1))
    return df


def ensure_retail(skip_download: bool = False) -> pd.DataFrame:
    """Raw lines from the Parquet cache, (re)built from the zip when missing. The manifest
    records the zip's SHA-256 on first run and stops the build if it changes later."""
    if not skip_download:
        download_retail()
    digest = sha256(ZIP_PATH)
    if MANIFEST.exists():
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if expected["sha256"] != digest:
            raise RuntimeError(f"{ZIP_PATH.name} changed since {MANIFEST.name} was written")
    if not PARQUET.exists():
        read_xlsx().to_parquet(PARQUET, index=False)
    raw = pd.read_parquet(PARQUET)
    if not MANIFEST.exists():
        MANIFEST.write_text(
            json.dumps(
                {
                    "file": ZIP_PATH.name,
                    "sha256": digest,
                    "rows": len(raw),
                    "rows_by_sheet": raw["sheet"].value_counts().sort_index().to_dict(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return raw


# ---------------------------------------------------------------- build


def build_retail(raw: pd.DataFrame) -> tuple[Tables, Mart, pd.DataFrame]:
    """raw lines -> (staging, mart, rows left after each cleaning rule)."""
    con = connect(Tables({"raw_retail": raw}))
    rules = con.execute(read_sql("retail/rule_counts.sql")).df()
    for name in STAGING + MART:
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {read_sql(f'retail/{name}.sql')}")
    staging = Tables({n: con.execute(f"SELECT * FROM {n}").df() for n in STAGING})
    frames = {n: con.execute(f"SELECT * FROM {n}").df() for n in MART_SCHEMA}
    con.close()
    for name, cols in MART_SCHEMA.items():
        if list(frames[name].columns) != list(cols):
            raise RuntimeError(f"{name}: columns {list(frames[name].columns)} != {list(cols)}")
    rules["removed"] = (-rules["rows_left"].diff()).fillna(0).astype(int)
    return staging, Mart(**frames), rules


def write_warehouse(staging: Tables, mart: Mart, path: Path = RETAIL_WAREHOUSE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    write_schema(staging, "staging", con)
    write_schema(mart.as_tables(), "mart", con)
    con.close()


def load_retail_mart(path: Path = RETAIL_WAREHOUSE) -> Mart:
    con = duckdb.connect(str(path), read_only=True)
    mart = Mart(**{n: con.execute(f"SELECT * FROM mart.{n}").df() for n in MART_SCHEMA})
    con.close()
    return mart


# ---------------------------------------------------------------- docs


def _table(df: pd.DataFrame) -> list[str]:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append(
            "| "
            + " | ".join(
                f"{v:,.4g}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)
                for v in r
            )
            + " |"
        )
    return out


def render_doc(rules: pd.DataFrame, mart: Mart, kpis: pd.DataFrame, dq: pd.DataFrame) -> str:
    kmap = load_kpi_map()
    p = kmap["kpi_params"]
    ref = kmap["dq"]["reference_rows"]["mart"]
    o, i = mart.fact_orders, mart.fact_order_items
    out = [
        "# Online Retail II adapter",
        "",
        "Generated by `python -m dqk.retail.adapter`. Do not edit. "
        "Mapping and subsets: `src/dqk/retail/kpi_map.yaml`; SQL: `sql/retail/`.",
        "",
        f"Source: {kmap['source']['citation']} {kmap['source']['url']} "
        f"({kmap['source']['license']}).",
        "",
        "## Cleaning rules (applied in order)",
        "",
        *_table(rules[["rule", "description", "removed", "rows_left"]]),
        "",
        "## Mart",
        "",
        f"- fact_orders: {len(o):,} invoices, {o['purchase_ts'].min()} to {o['purchase_ts'].max()}",
        f"- fact_order_items: {len(i):,} lines",
        f"- dim_customer: {len(mart.dim_customer):,} customers in "
        f"{mart.dim_customer['state'].nunique()} countries",
        f"- dim_product: {len(mart.dim_product):,} stock codes",
        f"- reference rows in kpi_map.yaml: orders {ref['orders']:,}, items {ref['items']:,}"
        + (
            ""
            if (ref["orders"], ref["items"]) == (len(o), len(i))
            else "  **(differ from this build: update kpi_map.yaml)**"
        ),
        "",
        f"## KPIs on the clean mart (window [{p['window_start']}, {p['window_end']}))",
        "",
    ]
    meaning = {k["id"]: k["retail"] for k in kmap["kpis"]}
    scalar = kpis[kpis["item"].isna()]
    out += _table(
        pd.DataFrame(
            {
                "KPI": scalar["kpi_id"],
                "meaning": scalar["kpi_id"].map(meaning),
                "value": scalar["value"].astype(float),
            }
        )
    )
    for kid in ("K11", "K13"):
        top = kpis[(kpis["kpi_id"] == kid) & kpis["rank"].notna()].head(5)
        out += [
            "",
            f"{kid} ({meaning[kid]}), first 5: "
            + ", ".join(f"{r.item} ({r.value:,.0f})" for r in top.itertuples()),
        ]
    out += [
        "",
        "Not applicable: " + "; ".join(f"{k} {v}" for k, v in kmap["not_applicable"].items()) + ".",
        "",
    ]
    out += ["## DQ checks on the clean mart", ""]
    out += _table(dq[["check_id", "dimension", "n_failed", "n_total", "fail_share", "status"]])
    out += [
        "",
        "Not applicable: "
        + "; ".join(f"{k} {v}" for k, v in kmap["dq"]["not_applicable"].items())
        + ".",
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    from dqk.kpis import compute_kpis

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args(argv)
    raw = ensure_retail(args.skip_download)
    staging, mart, rules = build_retail(raw)
    write_warehouse(staging, mart)
    kpis = compute_kpis(mart, retail_kpi_spec())
    dq = run_dq_checks(mart.as_tables(), "mart", retail_dq_config())
    doc = DOCS_DIR / "retail_adapter.md"
    doc.write_text(render_doc(rules, mart, kpis, dq), encoding="utf-8", newline="\n")
    print(rules.to_string(index=False))
    print(f"mart: {len(mart.fact_orders):,} orders, {len(mart.fact_order_items):,} items")
    print(dq[["check_id", "fail_share", "status"]].to_string(index=False))
    print(f"wrote {RETAIL_WAREHOUSE} and {doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
