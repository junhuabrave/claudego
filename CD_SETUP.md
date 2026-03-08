# CD Pipeline Setup — AWS ECS Fargate

This document captures everything needed to wire up automated deployments
from GitHub Actions to AWS. Once the prerequisites below are in place,
the deploy job in `ci.yml` can be added and deploys will trigger automatically
on every merge to `main`.

---

## Architecture overview

```
GitHub push → main
    └─ CI pipeline (lint + test + docker build)  [already done]
         └─ CD pipeline (ECR push + ECS rolling deploy)  [this doc]
              └─ AWS ECS Fargate
                   ├─ finmonitor-backend  (FastAPI / uvicorn)
                   └─ finmonitor-frontend (nginx serving React SPA)
```

Traffic path: `Internet → CloudFront → ALB → ECS tasks`

---

## Step 1 — AWS prerequisites (one-time manual setup)

These resources must exist before the pipeline can deploy.

### 1a. ECR repositories
```bash
aws ecr create-repository --repository-name finmonitor-backend  --region us-east-1
aws ecr create-repository --repository-name finmonitor-frontend --region us-east-1
```

### 1b. ECS cluster
```bash
aws ecs create-cluster --cluster-name finmonitor --region us-east-1
```

### 1c. ECS task definition
The task definition at `deploy/aws/task-definition.json` defines:
- Both containers (backend + frontend) in a single task (awsvpc mode — they share localhost)
- CPU: 512 mCPU, Memory: 1024 MB
- Secrets pulled from AWS Secrets Manager
- Logs sent to CloudWatch at `/ecs/finmonitor`

Register it once:
```bash
aws ecs register-task-definition \
  --cli-input-json file://deploy/aws/task-definition.json \
  --region us-east-1
```

### 1d. ECS service
```bash
aws ecs create-service \
  --cluster finmonitor \
  --service-name finmonitor-service \
  --task-definition finmonitor \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --region us-east-1
```

### 1e. AWS Secrets Manager entries
Store all sensitive config here. The task definition references them by ARN.
```bash
aws secretsmanager create-secret --name finmonitor/database_url      --secret-string "postgresql+asyncpg://..."
aws secretsmanager create-secret --name finmonitor/finnhub_api_key   --secret-string "..."
aws secretsmanager create-secret --name finmonitor/alpha_vantage_key --secret-string "..."
aws secretsmanager create-secret --name finmonitor/news_api_key      --secret-string "..."
aws secretsmanager create-secret --name finmonitor/jwt_secret_key    --secret-string "..."
aws secretsmanager create-secret --name finmonitor/google_client_id  --secret-string "..."
```

### 1f. RDS PostgreSQL
```bash
aws rds create-db-instance \
  --db-instance-identifier finmonitor-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 15 \
  --master-username finmonitor \
  --master-user-password <password> \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxx \
  --region us-east-1
```
Use the resulting endpoint as the `database_url` secret above.

---

## Step 2 — IAM role for GitHub Actions (choose one)

### Option A — OIDC federation (recommended, no long-lived keys)

**Why:** GitHub proves its identity to AWS via a signed JWT. No access keys stored anywhere.

1. Create the OIDC provider in AWS (one-time per account):
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

2. Create an IAM role with this trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:junhuabrave/claudego:ref:refs/heads/main"
      }
    }
  }]
}
```

3. Attach this inline policy to the role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["ecr:GetAuthorizationToken"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": [
        "arn:aws:ecr:us-east-1:<ACCOUNT_ID>:repository/finmonitor-backend",
        "arn:aws:ecr:us-east-1:<ACCOUNT_ID>:repository/finmonitor-frontend"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["iam:PassRole"],
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/finmonitor-task-execution-role"
    }
  ]
}
```

Add one GitHub secret:

| Secret name       | Value                                                    |
|-------------------|----------------------------------------------------------|
| `AWS_ROLE_ARN`    | `arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy`  |

---

### Option B — IAM user with access keys (simpler, less secure)

Create an IAM user, attach the same policy as above, generate an access key pair,
then add these GitHub secrets:

| Secret name             | Value                   |
|-------------------------|-------------------------|
| `AWS_ACCESS_KEY_ID`     | IAM access key ID       |
| `AWS_SECRET_ACCESS_KEY` | IAM secret access key   |

---

## Step 3 — GitHub Secrets (repo Settings → Secrets → Actions)

These must be set regardless of which IAM option you chose:

| Secret name                  | Value / notes                                              |
|------------------------------|------------------------------------------------------------|
| `AWS_REGION`                 | `us-east-1` (or whichever region)                         |
| `AWS_ACCOUNT_ID`             | 12-digit AWS account number                               |
| `ECR_BACKEND_REPO`           | `finmonitor-backend`                                       |
| `ECR_FRONTEND_REPO`          | `finmonitor-frontend`                                      |
| `ECS_CLUSTER`                | `finmonitor`                                               |
| `ECS_SERVICE`                | `finmonitor-service`                                       |
| `ECS_TASK_FAMILY`            | `finmonitor`                                               |
| `CLOUDFRONT_URL`             | CloudFront domain e.g. `d1yleiq0s9sk4n.cloudfront.net`    |
| `REACT_APP_GOOGLE_CLIENT_ID` | Google OAuth client ID (currently hardcoded in deploy.sh) |

Plus one of:
- `AWS_ROLE_ARN` (OIDC — Option A)
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (keys — Option B)

---

## Step 4 — What I will add to ci.yml once you confirm secrets are set

A `deploy` job that:
1. Runs only on push to `main` (not on PRs)
2. Requires all CI jobs to pass (`needs: [lint-backend, lint-frontend, test-backend, test-frontend]`)
3. Authenticates to AWS (OIDC or keys)
4. Pushes tagged images to ECR (`sha`-tagged for rollback capability, plus `latest`)
5. Forces a new ECS deployment
6. Waits for the service to stabilize before marking success

Optional additions (can be added later):
- Manual approval gate before production deploy
- Slack/email notification on deploy success/failure
- Automatic rollback if ECS health checks fail

---

## Known issues from previous manual deployments

Documented in `AWS_DEPLOYMENT_GUIDE.md` — 15 real issues encountered:

| # | Issue | Fix |
|---|-------|-----|
| 1 | Docker Desktop silent failures on non-interactive shells | Use Colima |
| 2 | Apple Silicon produces arm64 images, ECS needs amd64 | `--platform linux/amd64` in docker build |
| 3 | npm peer dependency conflicts | `--legacy-peer-deps` |
| 4 | ECS containers think they're on separate hosts | awsvpc mode shares localhost — backend URL is `http://localhost:8000` not `http://backend:8000` |
| 5 | WebSocket URL hardcoded to CloudFront domain | Pass as build arg `REACT_APP_WS_URL` |
| 6 | datetime serialization crashes cause silent DB rollbacks | Use `datetime.utcnow()` consistently |
| 7 | `.env` values leaking into Docker image layers | Use Secrets Manager, not `.env` files |

Full details in `AWS_DEPLOYMENT_GUIDE.md`.

---

## Current state of deploy script

`deploy/aws/deploy.sh` is functional but has two issues to fix before CI use:
1. `REACT_APP_WS_URL` is hardcoded to a specific CloudFront domain — must be parameterized via `$CLOUDFRONT_URL`
2. `REACT_APP_GOOGLE_CLIENT_ID` has a fallback to a hardcoded client ID — must be required, not defaulted

These will be fixed when the CD job is added to `ci.yml`.
