.PHONY: dev dev-down test lint build deploy-staging help

## Start local dev environment
dev:
	docker compose up --build

## Stop local dev environment
dev-down:
	docker compose down

## Run all tests
test: test-backend test-frontend

test-backend:
	cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

test-frontend:
	cd frontend && npm test -- --watchAll=false

## Run all linters
lint: lint-backend lint-frontend

lint-backend:
	ruff check backend/app
	cd backend && mypy app/ --ignore-missing-imports

lint-frontend:
	cd frontend && npx tsc --noEmit

## Build Docker images
build:
	docker build -t finmonitor-backend:local ./backend
	docker build -t finmonitor-frontend:local --build-arg NGINX_CONF=nginx.prod.conf ./frontend

## Deploy to staging (requires cloud credentials)
deploy-staging:
	@echo "Deploying to staging..."
	@echo "Set CLOUD_PROVIDER=aws|gcp|azure and ensure credentials are configured."
	@[ "$(CLOUD_PROVIDER)" ] || (echo "Error: CLOUD_PROVIDER not set" && exit 1)

help:
	@grep -E '^##' Makefile | sed 's/## //'
