-- K3 Average order value: K1 / K2.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
)
SELECT NULL::VARCHAR AS item,
       CAST((SELECT sum(i.price) FROM fact_order_items i JOIN d USING (order_id))
            / nullif((SELECT count(DISTINCT order_id) FROM d), 0) AS DOUBLE) AS value,
       NULL::INTEGER AS rank;
