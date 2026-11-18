-- C12 freight_value >= 0.
SELECT * FROM {{ ref('fact_order_items') }} WHERE freight_value < 0
