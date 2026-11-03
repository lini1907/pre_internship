-- K12 GMV per seller. seller_id not in dim_seller -> 'unknown', rank NULL.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
g AS (
    SELECT coalesce(s.seller_id, $unknown_label) AS item,
           CAST(sum(i.price) AS DOUBLE) AS value
    FROM fact_order_items i
    JOIN d USING (order_id)
    LEFT JOIN dim_seller s ON s.seller_id = i.seller_id
    GROUP BY 1
)
SELECT item,
       value,
       CASE WHEN item <> $unknown_label
            THEN CAST(row_number() OVER (
                     PARTITION BY item = $unknown_label
                     ORDER BY value DESC, item) AS INTEGER)
       END AS rank
FROM g
ORDER BY rank NULLS LAST, item;
