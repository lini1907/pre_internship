# Stage B pilot (week B1)

Run on 2026-11-08 on the clean mart of `warehouse/olist.duckdb`, commit `8823dee` + B1 code.

```bash
python run_experiment.py --grid config/grid_main.yaml --cell E3-missing_delivery_date-MNAR-0.05 --seeds 5 --out results/runs/pilot
```

## Achieved vs target rate

All 13 (error x mechanism) combinations at 5 %, 2 seeds each, plus the pilot cell with 5 seeds.
The achieved rate equals round(0.05 x N) / N in every run (deviation < 0.00001, rounding only).

| Error | Unit | N units | Selected at 5 % |
|---|---|---|---|
| E1 duplicate_order | order | 99 441 | 4 972 |
| E2 orphan_product | item | 112 650 | 5 633 |
| E3 missing_delivery_date | order with delivery date | 96 476 | 4 824 |
| E4 tz_shift_3h | order | 99 441 | 4 972 |
| E5 price_x100 | item with price > 0 | 112 650 | 5 633 |
| E6 category_reassign | product with category | 32 341 | 1 617 |

## Plausibility at 5 % (median over seeds)

- E1: K1 GMV +14-15 %, K14 MAPD ~0.14; K2 and K10 unchanged (distinct counts). Detected by C05, C06, C07, C18, C19, C20.
- E2: scalar KPIs unchanged; K11 top-10 overlap 0.95-1.0 ('unknown' grows). Detected by C08.
- E3 MNAR (late deliveries go missing): K5 on-time +1.7 %, K6 delivery time -5 %; MCAR effect is ~10x smaller. Detected by C03.
- E4 tz +3 h: almost no distortion (K5 +0.02 %); no check reacts.
- E5 x100: K1 x6 (MCAR) and x16 (MNAR, high prices); detected only by C18 (reconciliation).
- E6 reassign: no scalar change, K11 top-10 overlap 0.90-0.95; **no check reacts -> silent** in every run.

## Run time

One run (inject + 15 KPIs + 20 checks + measures) takes 0.60-0.70 s on one core
(inject 0.02 s, KPI + DQ 0.6 s). Main grid: 65 cells x 200 seeds = 13 000 runs
= about 2.4 h on one core, about 15-25 min with `--workers 10` on this 12-core laptop.
No need to cut seeds or merge KPI queries (threshold in code plan 5 was 3 s per run).
