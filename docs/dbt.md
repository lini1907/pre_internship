# dbt project (v1.1)

`dbt/` rebuilds the **staging** and **mart** layers with dbt-duckdb. KPI and DQ SQL stay
outside dbt (decision D1): the experiment runs them in memory on corrupted copies of the mart.

```bash
python -m venv .venv-dbt
.venv-dbt/Scripts/pip install -r requirements-dbt.txt   # dbt-core 1.12.7, dbt-duckdb 1.11.1, duckdb 2.0.0
python run_pipeline.py                                   # raw schema in warehouse/olist.duckdb
python dbt/sync_models.py                                # models from sql/staging, sql/mart
cd dbt && ../.venv-dbt/Scripts/dbt build --profiles-dir . && cd ..
cd dbt && ../.venv-dbt/Scripts/dbt docs generate --profiles-dir . && cd ..
python dbt/lineage.py                                    # docs/figures/dbt_lineage.png
pytest tests/test_dbt_parity.py                          # dbt mart == pipeline mart
```

- Sources: `warehouse/olist.duckdb`, schema `raw`, attached read-only as database `src`.
- Output: `warehouse/olist_dbt.duckdb` (schemas `staging`, `mart`); `olist.duckdb` is never written.
- Models are generated from `sql/staging/*.sql` and `sql/mart/*.sql` by `dbt/sync_models.py`
  (table names after FROM/JOIN become `source()` / `ref()`), so the SQL has one source.
  `tests/test_dbt_parity.py` fails if a model is out of date.
- Seed: `config/category_translation_extra.csv`.

Result on the clean load (2026-11-17): 1 seed, 13 models, 46 data tests, PASS 59, WARN 1
(C03: 8 delivered orders without a delivery date, as in the SQL check), ERROR 0. All 13
staging and mart tables built by dbt equal the pipeline's row for row (same columns, same
row count, empty `EXCEPT ALL` both ways).

## Core checks and dbt tests

| Check | dbt test | Where |
|---|---|---|
| C01 key columns not null | `not_null` on order_id, item order_id/product_id/seller_id | `models/schema.yml` |
| C02 product has a category | `not_null` category_en, warn > 659, error > 1,647 (2 % / 5 %) | `models/schema.yml` |
| C03 delivered order has a date | `not_null` where status = 'delivered', warn > 0, error > 96 | `models/schema.yml` |
| C04 review has a score | `not_null` review_score where review_id is not null | `models/schema.yml` |
| C05 order_id unique | `unique` | `models/schema.yml` |
| C06 (order_id, order_item_id) unique | singular | `tests/c06_order_item_unique.sql` |
| C07 review_id unique | `unique`, warn > 1,973, error > 4,933 (counts duplicated values, not rows) | `models/schema.yml` |
| C08-C10 foreign keys | `relationships` | `models/schema.yml` |
| C11 price > 0, C12 freight >= 0 | singular | `tests/c11_*.sql`, `tests/c12_*.sql` |
| C13 score in 1..5 | `accepted_values` | `models/schema.yml` |
| C14 valid state | `accepted_values` (27 states) | `models/schema.yml` |
| C15-C17 temporal | singular | `tests/c15_*.sql` ... `tests/c17_*.sql` |
| C18 payment reconciles | singular, warn > 493, error > 986 (0.5 % / 1 %) | `tests/c18_payment_reconciles.sql` |
| C19-C20 volume vs reference load | none (needs the previous load's row count) | - |
| C21 customer key (v1.1) | `not_null` customer_unique_id | `models/schema.yml` |
| C22-C24 (v1.1) | none: they compare with a reference load | - |

dbt's generic tests (`not_null`, `unique`, `relationships`, `accepted_values`) are the same
kind of rule as C01-C14: they test each row against a fixed rule. Like the SQL checks, they
cannot see a valid-looking value that is wrong (E4 time shift, E6 category reassignment).
