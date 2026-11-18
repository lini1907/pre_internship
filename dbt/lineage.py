"""Draw the dbt lineage graph from target/manifest.json (code plan v1.1, M1).

    cd dbt && dbt docs generate --profiles-dir . && cd ..
    python dbt/lineage.py            # -> docs/figures/dbt_lineage.png

Three columns: raw sources and the seed, staging models, mart models. Matplotlib only,
so the figure does not depend on the dbt docs web page.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "dbt" / "target" / "manifest.json"
OUT = ROOT / "docs" / "figures" / "dbt_lineage.png"

COLORS = {"source": "#dbe7f3", "seed": "#f3e6d0", "staging": "#dcefdc", "mart": "#f6d8d8"}
EDGE = {"source": "#4a78a8", "seed": "#b07a2a", "staging": "#3f8a3f", "mart": "#a84a4a"}


def load_graph(path: Path = MANIFEST):
    m = json.loads(path.read_text(encoding="utf-8"))
    nodes, edges = {}, []
    for uid, s in m["sources"].items():
        nodes[uid] = ("source", s["name"])
    for uid, n in m["nodes"].items():
        if n["resource_type"] == "seed":
            nodes[uid] = ("seed", n["name"])
        elif n["resource_type"] == "model":
            nodes[uid] = (n["config"]["schema"] or "mart", n["name"])
    for uid, n in m["nodes"].items():
        if n["resource_type"] == "model":
            edges += [(p, uid) for p in n["depends_on"]["nodes"] if p in nodes]
    used = {a for a, _ in edges} | {b for _, b in edges}
    return {k: v for k, v in nodes.items() if k in used}, edges


def draw(nodes, edges, out: Path = OUT) -> Path:
    cols = {"source": 0, "seed": 0, "staging": 1, "mart": 2}
    groups: dict[int, list[str]] = {0: [], 1: [], 2: []}
    order = {"source": 0, "seed": 1, "staging": 0, "mart": 0}
    for uid, (kind, _name) in sorted(nodes.items(), key=lambda kv: (order[kv[1][0]], kv[1][1])):
        groups[cols[kind]].append(uid)
    n_max = max(len(v) for v in groups.values())
    pos = {}
    for c, uids in groups.items():
        top = (n_max - len(uids)) / 2
        for i, uid in enumerate(uids):
            pos[uid] = (c * 4.2, -(top + i))
    plt.rcParams["font.family"] = "Times New Roman"
    fig, ax = plt.subplots(figsize=(11, 0.55 * n_max + 1.2))
    w, h = 2.9, 0.62
    for a, b in edges:
        (x0, y0), (x1, y1) = pos[a], pos[b]
        ax.annotate(
            "",
            xy=(x1 - w / 2, y1),
            xytext=(x0 + w / 2, y0),
            arrowprops={"arrowstyle": "-|>", "color": EDGE[nodes[a][0]], "lw": 0.8,
                        "alpha": 0.7, "shrinkA": 0, "shrinkB": 2},
        )
    for uid, (kind, name) in nodes.items():
        x, y = pos[uid]
        ax.add_patch(
            FancyBboxPatch(
                (x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                fc=COLORS[kind], ec="#555555", lw=0.6,
            )
        )
        label = f"raw.{name}" if kind == "source" else (f"seed: {name}" if kind == "seed" else name)
        ax.text(x, y, label, ha="center", va="center", fontsize=9)
    for c, title in enumerate(["Sources (raw) and seed", "Staging models", "Mart models"]):
        ax.text(c * 4.2, 0.9, title, ha="center", va="bottom", fontsize=11, weight="bold")
    ax.set_xlim(-w / 2 - 0.3, 2 * 4.2 + w / 2 + 0.3)
    ax.set_ylim(-n_max + 0.3, 1.5)
    ax.axis("off")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


if __name__ == "__main__":
    if not MANIFEST.exists():
        print("run `dbt docs generate --profiles-dir .` in dbt/ first")
        sys.exit(1)
    print(f"Wrote {draw(*load_graph())}")
