-- K15 Worst-rated category: lowest mean review score among named categories with
-- >= $min_reviews reviewed orders. Rank 1 is the decision; ties broken by name.
WITH w AS (
    SELECT *
    FROM fact_orders
    WHERE purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND purchase_ts <  CAST($window_end AS TIMESTAMP)
),
order_category AS (
    SELECT DISTINCT w.order_id, w.review_score, p.category_en AS category
    FROM w
    JOIN fact_order_items i USING (order_id)
    JOIN dim_product p ON p.product_id = i.product_id
    WHERE w.review_score IS NOT NULL
      AND p.category_en IS NOT NULL
      AND p.category_en <> $unknown_label
),
g AS (
    SELECT category AS item,
           avg(CAST(review_score AS DOUBLE)) AS value
    FROM order_category
    GROUP BY 1
    HAVING count(DISTINCT order_id) >= $min_reviews
)
SELECT item,
       value,
       CAST(row_number() OVER (ORDER BY value, item) AS INTEGER) AS rank
FROM g
ORDER BY rank;
