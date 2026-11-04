-- C01 Key columns not null. One unit per order row and per item row.
SELECT (SELECT count(*) FROM {{orders}} WHERE order_id IS NULL)
     + (SELECT count(*) FROM {{items}}
        WHERE order_id IS NULL OR product_id IS NULL OR seller_id IS NULL) AS n_failed,
       (SELECT count(*) FROM {{orders}}) + (SELECT count(*) FROM {{items}}) AS n_total;
