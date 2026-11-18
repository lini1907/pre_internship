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


def run() -> list[str]:
    FIGS.mkdir(parents=True, exist_ok=True)
    oof = pd.read_parquet(ML_DIR / "rq5_oof.parquet")
    auc = pd.read_csv(TABLES / "t8_rq5_auc.csv")
    imp = pd.read_csv(TABLES / "t8d_rq5_importance.csv")
    return [fig11(oof), fig12(imp), fig13(auc)]


def main(argv=None) -> int:
    for n in run():
        print("wrote", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
