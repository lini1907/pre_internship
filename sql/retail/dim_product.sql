-- One row per StockCode. There are no categories: category_en holds the StockCode, so the
-- Olist "top categories" query (K11) ranks products. category_pt keeps the most frequent
-- description, for reading the results.
WITH d AS (
    SELECT stock_code, description, count(*) AS n
    FROM stg_retail_lines
    GROUP BY 1, 2
),
best AS (
    SELECT stock_code, description
    FROM d
    QUALIFY row_number() OVER (
        PARTITION BY stock_code ORDER BY description IS NULL, n DESC, description) = 1
)
SELECT CAST(row_number() OVER (ORDER BY stock_code) AS INTEGER) AS product_key,
       stock_code                                               AS product_id,
       description                                              AS category_pt,
       stock_code                                               AS category_en
FROM best
ORDER BY product_key;
