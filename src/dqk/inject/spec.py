"""Error specification and injection log (code plan 4.1-4.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

Mechanism = Literal["MCAR", "MAR", "MNAR"]

# Stable integer ids feed np.random.SeedSequence. Never renumber: changing an id changes
# every random draw of that error. Append new codes / variants at the end.
CODE_IDS: dict[str, int] = {"E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5, "E6": 6}
VARIANT_IDS: dict[str, int] = {
    "duplicate_order": 1,
    "duplicate_order_rekeyed": 2,
    "orphan_product": 3,
    "orphan_seller": 4,
    "missing_delivery_date": 5,
    "missing_review_score": 6,
    "missing_category": 7,
    "tz_shift_3h": 8,
    "day_month_swap": 9,
    "price_x100": 10,
    "price_div100": 11,
    "category_reassign": 12,
    "category_spelling": 13,
}


@dataclass(frozen=True)
class ErrorSpec:
    """One error condition: what to corrupt, how units are chosen, and how many.

    ``params`` holds the mechanism settings:
      MCAR: {}
      MAR:  {by: <unit attribute>, groups: [...], weight: w}   w_i = w in groups, else 1
      MNAR: {by_value: <numeric attribute>, strength: s, log: bool}   w_i = exp(s * z_i)
    """

    code: str
    variant: str
    mechanism: Mechanism
    rate: float
    params: dict = field(default_factory=dict, hash=False, compare=False)

    def __post_init__(self):
        if self.code not in CODE_IDS:
            raise ValueError(f"unknown error code {self.code}")
        if self.variant not in VARIANT_IDS:
            raise ValueError(f"unknown variant {self.variant}")
        if not 0.0 <= self.rate <= 1.0:
            raise ValueError(f"rate must be in [0, 1], got {self.rate}")
        if self.mechanism == "MAR" and not {"by", "groups", "weight"} <= self.params.keys():
            raise ValueError("MAR needs by, groups, weight")
        if self.mechanism == "MNAR" and not {"by_value", "strength"} <= self.params.keys():
            raise ValueError("MNAR needs by_value, strength")


@dataclass
class InjectionLog:
    code: str
    variant: str
    mechanism: str
    rate: float
    seed: int
    n_units: int
    n_selected: int
    selected_ids: np.ndarray

    @property
    def achieved_rate(self) -> float:
        return self.n_selected / self.n_units if self.n_units else 0.0
