# NIA — Nodo de Inteligencia Activa para Turismo SaaS

> Multi-tenant, cloud-native conversational AI platform for tourism operators.  
> Embeddable widget · RAG knowledge base · FSM orchestration · Stripe checkout · Teams handoff

---

## Architecture at a Glance

```
Browser Widget (Preact + Shadow DOM)
        │  WebSocket / REST
        ▼
┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ Orchestrator │───▶│ RAG Service │───▶│ Model Adapter│
│  (FSM, 8001) │    │   (8002)    │    │   (8005)     │
└──────┬───────┘    └─────────────┘    └──────┬───────┘
       │                                       │
  ┌────┴───────┐                    ┌──────────┴───────┐
  │ Recommender│                    │ LM Studio (local)│
  │   (8004)   │                    │ Vertex AI (prod) │
  └────────────┘                    └──────────────────┘
       │
  ┌────┴──────────────────────────────────────────┐
  │ Checkout(8006) │ Handoff(8007) │ Transcript(8008) │
  └───────────────────────────────────────────────┘
       │
  ┌────┴────────────────────────┐
  │ Tenant Manager (8003)       │
  │ PostgreSQL 16 + RLS         │
  │ Redis 7  │  Qdrant          │
  └─────────────────────────────┘
```

---

## Quick Start (local dev — 5 minutes)

### Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | ≥ 4.28 |
| Node.js | ≥ 20 |
| Python | ≥ 3.12 |
| LM Studio | any (optional — for local LLM) |
| make | built-in on macOS/Linux |

### 1. Clone & configure

```bash
git clone <repo-url> nia && cd nia
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET to a random string
```

### 2. Start the stack

```bash
make dev
```

All 13 services start in Docker. On first run images are built (~3 min).

| Service | URL |
|---------|-----|
| Orchestrator API docs | http://localhost:8001/docs |
| RAG Service API docs | http://localhost:8002/docs |
| Tenant Manager API docs | http://localhost:8003/docs |
| Recommender API docs | http://localhost:8004/docs |
| Model Adapter API docs | http://localhost:8005/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Traefik dashboard | http://localhost:8080 |

### 3. Run DB migrations

```bash
make migrate
```

### 4. Seed demo data

```bash
make seed
```

This creates a `demo-turismo` tenant, loads 5 products, and ingests the knowledge base into Qdrant.

### 5. Install & build the widget

```bash
make install   # npm install + pip install -e shared/
make build     # builds packages/widget/dist/nia-widget.js
```

### 6. Test the widget

Embed the script in any HTML file:

```html
<!DOCTYPE html>
<html lang="es">
<head><title>Test NIA</title></head>
<body>
  <h1>Mi Agencia de Viajes</h1>
  <script
    src="http://localhost:3000/nia-widget.js"
    data-tenant="demo-turismo"
    data-api-url="http://localhost:8001"
    data-tenant-manager-url="http://localhost:8003">
  </script>
</body>
</html>
```

Or run the widget dev server for hot-reload:

```bash
cd packages/widget && npm run dev
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_PROVIDER` | `lmstudio` \| `vertexai` \| `openai` | `lmstudio` |
| `LMSTUDIO_URL` | LM Studio base URL | `http://host.docker.internal:1234` |
| `LMSTUDIO_MODEL` | Model name in LM Studio | `lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF` |
| `JWT_SECRET` | Secret for signing JWT tokens | ⚠️ **Change this** |
| `POSTGRES_DSN` | PostgreSQL async DSN | `postgresql+asyncpg://nia:nia@postgres:5432/nia` |
| `REDIS_URL` | Redis URL | `redis://redis:6379/0` |
| `QDRANT_URL` | Qdrant HTTP URL | `http://qdrant:6333` |
| `STRIPE_SECRET_KEY` | Stripe API key (checkout) | — |
| `TEAMS_WEBHOOK_URL` | MS Teams incoming webhook (handoff) | — |
| `GCP_PROJECT_ID` | GCP project (Vertex AI, production) | — |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP SA key JSON | — |

---

## Project Structure

```
nia/
├── docker-compose.yml          # 13-service local dev stack
├── .env.example                # All environment variables
├── Makefile                    # Developer shortcuts
├── pytest.ini                  # Python test configuration
├── conftest.py                 # Shared pytest fixtures
│
├── shared/                     # Shared Python library (all services)
│   ├── config/base.py          # BaseServiceSettings, ModelProvider enum
│   ├── db/connection.py        # Async SQLAlchemy engine + session
│   ├── db/redis_client.py      # Redis client + RedisKeys namespace
│   ├── security/jwt.py         # JWT create/verify (widget + admin)
│   ├── security/tenant.py      # TenantContextMiddleware
│   ├── models/domain.py        # Shared Pydantic DTOs
│   └── utils/                  # logging, responses, sanitizer
│
├── services/
│   ├── model-adapter/          # LLM provider abstraction (port 8005)
│   ├── tenant-manager/         # Tenant CRUD + provisioning (port 8003)
│   ├── rag-service/            # RAG ingest + query pipeline (port 8002)
│   ├── recommender/            # Multi-criteria scoring engine (port 8004)
│   ├── orchestrator/           # FSM conversation engine (port 8001)
│   ├── checkout/               # Stripe payment sessions (port 8006)
│   ├── handoff/                # Teams bot→human handoff (port 8007)
│   ├── transcript/             # Message persistence (port 8008)
│   └── fallback/               # Emergency fallback responses (port 8009)
│
├── packages/
│   └── widget/                 # Preact embeddable widget (~3KB)
│       ├── src/embed.tsx       # Entry point — Shadow DOM mount
│       ├── src/components/     # Widget, MessageList, InputBar, etc.
│       ├── src/hooks/          # useChat hook
│       ├── src/api/client.ts   # HTTP/WS client
│       └── src/styles/         # widget.css (Shadow DOM scoped)
│
├── infra/
│   ├── traefik/traefik.yml     # Reverse proxy config
│   └── db/
│       ├── init/01_init.sql    # PostgreSQL extensions + public schema
│       └── migrations/         # Alembic async migrations
│           ├── env.py
│           ├── alembic.ini
│           └── versions/0001_initial_schema.py
│
├── data/seed/
│   ├── tenants/demo_tenant.json
│   ├── products/demo_products.json
│   └── knowledge/demo_knowledge.json
│
├── scripts/
│   └── seed.sh                 # Seeds data via service APIs
│
├── stubs/
│   └── teams/server.js         # Local Teams webhook simulator
│
└── docs/
    ├── 00_resumen_ejecutivo.md
    ├── 01_contexto_y_objetivos.md
    ├── 02_arquitectura.md
    ├── 03_datos_y_seguridad.md
    └── 04_operaciones_y_roadmap.md
```

---

## Make Targets

```bash
make dev            # Start Docker Compose stack
make down           # Stop all containers
make logs           # Tail all service logs
make logs-rag       # Tail logs for a specific service

make migrate        # Alembic upgrade head
make seed           # Load demo tenant, products & knowledge

make test           # Run all tests
make test-py        # Python tests only (pytest)
make test-widget    # Widget tests only (vitest)

make lint           # Ruff (Python) + tsc (TypeScript)
make build          # Build widget bundle → dist/

make install        # npm install + pip install -e shared/
make clean          # Remove build artefacts

make shell-db       # psql inside postgres container
make shell-redis    # redis-cli inside redis container
```

---

## LLM Providers

NIA abstracts the LLM provider behind `ModelProvider` enum. Switch at runtime with `MODEL_PROVIDER` env var — no code changes required.

| Provider | Env | Notes |
|----------|-----|-------|
| `lmstudio` | `MODEL_PROVIDER=lmstudio` | Local dev. Requires LM Studio running on host port 1234. |
| `vertexai` | `MODEL_PROVIDER=vertexai` | Production. Requires `GCP_PROJECT_ID` + `GOOGLE_APPLICATION_CREDENTIALS`. Uses Gemini Flash. |
| `openai` | `MODEL_PROVIDER=openai` | Requires `OPENAI_API_KEY`. |

---

## Multi-Tenancy

Each tenant gets:
- A dedicated **PostgreSQL schema** (`tenant_<id>`) with Row Level Security
- A dedicated **Qdrant collection** (`<id>_docs`) for their knowledge base
- A **Redis namespace** (`nia:tenant:<id>:*`) for session state & caching
- Scoped **JWT tokens** (`tenant_id` claim validated on every request)
- Custom **branding** (color, logo, welcome message) served to their widget embed

Tenant provisioning is atomic: if any step fails the whole provisioning rolls back.

---

## FSM Conversation States

```
IDLE → GREETING → DISCOVERY → RECOMMENDATION → CHECKOUT → CONFIRMED
                                                         ↘ DISCOVERY (payment failed)
         any state → HANDOFF → RESOLVED
```

---

## Adding a New Service

1. Copy an existing service directory (e.g. `services/fallback/`)
2. Update `docker-compose.yml` with new service + port
3. Add to `infra/traefik/traefik.yml` routing rules
4. Share `shared/` library via `COPY ../../shared /app/shared` in `Dockerfile.dev`
5. Subclass `BaseServiceSettings` for new config vars

---

## Production Deployment (GCP)

See `docs/04_operaciones_y_roadmap.md` for the full Cloud Run + Cloud SQL + Vertex AI Vector Search deployment guide.

---

## License

Proprietary — © 2024 NIA SaaS. All rights reserved.
