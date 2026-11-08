"""Expand a grid YAML into experiment cells (code plan 4.1, 4.6).

A grid file holds either one grid (name, rates, n_seeds, errors, optional baseline) or a
list of ``scenarios`` that share the top-level defaults (robustness, code plan 4.6). Each
scenario is a grid of its own named ``<file name>/<scenario name>``, with its own baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel

from dqk.inject.spec import ErrorSpec


class ErrorEntry(BaseModel):
    code: str
    variant: str
    mechanisms: dict[str, dict]


class BaselineOptions(BaseModel):
    """How the clean baseline is built before injection (robustness, code plan 4.6).

    use_alt_kpis              report alt_definitions of kpi_spec.yaml instead of the main ones
    exclude_top_value_orders  drop this share of orders with the highest item value
    period                    keep only orders purchased in this calendar year
    """

    use_alt_kpis: bool = False
    exclude_top_value_orders: float | None = None
    period: int | None = None

    def key(self) -> str:
        return self.model_dump_json()


class GridConfig(BaseModel):
    name: str
    rates: list[float]
    n_seeds: int
    errors: list[ErrorEntry]
    baseline: BaselineOptions = BaselineOptions()


@dataclass(frozen=True)
class Cell:
    spec: ErrorSpec

    @property
    def cell_id(self) -> str:
        s = self.spec
        return f"{s.code}-{s.variant}-{s.mechanism}-{s.rate:g}"


def load_grid(path: str | Path) -> GridConfig:
    grids = load_grids(path)
    if len(grids) != 1:
        raise ValueError(f"{path} has {len(grids)} scenarios: use load_grids")
    return grids[0]


def load_grids(path: str | Path) -> list[GridConfig]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if "scenarios" not in raw:
        return [GridConfig.model_validate(raw)]
    defaults = {k: v for k, v in raw.items() if k not in ("name", "scenarios")}
    grids = [
        GridConfig.model_validate({**defaults, **sc, "name": f"{raw['name']}/{sc['name']}"})
        for sc in raw["scenarios"]
    ]
    names = [g.name for g in grids]
    if len(names) != len(set(names)):
        raise ValueError("duplicate scenario name")
    return grids


def expand(grid: GridConfig) -> list[Cell]:
    cells = [
        Cell(ErrorSpec(e.code, e.variant, mech, rate, params or {}))
        for e in grid.errors
        for mech, params in e.mechanisms.items()
        for rate in grid.rates
    ]
    ids = [c.cell_id for c in cells]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate cell id in grid")
    return cells
