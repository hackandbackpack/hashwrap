# HashWrap - Secure Password Cracking Service
# Development and deployment automation

.PHONY: help dev build test lint clean deploy stop logs status

# Default target
.DEFAULT_GOAL := help

# Configuration
COMPOSE_FILE := docker-compose.yml
COMPOSE_DEV_FILE := docker-compose.dev.yml
COMPOSE_PROD_FILE := docker-compose.prod.yml

help: ## Show this help message
	@echo "HashWrap - Available commands:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

# Development commands
dev: ## Start development environment with hot reload
	@echo "Starting HashWrap development environment..."
	docker-compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) up --build

dev-down: ## Stop development environment
	docker-compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) down

# Production commands
build: ## Build all Docker images
	@echo "Building HashWrap Docker images..."
	docker-compose build --no-cache

deploy: ## Deploy production environment
	@echo "Deploying HashWrap production environment..."
	@if [ ! -f .env ]; then echo "Error: .env file not found. Copy .env.example and configure."; exit 1; fi
	docker-compose -f $(COMPOSE_FILE) up -d --build

stop: ## Stop all services
	@echo "Stopping HashWrap services..."
	docker-compose down

restart: ## Restart all services
	@echo "Restarting HashWrap services..."
	docker-compose restart

# Monitoring commands
logs: ## Show logs for all services
	docker-compose logs -f

status: ## Show service status
	@echo "HashWrap Service Status:"
	@echo "======================="
	docker-compose ps
	@echo ""
	@echo "Health Checks:"
	@echo "============="
	@curl -s http://localhost/healthz || echo "❌ API Health Check Failed"
	@curl -s http://localhost/api/v1/health || echo "❌ API Endpoint Failed"

health: ## Run comprehensive health checks
	@echo "Running comprehensive health checks..."
	@./scripts/health-check.sh

# Testing commands
test: ## Run all tests
	@echo "Running HashWrap test suite..."
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

test-backend: ## Run backend tests only
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -v --cov=app

test-frontend: ## Run frontend tests only
	@echo "Running frontend tests..."
	cd frontend && npm test

# Code quality commands
lint: ## Run linting for all components
	@echo "Running linting checks..."
	@$(MAKE) lint-backend
	@$(MAKE) lint-frontend

lint-backend: ## Lint Python backend code
	@echo "Linting backend code..."
	cd backend && python -m ruff check .
	cd backend && python -m black . --check
	cd backend && python -m mypy app/

lint-frontend: ## Lint TypeScript frontend code
	@echo "Linting frontend code..."
	cd frontend && npm run lint
	cd frontend && npm run type-check

format: ## Auto-format all code
	@echo "Auto-formatting code..."
	cd backend && python -m black .
	cd backend && python -m ruff check . --fix
	cd frontend && npm run format

# Security commands
security-scan: ## Run security scans
	@echo "Running security scans..."
	cd backend && python -m bandit -r app/ -f json -o bandit-report.json
	cd frontend && npm audit --audit-level moderate
	docker run --rm -v $(PWD):/app -w /app aquasec/trivy fs .

# Database commands
db-migrate: ## Run database migrations
	@echo "Running database migrations..."
	docker-compose exec api python -m alembic upgrade head

db-reset: ## Reset database (⚠️  DESTRUCTIVE)
	@echo "⚠️  WARNING: This will destroy all data!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose down -v
	docker volume rm $(shell docker volume ls -q | grep hashwrap) 2>/dev/null || true
	docker-compose up -d postgres redis
	@sleep 10
	@$(MAKE) db-migrate

# Backup and restore
backup: ## Create database backup
	@echo "Creating database backup..."
	@mkdir -p backups
	docker-compose exec postgres pg_dump -U hashwrap hashwrap > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/"

restore: ## Restore from backup (set BACKUP_FILE=filename)
	@if [ -z "$(BACKUP_FILE)" ]; then echo "Error: Set BACKUP_FILE=filename"; exit 1; fi
	@echo "Restoring from $(BACKUP_FILE)..."
	docker-compose exec -T postgres psql -U hashwrap -d hashwrap < backups/$(BACKUP_FILE)

# Cleanup commands
clean: ## Clean up Docker resources
	@echo "Cleaning up Docker resources..."
	docker-compose down -v --remove-orphans
	docker system prune -f
	docker volume prune -f

clean-all: ## Clean up everything including images
	@echo "⚠️  WARNING: This will remove ALL HashWrap Docker resources!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	docker-compose down -v --remove-orphans --rmi all
	docker system prune -af
	docker volume prune -f

# Update commands
update: ## Update HashWrap to latest version
	@echo "Updating HashWrap..."
	git pull origin main
	docker-compose pull
	@$(MAKE) build
	@$(MAKE) deploy

# Setup commands
setup: ## Initial setup - run bootstrap script
	@echo "Running initial setup..."
	./bootstrap.sh

setup-dev: ## Setup development environment
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; fi
	@if [ ! -f hashwrap.yaml ]; then cp hashwrap.example.yaml hashwrap.yaml; fi
	@if [ ! -f notifiers.yaml ]; then cp notifiers.example.yaml notifiers.yaml; fi
	@echo "✅ Development environment configured"
	@echo "📝 Edit .env, hashwrap.yaml, and notifiers.yaml as needed"

# GPU commands
gpu-test: ## Test GPU availability
	@echo "Testing GPU availability..."
	nvidia-smi || echo "❌ NVIDIA drivers not found"
	docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi || echo "❌ Docker GPU support not available"

gpu-info: ## Show GPU information
	@echo "GPU Information:"
	@echo "==============="
	nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits || echo "❌ No GPUs detected"

# Monitoring commands
monitor: ## Monitor system resources
	@echo "Monitoring HashWrap resources..."
	watch -n 2 'docker stats --no-stream; echo ""; docker-compose ps; echo ""; curl -s http://localhost/healthz'

metrics: ## Show Prometheus metrics
	@echo "HashWrap Metrics:"
	@echo "================"
	curl -s http://localhost/metrics | head -20

# SSL/Security setup
ssl-setup: ## Generate self-signed SSL certificates
	@echo "Generating self-signed SSL certificates..."
	@mkdir -p nginx/ssl
	openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout nginx/ssl/hashwrap.key \
		-out nginx/ssl/hashwrap.crt \
		-subj "/C=US/ST=State/L=City/O=HashWrap/CN=localhost"
	@echo "✅ SSL certificates generated in nginx/ssl/"

# Performance testing
perf-test: ## Run performance tests
	@echo "Running performance tests..."
	@if command -v wrk >/dev/null 2>&1; then \
		wrk -t4 -c100 -d30s http://localhost/api/v1/health; \
	else \
		echo "Install 'wrk' for performance testing"; \
	fi

# Documentation
docs: ## Generate documentation
	@echo "Generating documentation..."
	@if [ -d "docs/" ]; then \
		cd docs && mkdocs build; \
	else \
		echo "Documentation not available"; \
	fi