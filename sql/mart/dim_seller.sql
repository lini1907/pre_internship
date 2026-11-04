SELECT CAST(row_number() OVER (ORDER BY seller_id) AS INTEGER) AS seller_key,
       seller_id,
       state
FROM stg_sellers
ORDER BY seller_key;
