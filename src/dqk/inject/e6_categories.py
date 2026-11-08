"""E6 category errors. Unit: product with a non-null category_en.

category_reassign  category moved to another existing category, drawn uniformly
category_spelling  same category spelt differently, which splits it in GROUP BY:
                   trailing space ('bed_bath_table '), Title_Case ('Bed_Bath_Table')
                   or UPPER ('BED_BATH_TABLE'), drawn uniformly
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from dqk.tables import Mart

VARIANTS = ("category_reassign", "category_spelling")
SPELLINGS = (
    lambda s: s + " ",
    lambda s: "_".join(w[:1].upper() + w[1:] for w in s.split("_")),
    str.upper,
)


def units(mart: Mart, variant: str) -> pd.DataFrame:
    p = mart.dim_product[mart.dim_product["category_en"].notna()]
    return pd.DataFrame(
        {"unit_id": p["product_id"].to_numpy(), "category": p["category_en"].to_numpy()}
    )


def apply(mart: Mart, variant: str, ids, rng: np.random.Generator) -> Mart:
    p = mart.dim_product.copy()
    mask = p["product_id"].isin(ids).to_numpy()
    old = p.loc[mask, "category_en"].to_numpy()
    if variant == "category_reassign":
        named = p[p["category_en"].notna()]
        cats = np.array(sorted(named["category_en"].unique()))
        pt_of = named.drop_duplicates("category_en").set_index("category_en")["category_pt"]
        own = np.searchsorted(cats, old)
        draw = rng.integers(0, len(cats) - 1, size=len(old))
        new = cats[draw + (draw >= own)]  # uniform over the other categories
        p.loc[mask, "category_en"] = new
        p.loc[mask, "category_pt"] = pt_of.reindex(new).to_numpy()
    else:
        which = rng.integers(0, len(SPELLINGS), size=len(old))
        p.loc[mask, "category_en"] = [SPELLINGS[w](s) for w, s in zip(which, old, strict=True)]
    return replace(mart, dim_product=p)
