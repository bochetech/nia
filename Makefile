# ============================================================
#  NIA — Nodo de Inteligencia Activa para Turismo SaaS
#  Makefile — developer shortcuts
# ============================================================
.DEFAULT_GOAL := help
SHELL         := /bin/bash

# ── Colors ───────────────────────────────────────────────────
BOLD  := \033[1m
GREEN := \033[0;32m
CYAN  := \033[0;36m
RESET := \033[0m

# ── Docker Compose ───────────────────────────────────────────
DC  := docker compose
DCF := -f docker-compose.yml

# ── Python ───────────────────────────────────────────────────
PYTHON := python3
PIP    := pip3

# ── Node ─────────────────────────────────────────────────────
NPM := npm

.PHONY: help dev down logs seed migrate test test-py test-widget \
        lint lint-py lint-widget build clean shell-db shell-redis

# ── help ─────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  $(BOLD)NIA Platform — available targets$(RESET)"
	@echo ""
	@echo "  $(CYAN)dev$(RESET)          Start all services with docker compose (dev mode)"
	@echo "  $(CYAN)down$(RESET)         Stop all services"
	@echo "  $(CYAN)logs$(RESET)         Tail logs from all services"
	@echo "  $(CYAN)migrate$(RESET)      Run Alembic DB migrations (upgrade head)"
	@echo "  $(CYAN)seed$(RESET)         Seed demo tenant, products & knowledge base"
	@echo "  $(CYAN)test$(RESET)         Run all tests (Python + Widget)"
	@echo "  $(CYAN)test-py$(RESET)      Run Python service tests only"
	@echo "  $(CYAN)test-widget$(RESET)  Run widget Vitest tests only"
	@echo "  $(CYAN)lint$(RESET)         Lint Python + TypeScript"
	@echo "  $(CYAN)build$(RESET)        Build widget bundle"
	@echo "  $(CYAN)clean$(RESET)        Remove build artefacts"
	@echo "  $(CYAN)shell-db$(RESET)     Open psql shell inside postgres container"
	@echo "  $(CYAN)shell-redis$(RESET)  Open redis-cli inside redis container"
	@echo ""

# ── dev ──────────────────────────────────────────────────────
dev:
	@echo -e "$(GREEN)$(BOLD)▶ Starting NIA stack…$(RESET)"
	@cp -n .env.example .env 2>/dev/null || true
	$(DC) $(DCF) up --build -d
	@echo ""
	@echo -e "$(GREEN)Services ready:$(RESET)"
	@echo "  Traefik dashboard : http://localhost:8080"
	@echo "  Orchestrator      : http://localhost:8001/docs"
	@echo "  RAG Service       : http://localhost:8002/docs"
	@echo "  Tenant Manager    : http://localhost:8003/docs"
	@echo "  Recommender       : http://localhost:8004/docs"
	@echo "  Model Adapter     : http://localhost:8005/docs"
	@echo "  Qdrant UI         : http://localhost:6333/dashboard"
	@echo ""
	@echo "  Run 'make seed' to load demo data."

# ── down ─────────────────────────────────────────────────────
down:
	$(DC) $(DCF) down

# ── logs ─────────────────────────────────────────────────────
logs:
	$(DC) $(DCF) logs -f

logs-%:
	$(DC) $(DCF) logs -f $*

# ── migrate ──────────────────────────────────────────────────
migrate:
	@echo -e "$(GREEN)$(BOLD)▶ Running Alembic migrations…$(RESET)"
	$(PYTHON) -m alembic -c infra/db/migrations/alembic.ini upgrade head

migrate-down:
	$(PYTHON) -m alembic -c infra/db/migrations/alembic.ini downgrade -1

migrate-history:
	$(PYTHON) -m alembic -c infra/db/migrations/alembic.ini history

# ── seed ─────────────────────────────────────────────────────
seed:
	@echo -e "$(GREEN)$(BOLD)▶ Seeding demo data…$(RESET)"
	@bash scripts/seed.sh

# ── test ─────────────────────────────────────────────────────
test: test-py test-widget
	@echo -e "$(GREEN)$(BOLD)All tests passed.$(RESET)"

test-py:
	@echo -e "$(GREEN)$(BOLD)▶ Running Python tests…$(RESET)"
	$(PIP) install --quiet pytest pytest-asyncio httpx pydantic-settings 2>/dev/null || true
	$(PYTHON) -m pytest

test-widget:
	@echo -e "$(GREEN)$(BOLD)▶ Running widget tests…$(RESET)"
	cd packages/widget && $(NPM) test

# ── lint ─────────────────────────────────────────────────────
lint: lint-py lint-widget

lint-py:
	@echo -e "$(GREEN)$(BOLD)▶ Linting Python (ruff)…$(RESET)"
	@command -v ruff &>/dev/null || $(PIP) install --quiet ruff
	ruff check services/ shared/ --fix

lint-widget:
	@echo -e "$(GREEN)$(BOLD)▶ Type-checking widget (tsc)…$(RESET)"
	cd packages/widget && $(NPM) run typecheck

# ── build ─────────────────────────────────────────────────────
build:
	@echo -e "$(GREEN)$(BOLD)▶ Building widget bundle…$(RESET)"
	cd packages/widget && $(NPM) run build
	@echo -e "$(GREEN)Widget built → packages/widget/dist/$(RESET)"

# ── install ───────────────────────────────────────────────────
install:
	@echo -e "$(GREEN)$(BOLD)▶ Installing widget dependencies…$(RESET)"
	cd packages/widget && $(NPM) install
	@echo -e "$(GREEN)$(BOLD)▶ Installing shared Python lib…$(RESET)"
	$(PIP) install -e shared/

# ── clean ────────────────────────────────────────────────────
clean:
	@echo -e "$(GREEN)$(BOLD)▶ Cleaning artefacts…$(RESET)"
	rm -rf packages/widget/dist packages/widget/node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# ── shells ────────────────────────────────────────────────────
shell-db:
	$(DC) $(DCF) exec postgres psql -U nia -d nia

shell-redis:
	$(DC) $(DCF) exec redis redis-cli
