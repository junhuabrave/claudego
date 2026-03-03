# Financial Markets Monitoring System

A real-time global financial markets monitoring dashboard with breaking news, IPO tracking, and personalized watchlists.

## Features

- **Breaking News Feed**: Real-time financial news that may impact markets
- **IPO Calendar**: Upcoming IPO events for the next 2 weeks with reminder/notification support
- **Personalized Watchlist**: Interactive chatbox to add/remove tickers
- **Notifications**: PagerDuty and email alerts for IPO events and market-moving news
- **Real-time Updates**: WebSocket-powered live data streaming

## Architecture

```
frontend/ (React + MUI)
  ├── Dashboard with news feed, IPO calendar, watchlist
  ├── Interactive chatbox for ticker management
  └── WebSocket client for real-time updates

backend/ (FastAPI + PostgreSQL)
  ├── REST API for CRUD operations
  ├── WebSocket server for real-time push
  ├── Data providers (abstracted for easy swap)
  │   ├── Finnhub (news + quotes)
  │   ├── Alpha Vantage (market data)
  │   └── SEC EDGAR (IPO filings)
  └── Notification services
      ├── PagerDuty integration
      └── Email (AWS SES / SMTP)

deploy/
  ├── Docker Compose (local dev)
  ├── AWS (ECS/Fargate + RDS + CloudFront)
  ├── GCP (Cloud Run + Cloud SQL)
  └── Azure (Container Apps + Azure SQL)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker & Docker Compose (optional)
- [Colima](https://github.com/abiosoft/colima) (macOS Docker runtime, if not using Docker Desktop)

### Local Development (with HTTPS)

#### 1. Generate local SSL certs
```bash
brew install mkcert
mkcert -install        # run once — needs sudo, adds CA to system trust
cd certs
mkcert localhost 127.0.0.1
```

#### 2. Start with Docker Compose (via Colima)
```bash
colima ssh -- sh -c "cd /Users/<you>/claudego && docker compose up --build -d"
```

Open **https://localhost:3443** for the dashboard.

> **Note:** On macOS with Colima, `docker-compose` is unavailable. Use `colima ssh -- sh -c "..."` to run compose commands inside the VM, which has `docker compose` (v5) built in.

#### Common Colima commands
```bash
# Start
colima ssh -- sh -c "cd /path/to/project && docker compose up -d"
# Rebuild
colima ssh -- sh -c "cd /path/to/project && docker compose up --build -d"
# Restart specific services
colima ssh -- sh -c "cd /path/to/project && docker compose restart frontend backend"
# Stop
colima ssh -- sh -c "cd /path/to/project && docker compose down"
# Logs
colima ssh -- sh -c "cd /path/to/project && docker compose logs <service> --tail=30"
```

## Production Deployment (AWS)

### Infrastructure
| Component | Service |
|---|---|
| Container runtime | ECS Fargate |
| Container registry | ECR |
| Load balancer | ALB (HTTP only — port 80) |
| HTTPS / CDN | CloudFront (`*.cloudfront.net` cert — free) |
| Database | RDS PostgreSQL |
| Secrets | AWS Secrets Manager (`finmonitor/config`) |

### Traffic flow
```
Browser ──HTTPS──▶ CloudFront ──HTTP──▶ ALB ──HTTP──▶ ECS (nginx + FastAPI)
        (encrypted)            (internal)    (internal)
```

### Deploy
```bash
cd /path/to/claudego
AWS_ACCOUNT_ID=<your-account-id> bash deploy/aws/deploy.sh
```

### Adding a custom domain later
1. CloudFront → Edit distribution → add CNAME + attach ACM cert
2. Update `deploy/aws/deploy.sh`: change `REACT_APP_WS_URL` to `wss://yourdomain.com/api/ws`
3. Redeploy with `deploy.sh`

## Configuration

All configuration is environment-based for cloud portability. See:
- `backend/.env.example` for backend settings
- `frontend/.env.example` for frontend settings
- `deploy/` for cloud-specific deployment configs

## API Keys Required

| Service | Purpose | Get Key |
|---------|---------|---------|
| Finnhub | Market news & quotes | https://finnhub.io/ |
| Alpha Vantage | Market data | https://www.alphavantage.co/ |
| NewsAPI | Breaking news | https://newsapi.org/ |
| PagerDuty | Alert notifications | https://www.pagerduty.com/ |

## Lessons Learned

### Local HTTPS (Docker + Colima)
- Use `mkcert` for trusted local certs — no browser warnings
- `mkcert -install` requires an interactive terminal (sudo) — cannot be scripted
- Nginx inside Docker must use the **Docker service name** (`http://backend:8000`) not `localhost` for proxying between containers
- `REACT_APP_*` env vars are baked into the React build at build time — set them via `--build-arg` in Docker, not just `.env`

### AWS CloudFront + ALB
- When CloudFront forwards to an HTTP-only ALB, set the origin protocol to **`http-only`** — CloudFront defaults to `https-only` which causes 504 errors
- CloudFront handles TLS termination — the ALB does not need an HTTPS listener
- `CORS_ORIGINS=["*"]` is insecure for production — restrict to your CloudFront or custom domain
- WebSocket (`wss://`) works natively through CloudFront with no extra config — just ensure `AllViewer` origin request policy is set on the `/api/*` behavior

### General
- DuckDNS cannot be used with AWS ACM (no support for adding CNAME validation records)
- CloudFront free tier (1TB + 10M requests/month) is sufficient for personal/dev projects at no cost

## License

MIT
