# FinMonitor Scaling Roadmap — 100K to 1M DAU

## Executive Summary

FinMonitor is a real-time financial markets monitoring platform. This document defines the engineering roadmap to scale from a single-developer project to a globally resilient platform serving 1M daily active users interested in any financial market worldwide.

---

## Current Architecture Audit

### What Works Well
- Async-first Python backend (FastAPI + asyncpg) — ready for horizontal scaling
- Provider abstraction pattern — easy to add new data sources (Bloomberg, Reuters, etc.)
- Container-based deployment — same image runs on AWS, GCP, Azure
- WebSocket broadcast — real-time updates without polling
- Google OAuth + anonymous sessions — frictionless onboarding

### What Needs Work Before Scale

| Issue | Risk at Scale | Priority |
|-------|---------------|----------|
| No database migrations (metadata.create_all) | Schema drift, data loss on team | P0 |
| No Redis cache | Every request hits DB, DB becomes bottleneck at 10K users | P0 |
| Single-instance WebSocket | Can't scale beyond 1 pod (broadcast is in-memory) | P0 |
| JWT secret is "change-me-in-production" | Security vulnerability | P0 |
| No rate limiting | Abuse, scraping, DDoS vulnerability | P0 |
| No CI/CD pipeline | Manual deploys, no automated testing | P1 |
| No structured logging | Can't debug issues in production | P1 |
| No health check endpoints | Load balancer can't route correctly | P1 |
| No monitoring/alerting | Blind to failures until users report | P1 |
| No pagination on news/IPO endpoints | Response size grows unbounded | P1 |
| No i18n | Can't serve non-English markets | P2 |
| No read replicas | Single DB handles all read+write traffic | P2 |

---

## Phase 1: Foundation (Weeks 1–6) — Target: 10K DAU

**Goal:** Production-ready with proper CI/CD, security, and monitoring.

### All Teams — Week 1 Kickoff
| Task | Owner | Days |
|------|-------|------|
| Set up GitHub Actions CI: lint + test + build | DevOps | 2 |
| Switch to Alembic migrations | Backend | 2 |
| Generate real JWT secret, audit all env vars | Auth/Security | 1 |
| Create Makefile for unified dev commands | DevOps | 1 |
| Set up code review process + branch protection | DevOps | 1 |

### Backend — Weeks 1–4
| Task | Priority | Days |
|------|----------|------|
| Add Redis cache for quotes (30s TTL) and news (60s TTL) | P0 | 3 |
| Configure DB connection pool (pool_size=20, max_overflow=10) | P0 | 1 |
| Add /health and /ready endpoints | P0 | 1 |
| Add structured logging (structlog, JSON output) | P1 | 2 |
| Add request ID middleware | P1 | 1 |
| Add cursor-based pagination to /news and /ipos | P1 | 2 |
| Create Alembic migration for current schema | P0 | 1 |
| Add circuit breaker for Finnhub/Alpha Vantage calls | P1 | 2 |
| Comprehensive NaN/Inf sanitization for yfinance | P1 | 1 |

### Frontend — Weeks 1–4
| Task | Priority | Days |
|------|----------|------|
| Add ESLint + Prettier configs | P0 | 1 |
| Add ErrorBoundary component | P1 | 1 |
| Implement code-splitting (React.lazy for dialogs) | P1 | 2 |
| Add loading skeletons for all data components | P1 | 2 |
| Bundle analysis + tree-shake unused MUI | P1 | 1 |
| Add WebSocket reconnection indicator | P1 | 1 |
| Service worker for offline caching | P2 | 2 |

### Auth/Security — Weeks 1–4
| Task | Priority | Days |
|------|----------|------|
| Replace hardcoded JWT secret with env var + validation | P0 | 0.5 |
| Implement rate limiting middleware (100 req/min) | P0 | 3 |
| Add refresh token flow (15-min access + 30-day refresh) | P0 | 3 |
| Audit and set all HTTP security headers (CSP, HSTS, etc.) | P0 | 1 |
| Add input validation regex for ticker symbols | P1 | 1 |
| Set API payload size limits (1MB max body) | P1 | 0.5 |

### Test Engineering — Weeks 1–6
| Task | Priority | Days |
|------|----------|------|
| Write missing backend tests (chat, scheduler, providers) | P0 | 5 |
| Write frontend component tests (all components) | P0 | 5 |
| Set up Playwright E2E framework | P1 | 3 |
| Write 5 core E2E flow tests | P1 | 3 |
| Create k6 smoke test, integrate into CI | P1 | 2 |
| Add coverage reporting (codecov) | P1 | 1 |

### DevOps — Weeks 1–6
| Task | Priority | Days |
|------|----------|------|
| GitHub Actions CI pipeline (lint + test + build) | P0 | 2 |
| Optimize Dockerfiles (multi-stage, non-root, .dockerignore) | P0 | 2 |
| Set up staging environment | P0 | 3 |
| Create deploy pipeline (staging auto, prod manual gate) | P1 | 3 |
| Set up basic monitoring dashboards | P1 | 2 |
| Create deployment + rollback runbook | P1 | 1 |
| Implement blue-green deployment | P2 | 3 |

**Phase 1 Exit Criteria:**
- [ ] CI pipeline runs on every PR, blocks merge on failure
- [ ] All tests pass, backend coverage >80%
- [ ] Rate limiting active, JWT secret rotated, security headers set
- [ ] Staging environment mirrors production
- [ ] Monitoring dashboard shows request rate, error rate, latency
- [ ] Deployment takes <5 min, rollback takes <2 min

---

## Phase 2: Scale (Weeks 7–14) — Target: 100K DAU

**Goal:** Horizontal scaling, multi-instance support, observability.

### Backend — Weeks 7–10
| Task | Priority | Days |
|------|----------|------|
| Redis pub/sub for WebSocket broadcast (multi-instance) | P0 | 5 |
| Database read replicas (route GET queries to replica) | P0 | 3 |
| API versioning: /api/v1/ prefix + deprecation headers | P1 | 2 |
| Background task queue (arq/Celery) for notifications | P1 | 3 |
| OpenTelemetry instrumentation | P1 | 2 |
| Graceful shutdown (drain WS, finish in-flight) | P1 | 2 |
| Add new data providers (markets beyond US) | P2 | 5 |

### Frontend — Weeks 7–10
| Task | Priority | Days |
|------|----------|------|
| i18n framework (react-i18next) + English extraction | P1 | 3 |
| Virtual scrolling for long lists (react-window) | P1 | 2 |
| Optimistic UI updates | P1 | 2 |
| Dark mode support (MUI theme toggle) | P2 | 2 |
| Migrate CRA → Vite | P2 | 3 |
| PWA manifest + icons | P2 | 1 |
| Accessibility audit + fixes | P2 | 3 |

### Auth/Security — Weeks 7–10
| Task | Priority | Days |
|------|----------|------|
| RBAC system (admin/premium/free permissions) | P0 | 5 |
| GitHub OAuth provider | P1 | 3 |
| Authenticated WebSocket (JWT in first message) | P1 | 3 |
| API key management for premium users | P2 | 3 |
| GDPR: account deletion + data export | P1 | 3 |
| External security audit / penetration test | P1 | coordinated |

### Test Engineering — Weeks 7–14
| Task | Priority | Days |
|------|----------|------|
| k6 load test (500 users, 5 min) + stress test (2K users) | P0 | 3 |
| Contract testing (Frontend ↔ Backend API schema) | P1 | 3 |
| Playwright visual regression testing | P2 | 2 |
| Chaos testing (kill backend during load) | P2 | 3 |
| Database migration testing in CI | P1 | 1 |

### DevOps — Weeks 7–14
| Task | Priority | Days |
|------|----------|------|
| Terraform/Pulumi IaC for primary cloud | P0 | 5 |
| Auto-scaling (CPU-based, 2–20 instances) | P0 | 3 |
| Redis cluster setup (ElastiCache/Memorystore) | P0 | 2 |
| Full observability: Prometheus + Grafana + Jaeger | P1 | 5 |
| PagerDuty alerting for SEV1/SEV2 incidents | P1 | 2 |
| CDN optimization (cache headers, edge caching) | P1 | 2 |
| Database automated backups + point-in-time recovery | P1 | 1 |

**Phase 2 Exit Criteria:**
- [ ] Backend scales to 20 instances without WebSocket issues
- [ ] P95 latency <500ms at 100K DAU load
- [ ] Read replicas serve GET traffic, primary handles writes only
- [ ] Observability: traces, metrics, logs all correlated by request ID
- [ ] RBAC enforced: premium features gated, admin tools protected
- [ ] Load test proves system handles 10K concurrent users

---

## Phase 3: Global (Weeks 15–24) — Target: 1M DAU

**Goal:** Multi-region, multi-language, enterprise-ready.

### Backend
- Event-driven architecture (SQS/Pub-Sub for price updates + alerts)
- CQRS: separate read/write paths for hot endpoints
- Database partitioning (user_watchlist by user_id range)
- Cold storage archival (news >90 days → S3/GCS)
- Multi-market data: add providers for Korea (KRX), Japan (TSE), EU (Euronext)
- GraphQL or gRPC for mobile/power-user clients

### Frontend
- Multi-language: EN, KO, JA, ZH, DE, FR
- Regional market pages with localized content
- Web Workers for chart rendering
- Mobile-first responsive redesign
- A/B testing framework
- Performance monitoring (Web Vitals dashboard)

### Auth/Security
- Enterprise SSO (SAML/OIDC)
- Multi-factor authentication (TOTP)
- SOC2 certification
- Regional data residency compliance
- Bug bounty program

### Test Engineering
- Multi-region latency benchmarks
- Performance regression detection in CI
- API fuzzing (hypothesis library)
- Synthetic monitoring (5-min E2E probes in each region)
- Accessibility automation (axe-core)

### DevOps
- 3-region active-active deployment (US, EU, Asia)
- Global load balancing (latency-based DNS)
- Cross-region DB replication
- Disaster recovery: RPO <1h, RTO <15min, quarterly drills
- Chaos engineering (automated failure injection)
- Cost optimization (reserved/spot instances)

---

## Key Metrics & SLAs

### Service Level Objectives (SLOs)
| Metric | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|
| Availability | 99.5% | 99.9% | 99.95% |
| API P95 latency | <1s | <500ms | <200ms |
| WebSocket reconnect time | <5s | <3s | <1s |
| Deploy frequency | 1x/week | 1x/day | Multiple/day |
| Rollback time | <10 min | <5 min | <1 min |
| Incident detection | Manual | <5 min | <1 min |
| Recovery time | <1 hour | <15 min | <5 min |

### Business Metrics to Track
- DAU / MAU ratio (engagement)
- Tickers per user (depth of use)
- Alert creation rate (feature adoption)
- WebSocket uptime per session (reliability)
- Time to first ticker (onboarding speed)
- Regional user distribution (global expansion)

---

## Architecture Decision Records (ADRs)

### ADR-001: PostgreSQL as Primary Database
- **Decision**: Continue with PostgreSQL
- **Rationale**: ACID for financial data, async driver (asyncpg), managed options on all clouds
- **Alternative considered**: MongoDB (rejected — financial data needs strong consistency)

### ADR-002: Redis for Caching and Pub/Sub
- **Decision**: Add Redis for quote caching (30s TTL) and WebSocket pub/sub
- **Rationale**: Most mature cache + pub/sub, managed options on all clouds, simple API
- **Alternative considered**: Memcached (rejected — no pub/sub), Kafka (overkill for current scale)

### ADR-003: Alembic for Database Migrations
- **Decision**: Replace metadata.create_all() with Alembic
- **Rationale**: Team development requires versioned, reviewable schema changes
- **Alternative considered**: Raw SQL migrations (rejected — no auto-generation from models)

### ADR-004: GitHub Actions for CI/CD
- **Decision**: GitHub Actions for all CI/CD
- **Rationale**: Integrated with repo, free tier generous, marketplace for cloud deployments
- **Alternative considered**: GitLab CI (would require repo migration), CircleCI (additional cost)

### ADR-005: Cloud-Agnostic Container Orchestration
- **Decision**: Support ECS Fargate (AWS), Cloud Run (GCP), Container Apps (Azure)
- **Rationale**: Avoid vendor lock-in, each cloud has managed container service
- **Future**: Consider Kubernetes (EKS/GKE/AKS) when team reaches 10+ engineers
