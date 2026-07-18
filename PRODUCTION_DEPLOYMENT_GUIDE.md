# Production Deployment Guide

## Prerequisites on Server

1. **Install Docker & Docker Compose**
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-plugin
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **Create Project Directory**
   ```bash
   mkdir -p /opt/careeros
   cd /opt/careeros
   ```

3. **Set Secure Permissions**
   ```bash
   sudo chmod 700 /opt/careeros
   ```

## Deployment Steps

### Step 1: Copy Files to Server
```bash
scp docker-compose.production.yml user@server:/opt/careeros/
scp .env.production user@server:/opt/careeros/.env
```

### Step 2: Configure Environment Variables
```bash
ssh user@server
cd /opt/careeros
nano .env  # Edit with your actual values
```

**Required Variables:**
- `DB_PASSWORD` - Strong PostgreSQL password
- `REDIS_PASSWORD` - Strong Redis password  
- `SECRET_KEY` - FastAPI/JWT signing secret (generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `REGISTRY` - Docker registry URL (e.g., docker.io/yourusername)
- `BACKEND_VERSION` - Version tag (e.g., 1.0.0)
- `WORKER_VERSION` - Version tag
- `FRONTEND_VERSION` - Version tag
- `DOMAIN` - Your production domain

### Step 3: Create Secrets File (Never Commit to Git)
```bash
sudo nano /opt/careeros/.env
# Add all sensitive values
sudo chmod 600 /opt/careeros/.env
```

### Step 4: Start Services
```bash
cd /opt/careeros
docker compose -f docker-compose.production.yml --env-file .env up -d
```

### Step 5: Verify Deployment
```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f backend
```

### Step 6: Run Migrations
```bash
docker compose -f docker-compose.production.yml exec backend \
  python -m alembic upgrade head
```

## SSL/TLS with Nginx Reverse Proxy

Create `/opt/careeros/nginx.conf`:
```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 100M;

    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Add to docker-compose.production.yml:
```yaml
  nginx:
    image: nginx:alpine
    container_name: careeros-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
    networks:
      - careeros
```

Install SSL Certificate with Certbot:
```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

## Monitoring & Logging

### View Logs
```bash
docker compose -f docker-compose.production.yml logs -f backend
docker compose -f docker-compose.production.yml logs -f worker
docker compose -f docker-compose.production.yml logs db
```

### Health Checks
```bash
docker compose -f docker-compose.production.yml ps
curl https://yourdomain.com/api/health
```

### Backup Database
```bash
docker compose -f docker-compose.production.yml exec db \
  pg_dump -U careeros careeros_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

## Scaling & Updates

### Update Images
```bash
export BACKEND_VERSION=1.0.1
export WORKER_VERSION=1.0.1
export FRONTEND_VERSION=1.0.1
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d
```

### Scale Workers (Replicas)
```bash
docker compose -f docker-compose.production.yml up -d --scale worker=3
```

## Troubleshooting

### Database Connection Issues
```bash
docker compose -f docker-compose.production.yml exec db \
  psql -U careeros -d careeros_db -c "SELECT 1;"
```

### Redis Connection
```bash
docker compose -f docker-compose.production.yml exec redis \
  redis-cli -a ${REDIS_PASSWORD} ping
```

### Clear All Data (Use Caution!)
```bash
docker compose -f docker-compose.production.yml down -v
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY
- [ ] Enable SSL/TLS certificates
- [ ] Set up firewall rules
- [ ] Configure backups
- [ ] Set up monitoring & alerts
- [ ] Use environment files (never commit .env)
- [ ] Restrict container capabilities (already in compose file)
- [ ] Set proper file permissions (chmod 600 for .env)
- [ ] Disable debug mode in production
