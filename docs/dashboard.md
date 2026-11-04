# Dashboard specification

Five pages (code plan 3.7). Data comes from `exports/` after `python run_pipeline.py`.
Decision D5: Power BI Desktop (free, no licence needed for local use).

## Build and open

```bash
python run_pipeline.py          # writes exports/*.parquet
python -m dqk.powerbi           # writes powerbi/Olist.pbip (TMDL model + PBIR report)
```

Open `powerbi/Olist.pbip` in Power BI Desktop and press **Refresh**. The model reads the
Parquet files through the parameter `ExportsFolder` (Transform data → Edit parameters) —
set it to your own `exports\` folder after cloning. The project is plain text and
regenerated from `src/dqk/powerbi.py`; edit that file, not the JSON/TMDL, so changes survive
a rebuild. CSV copies in `exports/` remain for Looker Studio.

Verified on 2026-11-04 (Power BI Desktop 2.159): the mart-side measures recompute K1, K2,
K5, K6 to the same values as the pipeline (13,181,027.13; 96,211; 0.9321; 12.54).

## Model

| File | Role | Relationship |
|---|---|---|
| `fact_order_items` | fact, 1 row per item | `order_id` → `fact_orders`; `product_id` → `dim_product`; `seller_id` → `dim_seller`; `purchase_date_key` → `dim_date` |
| `fact_orders` | fact, 1 row per order | `customer_unique_id` → `dim_customer` |
| `dim_customer`, `dim_product`, `dim_seller`, `dim_date` | dimensions | |
| `kpis_clean` | KPI values computed by the pipeline (`kpi_id, item, value, rank`) | none; filter on `kpi_id` |
| `dq_results` | 20 checks × layer (`check_id, layer, dimension, n_failed, n_total, fail_share, status`) | none |

Cards show values from `kpis_clean` so the dashboard and the pipeline cannot disagree. Charts
that need slicing (by month, state, category) use the mart, with the same filters as the
KPI spec: `is_delivered = true` and `purchase_ts` in [2017-01-01, 2018-09-01).

## Pages

| Page | Cards (from `kpis_clean`) | Charts (from the mart) |
|---|---|---|
| 1. Sales | K1 GMV, K2 delivered orders, K3 AOV, K4 freight ratio | K14 monthly GMV line; GMV by order status (all orders) |
| 2. Delivery | K5 on-time rate, K6 mean delivery days | on-time rate by month; delivery days distribution; on-time rate by customer state |
| 3. Satisfaction | K7 average score, K8 negative share, K15 worst category | score distribution; mean score by month; K15 table of eligible categories (`kpi_id = 'K15'`, all ranks) |
| 4. Customers & sellers | K9 repeat rate, K10 active customers | K11 top-10 categories bar; K12 top-20 sellers bar; K13 top-5 states bar / map |
| 5. Data quality | DQ score (mart), checks pass / warn / fail | `dq_results` table with conditional colour on `status`; `fail_share` by check, one series per layer |

Page 5 links Stage A to Stage B: it shows the clean baseline that Stage B compares against
(C03 warns on the clean mart, everything else passes).

## Reference values (clean build, 2026-11-03)

| KPI | Value |
|---|---|
| K1 GMV | 13,181,027 BRL |
| K2 delivered orders | 96,211 |
| K3 AOV | 137.00 BRL |
| K4 freight ratio | 0.1663 |
| K5 on-time rate | 0.9321 |
| K6 mean delivery time | 12.54 days |
| K7 average review score | 4.089 |
| K8 negative review share | 0.1463 |
| K9 repeat customer rate | 0.0300 |
| K10 active customers | 93,104 |
| K11 top category | health_beauty (1,229,558 BRL) |
| K13 top state | SP (5,057,382 BRL) |
| K15 worst-rated category | office_furniture (3.63) |

Screenshots for the report are taken in week A3.
