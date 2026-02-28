# AWS Deployment Guide — Financial Markets Monitor

> End-to-end walkthrough for deploying the full stack to AWS ECS Fargate.
> Tested with AWS CLI v2, Docker Desktop, us-east-1.

---

## Architecture Overview

```
Internet
   │
   ▼
Application Load Balancer  (port 80, public)
   │
   ▼
ECS Fargate Task  (awsvpc networking)
   ├── frontend container  (nginx :80)
   │     ├── serves React SPA  →  GET /
   │     └── proxies API calls →  /api/*  →  localhost:8000
   └── backend container   (uvicorn :8000)
         └── connects to ──►  RDS PostgreSQL  (private subnet, port 5432)
```

**Key insight — shared localhost:** In ECS `awsvpc` mode, all containers inside the same task share the same network namespace. That means the nginx container can reach the FastAPI backend at `http://localhost:8000` without any service discovery or DNS tricks.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | v2 | `brew install awscli` |
| Docker Desktop | latest | `brew install --cask docker` |
| jq | any | `brew install jq` |

> **AWS credentials** must be configured (`aws configure` or environment variables).
> The IAM user/role needs permissions for: ECR, ECS, RDS, Secrets Manager, IAM, ELB, CloudWatch Logs, VPC.

---

## Step-by-step

### Step 0 — Set environment variables

Copy and paste these into your terminal. Every subsequent command uses them.

```bash
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export APP="finmonitor"
```

---

### Step 1 — Install & start Docker Desktop

```bash
brew install --cask docker
open -a Docker          # start the GUI app
# wait ~30 s until the Docker menu-bar icon stops animating
docker info             # should print server info, not an error
```

---

### Step 2 — Create ECR repositories

ECR (Elastic Container Registry) is AWS's private Docker registry. We need one repo per image.

```bash
aws ecr create-repository --repository-name ${APP}-backend  --region $AWS_REGION
aws ecr create-repository --repository-name ${APP}-frontend --region $AWS_REGION
```

Save the registry URL for later:
```bash
export ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

---

### Step 3 — Create CloudWatch log group

ECS will stream container stdout/stderr here.

```bash
aws logs create-log-group --log-group-name /ecs/${APP} --region $AWS_REGION
```

---

### Step 4 — Networking — get VPC & subnets

We reuse the **default VPC** (every AWS account has one). Grab its ID and two of its public subnets.

```bash
export VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text)

export SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
  --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"
```

---

### Step 5 — Create security groups

Three groups, each with a narrow purpose:

```bash
# 1. ALB — accepts HTTP from anywhere on the internet
export ALB_SG=$(aws ec2 create-security-group \
  --group-name ${APP}-alb-sg \
  --description "Allow HTTP inbound to ALB" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ALB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0

# 2. ECS tasks — accept traffic from the ALB only
export ECS_SG=$(aws ec2 create-security-group \
  --group-name ${APP}-ecs-sg \
  --description "Allow traffic from ALB to ECS tasks" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG --protocol tcp --port 80 \
  --source-group $ALB_SG

# Allow all outbound (so the backend can call Finnhub, etc.)
aws ec2 authorize-security-group-egress \
  --group-id $ECS_SG --protocol -1 --port -1 --cidr 0.0.0.0/0 2>/dev/null || true

# 3. RDS — accept Postgres from ECS tasks only
export RDS_SG=$(aws ec2 create-security-group \
  --group-name ${APP}-rds-sg \
  --description "Allow Postgres from ECS" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG --protocol tcp --port 5432 \
  --source-group $ECS_SG

echo "ALB SG: $ALB_SG | ECS SG: $ECS_SG | RDS SG: $RDS_SG"
```

---

### Step 6 — Create RDS PostgreSQL

#### 6a. DB subnet group (required by RDS)
```bash
SUBNET_LIST=$(echo $SUBNET_IDS | tr ',' ' ')
aws rds create-db-subnet-group \
  --db-subnet-group-name ${APP}-subnet-group \
  --db-subnet-group-description "Subnets for finmonitor RDS" \
  --subnet-ids $SUBNET_LIST
```

#### 6b. Launch the instance
> **Why `db.t3.micro`?** It's free-tier eligible and sufficient for dev/staging. Upgrade to `db.t3.small` or larger for production load.

```bash
export DB_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/')"
echo "DB password (save this!): $DB_PASSWORD"

aws rds create-db-instance \
  --db-instance-identifier ${APP}-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15.7 \
  --master-username postgres \
  --master-user-password "$DB_PASSWORD" \
  --db-name finmonitor \
  --vpc-security-group-ids $RDS_SG \
  --db-subnet-group-name ${APP}-subnet-group \
  --no-publicly-accessible \
  --allocated-storage 20 \
  --storage-type gp2
```

#### 6c. Wait for it to be ready (~5–10 min)
```bash
echo "Waiting for RDS... (this takes ~5–10 minutes)"
aws rds wait db-instance-available --db-instance-identifier ${APP}-db
export RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier ${APP}-db \
  --query "DBInstances[0].Endpoint.Address" --output text)
echo "RDS endpoint: $RDS_ENDPOINT"
```

---

### Step 7 — Store secrets in AWS Secrets Manager

Never bake secrets into Docker images or task definitions. We store them in Secrets Manager and reference them by ARN in the task definition.

```bash
# Grab the Finnhub key from the local .env
export FINNHUB_KEY=$(grep FINNHUB_API_KEY backend/.env | cut -d= -f2)

export SECRET_ARN=$(aws secretsmanager create-secret \
  --name ${APP}/config \
  --description "finmonitor app secrets" \
  --secret-string "{
    \"database_url\": \"postgresql+asyncpg://postgres:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/finmonitor\",
    \"finnhub_api_key\": \"${FINNHUB_KEY}\",
    \"cors_origins\": \"[\\\"*\\\"]\"
  }" \
  --query ARN --output text)

echo "Secret ARN: $SECRET_ARN"
```

> `cors_origins` is set to `["*"]` initially. We'll tighten it to the ALB URL after we know it.

---

### Step 8 — Create IAM roles

ECS needs two IAM roles:
- **Execution role** — used by the ECS agent to pull images from ECR and read secrets.
- **Task role** — used by your application code at runtime (add permissions here if your app calls S3, SQS, etc.).

```bash
# --- Execution Role ---
aws iam create-role \
  --role-name ${APP}-execution-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy \
  --role-name ${APP}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Allow reading the specific Secrets Manager secret
aws iam put-role-policy \
  --role-name ${APP}-execution-role \
  --policy-name SecretsManagerRead \
  --policy-document "{
    \"Version\":\"2012-10-17\",
    \"Statement\":[{
      \"Effect\":\"Allow\",
      \"Action\":[\"secretsmanager:GetSecretValue\"],
      \"Resource\":\"${SECRET_ARN}\"
    }]
  }"

export EXEC_ROLE_ARN=$(aws iam get-role \
  --role-name ${APP}-execution-role \
  --query Role.Arn --output text)

# --- Task Role (minimal for now) ---
aws iam create-role \
  --role-name ${APP}-task-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

export TASK_ROLE_ARN=$(aws iam get-role \
  --role-name ${APP}-task-role \
  --query Role.Arn --output text)

echo "Exec role: $EXEC_ROLE_ARN"
echo "Task role: $TASK_ROLE_ARN"
```

---

### Step 9 — Code changes before building

Two small fixes are required for the containers to work correctly in ECS (they differ from the local Docker Compose setup):

#### 9a. `frontend/nginx.conf` — use `localhost` not `backend`
In Docker Compose, `backend` resolves via Docker's internal DNS.
In ECS `awsvpc` mode, containers share localhost — so we change the proxy target:

```bash
sed -i '' 's|http://backend:8000|http://localhost:8000|g' frontend/nginx.conf
```

#### 9b. `frontend/src/hooks/useWebSocket.ts` — dynamic WebSocket URL
The WS URL must be derived from the browser's current host (the ALB URL) at runtime,
because we don't know it at Docker build time:

The line:
```ts
const WS_URL = process.env.REACT_APP_WS_URL || "ws://localhost:8000/api/ws";
```
becomes:
```ts
const WS_URL = process.env.REACT_APP_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws`;
```

---

### Step 10 — Build & push Docker images

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_BASE

# Backend
docker build -t ${APP}-backend ./backend
docker tag ${APP}-backend:latest ${ECR_BASE}/${APP}-backend:latest
docker push ${ECR_BASE}/${APP}-backend:latest

# Frontend — pass REACT_APP_API_URL=/api so it uses nginx as the proxy
docker build \
  --build-arg REACT_APP_API_URL=/api \
  -t ${APP}-frontend ./frontend
docker tag ${APP}-frontend:latest ${ECR_BASE}/${APP}-frontend:latest
docker push ${ECR_BASE}/${APP}-frontend:latest
```

---

### Step 11 — Create ECS cluster

```bash
aws ecs create-cluster --cluster-name $APP
```

---

### Step 12 — Create the Application Load Balancer

#### 12a. Create ALB
```bash
export ALB_ARN=$(aws elbv2 create-load-balancer \
  --name ${APP}-alb \
  --subnets $(echo $SUBNET_IDS | tr ',' ' ') \
  --security-groups $ALB_SG \
  --scheme internet-facing \
  --type application \
  --query "LoadBalancers[0].LoadBalancerArn" --output text)

export ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" --output text)

echo "ALB DNS: $ALB_DNS"
```

#### 12b. Create target group
```bash
export TG_ARN=$(aws elbv2 create-target-group \
  --name ${APP}-tg \
  --protocol HTTP \
  --port 80 \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path / \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --query "TargetGroups[0].TargetGroupArn" --output text)
```

#### 12c. Create listener
```bash
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN
```

---

### Step 13 — Register the ECS task definition

```bash
aws ecs register-task-definition --cli-input-json "{
  \"family\": \"${APP}\",
  \"networkMode\": \"awsvpc\",
  \"requiresCompatibilities\": [\"FARGATE\"],
  \"cpu\": \"512\",
  \"memory\": \"1024\",
  \"executionRoleArn\": \"${EXEC_ROLE_ARN}\",
  \"taskRoleArn\": \"${TASK_ROLE_ARN}\",
  \"containerDefinitions\": [
    {
      \"name\": \"backend\",
      \"image\": \"${ECR_BASE}/${APP}-backend:latest\",
      \"essential\": true,
      \"portMappings\": [{\"containerPort\": 8000, \"protocol\": \"tcp\"}],
      \"secrets\": [
        {\"name\": \"DATABASE_URL\",    \"valueFrom\": \"${SECRET_ARN}:database_url::\"},
        {\"name\": \"FINNHUB_API_KEY\", \"valueFrom\": \"${SECRET_ARN}:finnhub_api_key::\"},
        {\"name\": \"CORS_ORIGINS\",    \"valueFrom\": \"${SECRET_ARN}:cors_origins::\"}
      ],
      \"environment\": [
        {\"name\": \"APP_ENV\",   \"value\": \"production\"},
        {\"name\": \"LOG_LEVEL\", \"value\": \"WARNING\"}
      ],
      \"logConfiguration\": {
        \"logDriver\": \"awslogs\",
        \"options\": {
          \"awslogs-group\":         \"/ecs/${APP}\",
          \"awslogs-region\":        \"${AWS_REGION}\",
          \"awslogs-stream-prefix\": \"backend\"
        }
      }
    },
    {
      \"name\": \"frontend\",
      \"image\": \"${ECR_BASE}/${APP}-frontend:latest\",
      \"essential\": true,
      \"portMappings\": [{\"containerPort\": 80, \"protocol\": \"tcp\"}],
      \"dependsOn\": [{\"containerName\": \"backend\", \"condition\": \"START\"}],
      \"logConfiguration\": {
        \"logDriver\": \"awslogs\",
        \"options\": {
          \"awslogs-group\":         \"/ecs/${APP}\",
          \"awslogs-region\":        \"${AWS_REGION}\",
          \"awslogs-stream-prefix\": \"frontend\"
        }
      }
    }
  ]
}"
```

---

### Step 14 — Create ECS service

```bash
aws ecs create-service \
  --cluster $APP \
  --service-name ${APP}-service \
  --task-definition $APP \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[$(echo $SUBNET_IDS | sed 's/,/,/g')],
    securityGroups=[$ECS_SG],
    assignPublicIp=ENABLED
  }" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=frontend,containerPort=80"
```

---

### Step 15 — Wait & verify

```bash
echo "Waiting for ECS service to stabilize (~3–5 min)..."
aws ecs wait services-stable \
  --cluster $APP \
  --services ${APP}-service

echo "✅ Service is stable!"
echo "App URL: http://${ALB_DNS}"
curl -s "http://${ALB_DNS}/api/health"
# Expected: {"status":"ok"}
```

Open `http://<ALB_DNS>` in your browser — the dashboard should load with news and prices.

---

## Re-deploy after code changes

```bash
# Rebuild & push
docker build -t ${APP}-backend ./backend
docker tag ${APP}-backend:latest ${ECR_BASE}/${APP}-backend:latest
docker push ${ECR_BASE}/${APP}-backend:latest

# Force new deployment (ECS will pull the new :latest image)
aws ecs update-service \
  --cluster $APP \
  --service ${APP}-service \
  --force-new-deployment
```

This is also what `deploy/aws/deploy.sh` does — it builds, pushes, and triggers a rolling update.

---

## Useful commands

```bash
# View running tasks
aws ecs list-tasks --cluster $APP

# View logs (backend)
aws logs tail /ecs/finmonitor --filter-pattern "backend" --follow

# Describe service health
aws ecs describe-services --cluster $APP --services ${APP}-service \
  --query "services[0].{status:status,running:runningCount,desired:desiredCount}"

# SSH-like exec into a running container (requires ECS Exec enabled)
aws ecs execute-command --cluster $APP \
  --task <task-id> --container backend \
  --interactive --command "/bin/bash"
```

---

## Teardown (avoid ongoing charges)

```bash
# Scale down service
aws ecs update-service --cluster $APP --service ${APP}-service --desired-count 0

# Delete service
aws ecs delete-service --cluster $APP --service ${APP}-service --force

# Delete RDS (takes a few minutes)
aws rds delete-db-instance \
  --db-instance-identifier ${APP}-db \
  --skip-final-snapshot

# Delete ALB + target group
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
aws elbv2 delete-target-group --target-group-arn $TG_ARN

# Delete ECR repos
aws ecr delete-repository --repository-name ${APP}-backend --force
aws ecr delete-repository --repository-name ${APP}-frontend --force

# Delete secrets
aws secretsmanager delete-secret --secret-id ${APP}/config --force-delete-without-recovery

# Delete security groups (must delete in order: ECS → RDS → ALB)
aws ec2 delete-security-group --group-id $ECS_SG
aws ec2 delete-security-group --group-id $RDS_SG
aws ec2 delete-security-group --group-id $ALB_SG

# Delete ECS cluster
aws ecs delete-cluster --cluster $APP
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Task stops immediately | Missing secret / bad DB URL | Check CloudWatch logs at `/ecs/finmonitor` |
| ALB returns 502 Bad Gateway | Frontend container not healthy | Ensure nginx is running; check target group health |
| News feed empty | Finnhub key invalid in Secrets Manager | Update secret, force new deployment |
| WebSocket not connecting | nginx proxy not forwarding Upgrade header | Check nginx.conf has `proxy_set_header Upgrade $http_upgrade` |
| `CannotPullContainerError` | ECR auth or wrong image URI | Verify execution role has ECR pull permissions |
