# Cleaning log

Every cleaning decision taken in `sql/staging/` and `sql/mart/` (code plan 3.2). Counts are
from the raw layer (`docs/profiling_report.md`, section 3) and the clean build of
2026-11-03. Used by report Chapter 4 and the paper's threats to validity.

General rule: staging casts with `TRY_CAST` (a value that does not parse becomes NULL and is
counted by the DQ checks), trims and normalises case, and keeps one row per key. It does
**not** drop or repair records that are plausible business events; those stay in the mart
and either pass the DQ checks or form the documented clean baseline.

| # | Issue | Rows affected | Handling | Reason |
|---|---|---|---|---|
| 1 | Orders with several reviews | 547 orders, 551 extra review rows | `stg_order_reviews` keeps the review with the latest `review_answer_timestamp`, ties by `review_id` | KPI decision 3: one review per order for K7, K8, K15 |
| 2 | `review_id` shared by several orders | 1,139 review rows after step 1 (1.15 %) | Kept | One review covering several orders of one purchase is a real event. C07 thresholds (warn 2 %, fail 5 %) sit above this level |
| 3 | Orders without review | 768 | `fact_orders.review_id`, `review_score` NULL | Not an error; K7/K8 use reviewed orders only |
| 4 | Products without category | 610 products (1,603 items) | `category_pt`, `category_en` NULL in the mart; KPIs map to `'unknown'` | KPI decision 4. C02 thresholds (warn 2 %, fail 5 %) sit above the 1.85 % level |
| 5 | Categories missing from translation table | 2 categories, 13 products | Added in `config/category_translation_extra.csv` (`pc_gamer`, `portable_kitchen_food_preparers`) | Otherwise 13 products would fall into `'unknown'` |
| 6 | Source column typo `product_name_lenght`, `product_description_lenght` | all products | Renamed to `*_length` | Readability |
| 7 | `customer_unique_id` in several states | 39 persons | `dim_customer.state` = state of the latest order | One state per person for K13 |
| 8 | Delivered orders without customer delivery date | 8 | Kept, `delivered_customer_ts` NULL; excluded from K5/K6 by their population | Real missing value. Check C03 warns on the clean mart (baseline) |
| 9 | Non-delivered orders with a delivery date | 6 | Kept; `is_delivered` follows `status` only | Status is the business definition of "delivered" |
| 10 | Carrier date before approval | 1,359 | Kept | Plausible (approval recorded late); no KPI uses the carrier date. Not a DQ check |
| 11 | Delivered to customer before carrier | 23 | Kept | Same as 10 |
| 12 | Payment rows `not_defined` / value 0 | 3 / 9 | Kept and summed into `payment_total` | Do not change any order total by more than tolerance |
| 13 | Order without payment row | 1 | `payment_total` NULL; excluded from C18 | |
| 14 | `payment_total` ≠ Σ(price + freight) by > 1 BRL | 249 orders (0.25 %) | Kept | Vouchers/instalment interest; GMV KPIs use item prices, not payments. C18 thresholds (warn 0.5 %, fail 1 %) sit above this level |
| 15 | Orders without items | 775 (none delivered) | Kept in `fact_orders` | They do not affect delivered-order KPIs; K7/K8 count their reviews |
| 16 | Status and state case/whitespace | — | `lower(trim(status))`, `upper(trim(state))` | No change on the current file, guards against reloads |

Clean baseline (`docs/dq_catalogue.md`): mart pass 19, warn 1 (C03), fail 0. Stage B counts
a run as detected only if a check gets worse than this baseline (decision D3).

## Online Retail II (Stage B, code plan 4.7)

Rules in `sql/retail/stg_retail_lines.sql`, applied in order; row counts are regenerated in
`docs/retail_adapter.md` by `python -m dqk.retail.adapter`.

| # | Issue | Rows (of 1,067,371) | Handling | Reason |
|---|---|---|---|---|
| R1 | Exact duplicate rows | 34,335 | Dropped | The two Excel sheets overlap on 2010-12-01..09; the source also repeats some lines verbatim |
| R2 | Invoice number not `[C]dddddd` | 6 | Dropped | `A...` bad-debt adjustments, not sales |
| R3 | Cancellation invoices `C...` | 19,104 | Dropped | Reversals, not orders |
| R4 | Sale line fully reversed by a cancellation (same customer, StockCode, opposite quantity, later) | 9,579 | Dropped | Without R4, dropping R3 would leave cancelled orders in GMV (e.g. the 80,995-unit line of 2011-12-09) |
| R5 | Non-product StockCode (POST, DOT, M, BANK CHARGES, AMAZONFEE, ...) | 4,434 | Dropped | Postage, fees and manual adjustments, not products |
| R6 | Quantity ≤ 0 or Price ≤ 0 | 5,927 | Dropped | Stock corrections and free lines |
| R7 | Missing Customer ID | 226,637 | Dropped | K9 and K10 need a customer (code plan 4.7) |
| — | Invoice with several timestamps | 83 invoices | Earliest timestamp, customer of the first line | One purchase time per order |
| — | Customer in several countries | 13 customers | Country of the latest invoice | Same rule as Olist item 7 |
| — | StockCode with several descriptions; lower-case suffixes | 1,232 codes | `upper(trim())`; most frequent description kept for reading | One product per code |

Result: 36,267 invoices, 767,349 lines, 5,838 customers, 4,611 products. Every applicable
check passes on the clean retail mart, so the baseline is all `pass`.
