"""Incident drill (code plan v1.1, P1 and M3): realistic, deterministic incidents on the
clean data, and what the pipeline's layers report.

    python -m dqk.drill                  # all scenarios
    python -m dqk.drill --exports        # also exports_drill/<scenario>/ for Power BI

Scenarios (units chosen by rule, not sampled; the value stream of E6 has a fixed seed):
  double_load         the order file of one week (2018-05-07 .. 2018-05-13) loaded twice:
                      e1_duplicates.apply(duplicate_order) on every order of that week
  price_in_cents      one seller (rank 10 by GMV) sends prices in centavos:
                      e5_units.apply(price_x100) on every item of that seller
  category_migration  3 % of the products of the largest category (by product count)
                      re-mapped when the category tree changes: e6_categories.apply
                      (category_reassign), first 3 % of its product_ids in sorted order
  schema_drift        the source renames order_items.price to unit_price: the raw data
                      contract stops the load before staging (M3)

For the mart scenarios: KPIs, the core suite (C01-C20) and the extended suite (C21-C24,
reference = the clean mart, i.e. the last accepted load). Writes
  results/drill/<scenario>/{kpis.csv, dq_results.csv}
  results/drill/summary.csv             one row per scenario
  results/drill/kpi_deltas.csv          scenario x KPI (scalar rel. change, ranking change)
  results/drill/dbt_test_{results,summary}.csv   with --dbt: the dbt tests on each mart
  docs/figures/drill_status.png         check status: clean vs each scenario
"""

from __future__ import annotations

import argparse

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dqk import DOCS_DIR, RESULTS_DIR, ROOT  # noqa: E402
from dqk.config import load_kpi_spec  # noqa: E402
from dqk.dq import STATUS_ORDER, load_dq_config, run_dq_checks, worsened  # noqa: E402
from dqk.experiment.measures import kpi_measures  # noqa: E402
from dqk.inject import e1_duplicates, e5_units, e6_categories  # noqa: E402
from dqk.inject._common import item_key  # noqa: E402
from dqk.kpis import compute_kpis  # noqa: E402
from dqk.tables import Mart, Tables  # noqa: E402

OUT = RESULTS_DIR / "drill"
SCENARIOS = ("double_load", "price_in_cents", "category_migration", "schema_drift")
WEEK = ("2018-05-07", "2018-05-14")
SELLER_RANK = 10
CATEGORY_SHARE = 0.03
DRILL_SEED = 20261117
HEADLINE_KPIS = ("K1", "K2", "K3", "K7", "K9", "K10", "K11", "K12", "K15")


def units_double_load(mart: Mart) -> np.ndarray:
    o = mart.fact_orders
    w = (o["purchase_ts"] >= WEEK[0]) & (o["purchase_ts"] < WEEK[1])
    return np.sort(o.loc[w, "order_id"].to_numpy())


def target_seller(mart: Mart, rank: int = SELLER_RANK) -> str:
    o = mart.fact_orders
    i = mart.fact_order_items.merge(o[["order_id", "is_delivered"]], on="order_id")
    gmv = i[i["is_delivered"]].groupby("seller_id")["price"].sum()
    return gmv.sort_values(ascending=False, kind="stable").index[rank - 1]


def units_price_in_cents(mart: Mart) -> np.ndarray:
    i = mart.fact_order_items
    return np.sort(item_key(i[i["seller_id"] == target_seller(mart)]).to_numpy())


def target_category(mart: Mart) -> str:
    return mart.dim_product["category_en"].value_counts().index[0]


def units_category_migration(mart: Mart) -> np.ndarray:
    p = mart.dim_product
    ids = np.sort(p.loc[p["category_en"] == target_category(mart), "product_id"].to_numpy())
    return ids[: int(round(CATEGORY_SHARE * len(ids)))]


def corrupt(mart: Mart, scenario: str) -> tuple[Mart, int, str]:
    """(corrupted mart, number of units, description of the units)."""
    rng = np.random.default_rng(DRILL_SEED)
    if scenario == "double_load":
        ids = units_double_load(mart)
        return e1_duplicates.apply(mart, "duplicate_order", ids, rng), len(ids), (
            f"orders purchased {WEEK[0]} .. 2018-05-13"
        )
    if scenario == "price_in_cents":
        ids = units_price_in_cents(mart)
        return e5_units.apply(mart, "price_x100", ids, rng), len(ids), (
            f"items of seller {target_seller(mart)[:8]}... (rank {SELLER_RANK} by GMV)"
        )
    if scenario == "category_migration":
        ids = units_category_migration(mart)
        return e6_categories.apply(mart, "category_reassign", ids, rng), len(ids), (
            f"{CATEGORY_SHARE:.0%} of products in {target_category(mart)}"
        )
    raise ValueError(scenario)


def schema_drift() -> dict:
    """Rename order_items.price in the raw data and run the contracts (M3)."""
    from dqk.contracts import ContractError, enforce
    from dqk.io import OLIST_DIR
    from dqk.pipeline import load_raw

    raw = load_raw(OLIST_DIR)
    frames = dict(raw.frames)
    frames["order_items"] = frames["order_items"].rename(columns={"price": "unit_price"})
    msgs: list[str] = []
    try:
        enforce(Tables(frames), echo=msgs.append)
        blocked = False
    except ContractError:
        blocked = True
    return {"blocked": blocked, "messages": msgs}


def run_drill(mart: Mart, scenarios=SCENARIOS[:3]) -> dict:
    spec = load_kpi_spec()
    core, ext = load_dq_config(), load_dq_config(suite="extended")
    ref = mart.as_tables()
    clean_kpis = compute_kpis(mart, spec)
    clean_core = run_dq_checks(mart.as_tables(), "mart", core)
    clean_ext = run_dq_checks(mart.as_tables(), "mart", ext, reference=ref)
    out = {"clean": {"kpis": clean_kpis, "dq": clean_ext}}
    for s in scenarios:
        m, n_units, what = corrupt(mart, s)
        kpis = compute_kpis(m, spec)
        dq_core = run_dq_checks(m.as_tables(), "mart", core)
        dq_ext = run_dq_checks(m.as_tables(), "mart", ext, reference=ref)
        out[s] = {
            "kpis": kpis,
            "dq": dq_ext,
            "measures": kpi_measures(clean_kpis, kpis, spec),
            "worse_core": worsened(clean_core, dq_core),
            "worse_ext": worsened(clean_ext, dq_ext),
            "n_units": n_units,
            "units": what,
        }
    return out


def _fmt_checks(w: pd.Series, dq: pd.DataFrame) -> str:
    ids = [cid for (cid, _layer), x in w.items() if x]
    st = dq.set_index("check_id")["status"]
    return ", ".join(f"{c} {st[c]}" for c in ids) or "none"


def summarise(res: dict, drift: dict | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, deltas = [], []
    for s, r in res.items():
        if s == "clean":
            continue
        m = r["measures"].set_index("kpi_id")
        w_core = r["worse_core"]
        w_ext = r["worse_ext"][r["worse_ext"].index.get_level_values(0) > "C20"]
        rows.append(
            {
                "scenario": s,
                "units": r["units"],
                "n_units": r["n_units"],
                "gmv_change": m.loc["K1", "value"] / m.loc["K1", "clean_value"] - 1,
                "orders_change": m.loc["K2", "value"] / m.loc["K2", "clean_value"] - 1,
                "aov_change": m.loc["K3", "value"] / m.loc["K3", "clean_value"] - 1,
                "top10_categories_changed": bool(m.loc["K11", "topk_changed"]),
                "top10_sellers_changed": bool(m.loc["K12", "topk_changed"]),
                "worst_category_changed": bool(m.loc["K15", "decision_flip"]),
                "n_material_kpis_1pct": int(m["material_0_01"].fillna(0).sum()),
                "core_checks_reacting": _fmt_checks(w_core, r["dq"]),
                "extended_checks_reacting": _fmt_checks(w_ext, r["dq"]),
                "detected_core": bool(w_core.any()),
                "detected_ext": bool(w_core.any() or w_ext.any()),
                "contract_blocked": False,
            }
        )
        for k, x in m.iterrows():
            deltas.append(
                {
                    "scenario": s,
                    "kpi_id": k,
                    "kpi_type": x["kpi_type"],
                    "clean_value": x.get("clean_value"),
                    "value": x.get("value"),
                    "rel_error": x.get("rel_error"),
                    "series_mapd": x.get("series_mapd"),
                    "topk_changed": x.get("topk_changed"),
                    "decision_flip": x.get("decision_flip"),
                    "material_1pct": x["material_0_01"],
                }
            )
    if drift is not None:
        rows.append(
            {
                "scenario": "schema_drift",
                "units": "order_items.price renamed to unit_price in the source file",
                "n_units": 1,
                "core_checks_reacting": "not reached (load stopped)",
                "extended_checks_reacting": "not reached (load stopped)",
                "contract_blocked": drift["blocked"],
                "contract_messages": " | ".join(drift["messages"]),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(deltas)


def fig_status(res: dict, path) -> None:
    plt.rcParams["font.family"] = "Times New Roman"
    cols = [c for c in res if c != "clean"]
    clean = res["clean"]["dq"].set_index("check_id")
    ids = list(clean.index)
    mat = np.array(
        [[STATUS_ORDER.get(clean.loc[c, "status"], -1) for c in ids]]
        + [[STATUS_ORDER.get(res[s]["dq"].set_index("check_id").loc[c, "status"], -1)
            for c in ids] for s in cols]
    ).T
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(["#D1FAE5", "#FDE68A", "#FCA5A5"])
    fig, ax = plt.subplots(figsize=(6.6, 7.8))
    ax.imshow(mat, cmap=cmap, vmin=0, vmax=2, aspect="auto")
    labels = {0: "pass", 1: "warn", 2: "fail"}
    for (i, j), v in np.ndenumerate(mat):
        changed = j > 0 and v > mat[i, 0]
        ax.text(j, i, labels.get(v, "-"), ha="center", va="center", fontsize=8.5,
                weight="bold" if changed else "normal")
    ax.set_xticks(range(len(cols) + 1),
                  ["clean"] + [c.replace("_", "\n") for c in cols], fontsize=9.5)
    ax.set_yticks(range(len(ids)), ids, fontsize=8.5)
    ax.axhline(19.5, color="black", lw=1)
    ax.text(len(cols) + 0.62, 21.5, "extended\n(v1.1)", va="center", fontsize=9, rotation=90)
    ax.text(len(cols) + 0.62, 9.5, "core suite", va="center", fontsize=9, rotation=90)
    ax.xaxis.tick_top()
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)


def dbt_drill(mart: Mart, scenarios=SCENARIOS[:3]) -> pd.DataFrame:
    """Run the project's dbt tests on the clean mart and on each corrupted mart (M1).

    Each mart is written to warehouse/drill/<scenario>.duckdb (schema mart); `dbt test`
    runs the tests attached to the mart models plus the singular tests against it
    (DBT_DUCKDB_PATH). One row per scenario x test with dbt's status and failures."""
    import json
    import os
    import subprocess

    import duckdb

    exe = dbt_executable()
    if exe is None:
        raise RuntimeError("dbt not installed (requirements-dbt.txt, e.g. in .venv-dbt)")
    folder = ROOT / "warehouse" / "drill"
    folder.mkdir(parents=True, exist_ok=True)
    marts = {"clean": mart} | {s: corrupt(mart, s)[0] for s in scenarios}
    rows = []
    for name, m in marts.items():
        db = folder / f"{name}.duckdb"
        db.unlink(missing_ok=True)
        with duckdb.connect(str(db)) as con:
            con.execute("CREATE SCHEMA mart")
            for t, df in m.as_tables():
                con.register("_t", df)
                con.execute(f"CREATE TABLE mart.{t} AS SELECT * FROM _t")
                con.unregister("_t")
        env = os.environ | {"DBT_DUCKDB_PATH": str(db)}
        subprocess.run(
            [exe, "test", "--profiles-dir", ".", "--select", "path:models/mart",
             "test_type:singular"],
            cwd=ROOT / "dbt", env=env, capture_output=True, text=True,
        )
        res = json.loads((ROOT / "dbt" / "target" / "run_results.json").read_text("utf-8"))
        for r in res["results"]:
            rows.append(
                {
                    "scenario": name,
                    "test": r["unique_id"].split(".")[2],
                    "status": r["status"],
                    "failures": r.get("failures"),
                }
            )
    out = pd.DataFrame(rows)
    out["scenario"] = pd.Categorical(out["scenario"], categories=list(marts), ordered=True)
    return out.sort_values(["scenario", "test"]).reset_index(drop=True)


def dbt_summary(t: pd.DataFrame) -> pd.DataFrame:
    """Per scenario: tests passing / warning / failing, and the tests that changed status
    compared with the clean mart."""
    clean = t[t["scenario"] == "clean"].set_index("test")["status"]
    rows = []
    for s, g in t.groupby("scenario", sort=True, observed=True):
        st = g.set_index("test")["status"]
        changed = [f"{k} {v}" for k, v in st.items() if v != clean.get(k)]
        rows.append(
            {
                "scenario": s,
                "n_tests": len(g),
                "n_pass": int((g["status"] == "pass").sum()),
                "n_warn": int((g["status"] == "warn").sum()),
                "n_fail": int(g["status"].isin(["fail", "error"]).sum()),
                "changed_vs_clean": ", ".join(changed) or "none",
            }
        )
    return pd.DataFrame(rows)


def dbt_executable() -> str | None:
    import shutil
    import sys

    sub = "Scripts" if sys.platform == "win32" else "bin"
    for cand in (ROOT / ".venv-dbt" / sub / "dbt.exe", ROOT / ".venv-dbt" / sub / "dbt"):
        if cand.exists():
            return str(cand)
    return shutil.which("dbt")


def main(argv=None) -> int:
    from dqk.experiment.runner import load_clean_mart

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exports", action="store_true", help="write exports_drill/<scenario>/")
    ap.add_argument("--no-schema-drift", action="store_true")
    ap.add_argument("--dbt", action="store_true", help="also run dbt tests on each drill mart")
    args = ap.parse_args(argv)
    mart = load_clean_mart()
    if args.dbt:
        t = dbt_drill(mart)
        t.to_csv(OUT / "dbt_test_results.csv", index=False, lineterminator="\n")
        s = dbt_summary(t)
        s.to_csv(OUT / "dbt_test_summary.csv", index=False, lineterminator="\n")
        print(s.to_string(index=False))
    res = run_drill(mart)
    drift = None if args.no_schema_drift else schema_drift()
    summary, deltas = summarise(res, drift)
    OUT.mkdir(parents=True, exist_ok=True)
    for s, r in res.items():
        if s == "clean":
            continue
        (OUT / s).mkdir(exist_ok=True)
        r["kpis"].to_csv(OUT / s / "kpis.csv", index=False, lineterminator="\n")
        r["dq"].to_csv(OUT / s / "dq_results.csv", index=False, lineterminator="\n")
        if args.exports:
            from dqk.export import export_all

            m, _, _ = corrupt(mart, s)
            export_all(m, r["kpis"], r["dq"], ROOT / "exports_drill" / s)
    summary.to_csv(OUT / "summary.csv", index=False, lineterminator="\n")
    deltas.to_csv(OUT / "kpi_deltas.csv", index=False, lineterminator="\n")
    fig_status(res, DOCS_DIR / "figures" / "drill_status.png")
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(summary.T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

