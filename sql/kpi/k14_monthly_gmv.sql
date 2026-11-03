-- K14 Monthly GMV series, anchored on purchase_ts.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT strftime(d.purchase_ts, '%Y-%m') AS item,
       CAST(sum(i.price) AS DOUBLE) AS value,
       NULL::INTEGER AS rank
FROM fact_order_items i
JOIN d USING (order_id)
GROUP BY 1
ORDER BY 1;
