-- C20 Order item row count vs the reference load (as C19).
SELECT abs(count(*) - $ref_items) AS n_failed,
       $ref_items AS n_total
FROM {{items}};
