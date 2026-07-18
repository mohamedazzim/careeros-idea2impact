#!/bin/bash
set -e

BACKUP_DIR="/backups/careeros"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
POSTGRES_USER=${POSTGRES_USER:-careeros}
POSTGRES_DB=${POSTGRES_DB:-careeros_db}

mkdir -p "$BACKUP_DIR"

echo "Running PostgreSQL backup..."
docker exec $(docker-compose ps -q db) pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -F c > "$BACKUP_DIR/db_$TIMESTAMP.dump"

echo "Running Qdrant backup (snapshot)..."
curl -X POST "http://localhost:6333/collections/resumes/snapshots"
# Depending on API, you'd then download the snapshot.

echo "Backup complete. Files stored in $BACKUP_DIR"
# Retention policy (keep last 7 days)
find "$BACKUP_DIR" -type f -mtime +7 -name '*.dump' -exec rm {} \;
