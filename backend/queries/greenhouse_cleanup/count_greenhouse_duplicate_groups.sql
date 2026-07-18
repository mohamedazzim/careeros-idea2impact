SELECT COUNT(*) AS groups
FROM (
    SELECT company, title, location, source_url, apply_url
    FROM jobs
    WHERE source = 'greenhouse'
    GROUP BY company, title, location, source_url, apply_url
    HAVING COUNT(*) > 1
) dup
