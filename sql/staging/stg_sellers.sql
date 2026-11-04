-- One row per seller_id.
SELECT seller_id,
       seller_zip_code_prefix    AS zip_code_prefix,
       lower(trim(seller_city))  AS city,
       upper(trim(seller_state)) AS state
FROM sellers
QUALIFY row_number() OVER (PARTITION BY seller_id ORDER BY seller_state) = 1
ORDER BY seller_id;
