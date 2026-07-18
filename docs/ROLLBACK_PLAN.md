# Fallback & Rollback Plan

## Failed Deployment Rollback
If a new deployment fails (e.g., containers crash or health checks fail):
1. Tag previous stable image (`docker tag careeros-backend:latest careeros-backend:stable`) before deployment.
2. If deploy fails, revert `docker-compose.prod.yml` to use `stable` tags.
3. Apply: `docker-compose up -d`

## Database Rollback
If a database migration corrupts data:
1. Stop backend: `docker-compose stop backend`
2. Run restore script pointing to the last known good backup.
3. Start backend: `docker-compose start backend`

## Configuration Rollback
- Configuration changes made in `.env` can be reverted by checking the `env.backup` file maintained by operations.
