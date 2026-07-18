# CareerOS Production Deployment Guide

Complete guide to deploy CareerOS on Ubuntu 24.04 Azure server with Docker Compose and Nginx.

## Prerequisites

- **Server**: Ubuntu 24.04 on Azure
- **Public host**: `<your-domain-or-server-ip>`
- **SSH User**: `<deploy-user>`
- **Deployment Path**: `/opt/careeros`

## System Requirements

- 2+ vCPU
- 4+ GB RAM
- 50+ GB storage
- Ports 80, 443 open in Azure NSG (Network Security Group)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Internet (HTTPS)                      │
└──────────────────────────┬──────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Nginx (443)  │
                    │  Reverse Proxy │
                    └──────┬────┬──┘
                           │    │
         ┌─────────────────┘    └────────────────┐
         │                                        │
    ┌────▼─────────┐                      ┌──────▼──────┐
    │ Frontend:3000│                      │Backend:8000 │
    │ (Next.js)    │                      │ (FastAPI)   │
    └──────┬───────┘                      └──────┬──────┘
           │                                      │
           └──────────────┬───────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    ┌───▼──────┐   ┌──────▼──────┐  ┌──────▼───┐
    │ DB:5432  │   │ Redis:6379  │  │Qdrant    │
    │PostgreSQL│   │ (Queue)     │  │:6333     │
    └──────────┘   └─────────────┘  └──────────┘
        │                 │
    ┌───▼───────────────▼──┐
    │ Worker (Background)   │
    │ (FastAPI + ARQ)       │
    └──────────────────────┘
```

## Step-by-Step Deployment

### Step 1: Set Up Azure Resources

#### 1.1 Create Network Security Group Rules

Add these inbound rules to your Azure NSG:

```
Rule 1: Allow SSH
  Protocol: TCP
  Port: 22
  Source: Your IP or * (0.0.0.0/0)
  Action: Allow

Rule 2: Allow HTTP
  Protocol: TCP
  Port: 80
  Source: *
  Action: Allow

Rule 3: Allow HTTPS
  Protocol: TCP
  Port: 443
  Source: *
  Action: Allow
```

### Step 2: Connect to Your Server

```bash
# SSH into your server
ssh <deploy-user>@<your-domain-or-server-ip>

# Verify connectivity
echo "Connected successfully!"
```

### Step 3: Clone the Repository

```bash
# Create applications directory
mkdir -p ~/apps
cd ~/apps

# Clone the CareerOS repository
git clone <your-repo-url> careeros
cd careeros
```

Or copy from your local machine:

```bash
# From your local machine:
scp -r /path/to/CareerOS <deploy-user>@<your-domain-or-server-ip>:/opt/careeros
```

### Step 4: Run Initial Server Setup

```bash
# Make setup script executable
chmod +x deploy/ubuntu-setup.sh

# Run as root or with sudo
sudo bash deploy/ubuntu-setup.sh
```

This will:
- Install Docker, Docker Compose, Nginx, Certbot, UFW
- Configure firewall rules
- Create necessary directories
- Add your user to the docker group

**Important**: After running this, log out and log back in for group changes to take effect.

```bash
exit
# Log back in
ssh <deploy-user>@<your-domain-or-server-ip>
cd /opt/careeros
```

### Step 5: Create Environment Configuration

```bash
# Copy the template
cp .env.example .env

# Edit with your actual values
nano .env
```

**Required Variables to Set:**

```bash
# Database
POSTGRES_USER=careeros
POSTGRES_PASSWORD=YourSecurePassword123!
POSTGRES_DB=careeros_db
REDIS_PASSWORD=YourRedisPassword456!

# API Keys (get from their respective services)
SECRET_KEY=YourRandomSecretKeyAtLeast50CharsLong
ANTHROPIC_API_KEY=<anthropic-api-key>
NVIDIA_API_KEY=<nvidia-api-key>
GEMINI_API_KEY=<gemini-api-key>

# Optional but recommended
TWILIO_ACCOUNT_SID=<twilio-account-sid>
ELEVENLABS_API_KEY=<elevenlabs-api-key>
```

**Generate a secure SECRET_KEY:**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 6: Set Up SSL Certificates

**Option A: Using Certbot (Recommended for real domains)**

```bash
# Install and get free certificate
sudo certbot certonly --standalone -d <your-domain>

# Copy certificates to deploy/ssl
mkdir -p deploy/ssl
sudo cp /etc/letsencrypt/live/<your-domain>/fullchain.pem deploy/ssl/cert.pem
sudo cp /etc/letsencrypt/live/<your-domain>/privkey.pem deploy/ssl/key.pem
sudo chown -R <deploy-user>:<deploy-user> deploy/ssl
```

**Option B: Using Self-Signed Certificates (for testing)**

```bash
mkdir -p deploy/ssl
openssl req -x509 -newkey rsa:4096 \
  -keyout deploy/ssl/key.pem \
  -out deploy/ssl/cert.pem \
  -days 365 -nodes \
  -subj "/CN=<your-domain-or-server-ip>"
```

### Step 7: Deploy the Application

```bash
# Make deployment script executable
chmod +x deploy/deploy.sh

# Run deployment
bash deploy/deploy.sh
```

This will:
- Validate .env exists
- Build Docker images
- Start all containers
- Run database migrations
- Display service status

### Step 8: Verify Deployment

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f backend

# Test health endpoints
curl -k https://<your-domain-or-server-ip>/health
curl -k https://<your-domain-or-server-ip>/api/health/live
```

## Common Operations

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Restart Services

```bash
# Restart all
docker compose -f docker-compose.prod.yml restart

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Stop Services

```bash
# Stop all (keeps data)
docker compose -f docker-compose.prod.yml stop

# Stop and remove containers (keeps volumes)
docker compose -f docker-compose.prod.yml down

# Stop and remove everything including data (DESTRUCTIVE!)
docker compose -f docker-compose.prod.yml down -v
```

### Database Operations

**Create Backup**

```bash
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U careeros careeros_db > ~/apps/careeros/backups/postgres_backup_$TIMESTAMP.sql
```

**Restore Backup**

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  psql -U careeros careeros_db < ~/apps/careeros/backups/postgres_backup_YYYYMMDD_HHMMSS.sql
```

**Connect to Database**

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U careeros -d careeros_db
```

### Check Resource Usage

```bash
# Real-time resource usage
docker stats

# Disk space
docker system df
```

### Clean Up Docker

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove all unused resources
docker system prune -a
```

### View Database Logs

```bash
docker compose -f docker-compose.prod.yml logs db
```

## Accessing the Application

Once deployed, access via:

- **Frontend**: `https://<your-domain-or-server-ip>`
- **API**: `https://<your-domain-or-server-ip>/api`
- **API Docs (Swagger)**: `https://<your-domain-or-server-ip>/api/docs`
- **API Health**: `https://<your-domain-or-server-ip>/api/health/live`

## Troubleshooting

### Issue: "Cannot connect to Docker daemon"

```bash
# Check if Docker is running
sudo systemctl status docker

# If not running, start it
sudo systemctl start docker

# Add user to docker group if you haven't
sudo usermod -aG docker $USER
```

### Issue: "Connection refused" on port 80/443

```bash
# Check if Nginx is running
docker compose -f docker-compose.prod.yml ps nginx

# Check Nginx logs
docker compose -f docker-compose.prod.yml logs nginx

# Verify ports are open
sudo ufw status

# Check if ports are in use
sudo netstat -tlnp | grep :80
sudo netstat -tlnp | grep :443
```

### Issue: Backend cannot connect to database

```bash
# Check database logs
docker compose -f docker-compose.prod.yml logs db

# Check if database is healthy
docker compose -f docker-compose.prod.yml ps db

# Test database connection
docker compose -f docker-compose.prod.yml exec backend \
  python -c "from sqlalchemy import create_engine; engine = create_engine('${DATABASE_URL}'); print('Connected!' if engine.connect() else 'Failed')"
```

### Issue: Migrations fail

```bash
# Check migration history
docker compose -f docker-compose.prod.yml exec backend \
  alembic history

# Run migrations manually
docker compose -f docker-compose.prod.yml exec backend \
  alembic upgrade head

# View migration status
docker compose -f docker-compose.prod.yml exec backend \
  alembic current
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up old images/containers
docker system prune -a

# Remove old backups
ls -lah ~/apps/careeros/backups/
rm ~/apps/careeros/backups/postgres_backup_old_*.sql
```

### Issue: Containers keep restarting

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Stop containers and check individual logs
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up backend

# Look for specific errors in output
```

## Monitoring & Maintenance

### Daily Checks

```bash
# Check container health
docker compose -f docker-compose.prod.yml ps

# Check error logs
docker compose -f docker-compose.prod.yml logs --since 1h | grep ERROR
```

### Weekly Tasks

```bash
# Database backup (automated in deploy.sh, but manual backup:)
bash -c 'docker compose -f docker-compose.prod.yml exec db pg_dump -U careeros careeros_db | gzip > backups/weekly_$(date +%Y%m%d_%H%M%S).sql.gz'

# Check disk space
df -h

# Review logs
docker compose -f docker-compose.prod.yml logs --tail 1000 > ~/logs/weekly_review.log
```

### SSL Certificate Renewal

```bash
# If using Certbot, it auto-renews, but verify:
sudo certbot renew --dry-run

# Manual renewal if needed:
sudo certbot renew --force-renewal
```

## Performance Optimization

### Database Optimization

```bash
# Analyze database
docker compose -f docker-compose.prod.yml exec db \
  psql -U careeros -d careeros_db -c "ANALYZE;"

# Vacuum (clean up dead rows)
docker compose -f docker-compose.prod.yml exec db \
  psql -U careeros -d careeros_db -c "VACUUM FULL;"
```

### Update Containers

```bash
# Pull latest base images
docker compose -f docker-compose.prod.yml pull

# Rebuild with new base images
docker compose -f docker-compose.prod.yml build --no-cache

# Restart
docker compose -f docker-compose.prod.yml up -d
```

## Security Checklist

- [ ] Change all default passwords in .env
- [ ] Use strong SECRET_KEY (50+ characters)
- [ ] Enable SSL/TLS certificates
- [ ] Configure UFW firewall (ports 22, 80, 443 only)
- [ ] Restrict SSH to key-based authentication
- [ ] Set proper file permissions on .env (600)
- [ ] Disable debug mode (ENVIRONMENT=production)
- [ ] Set up automated backups
- [ ] Monitor logs regularly
- [ ] Update Docker images regularly
- [ ] Use private Docker registry if possible
- [ ] Enable audit logging

## Contact & Support

For issues or questions:
1. Check logs: `docker compose -f docker-compose.prod.yml logs -f`
2. Check deployment log: `cat ~/apps/careeros/logs/deploy_*.log`
3. Review this guide's Troubleshooting section
4. Check GitHub issues or contact your development team

---

**Last Updated**: 2024
**Version**: 1.0.0
