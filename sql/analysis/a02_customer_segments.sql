-- A02 Customer segments: Recency x Monetary quintiles, with a repeat flag.
-- Frequency is left out: almost every customer has a single order, so an F score
-- would not separate customers (see the report).
-- recency_days = days from the customer's last order to $window_end;
-- monetary = item value (sum of price) of the customer's delivered orders.
-- r_quintile 5 = most recent, m_quintile 5 = highest value.
WITH d AS (
    SELECT o.customer_unique_id, o.order_id, o.purchase_ts
    FROM fact_orders o
    WHERE o.is_delivered
      AND o.customer_unique_id IS NOT NULL
      AND o.purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND o.purchase_ts <  CAST($window_end AS TIMESTAMP)
),
v AS (
    SELECT order_id, sum(price) AS value FROM fact_order_items GROUP BY 1
),
cust AS (
    SELECT d.customer_unique_id,
           date_diff('day', max(d.purchase_ts), CAST($window_end AS TIMESTAMP)) AS recency_days,
           count(DISTINCT d.order_id) AS n_orders,
           coalesce(sum(v.value), 0) AS monetary
    FROM d
    LEFT JOIN v ON v.order_id = d.order_id
    GROUP BY 1
),
q AS (
    SELECT *,
           ntile(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_quintile,
           ntile(5) OVER (ORDER BY monetary, customer_unique_id) AS m_quintile
    FROM cust
)
SELECT r_quintile,
       m_quintile,
       count(*) AS n_customers,
       sum(monetary) AS gmv,
       avg(CASE WHEN n_orders >= 2 THEN 1.0 ELSE 0.0 END) AS repeat_share,
       min(recency_days) AS recency_min,
       max(recency_days) AS recency_max,
       min(monetary) AS monetary_min,
       max(monetary) AS monetary_max
FROM q
GROUP BY 1, 2
ORDER BY 1, 2;
