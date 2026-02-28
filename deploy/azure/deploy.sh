#!/usr/bin/env bash
# Azure Container Apps deployment script
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
ACR_NAME="${ACR_NAME:?Set ACR_NAME}"
LOCATION="${LOCATION:-eastus}"

echo "=== Logging in to Azure Container Registry ==="
az acr login --name "$ACR_NAME"

echo "=== Building and pushing backend ==="
docker build -t finmonitor-backend ./backend
docker tag finmonitor-backend:latest "${ACR_NAME}.azurecr.io/finmonitor-backend:latest"
docker push "${ACR_NAME}.azurecr.io/finmonitor-backend:latest"

echo "=== Building and pushing frontend ==="
docker build -t finmonitor-frontend ./frontend
docker tag finmonitor-frontend:latest "${ACR_NAME}.azurecr.io/finmonitor-frontend:latest"
docker push "${ACR_NAME}.azurecr.io/finmonitor-frontend:latest"

echo "=== Deploying backend to Container Apps ==="
az containerapp update \
  --name finmonitor-backend \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_NAME}.azurecr.io/finmonitor-backend:latest"

echo "=== Deploying frontend to Container Apps ==="
az containerapp update \
  --name finmonitor-frontend \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_NAME}.azurecr.io/finmonitor-frontend:latest"

echo "=== Done ==="
az containerapp list --resource-group "$RESOURCE_GROUP" -o table
