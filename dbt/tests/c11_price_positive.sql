-- C11 price > 0 (NULL also fails).
SELECT * FROM {{ ref('fact_order_items') }} WHERE price IS NULL OR price <= 0
