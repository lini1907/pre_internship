-- C06 (order_id, order_item_id) unique.
SELECT order_id, order_item_id, count(*) AS n
FROM {{ ref('fact_order_items') }}
GROUP BY 1, 2
HAVING count(*) > 1
