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
        demo lint lint-py lint-widget build clean shell-db shell-redis

# ── help ─────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  $(BOLD)NIA Platform — available targets$(RESET)"
	@echo ""
	@echo "  $(CYAN)dev$(RESET)          Start all services with docker compose (dev mode)"
	@echo "  $(CYAN)down$(RESET)         Stop all services"
	@echo "  $(CYAN)logs$(RESET)         Tail logs from all services"
	@echo "  $(CYAN)demo$(RESET)         Start widget demo page at http://localhost:8088"
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
	@echo "  Run 'make demo' to start the widget demo page (http://localhost:8088)"

# ── demo ─────────────────────────────────────────────────────
demo:
	@echo -e "$(GREEN)$(BOLD)▶ Starting NIA widget demo…$(RESET)"
	@echo "  Open: http://localhost:8088"
	$(PYTHON) demo_server.py

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

# ══════════════════════════════════════════════════════════════════════════════
# 📮 Postman Collection Management
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: postman-generate postman-test postman-update postman-clean postman-install postman-watch

postman-install: ## 📦 Instalar herramientas de Postman
	@echo "📦 Instalando herramientas de Postman..."
	npm install -g newman openapi-to-postman

postman-generate: ## 🔄 Generar colección de Postman desde OpenAPI
	@echo "🔄 Generando colección de Postman..."
	@chmod +x scripts/generate-postman-collection.sh
	@./scripts/generate-postman-collection.sh
	@echo "✅ Colección generada en .postman/NIA-Complete-Collection.json"

postman-test: postman-generate ## 🧪 Probar colección de Postman
	@echo "🧪 Probando colección de Postman..."
	@if [ ! -f .postman/NIA-Complete-Collection.json ]; then \
		echo "❌ Colección no encontrada. Ejecuta 'make postman-generate' primero"; \
		exit 1; \
	fi
	newman run .postman/NIA-Complete-Collection.json \
		-e NIA-Environment-Development.json \
		--reporters cli,html \
		--reporter-html-export .postman/test-results.html \
		--timeout 10000 \
		--bail
	@echo "📊 Reporte HTML generado en .postman/test-results.html"

postman-update: up postman-generate postman-test ## 🚀 Actualización completa de Postman
	@echo "🚀 Actualización completa de Postman realizada"
	@echo "📋 Para importar en Postman:"
	@echo "   1. Abre Postman"
	@echo "   2. Import → .postman/NIA-Complete-Collection.json"
	@echo "   3. Import → NIA-Environment-Development.json"

postman-watch: ## 👀 Vigilar cambios y actualizar Postman automáticamente
	@echo "👀 Vigilando cambios en los servicios..."
	@echo "💡 Presiona Ctrl+C para detener"
	@while true; do \
		find services/ -name "*.py" -newer .postman/NIA-Complete-Collection.json 2>/dev/null | head -1 | grep -q . && { \
			echo "🔄 Cambios detectados, regenerando colección..."; \
			make postman-generate; \
		}; \
		sleep 5; \
	done

postman-clean: ## 🧹 Limpiar archivos de Postman generados
	@echo "🧹 Limpiando archivos de Postman..."
	rm -rf .postman/collections .postman/openapi .postman/test-results.*
	@echo "✅ Archivos de Postman limpiados"
