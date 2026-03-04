# AWS Deployment Guide — Financial Markets Monitor

> End-to-end walkthrough for deploying the full stack to AWS ECS Fargate.
> **Battle-tested:** every issue section below is a real problem encountered during the first deployment — not hypothetical.

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

**Key insight — shared localhost:** In ECS `awsvpc` mode, all containers inside the same task share the same network namespace. The nginx container can reach the FastAPI backend at `http://localhost:8000` — no service discovery or DNS needed. This is different from Docker Compose, where containers talk to each other by service name (e.g. `http://backend:8000`).

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | v2 | `brew install awscli` |
| Colima + Docker CLI | latest | see Step 1 — do NOT use `brew install --cask docker` |
| docker-buildx | latest | `brew install docker-buildx` |
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
export ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
```

---

### Step 1 — Install Docker (use Colima, not Docker Desktop)

> **Why Colima?** `brew install --cask docker` (Docker Desktop) requires `sudo` to create `/usr/local/cli-plugins` during install. In a non-interactive terminal it silently fails. Colima is a lightweight VM-based Docker runtime that installs without sudo and works identically for building and pushing images.

```bash
brew install colima docker docker-buildx

# Start the VM (2 CPU / 4 GB RAM is enough for building these images)
colima start --cpu 2 --memory 4

# Link the buildx plugin so `docker buildx` works
mkdir -p ~/.docker/cli-plugins
ln -sf /opt/homebrew/opt/docker-buildx/bin/docker-buildx ~/.docker/cli-plugins/docker-buildx

# Verify
docker info       # should show Server Version
docker buildx version
```

> **If you see `docker-credential-desktop: executable file not found`:**
> Docker's config file still references the Docker Desktop credential helper.
> Fix it by removing the `credsStore` entry:
> ```bash
> cat > ~/.docker/config.json << 'EOF'
> {
>   "auths": {},
>   "currentContext": "colima"
> }
> EOF
> ```

---

### Step 2 — Create ECR repositories

ECR (Elastic Container Registry) is AWS's private Docker registry. We need one repo per image.

```bash
aws ecr create-repository --repository-name ${APP}-backend  --region $AWS_REGION
aws ecr create-repository --repository-name ${APP}-frontend --region $AWS_REGION
```

---

### Step 3 — Create CloudWatch log group

ECS streams container stdout/stderr here. Check this first when a task fails to start.

```bash
aws logs create-log-group --log-group-name /ecs/${APP} --region $AWS_REGION
```

---

### Step 4 — Get default VPC & subnets

We reuse the **default VPC** (every AWS account has one).

```bash
export VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text)

# Get all public subnets — we'll use two for the ALB
export SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
  --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"

# Pick the first two for ALB (store separately — the ALB CLI needs space-separated, not comma)
export SUBNET_A=$(echo $SUBNET_IDS | cut -d, -f1)
export SUBNET_B=$(echo $SUBNET_IDS | cut -d, -f2)
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

# 2. ECS tasks — accept traffic only from the ALB
export ECS_SG=$(aws ec2 create-security-group \
  --group-name ${APP}-ecs-sg \
  --description "Allow traffic from ALB to ECS tasks" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG --protocol tcp --port 80 --source-group $ALB_SG
aws ec2 authorize-security-group-ingress \
  --group-id $ECS_SG --protocol tcp --port 8000 --source-group $ALB_SG

# 3. RDS — accepts Postgres only from ECS tasks
export RDS_SG=$(aws ec2 create-security-group \
  --group-name ${APP}-rds-sg \
  --description "Allow Postgres from ECS" \
  --vpc-id $VPC_ID \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG --protocol tcp --port 5432 --source-group $ECS_SG

echo "ALB SG: $ALB_SG | ECS SG: $ECS_SG | RDS SG: $RDS_SG"
```

---

### Step 6 — Create RDS PostgreSQL

#### 6a. DB subnet group (required by RDS — must span ≥ 2 AZs)
```bash
aws rds create-db-subnet-group \
  --db-subnet-group-name ${APP}-subnet-group \
  --db-subnet-group-description "Subnets for finmonitor RDS" \
  --subnet-ids $SUBNET_A $SUBNET_B
```

#### 6b. Launch the instance
> **Why `db.t3.micro`?** Free-tier eligible. Sufficient for dev/staging. Upgrade to `db.t3.small` or larger for production load.

```bash
export DB_PASSWORD="$(openssl rand -base64 18 | tr -d '=+/')"
echo "DB password (save this now!): $DB_PASSWORD"

aws rds create-db-instance \
  --db-instance-identifier ${APP}-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
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
echo "Waiting for RDS... (~5–10 minutes)"
aws rds wait db-instance-available --db-instance-identifier ${APP}-db

export RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier ${APP}-db \
  --query "DBInstances[0].Endpoint.Address" --output text)
echo "RDS endpoint: $RDS_ENDPOINT"
```

---

### Step 7 — Store secrets in AWS Secrets Manager

Never bake secrets into Docker images or task definitions. Store them here and reference by ARN.

```bash
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

> `cors_origins` is `["*"]` for now. Once you know your ALB DNS name, tighten it:
> ```bash
> aws secretsmanager update-secret --secret-id $SECRET_ARN \
>   --secret-string "{..., \"cors_origins\": \"[\\\"http://${ALB_DNS}\\\"]\"}"
> aws ecs update-service --cluster $APP --service ${APP}-service --force-new-deployment
> ```

---

### Step 8 — Create IAM roles

ECS needs two roles:
- **Execution role** — used by the ECS agent to pull ECR images and read Secrets Manager.
- **Task role** — used by your app code at runtime. Add permissions here if the app needs S3, SQS, etc.

```bash
# Execution role
aws iam create-role \
  --role-name ${APP}-execution-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name ${APP}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

aws iam put-role-policy \
  --role-name ${APP}-execution-role \
  --policy-name SecretsManagerRead \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"secretsmanager:GetSecretValue\"],\"Resource\":\"${SECRET_ARN}\"}]}"

export EXEC_ROLE_ARN=$(aws iam get-role --role-name ${APP}-execution-role --query Role.Arn --output text)

# Task role
aws iam create-role \
  --role-name ${APP}-task-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

export TASK_ROLE_ARN=$(aws iam get-role --role-name ${APP}-task-role --query Role.Arn --output text)

echo "Exec role: $EXEC_ROLE_ARN"
echo "Task role: $TASK_ROLE_ARN"
```

---

### Step 9 — Build & push Docker images

> **Important:** Use `docker buildx build --platform linux/amd64 --load` for cross-platform builds on Apple Silicon (M1/M2/M3). Plain `docker build --platform linux/amd64` with multi-stage Dockerfiles fails with a content digest error on ARM Macs. See Issues section below.

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_BASE

# Backend
docker buildx build --platform linux/amd64 --load \
  -t ${ECR_BASE}/${APP}-backend:latest ./backend
docker push ${ECR_BASE}/${APP}-backend:latest

# Frontend — REACT_APP_API_URL=/api makes all API calls relative,
# so nginx can proxy them to the backend on localhost:8000
docker buildx build --platform linux/amd64 --load \
  --build-arg REACT_APP_API_URL=/api \
  -t ${ECR_BASE}/${APP}-frontend:latest ./frontend
docker push ${ECR_BASE}/${APP}-frontend:latest
```

---

### Step 10 — Create ECS cluster

```bash
aws ecs create-cluster --cluster-name $APP --region $AWS_REGION
```

---

### Step 11 — Create Application Load Balancer

> **Important:** Pass `--subnets` as space-separated arguments, not a comma-separated string. `--subnets "id1,id2"` or `--subnets "id1 id2"` will fail with `InvalidSubnet`. Correct form is `--subnets id1 id2`.

```bash
export ALB_ARN=$(aws elbv2 create-load-balancer \
  --name ${APP}-alb \
  --subnets $SUBNET_A $SUBNET_B \
  --security-groups $ALB_SG \
  --scheme internet-facing \
  --type application \
  --region $AWS_REGION \
  --query "LoadBalancers[0].LoadBalancerArn" --output text)

export ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --query "LoadBalancers[0].DNSName" --output text)

echo "ALB DNS: $ALB_DNS"

# Target group (health check on / — nginx returns 200 for the React app)
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
  --region $AWS_REGION \
  --query "TargetGroups[0].TargetGroupArn" --output text)

# Listener
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn=$TG_ARN \
  --region $AWS_REGION
```

---

### Step 12 — Register ECS task definition

> **Important:** Do NOT pass the JSON inline as a shell string — variable expansion and escaping issues cause the registration to silently succeed but produce an empty task definition list. Always write the JSON to a file and use `file://`.

```bash
cat > /tmp/${APP}-taskdef.json << EOF
{
  "family": "${APP}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "${EXEC_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "${ECR_BASE}/${APP}-backend:latest",
      "essential": true,
      "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
      "secrets": [
        {"name": "DATABASE_URL",    "valueFrom": "${SECRET_ARN}:database_url::"},
        {"name": "FINNHUB_API_KEY", "valueFrom": "${SECRET_ARN}:finnhub_api_key::"},
        {"name": "CORS_ORIGINS",    "valueFrom": "${SECRET_ARN}:cors_origins::"}
      ],
      "environment": [
        {"name": "APP_ENV",   "value": "production"},
        {"name": "LOG_LEVEL", "value": "WARNING"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group":         "/ecs/${APP}",
          "awslogs-region":        "${AWS_REGION}",
          "awslogs-stream-prefix": "backend"
        }
      }
    },
    {
      "name": "frontend",
      "image": "${ECR_BASE}/${APP}-frontend:latest",
      "essential": true,
      "portMappings": [{"containerPort": 80, "protocol": "tcp"}],
      "dependsOn": [{"containerName": "backend", "condition": "START"}],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group":         "/ecs/${APP}",
          "awslogs-region":        "${AWS_REGION}",
          "awslogs-stream-prefix": "frontend"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition \
  --region $AWS_REGION \
  --cli-input-json file:///tmp/${APP}-taskdef.json \
  --query "taskDefinition.{arn:taskDefinitionArn,revision:revision}" \
  --output table
```

---

### Step 13 — Create ECS service

```bash
aws ecs create-service \
  --cluster $APP \
  --service-name ${APP}-service \
  --task-definition ${APP}:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_A},${SUBNET_B}],securityGroups=[${ECS_SG}],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=frontend,containerPort=80" \
  --region $AWS_REGION \
  --query "service.{status:status,desired:desiredCount}"
```

---

### Step 14 — Wait & verify

```bash
echo "Waiting for ECS service to stabilize (~3–5 min)..."
aws ecs wait services-stable \
  --cluster $APP \
  --services ${APP}-service \
  --region $AWS_REGION

echo "Service is stable!"
echo "App URL: http://${ALB_DNS}"

# Smoke test — the backend has no /api/health route, use /api/tickers instead
curl -s "http://${ALB_DNS}/api/tickers"
# Expected: [] (empty array — no tickers added yet, but 200 means everything is wired up)
```

Open `http://<ALB_DNS>` in your browser — the dashboard loads with news and prices.

---

## Re-deploy after code changes

```bash
# Rebuild & push (use the same buildx command as Step 9)
docker buildx build --platform linux/amd64 --load \
  -t ${ECR_BASE}/${APP}-backend:latest ./backend
docker push ${ECR_BASE}/${APP}-backend:latest

# Force ECS to pull the new :latest image with a rolling update
aws ecs update-service \
  --cluster $APP \
  --service ${APP}-service \
  --force-new-deployment \
  --region $AWS_REGION
```

This is also what `deploy/aws/deploy.sh` does — build, push, rolling update.

---

## Issues Encountered & Fixes

These are real problems that came up during the first deployment of this app. Read before you start.

---

### Issue 1: `brew install --cask docker` fails silently without sudo

**Symptom:**
```
Error: Failure while executing; `/usr/bin/sudo -E -- mkdir -p -- /usr/local/cli-plugins` exited with 1.
sudo: a terminal is required to read the password
```
Docker Desktop is installed and then immediately rolled back without error in the terminal output you are watching.

**Root cause:** Docker Desktop's post-install script needs `sudo` to create `/usr/local/cli-plugins`. In a non-interactive shell (or any automated context) it cannot prompt for a password, so it fails.

**Fix:** Use Colima instead. Same Docker CLI and daemon, no sudo required:
```bash
brew install colima docker
colima start --cpu 2 --memory 4
```

---

### Issue 2: `docker-credential-desktop: executable file not found`

**Symptom:** After installing Colima, every `docker push` or `docker login` fails with:
```
error getting credentials - err: exec: "docker-credential-desktop": executable file not found in $PATH
```

**Root cause:** A previous Docker Desktop install (even a failed/partial one) wrote `"credsStore": "desktop"` to `~/.docker/config.json`. Colima doesn't ship this helper.

**Fix:** Remove the `credsStore` entry from Docker config:
```bash
cat > ~/.docker/config.json << 'EOF'
{
  "auths": {},
  "currentContext": "colima"
}
EOF
```
Then re-run `aws ecr get-login-password ... | docker login ...`.

---

### Issue 3: `docker build --platform linux/amd64` fails on Apple Silicon with multi-stage Dockerfiles

**Symptom:**
```
failed to export image: NotFound: content digest sha256:...: not found
```
The build stage completes successfully but the export step fails.

**Root cause:** On ARM Macs (M1/M2/M3), plain `docker build --platform linux/amd64` uses QEMU emulation for cross-platform builds. Multi-stage builds can lose content references across stages when using the legacy builder.

**Fix:** Use `docker buildx build` with `--load`:
```bash
# Install buildx first
brew install docker-buildx
mkdir -p ~/.docker/cli-plugins
ln -sf /opt/homebrew/opt/docker-buildx/bin/docker-buildx ~/.docker/cli-plugins/docker-buildx

# Then use:
docker buildx build --platform linux/amd64 --load -t myimage ./mydir
```
The `--load` flag writes the result back into the local Docker image store so you can tag and push it.

---

### Issue 4: `npm install` in Dockerfile fails with peer dependency conflicts

**Symptom:** Frontend Docker build fails:
```
npm error code ERESOLVE
npm error ERESOLVE unable to resolve dependency tree
```

**Root cause:** `react-scripts@5` has peer dependency conflicts with React 18 and some MUI packages. The `npm install` default resolver is strict.

**Fix:** Add `--legacy-peer-deps` to `npm install` in `frontend/Dockerfile`:
```dockerfile
# Before
RUN npm install

# After
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps
```
Also copy `package-lock.json` alongside `package.json` for deterministic installs.

---

### Issue 5: ALB `--subnets` argument rejects comma or space-in-string formats

**Symptom:**
```
An error occurred (InvalidSubnet) when calling the CreateLoadBalancer operation:
The subnet ID 'subnet-xxx subnet-yyy' is not valid
```

**Root cause:** The AWS CLI `--subnets` parameter for `elbv2 create-load-balancer` must receive subnet IDs as separate positional values, not as a single comma-separated or space-separated string.

**Fix:** Pass subnets as separate arguments, not quoted together:
```bash
# Wrong
--subnets "subnet-aaa,subnet-bbb"
--subnets "subnet-aaa subnet-bbb"

# Correct
--subnets subnet-aaa subnet-bbb
# or using variables:
--subnets $SUBNET_A $SUBNET_B
```

---

### Issue 6: `aws ecs register-task-definition` with inline JSON silently registers nothing

**Symptom:** The command exits 0 (success), but `aws ecs list-task-definitions` returns an empty list.

**Root cause:** Passing a large JSON blob with embedded shell variable interpolation directly in `--cli-input-json "..."` is fragile. Shell escaping of nested quotes causes the JSON to be malformed in a way the AWS CLI accepts but ignores.

**Fix:** Write the JSON to a temp file with a heredoc (shell does variable expansion correctly), then point the CLI at the file:
```bash
cat > /tmp/taskdef.json << EOF
{ ... your JSON with $VARIABLES expanded ... }
EOF

aws ecs register-task-definition --cli-input-json file:///tmp/taskdef.json
```

---

### Issue 7: nginx proxy uses `backend` hostname — works in Docker Compose, breaks in ECS

**Symptom:** ECS task starts but all API calls from the browser return 502 or connection refused. Backend logs show the FastAPI process is running on port 8000 but nginx can't reach it.

**Root cause:** `frontend/nginx.conf` had:
```
proxy_pass http://backend:8000/api/;
```
In Docker Compose, `backend` is a valid hostname resolved by Docker's internal DNS. In ECS `awsvpc` mode, containers in the same task share `localhost` — there is no `backend` hostname.

**Fix:** Change the proxy target to `localhost`:
```nginx
proxy_pass http://localhost:8000/api/;
```

---

### Issue 8: Hard-coded WebSocket URL points to localhost in production

**Symptom:** Browser console shows WebSocket connection failed to `ws://localhost:8000/api/ws` even when visiting the ALB URL.

**Root cause:** `useWebSocket.ts` had a hard-coded fallback:
```ts
const WS_URL = process.env.REACT_APP_WS_URL || "ws://localhost:8000/api/ws";
```
`REACT_APP_WS_URL` wasn't set at build time (the ALB URL isn't known until after deployment), so the browser tried to connect to `localhost` instead of the ALB.

**Fix:** Derive the WS URL dynamically from the browser's current host at runtime:
```ts
const WS_URL = process.env.REACT_APP_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws`;
```
nginx already forwards WebSocket upgrades (`Upgrade` header is set in `nginx.conf`), so this works transparently.

---

### Issue 9: News articles fetched but never saved — silent rollback due to datetime serialization

**Symptom:** Backend logs show Finnhub API returning 200 and SQL `INSERT` statements, but `GET /api/news` returns `[]`. The scheduler logs show `Error polling news` every minute.

**Root cause (two-part):**
1. The article dict built in `finnhub_provider.py` contains `published_at` as a Python `datetime` object.
2. `scheduler.py` calls `ws_manager.broadcast("news", article)` *inside* the `async with async_session()` block. The broadcast does `json.dumps(article)`, which raises `TypeError: Object of type datetime is not JSON serializable`. This exception propagates back through the session context manager, causing a **rollback** before `session.commit()` is reached. Articles are inserted but never committed.

**Fix:** Add a custom JSON encoder to `websocket_manager.py` that serialises `datetime` objects to ISO 8601 strings:
```python
class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

# Then use it in broadcast():
payload = json.dumps({"type": message_type, "data": data}, cls=_DatetimeEncoder)
```

---

### Issue 10: Chat and API calls fail in production — `.env` leaks into Docker build

**Symptom:** The app loads and shows data, but every chat message returns "Sorry, something went wrong. Please try again." Browser DevTools shows the request going to `http://localhost:8081/api/chat` instead of the ALB URL.

**Root cause:** The `frontend/Dockerfile` did not declare `ARG REACT_APP_API_URL`. Without an explicit `ARG` declaration, Docker silently ignores `--build-arg` values. During `npm run build`, CRA reads environment variables in this priority order: shell env → `.env.local` → `.env`. Since the shell had no `REACT_APP_API_URL` (the arg was silently dropped), CRA used the value from the `.env` file: `http://localhost:8081/api`. This was then hard-coded into the compiled JS bundle, so every browser API call targeted localhost — which doesn't exist in production.

**Fix:** Declare `ARG` + `ENV` in the Dockerfile *before* `RUN npm run build`, with the correct production default:
```dockerfile
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL
RUN npm run build
```
The `ENV` instruction puts the value into the shell environment, which takes precedence over the `.env` file during the build. Using `/api` as the default means all API calls are relative and proxied by nginx — no ALB URL needed at build time.

**Key lesson:** In a CRA multi-stage Docker build, **every `REACT_APP_*` variable must be explicitly declared with `ARG` + `ENV`**, otherwise any value in `.env` files will silently win.

---

### Issue 11: WebSocket shows "Disconnected" — `REACT_APP_WS_URL` also leaked from `.env`

**Symptom:** After fixing Issue 10, the app works (chat, news, prices) but the status indicator permanently shows **Disconnected**. CloudWatch nginx logs show browser requests for tickers/news/ipos succeeding, but **no WebSocket upgrade request ever arrives at nginx**.

**Root cause:** Same `.env` leak pattern as Issue 10. `frontend/.env` contained `REACT_APP_WS_URL=ws://localhost:8081/api/ws`. Because `REACT_APP_WS_URL` *was* set (to the wrong value), the dynamic runtime fallback added in Issue 8 was never reached — `process.env.REACT_APP_WS_URL || <dynamic>` short-circuits on any truthy value, and a localhost URL is truthy. The browser silently tried to connect to `ws://localhost:8081/api/ws`, failed instantly, and showed Disconnected without logging anything obvious.

**Fix:** Declare the WS URL arg in the Dockerfile with an **empty default**, so the `.env` value is overridden with an empty string. An empty string is falsy in JavaScript, so the dynamic `window.location.host` fallback kicks in:
```dockerfile
ARG REACT_APP_WS_URL=
ENV REACT_APP_WS_URL=$REACT_APP_WS_URL
```

**How to confirm the bug without redeploying:** Open browser DevTools → Network tab → filter by `WS`. If no WebSocket connection attempt appears, the URL is wrong. If a failed connection to `localhost` appears, you have this bug.

**Key lesson:** Local `.env` files should never be committed with values that only make sense for local development. Consider adding `frontend/.env` to `.gitignore` (keep `.env.example` instead), or add a `frontend/.dockerignore` that excludes `.env` from the Docker build context entirely.

---

### Issue 12: `CannotPullContainerError: image Manifest does not contain descriptor matching platform 'linux/amd64'`

**Symptom:** ECS tasks fail to start repeatedly with:
```
CannotPullContainerError: pull image manifest has been retried 7 time(s):
image Manifest does not contain descriptor matching platform 'linux/amd64'
```
The service cycles through start → fail → start every ~15 minutes indefinitely.

**Root cause:** `deploy.sh` used plain `docker build` without `--platform linux/amd64`. On an Apple Silicon Mac (M1/M2/M3), Docker defaults to building `linux/arm64` images. ECS Fargate tasks run on x86 (`linux/amd64`) by default, so the image architecture doesn't match and the task can't be pulled.

**Fix:** Add `--platform linux/amd64` to both `docker build` commands in `deploy.sh`:
```bash
docker build --platform linux/amd64 -t finmonitor-backend ./backend
docker build --platform linux/amd64 -t finmonitor-frontend ./frontend ...
```

**Note:** The build will be slower (QEMU emulation for cross-compilation), but the resulting image runs correctly on Fargate. Alternatively use `docker buildx build --platform linux/amd64 --load` as documented in Step 9.

---

### Issue 13: International stock prices show $0.00 (e.g. VOD.L, BMW.DE)

**Symptom:** Tickers with exchange suffixes (`.L`, `.DE`, `.PA`, etc.) display `$0.00` for the price, but their charts load correctly.

**Root cause:** Price quotes use Finnhub (`/quote` endpoint), while charts use yfinance. Finnhub's free tier does not cover non-US exchanges — it returns `{"c": 0, "d": 0, "dp": 0, ...}` for unsupported symbols rather than an error. The code treated `c: 0` as a valid price of zero.

**Fix:** In `FinnhubQuoteProvider`, check if `c == 0` and fall back to yfinance:
```python
async def _yfinance_quote(symbol: str) -> dict:
    def _fetch():
        t = yf.Ticker(symbol)
        fi = t.fast_info
        price = fi.last_price
        prev = fi.previous_close
        change_pct = ((price - prev) / prev * 100) if prev else 0.0
        return price, change_pct
    price, change_pct = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    return {"symbol": symbol, "price": price or 0, "change_percent": change_pct or 0}

# In fetch_quote / fetch_quotes_batch:
price = data.get("c", 0)
if not price:
    return await _yfinance_quote(symbol)
```
yfinance is already used for chart data (candles endpoint) and requires no API key, so this is a zero-cost fallback.

---

### Issue 14: IPO section shows "No upcoming IPOs found" immediately after startup

**Symptom:** The IPO section displays the empty-state message on first load, even though Alpha Vantage has upcoming IPO data. It only populates after ~1 hour.

**Root cause (two-part):**
1. The APScheduler jobs were added with `scheduler.add_job(poll_ipos, "interval", seconds=3600)` — no `next_run_time` specified. APScheduler defaults to running the job after the first full interval, meaning IPO data isn't fetched until 1 hour after startup.
2. `AlphaVantageIPOProvider` returned `expected_date` as a plain string (`raw_date = "2026-03-10"`), but the `ipo_events.expected_date` DB column is typed `DATE`. asyncpg raised `AttributeError: 'str' object has no attribute 'toordinal'` during the INSERT, rolling back the transaction silently.

**Fix:**
```python
# scheduler.py — run immediately on startup
now = datetime.datetime.now(datetime.timezone.utc)
scheduler.add_job(poll_ipos, "interval", seconds=settings.ipo_poll_interval_seconds,
                  id="poll_ipos", next_run_time=now)

# alpha_vantage_provider.py — use the already-parsed date object, not the raw string
ipo_date = datetime.date.fromisoformat(raw_date)  # already done
results.append({
    ...
    "expected_date": ipo_date,  # was: raw_date (string)
    ...
})
```

---

### Issue 15: nginx config shared between local and prod — `backend` hostname crashes ECS

**Symptom:** After fixing local Docker Compose to use the Docker service name as upstream (`proxy_pass http://backend:8000/api/`), ECS task starts but the frontend container immediately exits with code 1. CloudWatch logs show:
```
[emerg] 1#1: host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:22
nginx: [emerg] host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:22
```

**Root cause:** The two environments have fundamentally different networking:

| Environment | How containers reach each other | nginx upstream |
|-------------|--------------------------------|----------------|
| Docker Compose | Docker internal DNS — service name resolves | `http://backend:8000` |
| ECS Fargate (`awsvpc`) | Shared network namespace — all containers share `localhost` | `http://localhost:8000` |

There is no single `nginx.conf` that satisfies both. At nginx startup it resolves all upstream hostnames — if `backend` doesn't exist in DNS (as in ECS), nginx refuses to start.

**Fix:** Keep two nginx configs and select the right one at Docker build time via a build arg:

```
frontend/
  nginx.conf          ← local dev: SSL on 443, upstream = backend:8000
  nginx.prod.conf     ← production: HTTP on 80, upstream = localhost:8000
```

`frontend/Dockerfile` (serve stage):
```dockerfile
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
```

`deploy/aws/deploy.sh`:
```bash
docker build --platform linux/amd64 -t finmonitor-frontend ./frontend \
  --build-arg REACT_APP_API_URL=/api \
  --build-arg REACT_APP_WS_URL=wss://<your-cloudfront-domain>/api/ws \
  --build-arg NGINX_CONF=nginx.prod.conf   # ← selects HTTP-only, localhost upstream
```

Local Docker Compose doesn't pass this arg, so it defaults to `nginx.conf` (with SSL and `backend` upstream).

---

## Useful commands

```bash
# Check service health
aws ecs describe-services --cluster $APP --services ${APP}-service --region $AWS_REGION \
  --query "services[0].{status:status,running:runningCount,desired:desiredCount}"

# Stream live logs
aws logs tail /ecs/finmonitor --follow --region $AWS_REGION

# List running tasks
aws ecs list-tasks --cluster $APP --region $AWS_REGION

# Smoke test API
curl http://${ALB_DNS}/api/tickers   # [] = healthy, error = something wrong
```

---

## Teardown (avoid ongoing charges)

```bash
aws ecs update-service --cluster $APP --service ${APP}-service --desired-count 0 --region $AWS_REGION
aws ecs delete-service --cluster $APP --service ${APP}-service --force --region $AWS_REGION
aws rds delete-db-instance --db-instance-identifier ${APP}-db --skip-final-snapshot
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN
aws elbv2 delete-target-group --target-group-arn $TG_ARN
aws ecr delete-repository --repository-name ${APP}-backend --force
aws ecr delete-repository --repository-name ${APP}-frontend --force
aws secretsmanager delete-secret --secret-id ${APP}/config --force-delete-without-recovery
# Security groups — delete in this order (ECS first, then RDS, then ALB)
aws ec2 delete-security-group --group-id $ECS_SG
aws ec2 delete-security-group --group-id $RDS_SG
aws ec2 delete-security-group --group-id $ALB_SG
aws ecs delete-cluster --cluster $APP --region $AWS_REGION
```

---

## Quick troubleshooting reference

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Task stops immediately | Bad secret / DB URL unreachable | Check CloudWatch: `aws logs tail /ecs/finmonitor --follow` |
| ALB returns 502 | nginx not healthy or can't reach backend | Confirm nginx.conf uses `localhost:8000`, not `backend:8000` |
| WebSocket connects to `localhost` | Hard-coded WS URL fallback | Use dynamic `window.location.host` — see Issue 8 |
| News feed always empty | datetime serialization crash rolls back DB | Add `_DatetimeEncoder` to `websocket_manager.py` — see Issue 9 |
| Chat returns "Something went wrong" | `.env` API URL baked into build | Declare `ARG`/`ENV REACT_APP_API_URL=/api` in Dockerfile — see Issue 10 |
| Status shows "Disconnected" permanently | `.env` WS URL baked into build | Declare `ARG`/`ENV REACT_APP_WS_URL=` (empty) in Dockerfile — see Issue 11 |
| `CannotPullContainerError: Manifest does not contain descriptor matching platform 'linux/amd64'` | ARM image pushed from Apple Silicon Mac | Add `--platform linux/amd64` to `docker build` in `deploy.sh` — see Issue 12 |
| International stock price shows $0.00 | Finnhub free tier doesn't cover non-US exchanges | yfinance fallback in `FinnhubQuoteProvider` — see Issue 13 |
| IPO section shows "No data" on fresh start | Scheduler waits full interval before first run | Set `next_run_time=now` in `start_scheduler()` — see Issue 14 |
| Frontend exits code 1 — `host not found in upstream "backend"` | `nginx.conf` uses Docker Compose service name, ECS needs `localhost` | Use `nginx.prod.conf` + `NGINX_CONF` build arg in `deploy.sh` — see Issue 15 |
| `CannotPullContainerError` | ECR auth or wrong image URI | Check execution role has `AmazonECSTaskExecutionRolePolicy` |
| `npm install` fails in Docker build | Peer dependency conflict | Add `--legacy-peer-deps` to `RUN npm install` in Dockerfile |
| Task definition registers but list is empty | Inline JSON escaping failure | Write JSON to a file, use `--cli-input-json file:///tmp/...` |
