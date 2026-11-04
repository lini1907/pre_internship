SELECT CAST(row_number() OVER (ORDER BY product_id) AS INTEGER) AS product_key,
       product_id,
       category_pt,
       category_en
FROM stg_products
ORDER BY product_key;
