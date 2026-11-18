# v1.1 results (N1 RQ4, N2, N3)

## N2 - KPI-weighted DQ score (main grid, RQ2)

Measures: `dq_drop` = overall DQ score drop (v1.0); `score_drop_g` = drop of the score over the group's guarding checks; `max_g` = largest fail_share increase among guarding checks; `n_worsened_g` = guarding checks that worsened

| measure | group | n_runs | rho | ci_lo | ci_hi | p | p_holm |
|---|---|---|---|---|---|---|---|
| dq_drop | monetary | 13000 | 0.154 | -0.117 | 0.423 | 0.272 | 0.856 |
| dq_drop | count | 13000 | nan | nan | nan | nan | nan |
| dq_drop | ratio | 13000 | 0.154 | -0.108 | 0.399 | 0.247 | 0.856 |
| dq_drop | rate | 13000 | 0.809 | 0.72 | 0.875 | 0.0005 | 0.004 |
| dq_drop | duration | 13000 | 0.919 | 0.832 | 0.969 | 0.0005 | 0.004 |
| dq_drop | score | 13000 | 0.669 | 0.478 | 0.804 | 0.0005 | 0.004 |
| dq_drop | ranking | 13000 | -0.124 | -0.317 | 0.0808 | 0.214 | 0.856 |
| dq_drop | series | 13000 | 0.0202 | -0.248 | 0.289 | 0.922 | 0.922 |
| dq_drop | decision | 13000 | -0.0894 | -0.119 | -0.0535 | 0.0005 | 0.004 |
| score_drop_g | monetary | 13000 | 0.947 | 0.887 | 0.983 | 0.0005 | 0.004 |
| score_drop_g | count | 13000 | nan | nan | nan | nan | nan |
| score_drop_g | ratio | 13000 | 0.947 | 0.884 | 0.982 | 0.0005 | 0.004 |
| score_drop_g | rate | 13000 | 0.813 | 0.715 | 0.877 | 0.0005 | 0.004 |
| score_drop_g | duration | 13000 | 0.546 | 0.282 | 0.759 | 0.0005 | 0.004 |
| score_drop_g | score | 13000 | 0.995 | 0.984 | 0.999 | 0.0005 | 0.004 |
| score_drop_g | ranking | 13000 | -0.0974 | -0.195 | 0.000468 | 0.051 | 0.051 |
| score_drop_g | series | 13000 | 0.437 | 0.258 | 0.621 | 0.0005 | 0.004 |
| score_drop_g | decision | 13000 | -0.0499 | -0.0732 | -0.0273 | 0.0005 | 0.004 |
| max_g | monetary | 13000 | 0.97 | 0.926 | 0.993 | 0.0005 | 0.004 |
| max_g | count | 13000 | nan | nan | nan | nan | nan |
| max_g | ratio | 13000 | 0.97 | 0.927 | 0.992 | 0.0005 | 0.004 |
| max_g | rate | 13000 | 0.814 | 0.723 | 0.885 | 0.0005 | 0.004 |
| max_g | duration | 13000 | 0.837 | 0.749 | 0.907 | 0.0005 | 0.004 |
| max_g | score | 13000 | 0.995 | 0.985 | 0.999 | 0.0005 | 0.004 |
| max_g | ranking | 13000 | -0.0974 | -0.192 | 0.00286 | 0.057 | 0.057 |
| max_g | series | 13000 | 0.437 | 0.25 | 0.615 | 0.0005 | 0.004 |
| max_g | decision | 13000 | -0.0499 | -0.0727 | -0.0265 | 0.0005 | 0.004 |
| n_worsened_g | monetary | 13000 | 0.93 | 0.853 | 0.976 | 0.0005 | 0.004 |
| n_worsened_g | count | 13000 | nan | nan | nan | nan | nan |
| n_worsened_g | ratio | 13000 | 0.93 | 0.855 | 0.978 | 0.0005 | 0.004 |
| n_worsened_g | rate | 13000 | 0.795 | 0.708 | 0.858 | 0.0005 | 0.004 |
| n_worsened_g | duration | 13000 | 0.767 | 0.616 | 0.876 | 0.0005 | 0.004 |
| n_worsened_g | score | 13000 | 0.995 | 0.987 | 0.999 | 0.0005 | 0.004 |
| n_worsened_g | ranking | 13000 | -0.105 | -0.209 | -0.00639 | 0.041 | 0.041 |
| n_worsened_g | series | 13000 | 0.422 | 0.25 | 0.604 | 0.0005 | 0.004 |
| n_worsened_g | decision | 13000 | -0.0501 | -0.074 | -0.0278 | 0.0005 | 0.004 |

## N1 - RQ4: extended checks (core vs extended suite)

Consistency with the main grid (cells in both grids, same seeds):

| n_runs | n_cells | detected_mismatch | material_mismatch |
|---|---|---|---|
| 4200 | 21 | 0 | 0 |

| dataset | code | variant | mechanism | rate | tau | n_runs | material_rate | silent_core | silent_core_lo | silent_core_hi | detected_core | silent_ext | silent_ext_lo | silent_ext_hi | detected_ext |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| olist | E4 | tz_shift_3h | MCAR | 0.05 | 0.01 | 200 | 0 | 0 | 0 | 0.0188 | 0 | 0 | 0 | 0.0188 | 0 |
| olist | E5 | price_div100 | MCAR | 0.05 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_div100 | MCAR | 0.1 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MCAR | 0.01 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MCAR | 0.02 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MCAR | 0.05 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MCAR | 0.1 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MCAR | 0.2 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MNAR | 0.01 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MNAR | 0.02 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MNAR | 0.05 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MNAR | 0.1 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E5 | price_x100 | MNAR | 0.2 | 0.01 | 200 | 1 | 0 | 0 | 0.0188 | 1 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MAR | 0.01 | 0.01 | 200 | 0.315 | 0.315 | 0.255 | 0.382 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MAR | 0.02 | 0.01 | 200 | 0.54 | 0.54 | 0.471 | 0.608 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MAR | 0.05 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MAR | 0.1 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MAR | 0.2 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MCAR | 0.01 | 0.01 | 200 | 0.45 | 0.45 | 0.383 | 0.519 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MCAR | 0.02 | 0.01 | 200 | 0.565 | 0.565 | 0.496 | 0.632 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MCAR | 0.05 | 0.01 | 200 | 0.795 | 0.795 | 0.734 | 0.845 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MCAR | 0.1 | 0.01 | 200 | 0.835 | 0.835 | 0.777 | 0.88 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_reassign | MCAR | 0.2 | 0.01 | 200 | 0.85 | 0.85 | 0.794 | 0.893 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_spelling | MCAR | 0.05 | 0.01 | 200 | 0.765 | 0.765 | 0.702 | 0.818 | 0 | 0 | 0 | 0.0188 | 1 |
| olist | E6 | category_spelling | MCAR | 0.1 | 0.01 | 200 | 0.805 | 0.805 | 0.745 | 0.854 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E3 | missing_customer_id | MCAR | 0.01 | 0.01 | 200 | 0.025 | 0.025 | 0.0107 | 0.0572 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E3 | missing_customer_id | MCAR | 0.02 | 0.01 | 200 | 0.035 | 0.035 | 0.0171 | 0.0705 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E3 | missing_customer_id | MCAR | 0.05 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E3 | missing_customer_id | MCAR | 0.1 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E3 | missing_customer_id | MCAR | 0.2 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MCAR | 0.01 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MCAR | 0.02 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MCAR | 0.05 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MCAR | 0.1 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MCAR | 0.2 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MNAR | 0.01 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MNAR | 0.02 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MNAR | 0.05 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MNAR | 0.1 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |
| retail | E5 | price_x100 | MNAR | 0.2 | 0.01 | 200 | 1 | 1 | 0.981 | 1 | 0 | 0 | 0 | 0.0188 | 1 |

Extended checks reacting (share of runs):

| dataset | code | variant | mechanism | rate | C21 | C22 | C23 | C24 |
|---|---|---|---|---|---|---|---|---|
| olist | E4 | tz_shift_3h | MCAR | 0.05 | 0 | 0 | 0 | 0 |
| olist | E5 | price_div100 | MCAR | 0.05 | 0 | 0 | 0 | 1 |
| olist | E5 | price_div100 | MCAR | 0.1 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MCAR | 0.01 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MCAR | 0.02 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MCAR | 0.05 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MCAR | 0.1 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MCAR | 0.2 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MNAR | 0.01 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MNAR | 0.02 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MNAR | 0.05 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MNAR | 0.1 | 0 | 0 | 0 | 1 |
| olist | E5 | price_x100 | MNAR | 0.2 | 0 | 0 | 0 | 1 |
| olist | E6 | category_reassign | MAR | 0.01 | 0 | 1 | 0.54 | 0 |
| olist | E6 | category_reassign | MAR | 0.02 | 0 | 1 | 1 | 0 |
| olist | E6 | category_reassign | MAR | 0.05 | 0 | 1 | 1 | 0.15 |
| olist | E6 | category_reassign | MAR | 0.1 | 0 | 1 | 1 | 1 |
| olist | E6 | category_reassign | MAR | 0.2 | 0 | 1 | 1 | 1 |
| olist | E6 | category_reassign | MCAR | 0.01 | 0 | 1 | 0.58 | 0 |
| olist | E6 | category_reassign | MCAR | 0.02 | 0 | 1 | 0.995 | 0 |
| olist | E6 | category_reassign | MCAR | 0.05 | 0 | 1 | 1 | 0.18 |
| olist | E6 | category_reassign | MCAR | 0.1 | 0 | 1 | 1 | 1 |
| olist | E6 | category_reassign | MCAR | 0.2 | 0 | 1 | 1 | 1 |
| olist | E6 | category_spelling | MCAR | 0.05 | 0 | 1 | 1 | 0 |
| olist | E6 | category_spelling | MCAR | 0.1 | 0 | 1 | 1 | 0 |
| retail | E3 | missing_customer_id | MCAR | 0.01 | 1 | nan | nan | 0 |
| retail | E3 | missing_customer_id | MCAR | 0.02 | 1 | nan | nan | 0 |
| retail | E3 | missing_customer_id | MCAR | 0.05 | 1 | nan | nan | 0 |
| retail | E3 | missing_customer_id | MCAR | 0.1 | 1 | nan | nan | 0 |
| retail | E3 | missing_customer_id | MCAR | 0.2 | 1 | nan | nan | 0 |
| retail | E5 | price_x100 | MCAR | 0.01 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MCAR | 0.02 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MCAR | 0.05 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MCAR | 0.1 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MCAR | 0.2 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MNAR | 0.01 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MNAR | 0.02 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MNAR | 0.05 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MNAR | 0.1 | 0 | nan | nan | 1 |
| retail | E5 | price_x100 | MNAR | 0.2 | 0 | nan | nan | 1 |

False alarms on clean data:

| dataset | check_id | method | warn_share | fail_share | n_trials | n_alarms | n_fail | alarm_rate | ci_low | ci_high | share_median | share_p99 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| olist | C21 | month_vs_past | 0 | 0.001 | 20 | 0 | 0 | 0 | 0 | 0.161 | 0 | 0 |
| olist | C21 | split_half | 0 | 0.001 | 200 | 0 | 0 | 0 | 0 | 0.0188 | 0 | 0 |
| olist | C22 | month_vs_past | 0.001 | 0.01 | 20 | 0 | 0 | 0 | 0 | 0.161 | 0 | 0 |
| olist | C22 | split_half | 0.001 | 0.01 | 200 | 0 | 0 | 0 | 0 | 0.0188 | 0 | 0 |
| olist | C23 | month_vs_past | 0.0271 | 0.0541 | 20 | 19 | 14 | 0.95 | 0.764 | 0.991 | 0.0959 | 0.187 |
| olist | C23 | split_half | 0.0271 | 0.0541 | 200 | 0 | 0 | 0 | 0 | 0.0188 | 0 | 0.027 |
| olist | C24 | month_vs_past | 0.0192 | 0.0383 | 20 | 7 | 0 | 0.35 | 0.181 | 0.567 | 0.0159 | 0.0324 |
| olist | C24 | split_half | 0.0192 | 0.0383 | 200 | 1 | 0 | 0.005 | 0.000883 | 0.0278 | 0.0152 | 0.0191 |
| retail | C21 | month_vs_past | 0 | 0.001 | 24 | 0 | 0 | 0 | 0 | 0.138 | 0 | 0 |
| retail | C21 | split_half | 0 | 0.001 | 200 | 0 | 0 | 0 | 0 | 0.0188 | 0 | 0 |
| retail | C24 | month_vs_past | 0.0268 | 0.0535 | 24 | 5 | 0 | 0.208 | 0.0924 | 0.405 | 0.0212 | 0.0335 |
| retail | C24 | split_half | 0.0268 | 0.0535 | 200 | 0 | 0 | 0 | 0 | 0.0188 | 0.0223 | 0.0267 |

## N3 - low error rates (dose-response)

| code | variant | mechanism | rate | n_runs | material_rate | silent_core | silent_ext | detected_core | detected_ext | cell_id | k15_flip | k11_changed | k1_rel_error_median | k1_rel_error_p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E5 | price_x100 | MCAR | 0.001 | 200 | 1 | 1 | 1 | 0 | 0 | E5-price_x100-MCAR-0.001 | 0 | 0.885 | 0.0961 | 0.128 |
| E5 | price_x100 | MCAR | 0.0025 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.0025 | 0 | 0.95 | 0.246 | 0.283 |
| E5 | price_x100 | MCAR | 0.005 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.005 | 0 | 0.99 | 0.49 | 0.551 |
| E5 | price_x100 | MCAR | 0.01 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.01 | 0 | 0.98 | 0.989 | 1.07 |
| E5 | price_x100 | MCAR | 0.02 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.02 | 0 | 0.995 | 1.99 | 2.1 |
| E5 | price_x100 | MCAR | 0.05 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.05 | 0 | 0.97 | 4.96 | 5.11 |
| E5 | price_x100 | MCAR | 0.1 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.1 | 0 | 0.955 | 9.9 | 10.1 |
| E5 | price_x100 | MCAR | 0.2 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MCAR-0.2 | 0 | 0.835 | 19.8 | 20.1 |
| E5 | price_x100 | MNAR | 0.001 | 200 | 1 | 1 | 1 | 0 | 0 | E5-price_x100-MNAR-0.001 | 0 | 1 | 0.361 | 0.441 |
| E5 | price_x100 | MNAR | 0.0025 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.0025 | 0 | 1 | 0.895 | 1.01 |
| E5 | price_x100 | MNAR | 0.005 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.005 | 0 | 1 | 1.78 | 1.94 |
| E5 | price_x100 | MNAR | 0.01 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.01 | 0 | 1 | 3.46 | 3.66 |
| E5 | price_x100 | MNAR | 0.02 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.02 | 0 | 1 | 6.63 | 6.92 |
| E5 | price_x100 | MNAR | 0.05 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.05 | 0 | 1 | 14.9 | 15.2 |
| E5 | price_x100 | MNAR | 0.1 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.1 | 0 | 1 | 25.8 | 26.1 |
| E5 | price_x100 | MNAR | 0.2 | 200 | 1 | 0 | 0 | 1 | 1 | E5-price_x100-MNAR-0.2 | 0 | 1 | 42.2 | 42.4 |
| E6 | category_reassign | MAR | 0.001 | 200 | 0.04 | 0.04 | 0.04 | 0 | 0 | E6-category_reassign-MAR-0.001 | 0 | 0.04 | 0 | 0 |
| E6 | category_reassign | MAR | 0.0025 | 200 | 0.12 | 0.12 | 0 | 0 | 1 | E6-category_reassign-MAR-0.0025 | 0.01 | 0.11 | 0 | 0 |
| E6 | category_reassign | MAR | 0.005 | 200 | 0.18 | 0.18 | 0 | 0 | 1 | E6-category_reassign-MAR-0.005 | 0.005 | 0.175 | 0 | 0 |
| E6 | category_reassign | MAR | 0.01 | 200 | 0.315 | 0.315 | 0 | 0 | 1 | E6-category_reassign-MAR-0.01 | 0.02 | 0.3 | 0 | 0 |
| E6 | category_reassign | MAR | 0.02 | 200 | 0.54 | 0.54 | 0 | 0 | 1 | E6-category_reassign-MAR-0.02 | 0.035 | 0.52 | 0 | 0 |
| E6 | category_reassign | MAR | 0.05 | 200 | 1 | 1 | 0 | 0 | 1 | E6-category_reassign-MAR-0.05 | 0.125 | 1 | 0 | 0 |
| E6 | category_reassign | MAR | 0.1 | 200 | 1 | 1 | 0 | 0 | 1 | E6-category_reassign-MAR-0.1 | 0.2 | 1 | 0 | 0 |
| E6 | category_reassign | MAR | 0.2 | 200 | 1 | 1 | 0 | 0 | 1 | E6-category_reassign-MAR-0.2 | 0.085 | 1 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.001 | 200 | 0.075 | 0.075 | 0.075 | 0 | 0 | E6-category_reassign-MCAR-0.001 | 0 | 0.075 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.0025 | 200 | 0.155 | 0.155 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.0025 | 0.005 | 0.15 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.005 | 200 | 0.28 | 0.28 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.005 | 0.01 | 0.27 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.01 | 200 | 0.45 | 0.45 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.01 | 0.03 | 0.44 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.02 | 200 | 0.565 | 0.565 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.02 | 0.04 | 0.55 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.05 | 200 | 0.795 | 0.795 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.05 | 0.075 | 0.78 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.1 | 200 | 0.835 | 0.835 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.1 | 0.17 | 0.805 | 0 | 0 |
| E6 | category_reassign | MCAR | 0.2 | 200 | 0.85 | 0.85 | 0 | 0 | 1 | E6-category_reassign-MCAR-0.2 | 0.105 | 0.84 | 0 | 0 |

