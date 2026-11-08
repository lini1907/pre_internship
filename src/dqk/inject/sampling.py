"""Choose which units get corrupted (code plan 4.2).

Every unit i gets a priority key k_i = -log(u_i) / w_i (Efraimidis-Spirakis) and the
round(rate * N) units with the smallest keys are corrupted. MCAR is the case w_i = 1.

Common random numbers: u_i depends only on (seed, code, variant) and on the unit's
position in the id-sorted unit list, never on rate or mechanism. Hence
  * the units hit at 1 % are a subset of those hit at 2 %, 5 %, ... (nested), and
  * MCAR, MAR and MNAR with the same seed share u_i,
so comparisons across rates and mechanisms are paired (proposal 6.2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dqk.inject.spec import CODE_IDS, VARIANT_IDS, ErrorSpec


def rng_streams(
    seed: int, code: str, variant: str
) -> tuple[np.random.Generator, np.random.Generator]:
    """Two independent generators: one for selection (u_i), one for replacement values."""
    ss = np.random.SeedSequence([seed, CODE_IDS[code], VARIANT_IDS[variant]])
    select, value = ss.spawn(2)
    return np.random.default_rng(select), np.random.default_rng(value)


def n_to_select(rate: float, n: int) -> int:
    """round(rate * n) with halves rounded up (Python's round() rounds half to even)."""
    return int(np.floor(rate * n + 0.5))


def mar_weights(values: pd.Series, groups: list, weight: float) -> np.ndarray:
    return np.where(values.isin(groups).to_numpy(), float(weight), 1.0)


def mnar_weights(values: pd.Series, strength: float, log: bool = False) -> np.ndarray:
    """w_i = exp(strength * z_i), z the standardised value. Missing values get z = 0."""
    x = pd.to_numeric(values, errors="coerce").astype(float).to_numpy()
    if log:
        x = np.log(np.where(x > 0, x, np.nan))
    mu, sd = np.nanmean(x), np.nanstd(x)
    z = (x - mu) / sd if sd > 0 else np.zeros_like(x)
    z = np.nan_to_num(z, nan=0.0)
    return np.exp(strength * z)


def weights_for(units: pd.DataFrame, spec: ErrorSpec) -> np.ndarray:
    if spec.mechanism == "MCAR":
        return np.ones(len(units))
    p = spec.params
    if spec.mechanism == "MAR":
        return mar_weights(units[p["by"]], p["groups"], p["weight"])
    return mnar_weights(units[p["by_value"]], p["strength"], p.get("log", False))


def priority_keys(u: np.ndarray, w: np.ndarray) -> np.ndarray:
    return -np.log(u) / w


def select_units(
    units: pd.DataFrame, spec: ErrorSpec, rng_select: np.random.Generator
) -> np.ndarray:
    """Return the unit_id values to corrupt. ``units`` must be sorted by unit_id."""
    n = len(units)
    u = rng_select.random(n)
    u = np.where(u == 0.0, np.finfo(float).tiny, u)  # -log(0) guard
    keys = priority_keys(u, weights_for(units, spec))
    k = n_to_select(spec.rate, n)
    order = np.argsort(keys, kind="stable")[:k]
    return units["unit_id"].to_numpy()[np.sort(order)]
