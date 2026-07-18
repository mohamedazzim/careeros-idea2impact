#!/bin/bash

# Production deployment script

set -e

# Configuration
REGISTRY="docker.io"  # or your private registry
USERNAME="your-docker-username"
BACKEND_VERSION="1.0.0"
WORKER_VERSION="1.0.0"
FRONTEND_VERSION="1.0.0"
DOMAIN="yourdomain.com"

echo "🔐 Logging in to Docker Registry..."
docker login $REGISTRY

echo "📦 Building Backend Image..."
docker build -f ./backend/Dockerfile -t $REGISTRY/$USERNAME/careeros-backend:$BACKEND_VERSION ./backend
docker tag $REGISTRY/$USERNAME/careeros-backend:$BACKEND_VERSION $REGISTRY/$USERNAME/careeros-backend:latest

echo "📦 Building Worker Image..."
docker build -f ./backend/Dockerfile -t $REGISTRY/$USERNAME/careeros-worker:$WORKER_VERSION ./backend
docker tag $REGISTRY/$USERNAME/careeros-worker:$WORKER_VERSION $REGISTRY/$USERNAME/careeros-worker:latest

echo "📦 Building Frontend Image..."
docker build -f ./frontend/Dockerfile -t $REGISTRY/$USERNAME/careeros-frontend:$FRONTEND_VERSION ./frontend
docker tag $REGISTRY/$USERNAME/careeros-frontend:$FRONTEND_VERSION $REGISTRY/$USERNAME/careeros-frontend:latest

echo "⬆️  Pushing Backend Image..."
docker push $REGISTRY/$USERNAME/careeros-backend:$BACKEND_VERSION
docker push $REGISTRY/$USERNAME/careeros-backend:latest

echo "⬆️  Pushing Worker Image..."
docker push $REGISTRY/$USERNAME/careeros-worker:$WORKER_VERSION
docker push $REGISTRY/$USERNAME/careeros-worker:latest

echo "⬆️  Pushing Frontend Image..."
docker push $REGISTRY/$USERNAME/careeros-frontend:$FRONTEND_VERSION
docker push $REGISTRY/$USERNAME/careeros-frontend:latest

echo "✅ All images pushed successfully!"
