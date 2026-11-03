# KPI specification

Generated from `config/kpi_spec.yaml` by `python -m dqk.config docs`. Do not edit.

Spec version 1. Window: purchase_ts in [2017-01-01, 2018-09-01). K15 minimum reviews: 100. Unmatched label: `'unknown'`.

## Decisions fixed before Stage B

1. **Time window.** All KPIs use orders with purchase_ts in [2017-01-01, 2018-09-01). 2016 has 329 orders in three months and 2018-09/10 have 20 orders and no deliveries (docs/profiling_report.md, section 4).
2. **Date anchor for K14.** purchase_ts, truncated to calendar month (YYYY-MM).
3. **K7 when an order has several reviews.** Use the single review per order kept by staging (latest review_answer_timestamp). fact_orders.review_score already holds that one value. 547 orders have more than one review in raw data.
4. **Orphan keys in ranking KPIs.** LEFT JOIN the dimension and label unmatched rows 'unknown'. The 'unknown' group keeps its value but gets rank NULL, so it never enters a top-k list. Products without a category also map to 'unknown'.
5. **K15 eligibility and ties.** Only named categories with >= 100 reviewed orders in the window. Lowest mean score wins; ties broken by category name ascending.

## Populations

- `delivered_orders`: fact_orders rows with is_delivered (status = 'delivered') and purchase_ts in the window.
- `window_orders`: fact_orders rows with purchase_ts in the window, any status.

## KPIs

| ID | Name | Type | Population | Rule | SQL |
|---|---|---|---|---|---|
| K1 | Gross merchandise value (GMV) | monetary | delivered_orders | sum of fact_order_items.price over delivered orders | `sql/kpi/k01_gmv.sql` |
| K2 | Delivered orders | count | delivered_orders | count(DISTINCT order_id) | `sql/kpi/k02_delivered_orders.sql` |
| K3 | Average order value (AOV) | ratio | delivered_orders | K1 / K2 | `sql/kpi/k03_aov.sql` |
| K4 | Freight ratio | ratio | delivered_orders | sum(freight_value) / sum(price) | `sql/kpi/k04_freight_ratio.sql` |
| K5 | On-time delivery rate | rate | delivered orders with non-null delivered_customer_ts | share with CAST(delivered_customer_ts AS DATE) <= estimated_delivery_date | `sql/kpi/k05_on_time_rate.sql` |
| K6 | Mean delivery time | duration | delivered orders with non-null delivered_customer_ts | mean(delivered_customer_ts - purchase_ts) in days (fractional) | `sql/kpi/k06_mean_delivery_days.sql` |
| K7 | Average review score | score | window_orders with non-null review_score | mean(review_score), one review per order (decision 3) | `sql/kpi/k07_avg_review_score.sql` |
| K8 | Negative review share | rate | window_orders with non-null review_score | share with review_score <= 2 | `sql/kpi/k08_negative_review_share.sql` |
| K9 | Repeat customer rate | rate | customer_unique_id with >= 1 delivered order | share with >= 2 distinct delivered orders | `sql/kpi/k09_repeat_customer_rate.sql` |
| K10 | Active customers | count | delivered_orders | count(DISTINCT customer_unique_id) | `sql/kpi/k10_active_customers.sql` |
| K11 | Top-10 categories by GMV (top 10) | ranking | delivered_orders | GMV per dim_product.category_en; orphan or missing -> 'unknown' (rank NULL) | `sql/kpi/k11_top_categories.sql` |
| K12 | Top-20 sellers by GMV (top 20) | ranking | delivered_orders | GMV per seller_id; seller_id not in dim_seller -> 'unknown' (rank NULL) | `sql/kpi/k12_top_sellers.sql` |
| K13 | Top-5 customer states by GMV (top 5) | ranking | delivered_orders | GMV per dim_customer.state; customer not in dim_customer -> 'unknown' (rank NULL). dim_customer holds one state per customer_unique_id (39 ids span several states in raw data; staging keeps the state of the latest order). | `sql/kpi/k13_top_states.sql` |
| K14 | Monthly GMV series | series | delivered_orders | GMV per strftime(purchase_ts, '%Y-%m') (decision 2) | `sql/kpi/k14_monthly_gmv.sql` |
| K15 | Worst-rated category | decision | window_orders with non-null review_score | Per named category, mean review_score over distinct reviewed orders containing that category; keep categories with >= min_reviews orders; rank ascending by mean, then name. The decision is the rank-1 item. | `sql/kpi/k15_worst_category.sql` |

## Alternative definitions (robustness only)

- **K5_all_orders** (for K5): undelivered orders count as not on time — `sql/kpi/k05b_on_time_rate_all_orders.sql`
