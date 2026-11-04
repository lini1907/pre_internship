-- C02 Product has a translated (English) category.
SELECT count(*) FILTER (WHERE category_en IS NULL) AS n_failed,
       count(*) AS n_total
FROM {{products}};
