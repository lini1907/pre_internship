-- Rows left after each staging rule of stg_retail_lines.sql, applied in order.
WITH dedup AS (
    SELECT *
    FROM raw_retail
    QUALIFY row_number() OVER (
        PARTITION BY Invoice, StockCode, Description, Quantity, InvoiceDate, Price,
                     "Customer ID", Country
        ORDER BY src_row) = 1
),
cancels AS (
    SELECT "Customer ID" AS cid, upper(trim(StockCode)) AS sc, -Quantity AS qty,
           InvoiceDate AS ts
    FROM dedup
    WHERE starts_with(trim(Invoice), 'C') AND "Customer ID" IS NOT NULL
),
r2 AS (SELECT * FROM dedup WHERE regexp_matches(trim(Invoice), '^C?[0-9]{6}$')),
r3 AS (SELECT * FROM r2 WHERE NOT starts_with(trim(Invoice), 'C')),
r4 AS (
    SELECT d.* FROM r3 d
    WHERE NOT EXISTS (
        SELECT 1 FROM cancels c
        WHERE c.cid = d."Customer ID" AND c.sc = upper(trim(d.StockCode))
          AND c.qty = d.Quantity AND c.ts >= d.InvoiceDate)
),
r5 AS (SELECT * FROM r4 WHERE regexp_matches(upper(trim(StockCode)), '^[0-9]{5}')),
r6 AS (SELECT * FROM r5 WHERE Quantity > 0 AND Price > 0),
r7 AS (SELECT * FROM r6 WHERE "Customer ID" IS NOT NULL)
SELECT 'R0' AS rule, 'raw rows (both sheets)' AS description,
       (SELECT count(*) FROM raw_retail) AS rows_left
UNION ALL SELECT 'R1', 'exact duplicate rows', (SELECT count(*) FROM dedup)
UNION ALL SELECT 'R2', 'malformed invoice number', (SELECT count(*) FROM r2)
UNION ALL SELECT 'R3', 'cancellation invoices (C...)', (SELECT count(*) FROM r3)
UNION ALL SELECT 'R4', 'sale lines reversed by a cancellation', (SELECT count(*) FROM r4)
UNION ALL SELECT 'R5', 'non-product stock codes', (SELECT count(*) FROM r5)
UNION ALL SELECT 'R6', 'quantity or price <= 0', (SELECT count(*) FROM r6)
UNION ALL SELECT 'R7', 'missing Customer ID', (SELECT count(*) FROM r7);
