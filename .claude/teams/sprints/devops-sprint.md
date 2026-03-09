# DevOps Team — Phase 1 Completion Sprint

**Sprint Duration:** 2 weeks
**Team Lead:** DevOps/CI-CD Team
**Reference:** [devops-cicd.md](../devops-cicd.md) for coding standards

---

## Sprint Goal

Provision a **staging environment with Redis** (unblocks Backend + Auth teams) and set up **basic monitoring dashboards** so we can observe the system before scaling to 10K DAU. These are the last infrastructure P0 blockers.

---

## Tasks

### Task 1: Staging Environment (P0) — 3 days

**Why:** No staging means every change goes straight to production. Backend team needs staging to validate Redis cache, Auth team needs it to validate rate limiting, Test team needs it for E2E tests. This is the #1 cross-team blocker.

**Implementation:**

Staging should mirror production architecture at minimal scale:

| Component | Staging Spec | Production Spec |
|-----------|-------------|-----------------|
| Backend | 1 instance, 0.5 vCPU, 1GB | 2+ instances, 1 vCPU, 2GB |
| PostgreSQL | db.t3.micro / Cloud SQL basic | db.r6g.large / Cloud SQL |
| Redis | cache.t3.micro / Memorystore basic | cache.r6g.large / Memorystore |
| Frontend | Static hosting (S3/GCS + CDN) | Same |

**Steps (AWS example, adapt for GCP/Azure per devops-cicd.md):**

1. Create staging VPC/network (or reuse default VPC for cost savings)
2. Provision RDS PostgreSQL (micro, same schema version):
   ```bash
   # Run Alembic against staging DB
   DATABASE_URL=postgresql+asyncpg://... alembic upgrade head
   ```
3. Provision ElastiCache Redis (single node, no cluster):
   ```
   REDIS_URL=redis://staging-redis.xxx.cache.amazonaws.com:6379/0
   ```
4. Deploy backend to ECS Fargate (1 task, reuse existing Dockerfile):
   ```bash
   # Environment variables for staging
   ENVIRONMENT=staging
   DATABASE_URL=...
   REDIS_URL=...
   JWT_SECRET=<generate-unique-for-staging>
   CORS_ORIGINS=["https://staging.finmonitor.app"]
   ```
5. Deploy frontend to S3 + CloudFront (or equivalent):
   ```bash
   REACT_APP_API_URL=https://staging-api.finmonitor.app/api
   npm run build
   aws s3 sync build/ s3://staging-finmonitor-frontend/
   ```
6. Set up DNS: `staging.finmonitor.app` and `staging-api.finmonitor.app`

**Auto-shutdown (cost savings):**
```yaml
# GitHub Actions scheduled workflow to stop staging at night
name: Staging Auto-Shutdown
on:
  schedule:
    - cron: "0 2 * * *"  # 2 AM UTC daily
jobs:
  shutdown:
    runs-on: ubuntu-latest
    steps:
      - run: |
          aws ecs update-service --cluster staging --service finmonitor --desired-count 0
```

**Acceptance Criteria:**
- [ ] Staging URL accessible: `https://staging.finmonitor.app`
- [ ] Backend connects to staging PostgreSQL + Redis
- [ ] Alembic migrations run successfully against staging DB
- [ ] Frontend points to staging API
- [ ] All teams can deploy to staging independently
- [ ] Auto-shutdown active (estimated cost: <$100/month)

---

### Task 2: Redis Provisioning (P0) — Included in Task 1

Redis is part of staging, but document the setup separately for production:

**Production Redis checklist:**
- [ ] Enable encryption in transit (TLS)
- [ ] Enable encryption at rest
- [ ] Set eviction policy: `allkeys-lru`
- [ ] Set maxmemory: 1GB (initial)
- [ ] Enable Redis AUTH password
- [ ] Put in private subnet (no public access)
- [ ] Configure `REDIS_URL` in Secrets Manager / Parameter Store

**Local development:**
```yaml
# Already in docker-compose.yml? If not, add:
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
```

---

### Task 3: Deploy Pipeline — Staging Auto, Prod Manual (P1) — 2 days

**Why:** Current CI builds but doesn't deploy. We need automated staging deploys and gated production deploys.

**Update `.github/workflows/ci.yml`:**

```yaml
deploy-staging:
  needs: [lint, test, build]
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  environment: staging
  steps:
    - uses: actions/checkout@v4
    - name: Deploy to staging
      run: |
        # Push Docker image to ECR
        # Update ECS service
        echo "Deploy to staging..."

deploy-production:
  needs: [deploy-staging]
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  environment:
    name: production
    # Manual approval gate
    url: https://finmonitor.app
  steps:
    - name: Deploy to production
      run: |
        echo "Deploy to production..."
```

**GitHub Environment Protection Rules:**
- `staging`: Auto-deploy on merge to main
- `production`: Require 1 approval from `@eng-leads` team

**Acceptance Criteria:**
- [ ] Merge to main → auto-deploy to staging
- [ ] Production deploy requires manual approval
- [ ] Rollback: redeploy previous image tag (documented in runbook)

---

### Task 4: Monitoring Dashboards (P1) — 2 days

**Why:** We're about to add Redis, rate limiting, and refresh tokens. We need visibility into how they behave before scaling.

**Metrics to dashboard (use CloudWatch/Cloud Monitoring/Azure Monitor):**

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Request rate (req/s) | ALB/API Gateway | > 1000 req/s |
| Error rate (5xx/total) | ALB/API Gateway | > 1% |
| P95 latency | ALB/API Gateway | > 2s |
| Active DB connections | RDS/Cloud SQL | > 80% of pool |
| Redis hit rate | ElastiCache metrics | < 50% |
| Redis memory usage | ElastiCache metrics | > 80% |
| CPU utilization | ECS/Cloud Run | > 70% |
| Memory utilization | ECS/Cloud Run | > 80% |
| WebSocket connections | Custom metric | > 5000 |

**Implementation:**
1. Create CloudWatch dashboard (or Grafana if preferred):
   - 4 panels: Traffic, Errors, Latency, Resources
2. Set up alarms for P95 > 2s and error rate > 1%
3. Notification channel: email (PagerDuty in Phase 2)

**Acceptance Criteria:**
- [ ] Dashboard URL accessible to all team leads
- [ ] Shows live metrics from staging (and production when deployed)
- [ ] Alarms fire on threshold breach
- [ ] At least request rate, error rate, latency, DB connections visible

---

### Task 5: Add Redis + ESLint to CI Pipeline (P1) — 0.5 days

**Update `.github/workflows/ci.yml`:**

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
    options: --health-cmd "redis-cli ping" --health-interval 10s

env:
  REDIS_URL: redis://localhost:6379/0

# Add frontend lint step
lint-frontend:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: npm
        cache-dependency-path: frontend/package-lock.json
    - run: cd frontend && npm ci
    - run: cd frontend && npm run lint
```

**Acceptance Criteria:**
- [ ] Redis service available in CI for backend tests
- [ ] Frontend ESLint runs in CI, blocks merge on failure
- [ ] CI time increase < 1 minute

---

## Coordination

- **With Backend:** Provide `REDIS_URL` format and staging DB connection string by Day 2. Backend needs Redis to start Task 1.
- **With Auth:** Rate limiting uses Redis. Same URL, same instance. Auth team can start local dev with docker-compose Redis immediately.
- **With Test:** E2E tests need staging URL. Target: staging available by Day 3, share URL in #test-engineering.
- **With Frontend:** ESLint step in CI — coordinate with frontend team's ESLint config PR.

---

## Out of Scope This Sprint

- Terraform/Pulumi IaC (Phase 2 — manual provisioning is fine for staging)
- Auto-scaling (Phase 2 — single instance for staging)
- Blue-green deployment (Phase 2)
- PagerDuty integration (Phase 2 — email alerts for now)
- CDN optimization (Phase 2)

---

*Questions? Tag @devops-lead in the PR or post in #devops-infra channel.*
