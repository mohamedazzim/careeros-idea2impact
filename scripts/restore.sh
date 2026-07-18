#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <backup_file.dump>"
  exit 1
fi

BACKUP_FILE=$1
POSTGRES_USER=${POSTGRES_USER:-careeros}
POSTGRES_DB=${POSTGRES_DB:-careeros_db}

if [ ! -f "$BACKUP_FILE" ]; then
  echo "File not found: $BACKUP_FILE"
  exit 1
fi

echo "Restoring PostgreSQL database..."
docker exec -i $(docker-compose ps -q db) pg_restore -U $POSTGRES_USER -d $POSTGRES_DB -1 < "$BACKUP_FILE"

echo "Restore complete."
