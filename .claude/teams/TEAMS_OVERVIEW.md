# FinMonitor — Team Structure & Scaling Roadmap

## Vision
Scale FinMonitor from a single-developer project to a platform serving **100K–1M daily active users** across global financial markets. Cloud-agnostic, globally resilient, real-time.

---

## Team Structure

| Team | Ownership | Headcount (suggested) |
|------|-----------|----------------------|
| **Backend Python** | FastAPI, data providers, schedulers, WebSocket, DB models | 3–4 engineers |
| **Frontend React** | React SPA, MUI components, real-time UI, charts | 2–3 engineers |
| **Test Engineering** | E2E, integration, load testing, CI test infra | 2 engineers |
| **Auth & Security** | OAuth, JWT, RBAC, rate limiting, secrets, compliance | 1–2 engineers |
| **DevOps / CI-CD** | Docker, K8s/ECS, CDN, multi-cloud, observability, IaC | 2–3 engineers |

**Total: 10–14 engineers** for Phase 1 (100K DAU target)

---

## Architecture (Current → Target)

### Current (single-instance)
```
CloudFront → ALB → ECS Fargate Task
                      ├── nginx (React SPA + /api proxy)
                      └── uvicorn (FastAPI)
                           └── RDS PostgreSQL
```

### Target (100K–1M DAU)
```
CloudFront / Global CDN (multi-region)
  ↓
Global Load Balancer (Route53 latency-based / GCP GLB / Azure Traffic Manager)
  ↓
┌─────────────────────────────────────────────────────────┐
│  Region: us-east-1 / europe-west1 / ap-northeast-1     │
│                                                          │
│  K8s Cluster or ECS Service (auto-scaling)              │
│    ├── Frontend pods (nginx, static SPA)                │
│    └── Backend pods (uvicorn x N, HPA on CPU/connections)│
│         ├── Redis Cluster (quotes cache, WS pub/sub)    │
│         ├── RDS/CloudSQL (primary + read replicas)      │
│         └── Message Queue (SQS/Pub-Sub for alerts)      │
│                                                          │
│  Shared Services                                         │
│    ├── Prometheus + Grafana (metrics)                    │
│    ├── OpenTelemetry → Jaeger (distributed tracing)     │
│    ├── ELK / CloudWatch / GCP Logging                   │
│    └── Vault / Secrets Manager (secrets rotation)       │
└─────────────────────────────────────────────────────────┘
```

---

## Scaling Phases

### Phase 1: Foundation (Weeks 1–6) — Target: 10K DAU
- [ ] **Backend**: Add Redis cache for quotes (30s TTL), connection pooling, Alembic migrations
- [ ] **Frontend**: Code-splitting, lazy loading, service worker for offline, bundle optimization
- [ ] **Test**: 80%+ backend coverage, frontend component tests, CI pipeline with tests
- [ ] **Auth/Security**: Rate limiting (100 req/min/user), JWT rotation, CSP headers audit
- [ ] **DevOps**: GitHub Actions CI/CD, Docker image optimization, health check endpoints

### Phase 2: Scale (Weeks 7–14) — Target: 100K DAU
- [ ] **Backend**: Read replicas, horizontal scaling (2–8 pods), WebSocket via Redis pub/sub
- [ ] **Frontend**: CDN-served static assets, WebSocket reconnection improvements, i18n framework
- [ ] **Test**: Load testing (k6/Locust for 10K concurrent), E2E with Playwright, chaos testing
- [ ] **Auth/Security**: RBAC (admin/premium/free), API key management, SOC2 prep, GDPR flows
- [ ] **DevOps**: Multi-region deployment, auto-scaling policies, RDS failover, observability stack

### Phase 3: Global (Weeks 15–24) — Target: 1M DAU
- [ ] **Backend**: Event-driven architecture (SQS/Pub-Sub), CQRS for reads, data partitioning
- [ ] **Frontend**: Multi-language (i18n), regional market support, PWA, mobile-responsive
- [ ] **Test**: Performance regression CI, synthetic monitoring, regional latency benchmarks
- [ ] **Auth/Security**: SSO enterprise support, compliance certifications, penetration testing
- [ ] **DevOps**: 3-region active-active, blue-green deployments, disaster recovery drills

---

## Inter-Team Contracts

### API Contract (Backend ↔ Frontend)
- OpenAPI spec is the **source of truth** — auto-generated from FastAPI
- Frontend consumes `/docs` (Swagger) for all endpoints
- Breaking API changes require a **2-sprint deprecation cycle** with versioned endpoints (`/api/v2/`)
- WebSocket message types are documented in `docs/WEBSOCKET_PROTOCOL.md` (to be created)

### Database Contract (Backend ↔ Auth/Security)
- All schema changes go through **Alembic migrations** — never use `metadata.create_all()` in production
- Auth team owns `users` table schema; backend team owns all other tables
- Any migration affecting `users` requires auth team review

### Deployment Contract (All Teams ↔ DevOps)
- All services must expose `/health` and `/ready` endpoints
- Docker images must pass security scan (Trivy) before merge
- Environment variables documented in `.env.example` — no hardcoded secrets
- Feature flags via environment variables, not code branches

### Testing Contract (All Teams ↔ Test Engineering)
- Every PR must include tests for new code paths
- No PR merges with <80% coverage on changed files
- Load test results required for any endpoint handling >1000 RPM
- Test team provides shared fixtures and test utilities

---

## Repository Structure (Target)

```
finmonitor/
├── .claude/
│   └── teams/           # ← You are here. Team agent standards.
├── .github/
│   └── workflows/       # CI/CD pipelines
├── backend/
│   ├── app/
│   │   ├── api/         # Route handlers (versioned: v1/, v2/)
│   │   ├── core/        # Config, database, auth, middleware
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── schemas/     # Pydantic request/response schemas
│   │   ├── providers/   # External data source adapters
│   │   └── services/    # Business logic, schedulers, notifications
│   ├── alembic/         # Database migrations
│   └── tests/           # Backend test suite
├── frontend/
│   ├── src/
│   │   ├── components/  # Reusable UI components
│   │   ├── pages/       # Page-level components
│   │   ├── contexts/    # React Context providers
│   │   ├── hooks/       # Custom React hooks
│   │   ├── services/    # API client layer
│   │   ├── types/       # TypeScript interfaces
│   │   └── __tests__/   # Frontend test suite
│   └── public/
├── deploy/
│   ├── aws/
│   ├── gcp/
│   ├── azure/
│   └── k8s/             # Kubernetes manifests (new)
├── tests/
│   ├── e2e/             # Playwright E2E tests (new)
│   ├── load/            # k6/Locust load tests (new)
│   └── security/        # Security scan configs (new)
├── docs/
│   ├── adr/             # Architecture Decision Records (new)
│   └── runbooks/        # Operational runbooks (new)
├── docker-compose.yml
└── Makefile             # Unified dev commands (new)
```

---

## Team Agent Files

Each team has a dedicated standards file in this directory:

| File | Team |
|------|------|
| [`backend-python.md`](./backend-python.md) | Backend Python Engineering |
| [`frontend-react.md`](./frontend-react.md) | Frontend React/TypeScript |
| [`test-engineering.md`](./test-engineering.md) | Test Engineering |
| [`auth-security.md`](./auth-security.md) | Auth & Security Engineering |
| [`devops-cicd.md`](./devops-cicd.md) | DevOps / CI-CD / SRE |

Each file is designed to be used as a **CLAUDE.md** or agent instruction file in Claude Code or VS Code Copilot. Engineers on each team should load their team file as context when working.

---

## Git Branching Strategy

**Trunk-based development** with short-lived feature branches:

```
main (protected — requires PR + CI pass + 1 approval)
  ├── feat/add-redis-cache         (Backend — max 3 days)
  ├── fix/websocket-reconnect      (Frontend — max 2 days)
  ├── infra/github-actions-ci      (DevOps — max 3 days)
  └── security/rate-limiting       (Auth — max 3 days)
```

**Rules:**
- `main` is always deployable — never push directly
- Branch naming: `<type>/<short-description>` where type is `feat`, `fix`, `infra`, `security`, `test`, `docs`
- Feature branches live max 3 days — break large work into smaller PRs
- Rebase on `main` before merging — no merge commits
- Delete branches after merge

## Code Review Process

| PR Type | Required Approvals | Reviewers |
|---------|-------------------|-----------|
| Feature (new endpoint, component) | 1 from own team + 1 from affected team | Backend ↔ Frontend for API changes |
| Security-related (auth, CORS, headers) | 1 from Auth team (mandatory) | Auth team reviews ALL security PRs |
| Database migration | 1 from Backend + 1 from Auth (if `users` table) | Backend + Auth |
| Infrastructure / CI-CD | 1 from DevOps team | DevOps |
| Test-only changes | 1 from any team | Test Engineering preferred |
| Docs-only changes | 1 from any team | Anyone |

**Review expectations:**
- Respond to review requests within 4 business hours
- Use "Approve", "Request Changes", or "Comment" — no silent approvals
- Check the PR checklist from the relevant team standards file
- Run tests locally before approving if CI is not yet set up

## Database Naming Conventions

- **Table names**: plural snake_case (`users`, `price_alerts`, `news_articles`)
- **Column names**: snake_case (`user_id`, `created_at`, `is_active`)
- **Foreign keys**: `<referenced_table_singular>_id` (e.g., `user_id`, `ipo_event_id`)
- **Indexes**: auto-named by SQLAlchemy, manual names as `ix_<table>_<column>`
- **Unique constraints**: `uq_<table>_<columns>` (e.g., `uq_user_watchlist_user_id_symbol`)
- **Boolean columns**: prefix with `is_` or `has_` (`is_active`, `is_public`, `has_premium`)
- **Timestamps**: always `DateTime(timezone=True)` with `server_default=func.now()`

## API Error Response Format

All API errors return this shape (enforced by FastAPI's `HTTPException`):
```json
{
  "detail": "Human-readable error message"
}
```

For validation errors (422), FastAPI returns:
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Rules:**
- Error messages must be user-safe — no stack traces, SQL errors, or internal paths
- Use consistent HTTP status codes across all endpoints (see backend-python.md)
- Frontend should handle both shapes (string detail and array detail)

---

## Communication Channels (Recommended)

- **Weekly sync**: All teams — 30 min standup on scaling progress
- **API review**: Backend + Frontend — review OpenAPI changes before implementation
- **Security review**: Auth + DevOps — weekly threat review and incident response
- **Deployment review**: DevOps + all teams — review deployment manifests before prod push
- **Retrospectives**: Bi-weekly per team, monthly cross-team
