# DevOps / CI-CD / SRE — Team Standards

> Load this file as agent context when working on infrastructure, deployment, CI/CD, and observability.

## Team Scope

You own **infrastructure, CI/CD pipelines, container orchestration, observability, and cloud operations** across all environments.

**Your files:**
- `deploy/aws/` — AWS ECS/Fargate deployment scripts and task definitions
- `deploy/gcp/` — Google Cloud Run configs
- `deploy/azure/` — Azure Container Apps configs
- `deploy/k8s/` — Kubernetes manifests (NEW — you create this)
- `.github/workflows/` — GitHub Actions CI/CD pipelines (NEW — you create this)
- `docker-compose.yml` — Local dev orchestration
- `backend/Dockerfile` — Backend container image
- `frontend/Dockerfile` — Frontend container image (build stages)
- `frontend/nginx.conf` / `frontend/nginx.prod.conf` — nginx configs
- `Makefile` — Unified dev/deploy commands (NEW — you create this)
- `docs/runbooks/` — Operational runbooks (NEW — you create this)

**Your responsibilities:**
- Design and maintain CI/CD pipelines
- Manage Docker images and container orchestration
- Implement auto-scaling and high availability
- Set up observability (metrics, logging, tracing, alerting)
- Manage cloud infrastructure (IaC with Terraform/Pulumi)
- Ensure <5 min deployment, <1 min rollback
- Own SLA targets: 99.9% uptime, P95 <500ms

**Not your files:**
- Application source code → Backend/Frontend teams
- Auth implementation → Auth/Security team
- Test suites → Test Engineering team (but you run them in CI)

---

## Infrastructure Standards

### Cloud-Agnostic Design

The project supports AWS, GCP, and Azure. All infrastructure must be designed to work across providers.

**Abstraction principles:**
- Use **containers** as the deployment unit — same image runs anywhere
- Use **environment variables** for all configuration — no cloud-specific SDKs in app code
- Use **managed services** with equivalent alternatives across clouds
- Use **Terraform** or **Pulumi** for IaC — cloud-specific modules behind a common interface

**Service mapping:**
| Capability | AWS | GCP | Azure |
|-----------|-----|-----|-------|
| Compute | ECS Fargate / EKS | Cloud Run / GKE | Container Apps / AKS |
| Database | RDS PostgreSQL | Cloud SQL | Azure PostgreSQL |
| Cache | ElastiCache Redis | Memorystore Redis | Azure Cache Redis |
| CDN | CloudFront | Cloud CDN | Azure CDN |
| Secrets | Secrets Manager | Secret Manager | Key Vault |
| DNS | Route53 | Cloud DNS | Azure DNS |
| Registry | ECR | Artifact Registry | ACR |
| Logging | CloudWatch Logs | Cloud Logging | Azure Monitor |
| Monitoring | CloudWatch Metrics | Cloud Monitoring | Azure Monitor |
| Queue | SQS | Pub/Sub | Service Bus |
| Object Storage | S3 | GCS | Blob Storage |

### Docker Standards

#### Backend Dockerfile
```dockerfile
# Multi-stage build
FROM python:3.11-slim AS base

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### Frontend Dockerfile
```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.prod.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Docker rules:**
- **Multi-stage builds** — build deps don't go into production image
- **Non-root user** — never run as root in production
- **No secrets in images** — use env vars or mounted secrets
- **.dockerignore** — exclude `node_modules/`, `__pycache__/`, `.env`, `tests/`, `.git/`
- **Pin versions** — `python:3.11-slim`, not `python:latest`
- **Health checks** in Dockerfile or orchestrator config
- **Multi-platform builds** — `linux/amd64` + `linux/arm64` (Graviton/M-series)

### CI/CD Pipeline (GitHub Actions)

#### Pipeline Architecture
```
PR opened/updated:
  ├── lint (parallel)
  │   ├── backend: ruff + mypy
  │   └── frontend: eslint + tsc
  ├── test (parallel)
  │   ├── backend: pytest --cov
  │   └── frontend: jest --coverage
  ├── build (after lint + test pass)
  │   ├── docker build backend
  │   └── docker build frontend
  └── security scan (parallel)
      ├── trivy (container scan)
      └── snyk (dependency scan)

Merge to main:
  ├── all PR checks pass
  ├── build + push images to registry (tagged: git sha + latest)
  ├── deploy to staging (auto)
  ├── run E2E smoke tests against staging
  ├── deploy to production (manual approval or auto)
  └── post-deploy smoke test + rollback on failure
```

#### GitHub Actions Template
```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install ruff mypy
      - run: ruff check backend/
      - run: cd backend && mypy app/ --ignore-missing-imports

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
      - run: cd frontend && npx tsc --noEmit

  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest tests/ -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4
        with:
          file: backend/coverage.xml

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: cd frontend && npm test -- --coverage --watchAll=false

  build:
    needs: [lint-backend, lint-frontend, test-backend, test-frontend]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker build -t finmonitor-backend:${{ github.sha }} ./backend
      - run: docker build -t finmonitor-frontend:${{ github.sha }} ./frontend

  deploy-staging:
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    needs: [build]
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - run: echo "Deploy to staging..."
      # Cloud-specific deployment steps here
```

### Auto-Scaling

#### ECS Fargate (AWS)
```json
{
  "scalingPolicy": {
    "targetTrackingScaling": {
      "targetValue": 70,
      "predefinedMetricSpecification": {
        "predefinedMetricType": "ECSServiceAverageCPUUtilization"
      },
      "scaleInCooldown": 300,
      "scaleOutCooldown": 60
    }
  },
  "minCapacity": 2,
  "maxCapacity": 20
}
```

#### Scaling Targets
| Metric | Scale Out | Scale In | Min | Max |
|--------|-----------|----------|-----|-----|
| CPU utilization | >70% | <30% | 2 | 20 |
| Memory utilization | >80% | <40% | 2 | 20 |
| Request count | >1000/min/instance | <200/min/instance | 2 | 20 |
| WebSocket connections | >500/instance | <100/instance | 2 | 20 |

### Observability

#### Metrics (Prometheus + Grafana)
```python
# Key application metrics to expose
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
http_requests_total = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
http_request_duration = Histogram("http_request_duration_seconds", "Request duration", ["endpoint"])

# Business metrics
websocket_connections = Gauge("websocket_connections", "Active WebSocket connections")
quotes_poll_duration = Histogram("quotes_poll_duration_seconds", "Quote polling duration")
alerts_triggered_total = Counter("alerts_triggered_total", "Price alerts triggered")

# Infrastructure metrics (auto-collected)
# - CPU, memory, disk usage
# - Database connection pool utilization
# - Redis cache hit/miss ratio
```

#### Logging (Structured JSON)
```python
# Use structlog for JSON logging
import structlog

logger = structlog.get_logger()

logger.info(
    "ticker_added",
    user_id=user.id,
    symbol="AAPL",
    request_id=request.state.request_id,
)

# Output (JSON, parsed by CloudWatch/ELK):
# {"event": "ticker_added", "user_id": 42, "symbol": "AAPL", "request_id": "abc-123", "timestamp": "..."}
```

**Logging rules:**
- **JSON format** in production — parseable by log aggregators
- **Request ID** in every log line — for distributed tracing
- **Never log secrets** — mask tokens, passwords, API keys
- **Log levels**: DEBUG (dev only), INFO (business events), WARNING (recoverable errors), ERROR (failures)
- **Retention**: 30 days hot (searchable), 1 year cold (archived)

#### Alerting
| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High error rate | 5xx > 1% of requests for 5 min | Critical | PagerDuty → on-call |
| High latency | P95 > 2s for 5 min | Warning | Slack notification |
| DB connections exhausted | pool usage > 90% | Critical | PagerDuty |
| WebSocket drops | >50% disconnections in 1 min | Warning | Slack |
| Disk space low | >85% on any volume | Warning | Slack |
| Certificate expiry | <14 days until expiry | Critical | PagerDuty |
| Deployment failed | ECS service not stable after 10 min | Critical | Auto-rollback + PagerDuty |

#### Distributed Tracing (OpenTelemetry)
- Add trace context to all HTTP requests (propagate `traceparent` header)
- Instrument FastAPI with `opentelemetry-instrumentation-fastapi`
- Instrument SQLAlchemy with `opentelemetry-instrumentation-sqlalchemy`
- Instrument httpx with `opentelemetry-instrumentation-httpx`
- Export traces to Jaeger, Tempo, or cloud-native (X-Ray, Cloud Trace)

### Health Checks
```python
# Backend health endpoints (required)

@app.get("/health")
async def health():
    """Liveness probe — is the process running?"""
    return {"status": "ok"}

@app.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Readiness probe — can it serve traffic?"""
    try:
        await db.execute(text("SELECT 1"))
        # TODO: Check Redis connectivity when Redis is added
        return {"status": "ready", "db": "ok"}
    except Exception as e:
        raise HTTPException(503, detail=f"Not ready: {e}")
```

- `/health` — liveness probe, always returns 200 if process is alive
- `/ready` — readiness probe, checks DB (and Redis) connectivity
- Load balancer uses `/health` for routing, `/ready` for startup
- Kubernetes: `livenessProbe` → `/health`, `readinessProbe` → `/ready`

---

## Multi-Region Architecture (Target)

### Phase 2: Active-Passive
```
Primary Region (us-east-1):
  └── Full stack (frontend + backend + primary DB)

Secondary Region (eu-west-1):
  └── Read-only frontend + read replica DB
      (failover to become primary if us-east-1 fails)
```

### Phase 3: Active-Active
```
Region: us-east-1           Region: eu-west-1         Region: ap-northeast-1
  ├── Frontend pods            ├── Frontend pods          ├── Frontend pods
  ├── Backend pods             ├── Backend pods           ├── Backend pods
  ├── Redis (regional)         ├── Redis (regional)       ├── Redis (regional)
  └── DB (primary)             └── DB (read replica)      └── DB (read replica)
       ↕ replication ↕              ↕ replication ↕

Global:
  ├── Route53 / GLB (latency-based routing)
  ├── CloudFront / Global CDN (static assets)
  └── Cross-region message bus (for alert sync)
```

**Multi-region rules:**
- Static assets (React SPA) served from CDN edge — zero backend dependency for initial load
- API requests routed to nearest region by latency
- Write operations always go to primary DB region
- Read replicas serve GET requests in non-primary regions
- WebSocket connections are regional — no cross-region WS routing
- Failover: promote read replica to primary, update DNS (automated via health checks)

---

## Scaling TODO

### Phase 1: Foundation
- [ ] **Create GitHub Actions CI pipeline**: lint + test + build on every PR
- [ ] **Create Makefile**: `make dev`, `make test`, `make lint`, `make build`, `make deploy-staging`
- [ ] **Optimize Docker images**: Multi-stage builds, .dockerignore, pin versions, non-root user
- [ ] **Add health endpoints**: `/health` and `/ready` in backend
- [ ] **Set up staging environment**: Separate ECS service/Cloud Run with same infra
- [ ] **Add structured logging**: structlog with JSON output
- [ ] **Create deployment runbook**: Step-by-step deploy, rollback, incident response
- [ ] **Set up basic monitoring**: CloudWatch/GCP Monitoring dashboards for CPU, memory, request count

### Phase 2: Scale
- [ ] **Infrastructure as Code**: Terraform modules for AWS (and GCP/Azure variants)
- [ ] **Auto-scaling**: CPU-based scaling (2–20 instances), test scaling policies
- [ ] **Redis cluster**: ElastiCache/Memorystore for caching + WebSocket pub/sub
- [ ] **Database optimization**: Read replicas, connection pooling (PgBouncer), automated backups
- [ ] **Observability stack**: Prometheus + Grafana for metrics, ELK for logs, Jaeger for traces
- [ ] **Alerting**: PagerDuty integration for critical alerts, Slack for warnings
- [ ] **Blue-green deployments**: Zero-downtime deploys with traffic shifting
- [ ] **CDN optimization**: Cache static assets at edge, proper cache headers
- [ ] **Secret rotation**: Automated rotation for DB passwords, API keys, JWT secrets

### Phase 3: Global
- [ ] **Multi-region deployment**: Active-active in 3 regions (US, EU, Asia)
- [ ] **Global load balancing**: Latency-based DNS routing (Route53 / GLB)
- [ ] **Cross-region DB replication**: PostgreSQL logical replication or managed cross-region replicas
- [ ] **Disaster recovery**: Documented DR plan, quarterly DR drills, RPO <1h, RTO <15min
- [ ] **Cost optimization**: Reserved instances, spot instances for non-critical workloads
- [ ] **Compliance infrastructure**: Data residency controls, audit logging, encryption everywhere
- [ ] **Chaos engineering**: Periodic failure injection (Netflix Chaos Monkey pattern)
- [ ] **Edge computing**: WebSocket termination at edge for lower latency

---

## Incident Response

### Severity Levels
| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| SEV1 | Service down, all users affected | 15 min | Backend crash, DB unreachable |
| SEV2 | Degraded, major feature broken | 30 min | WebSocket not connecting, quotes stale |
| SEV3 | Minor issue, workaround exists | 4 hours | One provider failing, UI glitch |
| SEV4 | Cosmetic, no impact | Next sprint | Logo alignment, tooltip text |

### Rollback Procedure (Cloud-Agnostic)

**AWS (ECS Fargate):**
```bash
aws ecs update-service --cluster finmonitor --service backend \
  --task-definition finmonitor-backend:<previous-revision> --force-new-deployment
aws ecs wait services-stable --cluster finmonitor --service backend
```

**GCP (Cloud Run):**
```bash
gcloud run revisions list --service finmonitor-backend --region us-central1
gcloud run services update-traffic finmonitor-backend \
  --to-revisions=finmonitor-backend-<prev>=100 --region us-central1
```

**Azure (Container Apps):**
```bash
az containerapp revision list -n finmonitor-backend -g finmonitor-rg
az containerapp ingress traffic set -n finmonitor-backend -g finmonitor-rg \
  --revision-weight finmonitor-backend--<prev>=100
```

**Verify (all clouds):** `curl https://api.finmonitor.example.com/health`

- Rollback must complete in <5 minutes
- Always roll forward if the fix is trivial (< 10 min to deploy)
- Post-incident review within 48 hours for SEV1/SEV2

---

## PR Checklist

- [ ] Docker images build successfully (`docker build .`)
- [ ] No secrets in Dockerfiles, configs, or code
- [ ] Health check endpoints exist and return correct responses
- [ ] CI pipeline passes all stages (lint, test, build, security scan)
- [ ] Deployment configs work with `docker-compose up` locally
- [ ] New environment variables documented in `.env.example`
- [ ] Infrastructure changes have rollback plan documented
- [ ] Monitoring/alerting updated for new services or endpoints
