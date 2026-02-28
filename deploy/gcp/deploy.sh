#!/usr/bin/env bash
# Google Cloud Run deployment script
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"

echo "=== Building backend with Cloud Build ==="
gcloud builds submit ./backend \
  --tag "gcr.io/${PROJECT_ID}/finmonitor-backend:latest" \
  --project "$PROJECT_ID"

echo "=== Deploying backend to Cloud Run ==="
gcloud run deploy finmonitor-backend \
  --image "gcr.io/${PROJECT_ID}/finmonitor-backend:latest" \
  --region "$REGION" \
  --allow-unauthenticated \
  --project "$PROJECT_ID"

echo "=== Building frontend with Cloud Build ==="
gcloud builds submit ./frontend \
  --tag "gcr.io/${PROJECT_ID}/finmonitor-frontend:latest" \
  --project "$PROJECT_ID"

echo "=== Deploying frontend to Cloud Run ==="
gcloud run deploy finmonitor-frontend \
  --image "gcr.io/${PROJECT_ID}/finmonitor-frontend:latest" \
  --region "$REGION" \
  --allow-unauthenticated \
  --project "$PROJECT_ID"

echo "=== Done ==="
gcloud run services list --project "$PROJECT_ID" --region "$REGION"
