#!/usr/bin/env bash
# AWS ECS Fargate deployment script
# Prerequisites: AWS CLI configured, ECR repos created, ECS cluster exists
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
CLUSTER_NAME="${CLUSTER_NAME:-finmonitor}"
SERVICE_NAME="${SERVICE_NAME:-finmonitor-service}"

ECR_BACKEND="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/finmonitor-backend"
ECR_FRONTEND="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/finmonitor-frontend"

echo "=== Logging in to ECR ==="
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "=== Building and pushing backend ==="
docker build -t finmonitor-backend ./backend
docker tag finmonitor-backend:latest "$ECR_BACKEND:latest"
docker push "$ECR_BACKEND:latest"

echo "=== Building and pushing frontend ==="
docker build -t finmonitor-frontend ./frontend \
  --build-arg REACT_APP_API_URL=/api \
  --build-arg REACT_APP_WS_URL=wss://d1yleiq0s9sk4n.cloudfront.net/api/ws
docker tag finmonitor-frontend:latest "$ECR_FRONTEND:latest"
docker push "$ECR_FRONTEND:latest"

echo "=== Updating ECS service ==="
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --force-new-deployment \
  --region "$AWS_REGION"

echo "=== Deployment triggered. Monitor at: ==="
echo "https://${AWS_REGION}.console.aws.amazon.com/ecs/v2/clusters/${CLUSTER_NAME}/services/${SERVICE_NAME}"
