-- A03 Concentration (Pareto) of GMV by seller and by category. GMV as K1: sum of item
-- price of delivered orders purchased in the window. Entities sorted by GMV (desc);
-- cum_share_entities = rank / n, cum_share_gmv = running GMV / total GMV.
-- Products without a category count as 'unknown' (KPI decision 4).
WITH i AS (
    SELECT it.seller_id,
           coalesce(p.category_en, $unknown_label) AS category,
           it.price
    FROM fact_order_items it
    JOIN fact_orders o ON o.order_id = it.order_id
    LEFT JOIN dim_product p ON p.product_id = it.product_id
    WHERE o.is_delivered
      AND o.purchase_ts >= CAST($window_start AS TIMESTAMP)
      AND o.purchase_ts <  CAST($window_end AS TIMESTAMP)
),
g AS (
    SELECT 'seller' AS dimension, seller_id AS entity, sum(price) AS gmv FROM i GROUP BY 2
    UNION ALL
    SELECT 'category', category, sum(price) FROM i GROUP BY 2
),
r AS (
    SELECT *,
           row_number() OVER (PARTITION BY dimension ORDER BY gmv DESC, entity) AS rank,
           count(*) OVER (PARTITION BY dimension) AS n,
           sum(gmv) OVER (PARTITION BY dimension) AS total
    FROM g
)
SELECT dimension,
       rank,
       entity,
       gmv,
       rank / n AS cum_share_entities,
       sum(gmv) OVER (PARTITION BY dimension ORDER BY rank) / total AS cum_share_gmv
FROM r
ORDER BY dimension, rank;
