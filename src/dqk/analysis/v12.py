"""Figures for RQ5 (code plan v1.2), from the tables written by dqk.ml.risk_model.

    python -m dqk.analysis.v12

fig11_rq5_roc.png                          ROC curves, run-level material, cell vs loeo split
fig12_rq5_importance_vs_traceability.png   permutation importance check x KPI group, with
                                           the guarding checks of Part 2 outlined
fig13_rq5_operating_point.png              recall vs false alarms of rules and models
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_curve  # noqa: E402

from dqk import RESULTS_DIR  # noqa: E402
from dqk.ml import ML_DIR  # noqa: E402
from dqk.ml.dataset import CORE  # noqa: E402

TABLES = RESULTS_DIR / "tables"
FIGS = RESULTS_DIR / "figures"
LABEL = {
    "detected": "Rules: any check worse",
    "dq_drop": "Aggregate DQ score",
    "n_worsened": "Rules: no. of checks worse",
    "logreg": "Logistic regression",
    "rf": "Random forest",
    "gb": "Gradient boosting (check-level)",
    "gb_mono_hybrid": "Gradient boosting, monotone (hybrid)",
    "gb_mono_agnostic": "Gradient boosting, monotone (check-agnostic)",
}
SPLIT = {
    "cell": "Seen error types (5-fold by cell)",
    "loeo": "Unseen error type (leave one out)",
    "variants": "Unseen error variants",
    "retail": "Unseen dataset (Online Retail II)",
}
GROUP_ORDER = ["monetary", "ratio", "rate", "duration", "ranking", "series", "decision"]


def fig11(oof: pd.DataFrame) -> str:
    methods = ["detected", "dq_drop", "gb", "gb_mono_agnostic"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    for ax, split in zip(axes, ["cell", "loeo"], strict=True):
        d0 = oof[(oof["split"] == split) & (oof["target"] == "material")]
        for m in methods:
            d = d0[d0["method"] == m]
            if d.empty:
                continue
            fpr, tpr, _ = roc_curve(d["y"], d["score"])
            from sklearn.metrics import roc_auc_score

            auc = roc_auc_score(d["y"], d["score"])
            ax.plot(fpr, tpr, label=f"{LABEL[m]} ({auc:.2f})",
                    drawstyle="steps-post" if m == "detected" else "default")
        ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls=":")
        ax.set_title(SPLIT[split], fontsize=10)
        ax.set_xlabel("False-alarm rate (non-material runs)")
        ax.legend(fontsize=7.5, loc="lower right")
    axes[0].set_ylabel("Recall (material runs)")
    fig.tight_layout()
    p = FIGS / "fig11_rq5_roc.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p.name


def fig12(imp: pd.DataFrame) -> str:
    d = imp[imp["group"].isin(GROUP_ORDER)]
    m = d.pivot(index="group", columns="check_id", values="importance").reindex(
        index=GROUP_ORDER, columns=CORE)
    g = d.pivot(index="group", columns="check_id", values="guards").reindex(
        index=GROUP_ORDER, columns=CORE).fillna(False).astype(bool)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    v = np.clip(m.to_numpy(float), 0, None)
    im = ax.imshow(v, cmap="Blues", aspect="auto", vmin=0, vmax=max(v.max(), 1e-6))
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            if g.iat[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                           edgecolor="#d1495b", lw=1.6))
            if v[i, j] >= 0.01:
                ax.text(j, i, f"{v[i, j]:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if v[i, j] > 0.5 * v.max() else "black")
    ax.set_xticks(range(len(CORE)), CORE, rotation=90, fontsize=8)
    ax.set_yticks(range(len(GROUP_ORDER)), GROUP_ORDER, fontsize=9)
    fig.colorbar(im, ax=ax, label="Permutation importance (AUROC drop)")
    ax.set_title("What the model relies on (shade) vs the checks that guard each KPI "
                 "group in Part 2 (red outline)", fontsize=9.5)
    fig.tight_layout()
    p = FIGS / "fig12_rq5_importance_vs_traceability.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p.name


def fig13(auc: pd.DataFrame) -> str:
    d = auc[auc["target"] == "material"]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharex=True, sharey=True)
    marker = {"detected": "s", "dq_drop": "D", "n_worsened": "s", "logreg": "o", "rf": "o",
              "gb": "o", "gb_mono_hybrid": "^", "gb_mono_agnostic": "^"}
    for ax, split in zip(axes, SPLIT, strict=True):
        for r in d[d["split"] == split].itertuples():
            ax.scatter(r.alarm_rate_nonmaterial_j, r.recall_material_j, marker=marker[r.method],
                       s=40, label=LABEL[r.method])
        ax.set_title(SPLIT[split], fontsize=9)
        ax.set_xlabel("False-alarm rate")
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Recall of material runs")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=4, fontsize=7.5, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    p = FIGS / "fig13_rq5_operating_point.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p.name


# ---------------------------------------------------------------- RQ6

ML_RUNS = RESULTS_DIR / "runs" / "ml"
CORE_IDS = [f"C{i:02d}" for i in range(1, 21)]
EXT_IDS = CORE_IDS + ["C21", "C22", "C23", "C24"]
ML_IDS = ["M01", "M02", "M03"]
SUITES = {
    "core": CORE_IDS,
    "ext": EXT_IDS,
    "ml": ML_IDS,
    "core+ml": CORE_IDS + ML_IDS,
    "all": EXT_IDS + ML_IDS,
}
SUITE_LABEL = {
    "core": "Core rules C01-C20",
    "ext": "Core + snapshot/semantic rules C21-C24",
    "ml": "ML detectors M01-M03 only",
    "core+ml": "Core rules + ML (no snapshot)",
    "all": "All",
}


def load_ml_runs() -> pd.DataFrame:
    """One row per run of the ML grid: keys, material_0_01 and detected_<suite>."""
    from dqk.analysis.stats import load_results

    parts = []
    for scen in ("olist_ml", "olist_ml_lowrate", "retail_ml"):
        folder = ML_RUNS / scen
        if not folder.exists():
            continue
        g = load_results(folder, with_dq=True)
        w = g.dq.pivot_table(index=["cell_id", "seed"], columns="check_id",
                             values="worsened", aggfunc="max").astype(float)
        r = g.runs.set_index(["cell_id", "seed"])
        for s, ids in SUITES.items():
            cols = [c for c in ids if c in w]
            r[f"detected_{s}"] = w[cols].fillna(0).max(axis=1) if cols else 0.0
        for c in ML_IDS + ["C18", "C22", "C23", "C24"]:
            r[f"w_{c}"] = w[c] if c in w else np.nan
        r["dataset"] = "retail" if scen.startswith("retail") else "olist"
        parts.append(r.reset_index())
    return pd.concat(parts, ignore_index=True)


def rq6_silent(runs: pd.DataFrame, tau: str = "material_0_01") -> pd.DataFrame:
    """Silent-error rate (material and not detected, over all runs) per cell and suite."""
    from dqk.analysis.stats import wilson

    rows = []
    keys = ["dataset", "code", "variant", "mechanism", "rate"]
    for k, d in runs.groupby(keys, sort=False):
        row = dict(zip(keys, k, strict=True)) | {"n": len(d), "material": d[tau].mean()}
        for s in SUITES:
            silent = ((d[tau] == 1) & (d[f"detected_{s}"] == 0))
            row[f"silent_{s}"] = silent.mean()
            lo, hi = wilson(int(silent.sum()), len(d))
            row[f"silent_{s}_lo"], row[f"silent_{s}_hi"] = lo, hi
        for c in ML_IDS + ["C18", "C22", "C23", "C24"]:
            row[f"react_{c}"] = d[f"w_{c}"].mean()
        rows.append(row)
    return pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)


def fig14(t: pd.DataFrame) -> str:
    """Silent rate by suite for the error types that are silent in the core suite."""
    panels = [
        ("olist", "E6", "category_reassign", "Olist: category mislabels (E6)"),
        ("olist", "E5", "price_x100", "Olist: prices x100 (E5)"),
        ("retail", "E5", "price_x100", "Online Retail II: prices x100 (E5)"),
        ("retail", "E3", "missing_customer_id", "Online Retail II: missing customer (E3)"),
    ]
    suites = ["core", "ext", "core+ml"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.8), sharey=True)
    for ax, (ds, code, var, title) in zip(axes, panels, strict=True):
        d = t[(t["dataset"] == ds) & (t["code"] == code) & (t["variant"] == var)]
        d = d.groupby("rate")[[f"silent_{s}" for s in suites]].mean()
        x = np.arange(len(d))
        for j, s in enumerate(suites):
            ax.bar(x + (j - 1) * 0.27, d[f"silent_{s}"], 0.27, label=SUITE_LABEL[s])
        ax.set_xticks(x, [f"{r:.2%}".rstrip("0").rstrip(".") for r in d.index], fontsize=7.5,
                      rotation=45)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Error rate")
    axes[0].set_ylabel("Silent runs (material, not detected)")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    p = FIGS / "fig14_rq6_silent_by_suite.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p.name


def fig15(t: pd.DataFrame, fa: pd.DataFrame, fa_rules: pd.DataFrame) -> str:
    """Each check as a point: share of runs it reacts to at a 1 % error rate (its target
    error) against its false-alarm rate when compared with past months."""
    target = {"C22": ("olist", "E6"), "C23": ("olist", "E6"), "M01": ("olist", "E6"),
              "C24": ("retail", "E5"), "M02": ("retail", "E5"), "M03": ("retail", "E5")}
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    for c, (ds, code) in target.items():
        d = t[(t["dataset"] == ds) & (t["code"] == code) & (t["rate"] == 0.01)]
        det = d[f"react_{c}"].mean()
        src = fa if c.startswith("M") else fa_rules
        f = src[(src["dataset"] == ds) & (src["check_id"] == c)
                & (src["method"] == "month_vs_past")]
        if f.empty or np.isnan(det):
            continue
        ax.scatter(f["rate"].iat[0], det, s=60, marker="^" if c.startswith("M") else "s",
                   color="#d1495b" if c.startswith("M") else "#30638e")
        ax.annotate(f"{c} ({'Olist' if ds == 'olist' else 'Retail'})",
                    (f["rate"].iat[0], det), textcoords="offset points", xytext=(6, 4),
                    fontsize=8)
    ax.set_xlabel("False-alarm rate, month vs past (clean data)")
    ax.set_ylabel("Reacts at 1 % error rate (target error)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(alpha=0.3)
    ax.set_title("Rules (squares) vs ML detectors (triangles)", fontsize=10)
    fig.tight_layout()
    p = FIGS / "fig15_rq6_detection_vs_false_alarm.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p.name


def run_rq6() -> list[str]:
    runs = load_ml_runs()
    t = rq6_silent(runs)
    t.to_csv(TABLES / "t9b_rq6_silent.csv", index=False)
    cards = [pd.read_csv(ML_DIR / f"model_card_{d}.csv", index_col=0)["value"].rename(d)
             for d in ("olist", "retail") if (ML_DIR / f"model_card_{d}.csv").exists()]
    pd.concat(cards, axis=1).to_csv(TABLES / "t9_rq6_model_card.csv")
    fa = pd.read_csv(TABLES / "f2_ml_false_alarms.csv")
    fa_rules = pd.read_csv(TABLES / "f1_false_alarms.csv")
    fa_rules = fa_rules.rename(columns={"alarm_rate": "rate"})
    return ["t9b_rq6_silent.csv", "t9_rq6_model_card.csv", fig14(t), fig15(t, fa, fa_rules)]


def run() -> list[str]:
    FIGS.mkdir(parents=True, exist_ok=True)
    oof = pd.read_parquet(ML_DIR / "rq5_oof.parquet")
    auc = pd.read_csv(TABLES / "t8_rq5_auc.csv")
    imp = pd.read_csv(TABLES / "t8d_rq5_importance.csv")
    out = [fig11(oof), fig12(imp), fig13(auc)]
    if ML_RUNS.exists():
        out += run_rq6()
    return out


def main(argv=None) -> int:
    for n in run():
        print("wrote", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
