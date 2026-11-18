# Data quality check catalogue

Generated from `config/dq_checks.yaml` by `python -m dqk.dq docs`. Do not edit.

Each check returns `n_failed` and `n_total`; `fail_share = n_failed / n_total`. Status is `fail` if `fail_share > fail`, `warn` if `> warn`, otherwise `pass`. DQ score = mean(1 − fail_share) over checks marked *score* (completeness, uniqueness, validity).

Parameters: data period [2016-09-01, 2018-11-01), payment tolerance 1 BRL, 27 valid states.

| ID | Dimension | Check | Layers | warn | fail | score | SQL | Clean mart: failed / total | share | status |
|---|---|---|---|---|---|---|---|---|---|---|
| C01 | completeness | key columns not null (order_id; item order_id, product_id, seller_id) | staging, mart | 0 | 0.001 | yes | `sql/dq/c01_keys_not_null.sql` | 0 / 212,091 | 0.000% | pass |
| C02 | completeness | product has a translated category | staging, mart | 0.02 | 0.05 | yes | `sql/dq/c02_product_category_present.sql` | 610 / 32,951 | 1.851% | pass |
| C03 | completeness | delivered order has a customer delivery date | staging, mart | 0 | 0.001 | yes | `sql/dq/c03_delivered_has_date.sql` | 8 / 96,478 | 0.008% | warn |
| C04 | completeness | review has a score | staging, mart | 0 | 0.001 | yes | `sql/dq/c04_review_has_score.sql` | 0 / 98,673 | 0.000% | pass |
| C05 | uniqueness | order_id unique | staging, mart | 0 | 0.001 | yes | `sql/dq/c05_order_id_unique.sql` | 0 / 99,441 | 0.000% | pass |
| C06 | uniqueness | (order_id, order_item_id) unique | staging, mart | 0 | 0.001 | yes | `sql/dq/c06_order_item_unique.sql` | 0 / 112,650 | 0.000% | pass |
| C07 | uniqueness | review_id unique | staging, mart | 0.02 | 0.05 | yes | `sql/dq/c07_review_id_unique.sql` | 1,139 / 98,673 | 1.154% | pass |
| C08 | referential_integrity | item references an existing product | staging, mart | 0 | 0.001 |  | `sql/dq/c08_item_product_fk.sql` | 0 / 112,650 | 0.000% | pass |
| C09 | referential_integrity | item references an existing seller | staging, mart | 0 | 0.001 |  | `sql/dq/c09_item_seller_fk.sql` | 0 / 112,650 | 0.000% | pass |
| C10 | referential_integrity | item references an existing order | staging, mart | 0 | 0.001 |  | `sql/dq/c10_item_order_fk.sql` | 0 / 112,650 | 0.000% | pass |
| C11 | validity | price > 0 | staging, mart | 0 | 0.001 | yes | `sql/dq/c11_price_positive.sql` | 0 / 112,650 | 0.000% | pass |
| C12 | validity | freight_value >= 0 | staging, mart | 0 | 0.001 | yes | `sql/dq/c12_freight_nonnegative.sql` | 0 / 112,650 | 0.000% | pass |
| C13 | validity | review_score in 1..5 | staging, mart | 0 | 0.001 | yes | `sql/dq/c13_review_score_range.sql` | 0 / 98,673 | 0.000% | pass |
| C14 | validity | customer and seller state is one of the 27 Brazilian states | staging, mart | 0 | 0.001 | yes | `sql/dq/c14_state_valid.sql` | 0 / 99,191 | 0.000% | pass |
| C15 | temporal | approved_ts >= purchase_ts | staging, mart | 0 | 0.001 |  | `sql/dq/c15_approved_after_purchase.sql` | 0 / 99,281 | 0.000% | pass |
| C16 | temporal | delivered_customer_ts >= purchase_ts | staging, mart | 0 | 0.001 |  | `sql/dq/c16_delivered_after_purchase.sql` | 0 / 96,476 | 0.000% | pass |
| C17 | temporal | order timestamps within the data period | staging, mart | 0 | 0.001 |  | `sql/dq/c17_timestamps_in_period.sql` | 0 / 99,441 | 0.000% | pass |
| C18 | reconciliation | payment_total matches sum(price + freight) within tolerance | mart | 0.005 | 0.01 |  | `sql/dq/c18_payment_reconciles.sql` | 249 / 98,665 | 0.252% | pass |
| C19 | volume | orders row count within tolerance of the reference load | raw, staging, mart | 0.01 | 0.05 |  | `sql/dq/c19_orders_volume.sql` | 0 / 99,441 | 0.000% | pass |
| C20 | volume | order item row count within tolerance of the reference load | raw, staging, mart | 0.01 | 0.05 |  | `sql/dq/c20_items_volume.sql` | 0 / 112,650 | 0.000% | pass |

Clean baseline by layer — raw: pass 2, staging: pass 18, warn 1, mart: pass 19, warn 1.

## Extended suite (v1.1)

Generated from `config/dq_checks_extended.yaml` (`load_dq_config(suite="extended")`). Not in the DQ score. C22-C24 compare the load with a reference (the last accepted load, tables `ref_dim_product`, `ref_fact_order_items`) and are `skipped` without one.

Parameters: C23 drift when |n_cur - n_exp| > 4 * sqrt(n_exp) + 10; C24 band median +- 5 * MAD of log(price); categories with fewer than 30 reference lines use global statistics.

| ID | Dimension | Check | warn | fail | SQL |
|---|---|---|---|---|---|
| C21 | completeness | order has a customer key | 0 | 0.001 | `sql/dq/c21_customer_key_not_null.sql` |
| C22 | semantic | product category unchanged vs the reference snapshot | 0.001 | 0.01 | `sql/dq/c22_category_vs_snapshot.sql` |
| C23 | semantic | category mix of order lines within tolerance of the reference | 0.0271 | 0.0541 | `sql/dq/c23_category_mix_drift.sql` |
| C24 | semantic | price plausible within its category (log price within median +- k MAD) | 0.0192 | 0.0383 | `sql/dq/c24_price_plausible.sql` |

C23 and C24 thresholds: warn = 99th percentile of fail_share over 200 random split-half pairs of the clean mart, fail = 2 x warn, set before any injection run (`python -m dqk.analysis.false_alarms --calibrate`). Online Retail II uses its own C24 thresholds (`src/dqk/retail/kpi_map.yaml`).

False alarms on clean data (`results/tables/f1_false_alarms.csv`):

| Dataset | Check | Method | Trials | Alarms | Rate | 95 % CI |
|---|---|---|---|---|---|---|
| olist | C21 | month_vs_past | 20 | 0 | 0.0% | 0.0%-16.1% |
| olist | C21 | split_half | 200 | 0 | 0.0% | 0.0%-1.9% |
| olist | C22 | month_vs_past | 20 | 0 | 0.0% | 0.0%-16.1% |
| olist | C22 | split_half | 200 | 0 | 0.0% | 0.0%-1.9% |
| olist | C23 | month_vs_past | 20 | 19 | 95.0% | 76.4%-99.1% |
| olist | C23 | split_half | 200 | 0 | 0.0% | 0.0%-1.9% |
| olist | C24 | month_vs_past | 20 | 7 | 35.0% | 18.1%-56.7% |
| olist | C24 | split_half | 200 | 1 | 0.5% | 0.1%-2.8% |
| retail | C21 | month_vs_past | 24 | 0 | 0.0% | 0.0%-13.8% |
| retail | C21 | split_half | 200 | 0 | 0.0% | 0.0%-1.9% |
| retail | C24 | month_vs_past | 24 | 5 | 20.8% | 9.2%-40.5% |
| retail | C24 | split_half | 200 | 0 | 0.0% | 0.0%-1.9% |
