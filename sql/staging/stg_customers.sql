-- One row per customer_id (Olist issues one per order); customer_unique_id is the person.
SELECT customer_id,
       customer_unique_id,
       customer_zip_code_prefix    AS zip_code_prefix,
       lower(trim(customer_city))  AS city,
       upper(trim(customer_state)) AS state
FROM customers
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY customer_unique_id) = 1
ORDER BY customer_id;
