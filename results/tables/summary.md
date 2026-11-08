# Stage B results: main grid

65 cells, 13000 runs, seeds per cell 200–200. Max |achieved − target rate| = 1.27e-05.

## RQ1: which error type distorts KPIs most (MCAR, Friedman)

Blocks = KPI (K1–K10, K14) × rate; value = cell median distortion.
 Blocks where all error types tie: 15.

| n_blocks | k | chi2 | p | kendall_w | rate | p_holm |
|---|---|---|---|---|---|---|
| 55 | 6 | 102 | 2.52e-20 | 0.369 | all | nan |
| 11 | 6 | 23.4 | 0.000288 | 0.425 | 0.01 | 0.00144 |
| 11 | 6 | 21.5 | 0.000641 | 0.392 | 0.02 | 0.00256 |
| 11 | 6 | 19.6 | 0.00148 | 0.357 | 0.05 | 0.00444 |
| 11 | 6 | 19.6 | 0.00148 | 0.357 | 0.1 | 0.00444 |
| 11 | 6 | 18 | 0.00295 | 0.327 | 0.2 | 0.00444 |

Mean rank (1 = least distortion):

| code | mean_rank |
|---|---|
| E2 | 2.77 |
| E6 | 2.77 |
| E4 | 3.25 |
| E3 | 3.31 |
| E5 | 4.09 |
| E1 | 4.81 |

Nemenyi p-values:

| code | E1 | E2 | E3 | E4 | E5 | E6 |
|---|---|---|---|---|---|---|
| E1 | 1 | 1.71e-07 | 0.000376 | 0.00017 | 0.335 | 1.71e-07 |
| E2 | 1.71e-07 | 1 | 0.662 | 0.771 | 0.00301 | 1 |
| E3 | 0.000376 | 0.662 | 1 | 1 | 0.242 | 0.662 |
| E4 | 0.00017 | 0.771 | 1 | 1 | 0.167 | 0.771 |
| E5 | 0.335 | 0.00301 | 0.242 | 0.167 | 1 | 0.00301 |
| E6 | 1.71e-07 | 1 | 0.662 | 0.771 | 0.00301 | 1 |

## RQ2: Spearman ρ between DQ score drop and KPI distortion

All runs; 95 % CI and p from a bootstrap that resamples cells (p floor 1/n_boot); p_holm across groups; p_naive treats runs as independent (reference only).

| group | n_runs | n_cells | rho | ci_lo | ci_hi | p | p_naive | p_holm |
|---|---|---|---|---|---|---|---|---|
| monetary | 13000 | 65 | 0.154 | -0.117 | 0.423 | 0.272 | 1.34e-69 | 0.856 |
| count | 13000 | 65 | nan | nan | nan | nan | nan | nan |
| ratio | 13000 | 65 | 0.154 | -0.108 | 0.399 | 0.247 | 1.32e-69 | 0.856 |
| rate | 13000 | 65 | 0.809 | 0.72 | 0.875 | 0.0005 | 0 | 0.004 |
| duration | 13000 | 65 | 0.919 | 0.832 | 0.969 | 0.0005 | 0 | 0.004 |
| score | 13000 | 65 | 0.669 | 0.478 | 0.804 | 0.0005 | 0 | 0.004 |
| ranking | 13000 | 65 | -0.124 | -0.317 | 0.0808 | 0.214 | 6.38e-46 | 0.856 |
| series | 13000 | 65 | 0.0202 | -0.248 | 0.289 | 0.922 | 0.0213 | 0.922 |
| decision | 13000 | 65 | -0.0894 | -0.119 | -0.0535 | 0.0005 | 1.78e-24 | 0.004 |

Same with the number of worsened checks as detection signal:

| group | n_runs | n_cells | rho | ci_lo | ci_hi | p | p_naive | p_holm |
|---|---|---|---|---|---|---|---|---|
| monetary | 13000 | 65 | 0.562 | 0.451 | 0.667 | 0.0005 | 0 | 0.004 |
| count | 13000 | 65 | nan | nan | nan | nan | nan | nan |
| ratio | 13000 | 65 | 0.562 | 0.456 | 0.66 | 0.0005 | 0 | 0.004 |
| rate | 13000 | 65 | 0.373 | 0.169 | 0.538 | 0.003 | 0 | 0.006 |
| duration | 13000 | 65 | 0.575 | 0.465 | 0.674 | 0.0005 | 0 | 0.004 |
| score | 13000 | 65 | 0.691 | 0.52 | 0.81 | 0.0005 | 0 | 0.004 |
| ranking | 13000 | 65 | 0.251 | 0.118 | 0.365 | 0.001 | 5.34e-186 | 0.004 |
| series | 13000 | 65 | 0.319 | 0.104 | 0.481 | 0.006 | 1.22e-305 | 0.006 |
| decision | 13000 | 65 | -0.156 | -0.2 | -0.101 | 0.0005 | 7.59e-72 | 0.004 |

## RQ3: silent errors (τ = 0.01, mechanisms pooled)

| code | rate | n_runs | silent_rate | silent_lo | silent_hi | material_rate | detected_rate |
|---|---|---|---|---|---|---|---|
| E1 | 0.01 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E1 | 0.02 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E1 | 0.05 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E1 | 0.1 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E1 | 0.2 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E2 | 0.01 | 400 | 0 | 0 | 0.00951 | 0.122 | 1 |
| E2 | 0.02 | 400 | 0 | 0 | 0.00951 | 0.215 | 1 |
| E2 | 0.05 | 400 | 0 | 0 | 0.00951 | 0.603 | 1 |
| E2 | 0.1 | 400 | 0 | 0 | 0.00951 | 0.75 | 1 |
| E2 | 0.2 | 400 | 0 | 0 | 0.00951 | 0.777 | 1 |
| E3 | 0.01 | 600 | 0 | 0 | 0.00636 | 0.333 | 1 |
| E3 | 0.02 | 600 | 0 | 0 | 0.00636 | 0.333 | 1 |
| E3 | 0.05 | 600 | 0 | 0 | 0.00636 | 0.333 | 1 |
| E3 | 0.1 | 600 | 0 | 0 | 0.00636 | 0.643 | 1 |
| E3 | 0.2 | 600 | 0 | 0 | 0.00636 | 0.667 | 1 |
| E4 | 0.01 | 400 | 0 | 0 | 0.00951 | 0 | 0 |
| E4 | 0.02 | 400 | 0 | 0 | 0.00951 | 0 | 0 |
| E4 | 0.05 | 400 | 0 | 0 | 0.00951 | 0 | 0 |
| E4 | 0.1 | 400 | 0 | 0 | 0.00951 | 0 | 0 |
| E4 | 0.2 | 400 | 0 | 0 | 0.00951 | 0 | 0 |
| E5 | 0.01 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E5 | 0.02 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E5 | 0.05 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E5 | 0.1 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E5 | 0.2 | 400 | 0 | 0 | 0.00951 | 1 | 1 |
| E6 | 0.01 | 400 | 0.383 | 0.336 | 0.431 | 0.383 | 0 |
| E6 | 0.02 | 400 | 0.552 | 0.504 | 0.6 | 0.552 | 0 |
| E6 | 0.05 | 400 | 0.897 | 0.864 | 0.924 | 0.897 | 0 |
| E6 | 0.1 | 400 | 0.917 | 0.886 | 0.941 | 0.917 | 0 |
| E6 | 0.2 | 400 | 0.925 | 0.895 | 0.947 | 0.925 | 0 |

Materiality threshold sensitivity (all rates pooled):

| code | tau | silent_rate | silent_lo | silent_hi | material_rate |
|---|---|---|---|---|---|
| E1 | 0.005 | 0 | 1.08e-19 | 0.00192 | 1 |
| E2 | 0.005 | 0 | 1.08e-19 | 0.00192 | 0.493 |
| E3 | 0.005 | 0 | 0 | 0.00128 | 0.521 |
| E4 | 0.005 | 0 | 1.08e-19 | 0.00192 | 0 |
| E5 | 0.005 | 0 | 1.08e-19 | 0.00192 | 1 |
| E6 | 0.005 | 0.735 | 0.715 | 0.754 | 0.735 |
| E1 | 0.01 | 0 | 1.08e-19 | 0.00192 | 1 |
| E2 | 0.01 | 0 | 1.08e-19 | 0.00192 | 0.493 |
| E3 | 0.01 | 0 | 0 | 0.00128 | 0.462 |
| E4 | 0.01 | 0 | 1.08e-19 | 0.00192 | 0 |
| E5 | 0.01 | 0 | 1.08e-19 | 0.00192 | 1 |
| E6 | 0.01 | 0.735 | 0.715 | 0.754 | 0.735 |
| E1 | 0.05 | 0 | 1.08e-19 | 0.00192 | 0.994 |
| E2 | 0.05 | 0 | 1.08e-19 | 0.00192 | 0.493 |
| E3 | 0.05 | 0 | 0 | 0.00128 | 0.16 |
| E4 | 0.05 | 0 | 1.08e-19 | 0.00192 | 0 |
| E5 | 0.05 | 0 | 1.08e-19 | 0.00192 | 1 |
| E6 | 0.05 | 0.735 | 0.715 | 0.754 | 0.735 |

## Which checks react to which error (share of runs)

| code | variant | C03 | C05 | C06 | C07 | C08 | C18 | C19 | C20 |
|---|---|---|---|---|---|---|---|---|---|
| E1 | duplicate_order | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.80 | 0.92 |
| E2 | orphan_product | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| E3 | missing_delivery_date | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| E4 | tz_shift_3h | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| E5 | price_x100 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 |
| E6 | category_reassign | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Figures

- `results/figures/fig1_heatmap_rate05.png`
- `results/figures/fig1_heatmap_rate20.png`
- `results/figures/fig2_rate_lines.png`
- `results/figures/fig3_dq_vs_distortion.png`
- `results/figures/fig4_silent_rate.png`

# Robustness (proposal 6.5)

## RQ1 mean ranks per scenario (rates 5 % and 10 %, MCAR)

| code | alt_kpi | main | no_top1pct | period_2017 | period_2018 |
|---|---|---|---|---|---|
| E1 | 4.77 | 4.77 | 4.73 | 4.82 | 4.68 |
| E2 | 2.77 | 2.77 | 2.77 | 2.77 | 2.77 |
| E3 | 3.36 | 3.27 | 3.32 | 3.41 | 3.36 |
| E4 | 3.23 | 3.32 | 3.32 | 3.14 | 3.32 |
| E5 | 4.09 | 4.09 | 4.09 | 4.09 | 4.09 |
| E6 | 2.77 | 2.77 | 2.77 | 2.77 | 2.77 |

Kendall's W: alt_kpi 0.36, main 0.36, no_top1pct 0.34, period_2017 0.38, period_2018 0.33

## RQ2 ρ per scenario

| group | alt_kpi | main | no_top1pct | period_2017 | period_2018 | rekeyed | variants |
|---|---|---|---|---|---|---|---|
| count | nan | nan | nan | nan | nan | 0.961 | -0.324 |
| decision | -0.119 | -0.114 | -0.122 | -0.187 | -0.107 | 0.148 | -0.118 |
| duration | 0.898 | 0.898 | 0.898 | 0.899 | 0.894 | 0.56 | -0.324 |
| monetary | 0.179 | 0.179 | 0.179 | 0.179 | 0.179 | 0.959 | -0.497 |
| ranking | -0.0834 | -0.0775 | 0.0143 | 0.0793 | 0.123 | 0.377 | -0.255 |
| rate | 0.807 | 0.805 | 0.809 | 0.839 | 0.806 | 0.967 | 0.476 |
| ratio | 0.179 | 0.179 | 0.179 | 0.179 | 0.179 | 0.615 | -0.497 |
| score | 0.712 | 0.712 | 0.712 | 0.712 | 0.712 | 0.459 | 0.531 |
| series | 0.0469 | 0.047 | 0.0469 | 0.0472 | 0.0473 | 0.959 | -0.497 |

## RQ3 silent rate per scenario (τ = 0.01)

| code | variant | rate | alt_kpi | main | no_top1pct | period_2017 | period_2018 | rekeyed | variants |
|---|---|---|---|---|---|---|---|---|---|
| E1 | duplicate_order | 0.05 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E1 | duplicate_order | 0.1 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E1 | duplicate_order_rekeyed | 0.01 | nan | nan | nan | nan | nan | 0 | nan |
| E1 | duplicate_order_rekeyed | 0.02 | nan | nan | nan | nan | nan | 0 | nan |
| E1 | duplicate_order_rekeyed | 0.05 | nan | nan | nan | nan | nan | 0 | nan |
| E1 | duplicate_order_rekeyed | 0.1 | nan | nan | nan | nan | nan | 0 | nan |
| E1 | duplicate_order_rekeyed | 0.2 | nan | nan | nan | nan | nan | 0 | nan |
| E2 | orphan_product | 0.05 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E2 | orphan_product | 0.1 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E2 | orphan_seller | 0.05 | nan | nan | nan | nan | nan | nan | 0 |
| E2 | orphan_seller | 0.1 | nan | nan | nan | nan | nan | nan | 0 |
| E3 | missing_category | 0.05 | nan | nan | nan | nan | nan | nan | 0 |
| E3 | missing_category | 0.1 | nan | nan | nan | nan | nan | nan | 0 |
| E3 | missing_delivery_date | 0.05 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E3 | missing_delivery_date | 0.1 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E3 | missing_review_score | 0.05 | nan | nan | nan | nan | nan | nan | 0 |
| E3 | missing_review_score | 0.1 | nan | nan | nan | nan | nan | nan | 0 |
| E4 | day_month_swap | 0.05 | nan | nan | nan | nan | nan | nan | 0 |
| E4 | day_month_swap | 0.1 | nan | nan | nan | nan | nan | nan | 0 |
| E4 | tz_shift_3h | 0.05 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E4 | tz_shift_3h | 0.1 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E5 | price_div100 | 0.05 | nan | nan | nan | nan | nan | nan | 0 |
| E5 | price_div100 | 0.1 | nan | nan | nan | nan | nan | nan | 0 |
| E5 | price_x100 | 0.05 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E5 | price_x100 | 0.1 | 0 | 0 | 0 | 0 | 0 | nan | nan |
| E6 | category_reassign | 0.05 | 0.89 | 0.897 | 0.505 | 0.87 | 0.745 | nan | nan |
| E6 | category_reassign | 0.1 | 0.92 | 0.917 | 0.885 | 0.925 | 0.855 | nan | nan |
| E6 | category_spelling | 0.05 | nan | nan | nan | nan | nan | nan | 0.885 |
| E6 | category_spelling | 0.1 | nan | nan | nan | nan | nan | nan | 0.885 |

## RQ1 sensitivity: E1 variant, KPI set, ranking measure (MCAR, all rates)

Mean rank (1 = least distortion). Main result = first row.

| variant | E2 | E6 | E4 | E3 | E5 | E1 | n_blocks | n_tied | kendall_w | p |
|---|---|---|---|---|---|---|---|---|---|---|
| main: E1 same key, 11 KPIs | 2.77 | 2.77 | 3.25 | 3.31 | 4.09 | 4.81 | 55 | 15 | 0.369 | 2.52e-20 |
| E1 same key, 15 KPIs, overlap | 2.91 | 2.91 | 3.26 | 3.31 | 4.2 | 4.41 | 75 | 27 | 0.291 | 6.24e-22 |
| E1 same key, 15 KPIs, Kendall tau | 2.84 | 2.97 | 3.14 | 3.19 | 4.26 | 4.61 | 75 | 25 | 0.333 | 2.66e-25 |
| E1 re-keyed, 11 KPIs | 2.68 | 2.68 | 3.15 | 3.24 | 4 | 5.25 | 55 | 5 | 0.478 | 1.16e-26 |
| E1 re-keyed, 15 KPIs, overlap | 2.85 | 2.85 | 3.19 | 3.25 | 4.13 | 4.73 | 75 | 17 | 0.355 | 4.79e-27 |
| E1 re-keyed, 15 KPIs, Kendall tau | 2.81 | 2.91 | 3.1 | 3.16 | 4.19 | 4.83 | 75 | 15 | 0.368 | 5.02e-28 |

## D6: re-keyed duplicates vs plain duplicates (silent rate, τ = 0.01)

| variant | rate | silent_rate | silent_lo | silent_hi | material_rate | detected_rate |
|---|---|---|---|---|---|---|
| duplicate_order | 0.01 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order | 0.02 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order | 0.05 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order | 0.1 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order | 0.2 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order_rekeyed | 0.01 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order_rekeyed | 0.02 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order_rekeyed | 0.05 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order_rekeyed | 0.1 | 0 | 0 | 0.00951 | 1 | 1 |
| duplicate_order_rekeyed | 0.2 | 0 | 0 | 0.00951 | 1 | 1 |


# Online Retail II (code plan 4.7)

30 cells, 6000 runs. KPIs K1, K2, K3, K9, K10, K14, K11, K13; E3 = missing_customer_id (Olist main grid: missing_delivery_date); E6 not applicable. Mapping: `docs/retail_adapter.md`.

## Median distortion at 5 % (MCAR), Olist (O) vs Online Retail II (R)

Scalar: relative error; K14: MAPD; K11/K13: 1 − top-k overlap.

| code | K1 O | K1 R | K2 O | K2 R | K3 O | K3 R | K9 O | K9 R | K10 O | K10 R | K14 O | K14 R | K11 O | K11 R | K13 O | K13 R |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E1 | 0.15 | 0.149 | 0 | 0 | 0.15 | 0.149 | 0 | 0 | 0 | 0 | 0.15 | 0.149 | 0 | 0 | 0 | 0 |
| E2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| E3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.00922 | 0 | 0.0145 | 0 | 0 | 0 | 0 | 0 | 0 |
| E4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000389 | 0 | 0 | 0 | 0 | 0 |
| E5 | 4.96 | 4.95 | 0 | 0 | 4.96 | 4.95 | 0 | 0 | 0 | 0 | 4.96 | 4.95 | 0.1 | 0.3 | 0 | 0 |

## RQ1 on the KPIs both datasets share (MCAR, E1–E5)

| code | olist (E1-E5) | retail |
|---|---|---|
| E1 | 3.5 | 3.33 |
| E2 | 2.42 | 2.33 |
| E3 | 2.42 | 3.17 |
| E4 | 2.67 | 2.33 |
| E5 | 4 | 3.83 |

Kendall's W: olist (E1-E5) 0.48 (p = 9.1e-12), retail 0.30 (p = 2.3e-07)

## RQ2 ρ (DQ score drop vs distortion), shared KPIs

| group | olist | retail |
|---|---|---|
| count | nan | -0.198 |
| monetary | 0.154 | 0.145 |
| ranking | -0.144 | -0.102 |
| rate | nan | -0.198 |
| ratio | 0.154 | 0.145 |
| series | 0.0202 | 0.145 |

## RQ3 silent rate (MCAR, τ = 0.01)

| code | rate | olist | retail |
|---|---|---|---|
| E1 | 0.01 | 0 | 0 |
| E1 | 0.02 | 0 | 0 |
| E1 | 0.05 | 0 | 0 |
| E1 | 0.1 | 0 | 0 |
| E1 | 0.2 | 0 | 0 |
| E2 | 0.01 | 0 | 0 |
| E2 | 0.02 | 0 | 0 |
| E2 | 0.05 | 0 | 0 |
| E2 | 0.1 | 0 | 0 |
| E2 | 0.2 | 0 | 0 |
| E3 | 0.01 | 0 | 0.025 |
| E3 | 0.02 | 0 | 0.035 |
| E3 | 0.05 | 0 | 1 |
| E3 | 0.1 | 0 | 1 |
| E3 | 0.2 | 0 | 1 |
| E4 | 0.01 | 0 | 0 |
| E4 | 0.02 | 0 | 0 |
| E4 | 0.05 | 0 | 0 |
| E4 | 0.1 | 0 | 0 |
| E4 | 0.2 | 0 | 0 |
| E5 | 0.01 | 0 | 1 |
| E5 | 0.02 | 0 | 1 |
| E5 | 0.05 | 0 | 1 |
| E5 | 0.1 | 0 | 1 |
| E5 | 0.2 | 0 | 1 |
| E6 | 0.01 | 0.45 | nan |
| E6 | 0.02 | 0.565 | nan |
| E6 | 0.05 | 0.795 | nan |
| E6 | 0.1 | 0.835 | nan |
| E6 | 0.2 | 0.85 | nan |

## Which checks react on Online Retail II (share of runs)

| code | variant | C05 | C06 | C08 | C19 | C20 |
|---|---|---|---|---|---|---|
| E1 | duplicate_order | 1.00 | 1.00 | 0.00 | 1.00 | 0.91 |
| E2 | orphan_product | 0.00 | 0.00 | 1.00 | 0.00 | 0.00 |
| E3 | missing_customer_id | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| E4 | tz_shift_3h | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| E5 | price_x100 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Figures

- `results/figures/fig6_silent_retail.png`
- `results/figures/fig7_retail_vs_olist.png`

