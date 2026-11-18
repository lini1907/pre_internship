"""Run the data quality checks of config/dq_checks.yaml on one layer.

Usage: python -m dqk.dq docs   -> docs/dq_catalogue.md (adds baseline columns when
                                  results/stage_a/dq_results.csv exists)
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, model_validator

from dqk import CONFIG_DIR, DOCS_DIR, RESULTS_DIR, SQL_DIR
from dqk.db import connect, read_sql, run_sql
from dqk.tables import Tables

DQ_CHECKS = CONFIG_DIR / "dq_checks.yaml"
DQ_CHECKS_EXTENDED = CONFIG_DIR / "dq_checks_extended.yaml"

Layer = Literal["raw", "staging", "mart"]
Suite = Literal["core", "extended"]
Dimension = Literal[
    "completeness",
    "uniqueness",
    "referential_integrity",
    "validity",
    "temporal",
    "reconciliation",
    "volume",
    "semantic",
]
REF_PREFIX = "ref_"
STATUS_ORDER = {"pass": 0, "warn": 1, "fail": 2}
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class DqParams(BaseModel):
    data_start: date
    data_end: date
    payment_tolerance: float
    valid_states: list[str]
    # Extended suite (config/dq_checks_extended.yaml); None in the core suite.
    drift_z: float | None = None
    drift_min_abs: float | None = None
    price_k: float | None = None
    price_min_items: int | None = None


class Check(BaseModel):
    id: str
    name: str
    dimension: Dimension
    layers: list[Layer]
    sql: str
    warn_share: float | None = None
    fail_share: float | None = None
    in_dq_score: bool

    def reference_tables(self) -> list[str]:
        """Logical tables of a reference (prefix ref_) that this check reads."""
        names = _PLACEHOLDER.findall(read_sql(self.sql))
        return sorted(t for t in names if t.startswith(REF_PREFIX))


class DqConfig(BaseModel):
    version: int
    params: DqParams
    layers: dict[Layer, dict[str, str]]
    reference_rows: dict[Layer, dict[str, int]]
    defaults: dict[str, float]
    checks: list[Check]

    @model_validator(mode="after")
    def _check(self):
        ids = [c.id for c in self.checks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate check id")
        for c in self.checks:
            if not (SQL_DIR / c.sql).exists():
                raise ValueError(f"missing SQL file: sql/{c.sql}")
            c.warn_share = self.defaults["warn_share"] if c.warn_share is None else c.warn_share
            c.fail_share = self.defaults["fail_share"] if c.fail_share is None else c.fail_share
            if c.warn_share > c.fail_share:
                raise ValueError(f"{c.id}: warn_share > fail_share")
            for layer in c.layers:
                missing = set(_PLACEHOLDER.findall(read_sql(c.sql))) - self.layers[layer].keys()
                if missing:
                    raise ValueError(f"{c.id}: layer {layer} has no table for {sorted(missing)}")
        return self

    def layer_params(self, layer: Layer) -> dict:
        ref = self.reference_rows.get(layer, {})
        return self.params.model_dump() | {f"ref_{k}": v for k, v in ref.items()}


def load_dq_config(
    path: Path = DQ_CHECKS, suite: Suite = "core", extended_path: Path = DQ_CHECKS_EXTENDED
) -> DqConfig:
    """The core catalogue (C01-C20); with suite="extended" also C21-C24, their params and
    the reference table names (mart layer) of config/dq_checks_extended.yaml."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if suite == "extended":
        ext = yaml.safe_load(extended_path.read_text(encoding="utf-8"))
        raw["params"] = {**raw["params"], **ext["params"]}
        raw["layers"]["mart"] = {**raw["layers"]["mart"], **ext["reference"]}
        raw["checks"] = raw["checks"] + ext["checks"]
    elif suite != "core":
        raise ValueError(f"unknown suite {suite}")
    return DqConfig.model_validate(raw)


def render_sql(sql: str, table_map: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: table_map[m.group(1)], sql)


def status_of(share: float, warn_share: float, fail_share: float) -> str:
    if share > fail_share:
        return "fail"
    if share > warn_share:
        return "warn"
    return "pass"


def run_dq_checks(
    tables: Tables,
    layer: Layer,
    config: DqConfig | None = None,
    reference: Tables | None = None,
) -> pd.DataFrame:
    """One row per check that applies to ``layer``:
    check_id, layer, dimension, n_failed, n_total, fail_share, status, in_dq_score.

    ``reference`` (e.g. the last accepted mart) is registered next to ``tables`` with the
    prefix ref_. A check that reads a reference table gets status "skipped" (n_failed and
    n_total 0, fail_share NaN) when no reference is given."""
    config = config or load_dq_config()
    table_map = config.layers[layer]
    params = config.layer_params(layer)
    frames = dict(tables.frames)
    if reference is not None:
        frames |= {f"{REF_PREFIX}{n}": df for n, df in reference}
    con = connect(Tables(frames))
    rows = []
    for c in config.checks:
        if layer not in c.layers:
            continue
        if reference is None and c.reference_tables():
            rows.append(
                {
                    "check_id": c.id,
                    "layer": layer,
                    "dimension": c.dimension,
                    "n_failed": 0,
                    "n_total": 0,
                    "fail_share": float("nan"),
                    "status": "skipped",
                    "in_dq_score": c.in_dq_score,
                }
            )
            continue
        sql = render_sql(read_sql(c.sql), table_map)
        n_failed, n_total = run_sql(con, sql, params).iloc[0][["n_failed", "n_total"]]
        n_failed, n_total = int(n_failed), int(n_total)
        share = n_failed / n_total if n_total else 0.0
        rows.append(
            {
                "check_id": c.id,
                "layer": layer,
                "dimension": c.dimension,
                "n_failed": n_failed,
                "n_total": n_total,
                "fail_share": share,
                "status": status_of(share, c.warn_share, c.fail_share),
                "in_dq_score": c.in_dq_score,
            }
        )
    con.close()
    return pd.DataFrame(rows)


def dq_score(results: pd.DataFrame) -> float:
    """mean(1 - fail_share) over checks with in_dq_score (proposal 6.3)."""
    r = results[results["in_dq_score"]]
    return float((1 - r["fail_share"].clip(upper=1)).mean())


def worsened(baseline: pd.DataFrame, results: pd.DataFrame) -> pd.Series:
    """Per check: True if its status is worse than in the clean baseline (decision D3).

    A run counts as detected when any check worsened; a check that already warns on the
    clean mart only counts if it moves to fail."""
    b = baseline.set_index(["check_id", "layer"])["status"].map(STATUS_ORDER)
    r = results.set_index(["check_id", "layer"])["status"].map(STATUS_ORDER)
    return (r > b.reindex(r.index)).rename("worsened")


def detected(baseline: pd.DataFrame, results: pd.DataFrame) -> bool:
    return bool(worsened(baseline, results).any())


def render_catalogue(config: DqConfig, baseline: pd.DataFrame | None = None) -> str:
    out = [
        "# Data quality check catalogue",
        "",
        "Generated from `config/dq_checks.yaml` by `python -m dqk.dq docs`. Do not edit.",
        "",
        "Each check returns `n_failed` and `n_total`; `fail_share = n_failed / n_total`. "
        "Status is `fail` if `fail_share > fail`, `warn` if `> warn`, otherwise `pass`. "
        "DQ score = mean(1 − fail_share) over checks marked *score* "
        "(completeness, uniqueness, validity).",
        "",
        f"Parameters: data period [{config.params.data_start}, {config.params.data_end}), "
        f"payment tolerance {config.params.payment_tolerance:g} BRL, "
        f"{len(config.params.valid_states)} valid states.",
        "",
    ]
    head = "| ID | Dimension | Check | Layers | warn | fail | score | SQL |"
    sep = "|---|---|---|---|---|---|---|---|"
    if baseline is not None:
        head += " Clean mart: failed / total | share | status |"
        sep += "---|---|---|"
        base = baseline[baseline["layer"] == "mart"].set_index("check_id")
    out += [head, sep]
    for c in config.checks:
        row = (
            f"| {c.id} | {c.dimension} | {c.name} | {', '.join(c.layers)} | "
            f"{c.warn_share:g} | {c.fail_share:g} | {'yes' if c.in_dq_score else ''} | "
            f"`sql/{c.sql}` |"
        )
        if baseline is not None:
            if c.id in base.index:
                b = base.loc[c.id]
                row += f" {b.n_failed:,} / {b.n_total:,} | {b.fail_share:.3%} | {b.status} |"
            else:
                row += " | | |"
        out.append(row)
    if baseline is not None:
        layers = ", ".join(
            f"{layer}: " + ", ".join(f"{s} {n}" for s, n in g["status"].value_counts().items())
            for layer, g in baseline.groupby("layer", sort=False)
        )
        out += ["", f"Clean baseline by layer — {layers}."]
    out.append("")
    return "\n".join(out)


def render_extended(config: DqConfig, false_alarms: pd.DataFrame | None = None) -> str:
    """The "Extended suite (v1.1)" section: C21-C24, their parameters and false alarms."""
    p = config.params
    out = [
        "## Extended suite (v1.1)",
        "",
        "Generated from `config/dq_checks_extended.yaml` (`load_dq_config(suite=\"extended\")`). "
        "Not in the DQ score. C22-C24 compare the load with a reference (the last accepted "
        "load, tables `ref_dim_product`, `ref_fact_order_items`) and are `skipped` without one.",
        "",
        f"Parameters: C23 drift when |n_cur - n_exp| > {p.drift_z:g} * sqrt(n_exp) + "
        f"{p.drift_min_abs:g}; C24 band median +- {p.price_k:g} * MAD of log(price); "
        f"categories with fewer than {p.price_min_items} reference lines use global statistics.",
        "",
        "| ID | Dimension | Check | warn | fail | SQL |",
        "|---|---|---|---|---|---|",
    ]
    for c in config.checks[20:]:
        out.append(
            f"| {c.id} | {c.dimension} | {c.name} | {c.warn_share:g} | {c.fail_share:g} | "
            f"`sql/{c.sql}` |"
        )
    out += [
        "",
        "C23 and C24 thresholds: warn = 99th percentile of fail_share over 200 random "
        "split-half pairs of the clean mart, fail = 2 x warn, set before any injection run "
        "(`python -m dqk.analysis.false_alarms --calibrate`). Online Retail II uses its own "
        "C24 thresholds (`src/dqk/retail/kpi_map.yaml`).",
    ]
    if false_alarms is not None:
        out += [
            "",
            "False alarms on clean data (`results/tables/f1_false_alarms.csv`):",
            "",
            "| Dataset | Check | Method | Trials | Alarms | Rate | 95 % CI |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in false_alarms.itertuples():
            out.append(
                f"| {r.dataset} | {r.check_id} | {r.method} | {r.n_trials} | {r.n_alarms} | "
                f"{r.alarm_rate:.1%} | {r.ci_low:.1%}-{r.ci_high:.1%} |"
            )
    out.append("")
    return "\n".join(out)


def write_catalogue(results_csv: Path = RESULTS_DIR / "stage_a" / "dq_results.csv") -> Path:
    baseline = pd.read_csv(results_csv) if results_csv.exists() else None
    fa_csv = RESULTS_DIR / "tables" / "f1_false_alarms.csv"
    false_alarms = pd.read_csv(fa_csv) if fa_csv.exists() else None
    text = render_catalogue(load_dq_config(), baseline) + "\n" + render_extended(
        load_dq_config(suite="extended"), false_alarms
    )
    path = DOCS_DIR / "dq_catalogue.md"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    if sys.argv[1:] == ["docs"]:
        print(f"Wrote {write_catalogue()}")
    else:
        print(__doc__)
        sys.exit(2)
