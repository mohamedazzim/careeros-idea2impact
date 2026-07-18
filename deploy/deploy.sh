#!/bin/bash

# CareerOS Production Deployment Script
# Run this to deploy/update the application
# Usage: bash deploy/deploy.sh

set -e

echo "========================================="
echo "CareerOS Production Deployment"
echo "========================================="

# Define application directory. Override CAREEROS_DEPLOY_DIR for custom hosts.
APP_DIR="${CAREEROS_DEPLOY_DIR:-/opt/careeros}"
PUBLIC_HOST="${CAREEROS_PUBLIC_HOST:-your-domain.example.com}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$APP_DIR/logs/deploy_$TIMESTAMP.log"
mkdir -p "$APP_DIR/logs"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

cd "$APP_DIR"

log "Deployment started at $(date)"

# Step 1: Check if .env exists
log "Step 1: Checking environment configuration..."
if [ ! -f "$APP_DIR/.env" ]; then
    error ".env file not found! Copy .env.example to .env and fill in values"
fi
log "✓ .env file found"

# Step 2: Pull latest code (if git repo)
log "Step 2: Pulling latest code..."
if [ -d ".git" ]; then
    git pull origin main 2>/dev/null || warn "Could not pull from git (may not be a git repo)"
else
    warn "Not a git repository, skipping pull"
fi

# Step 3: Load environment variables
log "Step 3: Loading environment variables..."
source "$APP_DIR/.env"

# Step 4: Create SSL directory if missing
log "Step 4: Checking SSL certificates..."
if [ ! -d "deploy/ssl" ]; then
    mkdir -p "deploy/ssl"
    warn "SSL directory created. Generate certificates with:"
    warn "  sudo certbot certonly --standalone -d $PUBLIC_HOST"
    warn "  sudo cp /etc/letsencrypt/live/$PUBLIC_HOST/* deploy/ssl/"
fi

# Step 5: Backup current database (optional but recommended)
log "Step 5: Creating database backup..."
if docker compose -f docker-compose.prod.yml ps db 2>/dev/null | grep -q "careeros-db"; then
    BACKUP_FILE="$APP_DIR/backups/postgres_backup_$TIMESTAMP.sql"
    docker compose -f docker-compose.prod.yml exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$BACKUP_FILE" 2>/dev/null || warn "Could not create database backup"
    [ -f "$BACKUP_FILE" ] && log "✓ Database backup created: $BACKUP_FILE" || warn "Database backup may have failed"
else
    log "Database not running yet, skipping backup"
fi

# Step 6: Stop old containers
log "Step 6: Stopping old containers..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || log "No containers to stop"

# Step 7: Build images
log "Step 7: Building Docker images..."
docker compose -f docker-compose.prod.yml build --no-cache 2>&1 | tee -a "$LOG_FILE" || error "Build failed"

# Step 8: Start containers
log "Step 8: Starting containers..."
docker compose -f docker-compose.prod.yml up -d 2>&1 | tee -a "$LOG_FILE" || error "Container startup failed"

# Step 9: Wait for services to be healthy
log "Step 9: Waiting for services to be healthy..."
for i in {1..60}; do
    if docker compose -f docker-compose.prod.yml ps | grep -q "careeros-db.*healthy"; then
        log "✓ Database is healthy"
        break
    fi
    if [ $i -eq 60 ]; then
        error "Database failed to become healthy after 60 seconds"
    fi
    sleep 1
done

# Step 10: Run migrations
log "Step 10: Running database migrations..."
if [ -f "backend/alembic/versions" ] || [ -f "backend/alembic.ini" ]; then
    docker compose -f docker-compose.prod.yml exec -T backend python -m alembic upgrade head 2>&1 | tee -a "$LOG_FILE" || warn "Migrations may have failed or weren't needed"
else
    log "No migrations found, skipping"
fi

# Step 11: Verify deployment
log "Step 11: Verifying deployment..."
log ""
log "========================================="
log "Container Status:"
log "========================================="
docker compose -f docker-compose.prod.yml ps 2>&1 | tee -a "$LOG_FILE"

log ""
log "========================================="
log "Service Health Checks:"
log "========================================="
for service in db redis qdrant backend worker frontend nginx; do
    if docker compose -f docker-compose.prod.yml ps | grep -q "careeros-$service"; then
        status=$(docker compose -f docker-compose.prod.yml ps | grep "careeros-$service" | awk '{print $NF}')
        log "✓ $service: $status"
    else
        warn "✗ $service: not running"
    fi
done

log ""
log "========================================="
log "Access Points:"
log "========================================="
log "Frontend:  https://$PUBLIC_HOST"
log "Backend:   https://$PUBLIC_HOST/api"
log "API Health: https://$PUBLIC_HOST/api/health/live"
log ""
log "========================================="
log "✅ Deployment completed successfully!"
log "========================================="
log ""
log "Logs written to: $LOG_FILE"
log ""
log "Useful commands:"
log "  View logs:     docker compose -f docker-compose.prod.yml logs -f backend"
log "  Restart:       docker compose -f docker-compose.prod.yml restart"
log "  Stop:          docker compose -f docker-compose.prod.yml down"
log "  Backup DB:     docker compose -f docker-compose.prod.yml exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql"
log ""
