-- K11 GMV per category. Orphan product_id or missing category -> 'unknown', rank NULL.
-- All categories are returned; top_k is applied when measuring.
WITH d AS (
    SELECT *
    FROM fact_orders
    WHERE is_delivered
      AND purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
g AS (
    SELECT coalesce(p.category_en, $unknown_label) AS item,
           CAST(sum(i.price) AS DOUBLE) AS value
    FROM fact_order_items i
    JOIN d USING (order_id)
    LEFT JOIN dim_product p ON p.product_id = i.product_id
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
