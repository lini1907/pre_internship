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
