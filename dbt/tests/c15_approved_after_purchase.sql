-- C15 approved_ts >= purchase_ts.
SELECT * FROM {{ ref('fact_orders') }} WHERE approved_ts < purchase_ts
