-- A01 Cohort retention. Population as the KPIs: delivered orders purchased in
-- [$window_start, $window_end). Cohort = month of a customer's first such order.
-- repeat_rate(h) = share of the cohort with a second order within h days of the first
-- (h = 30, 91, 182, 365, i.e. about 1, 3, 6, 12 months). Cumulative by construction.
-- censored = the window ends before first purchase + h for the cohort's last day, so
-- the rate is a lower bound; the report shows censored cells greyed out or not at all.
WITH d AS (
    SELECT customer_unique_id, order_id, purchase_ts
    FROM fact_orders
    WHERE is_delivered
      AND customer_unique_id IS NOT NULL
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
ranked AS (
    SELECT customer_unique_id, purchase_ts,
           row_number() OVER (PARTITION BY customer_unique_id ORDER BY purchase_ts, order_id) AS k
    FROM d
),
cust AS (
    SELECT customer_unique_id,
           max(purchase_ts) FILTER (WHERE k = 1) AS first_ts,
           max(purchase_ts) FILTER (WHERE k = 2) AS second_ts
    FROM ranked
    GROUP BY 1
),
h AS (SELECT unnest([30, 91, 182, 365]) AS horizon_days)
SELECT strftime(date_trunc('month', c.first_ts), '%Y-%m') AS cohort,
       h.horizon_days,
       count(*) AS n_customers,
       count(*) FILTER (
           WHERE c.second_ts IS NOT NULL
             AND c.second_ts <= c.first_ts + to_days(CAST(h.horizon_days AS INTEGER))
       ) AS n_repeat,
       avg(CASE WHEN c.second_ts IS NOT NULL
                 AND c.second_ts <= c.first_ts + to_days(CAST(h.horizon_days AS INTEGER))
                THEN 1.0 ELSE 0.0 END) AS repeat_rate,
       max(c.first_ts) + to_days(CAST(h.horizon_days AS INTEGER))
           > CAST($window_end AS TIMESTAMP) AS censored
FROM cust c
CROSS JOIN h
GROUP BY 1, 2
ORDER BY 1, 2;
