"""Descriptive profile of the raw layer (Deliverable 1).

Usage: python -m dqk.profiling   -> docs/profiling_report.md, docs/figures/*.png,
                                    results/stage_a/profiling.json
"""

from __future__ import annotations

import json
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from dqk import DOCS_DIR, RESULTS_DIR
from dqk.db import connect
from dqk.io import MANIFEST, ensure_olist
from dqk.pipeline import load_raw
from dqk.tables import Tables

TOP_N = 5  # top values shown for a categorical column
MAX_CATEGORICAL = 100  # above this many distinct values a column is treated as an identifier/text

# Known or suspected issues in Olist (code plan 3.2). Each query returns one count.
ISSUE_QUERIES: dict[str, tuple[str, str]] = {
    "review_id_duplicated": (
        "Review rows whose review_id appears more than once",
        "SELECT count(*) FROM order_reviews WHERE review_id IN "
        "(SELECT review_id FROM order_reviews GROUP BY 1 HAVING count(*) > 1)",
    ),
    "review_id_distinct_dup": (
        "Distinct review_id values that are duplicated",
        "SELECT count(*) FROM (SELECT review_id FROM order_reviews GROUP BY 1 HAVING count(*) > 1)",
    ),
    "orders_multi_review": (
        "Orders with more than one review",
        "SELECT count(*) FROM (SELECT order_id FROM order_reviews GROUP BY 1 HAVING count(*) > 1)",
    ),
    "orders_without_review": (
        "Orders with no review row",
        "SELECT count(*) FROM orders o WHERE NOT EXISTS "
        "(SELECT 1 FROM order_reviews r WHERE r.order_id = o.order_id)",
    ),
    "review_score_invalid": (
        "Review rows with score not in 1..5",
        "SELECT count(*) FROM order_reviews "
        "WHERE TRY_CAST(review_score AS INTEGER) IS NULL "
        "OR TRY_CAST(review_score AS INTEGER) NOT BETWEEN 1 AND 5",
    ),
    "products_no_category": (
        "Products with no category",
        "SELECT count(*) FROM products WHERE product_category_name IS NULL",
    ),
    "categories_untranslated": (
        "Distinct categories missing from the translation table",
        "SELECT count(DISTINCT p.product_category_name) FROM products p "
        "LEFT JOIN product_category_name_translation t USING (product_category_name) "
        "WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL",
    ),
    "delivered_no_delivery_date": (
        "Orders with status 'delivered' but no customer delivery date",
        "SELECT count(*) FROM orders WHERE order_status = 'delivered' "
        "AND order_delivered_customer_date IS NULL",
    ),
    "not_delivered_with_delivery_date": (
        "Orders not 'delivered' that still have a customer delivery date",
        "SELECT count(*) FROM orders WHERE order_status <> 'delivered' "
        "AND order_delivered_customer_date IS NOT NULL",
    ),
    "approved_before_purchase": (
        "Orders approved before purchase",
        "SELECT count(*) FROM orders WHERE CAST(order_approved_at AS TIMESTAMP) "
        "< CAST(order_purchase_timestamp AS TIMESTAMP)",
    ),
    "carrier_before_approved": (
        "Orders handed to carrier before approval",
        "SELECT count(*) FROM orders WHERE CAST(order_delivered_carrier_date AS TIMESTAMP) "
        "< CAST(order_approved_at AS TIMESTAMP)",
    ),
    "delivered_before_carrier": (
        "Orders delivered to customer before handed to carrier",
        "SELECT count(*) FROM orders WHERE CAST(order_delivered_customer_date AS TIMESTAMP) "
        "< CAST(order_delivered_carrier_date AS TIMESTAMP)",
    ),
    "delivered_before_purchase": (
        "Orders delivered before purchase",
        "SELECT count(*) FROM orders WHERE CAST(order_delivered_customer_date AS TIMESTAMP) "
        "< CAST(order_purchase_timestamp AS TIMESTAMP)",
    ),
    "payment_not_defined": (
        "Payment rows with payment_type = 'not_defined'",
        "SELECT count(*) FROM order_payments WHERE payment_type = 'not_defined'",
    ),
    "payment_zero": (
        "Payment rows with payment_value = 0",
        "SELECT count(*) FROM order_payments WHERE CAST(payment_value AS DOUBLE) = 0",
    ),
    "orders_without_payment": (
        "Orders with no payment row",
        "SELECT count(*) FROM orders o WHERE NOT EXISTS "
        "(SELECT 1 FROM order_payments p WHERE p.order_id = o.order_id)",
    ),
    "orders_without_items": (
        "Orders with no item row",
        "SELECT count(*) FROM orders o WHERE NOT EXISTS "
        "(SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)",
    ),
    "delivered_without_items": (
        "Delivered orders with no item row",
        "SELECT count(*) FROM orders o WHERE order_status = 'delivered' AND NOT EXISTS "
        "(SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)",
    ),
    "price_nonpositive": (
        "Item rows with price <= 0",
        "SELECT count(*) FROM order_items WHERE CAST(price AS DOUBLE) <= 0",
    ),
    "freight_zero": (
        "Item rows with freight_value = 0",
        "SELECT count(*) FROM order_items WHERE CAST(freight_value AS DOUBLE) = 0",
    ),
    "payment_mismatch_gt1": (
        "Orders where |sum(payment) - sum(price + freight)| > 1 BRL",
        "WITH p AS (SELECT order_id, sum(CAST(payment_value AS DOUBLE)) pay "
        "FROM order_payments GROUP BY 1), "
        "i AS (SELECT order_id, sum(CAST(price AS DOUBLE) + CAST(freight_value AS DOUBLE)) amt "
        "FROM order_items GROUP BY 1) "
        "SELECT count(*) FROM p JOIN i USING (order_id) WHERE abs(pay - amt) > 1",
    ),
    "customer_unique_multi_state": (
        "customer_unique_id values seen in more than one state",
        "SELECT count(*) FROM (SELECT customer_unique_id FROM customers GROUP BY 1 "
        "HAVING count(DISTINCT customer_state) > 1)",
    ),
    "item_orphan_product": (
        "Item rows whose product_id is not in products",
        "SELECT count(*) FROM order_items i WHERE NOT EXISTS "
        "(SELECT 1 FROM products p WHERE p.product_id = i.product_id)",
    ),
    "item_orphan_seller": (
        "Item rows whose seller_id is not in sellers",
        "SELECT count(*) FROM order_items i WHERE NOT EXISTS "
        "(SELECT 1 FROM sellers s WHERE s.seller_id = i.seller_id)",
    ),
}


def profile_columns(con, name: str, df: pd.DataFrame) -> pd.DataFrame:
    """One row per column: null share, distinct count, inferred kind, range or top values."""
    rows = []
    n = len(df)
    for col in df.columns:
        q = f'"{col}"'
        nulls, distinct, n_num, n_ts = con.execute(
            f"SELECT count(*) - count({q}), count(DISTINCT {q}), "
            f"count(TRY_CAST({q} AS DOUBLE)), count(TRY_CAST({q} AS TIMESTAMP)) FROM {name}"
        ).fetchone()
        non_null = n - nulls
        if non_null and n_num == non_null:
            kind = "numeric"
            lo, hi = con.execute(
                f"SELECT min(CAST({q} AS DOUBLE)), max(CAST({q} AS DOUBLE)) FROM {name}"
            ).fetchone()
            detail = f"{lo:g} – {hi:g}"
        elif non_null and n_ts == non_null:
            kind = "timestamp"
            lo, hi = con.execute(
                f"SELECT min(CAST({q} AS TIMESTAMP)), max(CAST({q} AS TIMESTAMP)) FROM {name}"
            ).fetchone()
            detail = f"{lo:%Y-%m-%d} – {hi:%Y-%m-%d}"
        elif distinct <= MAX_CATEGORICAL:
            kind = "categorical"
            top = con.execute(
                f"SELECT {q}, count(*) c FROM {name} WHERE {q} IS NOT NULL "
                f"GROUP BY 1 ORDER BY c DESC, 1 LIMIT {TOP_N}"
            ).fetchall()
            detail = ", ".join(f"{v} ({c / n:.1%})" for v, c in top)
        else:
            kind = "id/text"
            detail = ""
        rows.append(
            {
                "table": name,
                "column": col,
                "kind": kind,
                "null_share": nulls / n if n else 0.0,
                "n_distinct": distinct,
                "detail": detail,
            }
        )
    return pd.DataFrame(rows)


def monthly_orders(con) -> pd.DataFrame:
    return con.execute(
        """
        SELECT strftime(CAST(order_purchase_timestamp AS TIMESTAMP), '%Y-%m') AS year_month,
               count(*) AS orders,
               count(*) FILTER (WHERE order_status = 'delivered') AS delivered
        FROM orders GROUP BY 1 ORDER BY 1
        """
    ).df()


def category_review_counts(con) -> pd.DataFrame:
    """Reviewed orders per category, to check the >= 100 review threshold of K15."""
    return con.execute(
        """
        SELECT coalesce(p.product_category_name, 'unknown') AS category,
               count(DISTINCT r.order_id) AS reviewed_orders
        FROM order_reviews r
        JOIN order_items i USING (order_id)
        LEFT JOIN products p USING (product_id)
        GROUP BY 1 ORDER BY 2 DESC
        """
    ).df()


def make_figures(con, monthly: pd.DataFrame, out_dir) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(monthly["year_month"], monthly["orders"], color="#4C72B0", label="all orders")
    ax.bar(monthly["year_month"], monthly["delivered"], color="#55A868", label="delivered")
    ax.set_title("Orders per purchase month")
    ax.set_ylabel("orders")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.legend()
    fig.tight_layout()
    paths["orders_per_month"] = "figures/orders_per_month.png"
    fig.savefig(out_dir / "orders_per_month.png", dpi=300)
    plt.close(fig)

    price = con.execute("SELECT CAST(price AS DOUBLE) p FROM order_items").df()["p"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(price, bins=100, log=True, color="#4C72B0")
    ax.set_xscale("log")
    ax.set_title("Item price distribution (BRL, log-log)")
    ax.set_xlabel("price")
    ax.set_ylabel("items")
    fig.tight_layout()
    paths["price_distribution"] = "figures/price_distribution.png"
    fig.savefig(out_dir / "price_distribution.png", dpi=300)
    plt.close(fig)

    scores = con.execute(
        "SELECT review_score, count(*) n FROM order_reviews GROUP BY 1 ORDER BY 1"
    ).df()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(scores["review_score"].astype(str), scores["n"], color="#C44E52")
    ax.set_title("Review score distribution")
    ax.set_xlabel("score")
    ax.set_ylabel("reviews")
    fig.tight_layout()
    paths["review_scores"] = "figures/review_scores.png"
    fig.savefig(out_dir / "review_scores.png", dpi=300)
    plt.close(fig)
    return paths


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def profile(raw: Tables) -> dict:
    con = connect(raw)
    columns = pd.concat([profile_columns(con, n, df) for n, df in raw], ignore_index=True)
    issues = {
        key: {"description": desc, "count": int(con.execute(sql).fetchone()[0])}
        for key, (desc, sql) in ISSUE_QUERIES.items()
    }
    monthly = monthly_orders(con)
    cat_reviews = category_review_counts(con)
    figures = make_figures(con, monthly, DOCS_DIR / "figures")
    return {
        "tables": {n: {"rows": len(df), "columns": df.shape[1]} for n, df in raw},
        "columns": columns,
        "issues": issues,
        "monthly": monthly,
        "category_reviews": cat_reviews,
        "figures": figures,
        "con": con,
    }


def render_report(p: dict) -> str:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tables = pd.DataFrame(
        [
            {
                "table": n,
                "rows": f"{m['rows']:,}",
                "columns": m["columns"],
                "sha256 (first 12)": manifest[n]["sha256"][:12],
            }
            for n, m in p["tables"].items()
        ]
    )
    cols = p["columns"].copy()
    cols["null_share"] = cols["null_share"].map(lambda x: f"{x:.2%}")
    issues = pd.DataFrame(
        [
            {"check": k, "description": v["description"], "count": f"{v['count']:,}"}
            for k, v in p["issues"].items()
        ]
    )
    monthly = p["monthly"]
    cat = p["category_reviews"]
    eligible = cat[(cat["category"] != "unknown") & (cat["reviewed_orders"] >= 100)]

    out = [
        "# Profiling report: Olist raw layer",
        "",
        f"Generated by `python -m dqk.profiling` on {date.today():%Y-%m-%d}. "
        "All numbers are computed from the raw CSV files (every column read as VARCHAR); "
        "nothing has been cleaned yet.",
        "",
        "## 1. Tables",
        "",
        _md_table(tables),
        "",
        "## 2. Columns",
        "",
        "`kind` is inferred: a column is numeric/timestamp only if every non-null value casts. "
        f"Categorical columns (≤ {MAX_CATEGORICAL} distinct values) show the top {TOP_N} values.",
        "",
        _md_table(cols),
        "",
        "## 3. Data issues (input to staging rules, code plan 3.2)",
        "",
        _md_table(issues),
        "",
        "## 4. Orders per month",
        "",
        f"![Orders per month]({p['figures']['orders_per_month']})",
        "",
        _md_table(monthly),
        "",
        "## 5. Distributions",
        "",
        f"![Price distribution]({p['figures']['price_distribution']})",
        "",
        f"![Review scores]({p['figures']['review_scores']})",
        "",
        "## 6. Categories with enough reviews for K15",
        "",
        f"{len(eligible)} of {len(cat[cat['category'] != 'unknown'])} named categories have "
        "≥ 100 reviewed orders (raw data, all months; the KPI applies the time window).",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    ensure_olist()
    p = profile(load_raw())
    (DOCS_DIR / "profiling_report.md").write_text(render_report(p), encoding="utf-8")
    out = RESULTS_DIR / "stage_a"
    out.mkdir(parents=True, exist_ok=True)
    (out / "profiling.json").write_text(
        json.dumps(
            {
                "tables": p["tables"],
                "issues": p["issues"],
                "monthly": p["monthly"].to_dict(orient="records"),
                "columns": p["columns"].to_dict(orient="records"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {DOCS_DIR / 'profiling_report.md'}")


if __name__ == "__main__":
    main()
