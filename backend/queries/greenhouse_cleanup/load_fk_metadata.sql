SELECT
    c.conrelid::regclass::text AS table_name,
    a.attname AS column_name,
    c.confdeltype AS confdeltype,
    EXISTS (
        SELECT 1
        FROM pg_constraint uc
        WHERE uc.conrelid = c.conrelid
          AND uc.contype IN ('p', 'u')
          AND a.attnum = ANY (uc.conkey)
    ) AS column_is_unique
FROM pg_constraint c
JOIN pg_class parent ON parent.oid = c.confrelid
JOIN unnest(c.conkey) AS col(attnum) ON TRUE
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = col.attnum
WHERE c.contype = 'f'
  AND parent.relname = 'jobs'
  AND parent.relnamespace = 'public'::regnamespace
ORDER BY table_name, column_name
