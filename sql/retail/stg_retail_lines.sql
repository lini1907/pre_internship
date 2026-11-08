-- Online Retail II staging: one row per kept invoice line (code plan 4.7).
-- Input view raw_retail = both Excel sheets concatenated, with a row number src_row.
-- Rules, in order (rows left after each: sql/retail/rule_counts.sql, docs/retail_adapter.md):
--   R1 exact duplicate rows dropped (the two sheets overlap on 2010-12-01..09, and the
--      source repeats some lines verbatim)
--   R2 Invoice not of the form [C]dddddd dropped ('A...' bad-debt adjustments)
--   R3 cancellations (Invoice 'C...') dropped: reversals, not orders
--   R4 a sale line fully reversed by a cancellation line (same customer and StockCode,
--      quantity of opposite sign, cancelled at or after the sale) dropped, so that a
--      cancelled order does not stay in GMV once its reversal is gone
--   R5 StockCode not starting with 5 digits dropped (POST, DOT, M, BANK CHARGES, ...)
--   R6 Quantity <= 0 or Price <= 0 dropped
--   R7 missing Customer ID dropped (repeat rate / active customers need it)
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
r4 AS (
    SELECT d.*
    FROM dedup d
    WHERE regexp_matches(trim(d.Invoice), '^C?[0-9]{6}$')
      AND NOT starts_with(trim(d.Invoice), 'C')
      AND NOT EXISTS (
          SELECT 1 FROM cancels c
          WHERE c.cid = d."Customer ID" AND c.sc = upper(trim(d.StockCode))
            AND c.qty = d.Quantity AND c.ts >= d.InvoiceDate)
)
SELECT src_row,
       trim(Invoice)                                  AS invoice,
       upper(trim(StockCode))                         AS stock_code,
       nullif(trim(Description), '')                  AS description,
       CAST(Quantity AS INTEGER)                      AS quantity,
       CAST(Price AS DOUBLE)                          AS unit_price,
       CAST(InvoiceDate AS TIMESTAMP)                 AS invoice_ts,
       CAST(CAST("Customer ID" AS BIGINT) AS VARCHAR) AS customer_id,
       trim(Country)                                  AS country
FROM r4
WHERE regexp_matches(upper(trim(StockCode)), '^[0-9]{5}')
  AND Quantity > 0
  AND Price > 0
  AND "Customer ID" IS NOT NULL
ORDER BY src_row;
