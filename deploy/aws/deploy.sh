#!/usr/bin/env bash
# AWS ECS Fargate deployment script
# Prerequisites: AWS CLI configured, ECR repos created, ECS cluster exists
#
# All required environment variables are documented in deploy/aws/.env.example
# Quick start:
#   cp deploy/aws/.env.example deploy/aws/.env   # fill in values
#   set -a && source deploy/aws/.env && set +a
#   bash deploy/aws/deploy.sh
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
CLUSTER_NAME="${CLUSTER_NAME:-finmonitor}"
SERVICE_NAME="${SERVICE_NAME:-finmonitor-service}"
TASK_FAMILY="${TASK_FAMILY:-finmonitor}"

# Fail fast — no hardcoded fallbacks for secrets or environment-specific values
REACT_APP_GOOGLE_CLIENT_ID="${REACT_APP_GOOGLE_CLIENT_ID:?Set REACT_APP_GOOGLE_CLIENT_ID}"
REACT_APP_WS_URL="${REACT_APP_WS_URL:?Set REACT_APP_WS_URL}"

# Network config required for Fargate tasks (migration + service)
SUBNET_IDS="${SUBNET_IDS:?Set SUBNET_IDS (comma-separated subnet IDs)}"
SECURITY_GROUP_IDS="${SECURITY_GROUP_IDS:?Set SECURITY_GROUP_IDS (comma-separated sg IDs)}"
TARGET_GROUP_ARN="${TARGET_GROUP_ARN:?Set TARGET_GROUP_ARN (ALB target group ARN)}"

NETWORK_CONFIG="awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SECURITY_GROUP_IDS}],assignPublicIp=ENABLED}"

ECR_BACKEND="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/finmonitor-backend"
ECR_FRONTEND="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/finmonitor-frontend"

echo "=== Logging in to ECR ==="
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "=== Building and pushing backend ==="
docker build --platform linux/amd64 -t finmonitor-backend ./backend
docker tag finmonitor-backend:latest "$ECR_BACKEND:latest"
docker push "$ECR_BACKEND:latest"

echo "=== Building and pushing frontend ==="
docker build --platform linux/amd64 -t finmonitor-frontend ./frontend \
  --build-arg REACT_APP_API_URL=/api \
  --build-arg REACT_APP_WS_URL="$REACT_APP_WS_URL" \
  --build-arg REACT_APP_GOOGLE_CLIENT_ID="$REACT_APP_GOOGLE_CLIENT_ID" \
  --build-arg NGINX_CONF=nginx.prod.conf
docker tag finmonitor-frontend:latest "$ECR_FRONTEND:latest"
docker push "$ECR_FRONTEND:latest"

echo "=== Running DB migrations ==="
MIGRATION_TASK_ARN=$(aws ecs run-task \
  --cluster "$CLUSTER_NAME" \
  --task-definition "$TASK_FAMILY" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}' \
  --launch-type FARGATE \
  --network-configuration "$NETWORK_CONFIG" \
  --region "$AWS_REGION" \
  --query 'tasks[0].taskArn' \
  --output text)

echo "Migration task: $MIGRATION_TASK_ARN — waiting for completion..."
aws ecs wait tasks-stopped \
  --cluster "$CLUSTER_NAME" \
  --tasks "$MIGRATION_TASK_ARN" \
  --region "$AWS_REGION"

MIGRATION_EXIT_CODE=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$MIGRATION_TASK_ARN" \
  --region "$AWS_REGION" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)

if [ "$MIGRATION_EXIT_CODE" != "0" ]; then
  echo "ERROR: Migration failed with exit code $MIGRATION_EXIT_CODE. Aborting deploy."
  exit 1
fi
echo "Migrations applied successfully."

echo "=== Updating ALB health check to /ready ==="
aws elbv2 modify-target-group \
  --target-group-arn "$TARGET_GROUP_ARN" \
  --health-check-path /ready \
  --health-check-interval-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region "$AWS_REGION"

echo "=== Updating ECS service (task def: ${TASK_FAMILY}:latest) ==="
aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --task-definition "$TASK_FAMILY" \
  --force-new-deployment \
  --region "$AWS_REGION"

echo "=== Deployment triggered. Monitor at: ==="
echo "https://${AWS_REGION}.console.aws.amazon.com/ecs/v2/clusters/${CLUSTER_NAME}/services/${SERVICE_NAME}"
