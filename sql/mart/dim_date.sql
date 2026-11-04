-- Calendar covering every purchase date; date_key = YYYYMMDD.
WITH bounds AS (
    SELECT CAST(min(purchase_ts) AS DATE) AS lo, CAST(max(purchase_ts) AS DATE) AS hi
    FROM stg_orders
),
days AS (
    SELECT CAST(g.d AS DATE) AS date
    FROM bounds,
         generate_series(CAST(lo AS TIMESTAMP), CAST(hi AS TIMESTAMP), INTERVAL 1 DAY) g(d)
)
SELECT CAST(strftime(date, '%Y%m%d') AS INTEGER) AS date_key,
       date,
       CAST(year(date) AS INTEGER)  AS year,
       CAST(month(date) AS INTEGER) AS month,
       strftime(date, '%Y-%m')      AS year_month
FROM days
ORDER BY date;
