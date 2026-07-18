UPDATE {{table_name}}
SET {{column_name}} = :survivor_id
WHERE {{column_name}} = ANY(:job_ids)
