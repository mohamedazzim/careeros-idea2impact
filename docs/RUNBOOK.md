# CareerOS Runbook

## Service Restart
- Restart all services: `docker-compose restart`
- Restart specific service: `docker-compose restart backend`
- Rebuild & restart: `docker-compose up -d --build`

## Log Inspection
- View backend logs: `docker-compose logs -f backend`
- View Nginx errors: `docker-compose logs -f nginx`
- View Qdrant logs: `docker-compose logs -f qdrant`

## Backup Execution
- Run `bash scripts/backup.sh`
- Backups are stored in `/backups/careeros`

## Restore Execution
- Run `bash scripts/restore.sh /backups/careeros/<filename>.dump`

## Health Verification
- Open `https://<domain>/health/deep` for granular dependency statuses.

## Incident Response
- **Database Failure**: Restart DB container. If unrecoverable, run restore script.
- **High Latency**: Check `docker stats` for CPU/RAM usage. Scale backend containers if needed.
