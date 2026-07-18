#!/bin/bash

# CareerOS Production Server Setup Script
# Run this once on your Ubuntu 24.04 Azure server
# Usage: bash deploy/ubuntu-setup.sh

set -e

echo "========================================="
echo "CareerOS Production Setup Script"
echo "Ubuntu 24.04"
echo "========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

echo ""
echo "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y

echo ""
echo "[2/8] Installing Docker..."
apt-get install -y ca-certificates curl gnupg lsb-release

mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo ""
echo "[3/8] Starting Docker service..."
systemctl start docker
systemctl enable docker

echo ""
echo "[4/8] Installing required tools..."
apt-get install -y git curl wget htop nano vim nginx certbot python3-certbot-nginx ufw

echo ""
echo "[5/8] Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
echo "y" | ufw enable

echo ""
echo "[6/8] Creating application directory..."
APP_DIR="${CAREEROS_DEPLOY_DIR:-/opt/careeros}"
DEPLOY_USER="${CAREEROS_DEPLOY_USER:-${SUDO_USER:-ubuntu}}"
mkdir -p "$APP_DIR"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"
chmod 755 "$APP_DIR"

echo ""
echo "[7/8] Creating deployment directories..."
mkdir -p "$APP_DIR/deploy/ssl"
mkdir -p "$APP_DIR/logs"
mkdir -p "$APP_DIR/backups"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR/deploy"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR/logs"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR/backups"

echo ""
echo "[8/8] Adding user to docker group..."
usermod -aG docker "$DEPLOY_USER"

echo ""
echo "========================================="
echo "✅ Server setup completed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Log out and log back in for group changes to take effect"
echo "2. cd $APP_DIR"
echo "3. Copy this repository code to the server"
echo "4. Create .env file from .env.example"
echo "5. Run: bash deploy/deploy.sh"
echo ""
echo "To generate SSL certificates:"
echo "  sudo certbot certonly --standalone -d <your-domain>"
echo ""
echo "For self-signed certificates:"
echo "  mkdir -p deploy/ssl"
echo "  openssl req -x509 -newkey rsa:4096 -keyout deploy/ssl/key.pem -out deploy/ssl/cert.pem -days 365 -nodes"
echo ""
