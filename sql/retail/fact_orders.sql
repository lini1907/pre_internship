-- One row per invoice, in the Olist fact_orders schema. Every kept invoice counts as a
-- delivered order. The source has no delivery dates, payments or reviews: those are NULL.
-- An invoice with several timestamps (83 in raw data) takes the earliest; customer and
-- country come from its first line.
WITH firsts AS (
    SELECT invoice,
           min(invoice_ts) AS purchase_ts,
           arg_min(customer_id, src_row) AS customer_id
    FROM stg_retail_lines
    GROUP BY 1
)
SELECT invoice                       AS order_id,
       customer_id                   AS customer_unique_id,
       'delivered'                   AS status,
       purchase_ts,
       NULL::TIMESTAMP               AS approved_ts,
       NULL::TIMESTAMP               AS delivered_carrier_ts,
       NULL::TIMESTAMP               AS delivered_customer_ts,
       NULL::DATE                    AS estimated_delivery_date,
       NULL::DECIMAL(12,2)           AS payment_total,
       NULL::VARCHAR                 AS review_id,
       NULL::INTEGER                 AS review_score,
       TRUE                          AS is_delivered
FROM firsts
ORDER BY order_id;
