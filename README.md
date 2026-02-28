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
  ├── AWS (ECS/Fargate + RDS)
  ├── GCP (Cloud Run + Cloud SQL)
  └── Azure (Container Apps + Azure SQL)
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Docker & Docker Compose (optional)

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp .env.example .env  # Edit with backend URL
npm start
```

### Docker Compose

```bash
docker compose up --build
```

Open http://localhost:3000 for the dashboard.

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

## License

MIT
