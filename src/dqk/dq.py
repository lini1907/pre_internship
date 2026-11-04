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

Layer = Literal["raw", "staging", "mart"]
Dimension = Literal[
    "completeness",
    "uniqueness",
    "referential_integrity",
    "validity",
    "temporal",
    "reconciliation",
    "volume",
]
STATUS_ORDER = {"pass": 0, "warn": 1, "fail": 2}
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class DqParams(BaseModel):
    data_start: date
    data_end: date
    payment_tolerance: float
    valid_states: list[str]


class Check(BaseModel):
    id: str
    name: str
    dimension: Dimension
    layers: list[Layer]
    sql: str
    warn_share: float | None = None
    fail_share: float | None = None
    in_dq_score: bool


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


def load_dq_config(path: Path = DQ_CHECKS) -> DqConfig:
    return DqConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def render_sql(sql: str, table_map: dict[str, str]) -> str:
    return _PLACEHOLDER.sub(lambda m: table_map[m.group(1)], sql)


def status_of(share: float, warn_share: float, fail_share: float) -> str:
    if share > fail_share:
        return "fail"
    if share > warn_share:
        return "warn"
    return "pass"


def run_dq_checks(tables: Tables, layer: Layer, config: DqConfig | None = None) -> pd.DataFrame:
    """One row per check that applies to ``layer``:
    check_id, layer, dimension, n_failed, n_total, fail_share, status, in_dq_score."""
    config = config or load_dq_config()
    table_map = config.layers[layer]
    params = config.layer_params(layer)
    con = connect(tables)
    rows = []
    for c in config.checks:
        if layer not in c.layers:
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


def write_catalogue(results_csv: Path = RESULTS_DIR / "stage_a" / "dq_results.csv") -> Path:
    baseline = pd.read_csv(results_csv) if results_csv.exists() else None
    path = DOCS_DIR / "dq_catalogue.md"
    path.write_text(render_catalogue(load_dq_config(), baseline), encoding="utf-8")
    return path


if __name__ == "__main__":
    if sys.argv[1:] == ["docs"]:
        print(f"Wrote {write_catalogue()}")
    else:
        print(__doc__)
        sys.exit(2)
