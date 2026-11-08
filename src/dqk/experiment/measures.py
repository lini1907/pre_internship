"""Distortion and detection measures for one run (code plan 4.4)."""

from __future__ import annotations

import math

import pandas as pd
from scipy.stats import kendalltau

from dqk.config import KpiSpec
from dqk.dq import dq_score, worsened

TAUS = (0.005, 0.01, 0.05)
SCALAR_TYPES = {"monetary", "count", "ratio", "rate", "duration", "score"}


def _tau_col(tau: float) -> str:
    return f"material_{tau:g}".replace(".", "_")


def rel_error(x0: float, xc: float) -> float:
    if x0 is None or xc is None or (isinstance(x0, float) and math.isnan(x0)):
        return math.nan
    if isinstance(xc, float) and math.isnan(xc):
        return math.inf  # KPI vanished
    if x0 == 0:
        return 0.0 if xc == 0 else math.inf
    return abs(xc - x0) / abs(x0)


def ranking_measures(clean: pd.DataFrame, corr: pd.DataFrame, k: int) -> dict:
    """clean / corr: rows of one ranking KPI (item, value, rank)."""
    top0 = clean[clean["rank"].notna() & (clean["rank"] <= k)].sort_values("rank")["item"].tolist()
    topc = corr[corr["rank"].notna() & (corr["rank"] <= k)].sort_values("rank")["item"].tolist()
    union = list(dict.fromkeys(top0 + topc))
    v0 = clean.set_index("item")["value"]
    vc = corr.set_index("item")["value"]
    a = v0.reindex(union).fillna(0.0).to_numpy(float)
    b = vc.reindex(union).fillna(0.0).to_numpy(float)
    tau = kendalltau(a, b, variant="b").statistic if len(union) >= 2 else math.nan
    return {
        "kendall_tau_b": float(tau),
        "topk_overlap": len(set(top0) & set(topc)) / k,
        "top1_flip": float(bool(top0) and bool(topc) and top0[0] != topc[0]),
        "topk_changed": float(top0 != topc),  # set or order differs
    }


def series_mapd(clean: pd.DataFrame, corr: pd.DataFrame) -> float:
    """Mean |x_c,m - x_0,m| / x_0,m over the clean months (missing month -> 0)."""
    v0 = clean.set_index("item")["value"]
    vc = corr.set_index("item")["value"].reindex(v0.index).fillna(0.0)
    v0 = v0[v0 != 0]
    return float((vc.reindex(v0.index) - v0).abs().div(v0.abs()).mean())


def kpi_measures(
    clean_kpis: pd.DataFrame, kpis: pd.DataFrame, spec: KpiSpec, taus=TAUS
) -> pd.DataFrame:
    """One row per KPI: clean_value, value, rel_error / ranking / series / decision measures,
    and material_<tau> flags.

    material: scalar KPI rel_error > tau; series MAPD > tau; ranking top-k list changed
    (any tau); decision answer changed (any tau)."""
    rows = []
    for k in spec.kpis:
        c0 = clean_kpis[clean_kpis["kpi_id"] == k.id]
        cc = kpis[kpis["kpi_id"] == k.id]
        r = {"kpi_id": k.id, "kpi_type": k.type}
        if k.type in SCALAR_TYPES:
            x0 = float(c0["value"].iloc[0]) if len(c0) else math.nan
            xc = float(cc["value"].iloc[0]) if len(cc) else math.nan
            r |= {"clean_value": x0, "value": xc, "rel_error": rel_error(x0, xc)}
            for t in taus:
                r[_tau_col(t)] = float(r["rel_error"] > t)
        elif k.type == "ranking":
            r |= ranking_measures(c0, cc, k.top_k)
            for t in taus:
                r[_tau_col(t)] = r["topk_changed"]
        elif k.type == "series":
            r["series_mapd"] = series_mapd(c0, cc)
            for t in taus:
                r[_tau_col(t)] = float(r["series_mapd"] > t)
        elif k.type == "decision":
            a0 = c0.loc[c0["rank"] == 1, "item"]
            ac = cc.loc[cc["rank"] == 1, "item"]
            a0 = a0.iloc[0] if len(a0) else None
            ac = ac.iloc[0] if len(ac) else None
            r["decision_flip"] = float(a0 != ac)
            for t in taus:
                r[_tau_col(t)] = r["decision_flip"]
        rows.append(r)
    return pd.DataFrame(rows)


def dq_measures(clean_dq: pd.DataFrame, dq: pd.DataFrame) -> pd.DataFrame:
    """One row per mart check: fail_share, status and whether it worsened vs the baseline."""
    w = worsened(clean_dq, dq).reset_index()
    out = dq[["check_id", "dimension", "n_failed", "n_total", "fail_share", "status"]].copy()
    out["clean_status"] = out["check_id"].map(clean_dq.set_index("check_id")["status"])
    out["worsened"] = w["worsened"].to_numpy()
    return out


def run_summary(kpi_m: pd.DataFrame, dq_m: pd.DataFrame, clean_dq: pd.DataFrame, taus=TAUS) -> dict:
    """Run-level flags: dq_score, dq_drop, detected, material_<tau>, silent_<tau>."""
    score_c = dq_score(clean_dq)
    score = dq_score(
        dq_m.assign(in_dq_score=dq_m["check_id"].map(clean_dq.set_index("check_id")["in_dq_score"]))
    )
    out = {
        "dq_score": score,
        "dq_drop": score_c - score,
        "detected": float(dq_m["worsened"].any()),
        "n_worsened": int(dq_m["worsened"].sum()),
        "worsened_checks": ",".join(dq_m.loc[dq_m["worsened"], "check_id"]),
    }
    for t in taus:
        col = _tau_col(t)
        material = float(kpi_m[col].fillna(0).max() > 0)
        out[col] = material
        out[col.replace("material", "silent")] = float(material and not out["detected"])
    return out


__all__ = [
    "TAUS",
    "dq_measures",
    "kpi_measures",
    "ranking_measures",
    "rel_error",
    "run_summary",
    "series_mapd",
]
