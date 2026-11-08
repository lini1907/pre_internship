"""Controlled error injection into the mart (Stage B, code plan 4.1-4.2)."""

from __future__ import annotations

from types import ModuleType

from dqk.inject import (
    e1_duplicates,
    e2_orphans,
    e3_missing,
    e4_timestamps,
    e5_units,
    e6_categories,
)
from dqk.inject.sampling import rng_streams, select_units
from dqk.inject.spec import ErrorSpec, InjectionLog
from dqk.tables import Mart

INJECTORS: dict[str, ModuleType] = {
    "E1": e1_duplicates,
    "E2": e2_orphans,
    "E3": e3_missing,
    "E4": e4_timestamps,
    "E5": e5_units,
    "E6": e6_categories,
}


def unit_table(mart: Mart, code: str, variant: str):
    mod = INJECTORS[code]
    if variant not in mod.VARIANTS:
        raise ValueError(f"{code} has no variant {variant}")
    u = mod.units(mart, variant)
    return u.sort_values("unit_id", kind="stable").reset_index(drop=True)


def inject_errors(mart: Mart, spec: ErrorSpec, seed: int, units=None) -> tuple[Mart, InjectionLog]:
    """Corrupt round(rate * N) units of the clean mart; the clean mart is not modified.

    ``units`` may pass a precomputed ``unit_table(mart, code, variant)`` (it depends only
    on the clean mart, so the runner computes it once per cell)."""
    u = unit_table(mart, spec.code, spec.variant) if units is None else units
    rng_select, rng_value = rng_streams(seed, spec.code, spec.variant)
    ids = select_units(u, spec, rng_select)
    out = INJECTORS[spec.code].apply(mart, spec.variant, ids, rng_value) if len(ids) else mart
    log = InjectionLog(
        code=spec.code,
        variant=spec.variant,
        mechanism=spec.mechanism,
        rate=spec.rate,
        seed=seed,
        n_units=len(u),
        n_selected=len(ids),
        selected_ids=ids,
    )
    return out, log


__all__ = ["ErrorSpec", "InjectionLog", "INJECTORS", "inject_errors", "unit_table"]
