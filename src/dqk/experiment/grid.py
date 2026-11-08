"""Expand a grid YAML into experiment cells (code plan 4.1)."""

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


class GridConfig(BaseModel):
    name: str
    rates: list[float]
    n_seeds: int
    errors: list[ErrorEntry]


@dataclass(frozen=True)
class Cell:
    spec: ErrorSpec

    @property
    def cell_id(self) -> str:
        s = self.spec
        return f"{s.code}-{s.variant}-{s.mechanism}-{s.rate:g}"


def load_grid(path: str | Path) -> GridConfig:
    return GridConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


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
