-- One row per Customer ID. state holds the country; a customer seen in several countries
-- keeps the country of the latest invoice (as Olist keeps the latest state).
WITH latest AS (
    SELECT customer_id, country
    FROM stg_retail_lines
    QUALIFY row_number() OVER (
        PARTITION BY customer_id ORDER BY invoice_ts DESC, src_row DESC) = 1
)
SELECT CAST(row_number() OVER (ORDER BY customer_id) AS INTEGER) AS customer_key,
       customer_id                                               AS customer_unique_id,
       country                                                   AS state
FROM latest
ORDER BY customer_key;
