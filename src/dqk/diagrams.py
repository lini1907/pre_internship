"""Draw the mart star schema from MART_SCHEMA.  Usage: python -m dqk.diagrams"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from dqk import DOCS_DIR
from dqk.tables import MART_SCHEMA

# Box centre (x, y) on a 16 x 10 canvas.
LAYOUT = {
    "fact_orders": (5.0, 4.5),
    "fact_order_items": (11.0, 5.0),
    "dim_customer": (5.0, 9.2),
    "dim_date": (8.0, 1.1),
    "dim_product": (11.0, 8.9),
    "dim_seller": (14.4, 1.4),
}
# (from table, from column, to table, to column)
LINKS = [
    ("fact_orders", "customer_unique_id", "dim_customer", "customer_unique_id"),
    ("fact_order_items", "order_id", "fact_orders", "order_id"),
    ("fact_order_items", "product_id", "dim_product", "product_id"),
    ("fact_order_items", "seller_id", "dim_seller", "seller_id"),
    ("fact_order_items", "purchase_date_key", "dim_date", "date_key"),
]
KEYS = {
    "order_id",
    "order_item_id",
    "customer_unique_id",
    "product_id",
    "seller_id",
    "date_key",
    "customer_key",
    "product_key",
    "seller_key",
}
ROW_H = 0.32
WIDTH = 3.6


def _box(ax, name, cols, x, y):
    h = ROW_H * (len(cols) + 1.3)
    fact = name.startswith("fact")
    ax.add_patch(
        FancyBboxPatch(
            (x - WIDTH / 2, y - h / 2),
            WIDTH,
            h,
            boxstyle="round,pad=0.04",
            lw=1.4,
            ec="#2F4B7C" if fact else "#4C8C4A",
            fc="#E8EEF7" if fact else "#EAF4E8",
        )
    )
    top = y + h / 2
    ax.text(x, top - ROW_H * 0.65, name, ha="center", va="center", weight="bold", fontsize=10)
    ax.plot([x - WIDTH / 2, x + WIDTH / 2], [top - ROW_H * 1.15] * 2, color="#888", lw=0.8)
    for i, (c, t) in enumerate(cols.items()):
        ax.text(
            x - WIDTH / 2 + 0.12,
            top - ROW_H * (1.75 + i),
            c,
            ha="left",
            va="center",
            fontsize=7.5,
            weight="bold" if c in KEYS else "normal",
        )
        ax.text(
            x + WIDTH / 2 - 0.12,
            top - ROW_H * (1.75 + i),
            t.lower(),
            ha="right",
            va="center",
            fontsize=6.5,
            color="#666",
        )


def draw(path=None):
    path = path or DOCS_DIR / "star_schema.png"
    fig, ax = plt.subplots(figsize=(13, 8.5))
    ax.set_xlim(0, 16.5)
    ax.set_ylim(-0.6, 10.6)
    ax.axis("off")
    for a, _, b, _ in LINKS:
        (x1, y1), (x2, y2) = LAYOUT[a], LAYOUT[b]
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            zorder=0,
            arrowprops=dict(arrowstyle="-|>", color="#999", lw=1.2, shrinkA=0, shrinkB=0),
        )
    for name, (x, y) in LAYOUT.items():
        _box(ax, name, MART_SCHEMA[name], x, y)
    for a, ca, b, cb in LINKS:
        (x1, y1), (x2, y2) = LAYOUT[a], LAYOUT[b]
        label = ca if ca == cb else f"{ca} → {cb}"
        ax.text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            label,
            fontsize=7,
            ha="center",
            va="center",
            bbox=dict(fc="white", ec="none", pad=1),
        )
    ax.set_title(
        "Olist mart: star schema (facts keep natural keys for orphan-key injection)", fontsize=11
    )
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(f"Wrote {draw()}")
