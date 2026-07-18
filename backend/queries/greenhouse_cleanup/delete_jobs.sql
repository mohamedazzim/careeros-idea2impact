DELETE FROM jobs
WHERE id = ANY(:job_ids)
