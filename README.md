# NIA — Nodo de Inteligencia Activa

> Multi-tenant conversational AI platform.  
> Embeddable widget · RAG knowledge base · FSM orchestration · Stripe checkout · Teams handoff · Telegram channel

---

## Architecture

NIA is a monorepo of independent microservices organized in four layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│  CHANNELS  (user-facing adapters)                                      │
│  ✈️  Telegram Gateway (8010)   ·   🌐 Widget JS (Preact, port 3000)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │  JWT + REST
┌───────────────────────────────────▼────────────────────────────────────┐
│  CORE                                                                  │
│  🧠 Orchestrator (8001)   ·   🏢 Tenant Manager (8003)                │
│  🤖 Model Adapter (8005)  ← LM Studio / Vertex AI / OpenAI            │
└───────┬────────────────────────────────────────────────────────────────┘
        │  Internal HTTP (service-to-service)
        │
        ├── SKILLS  (action handlers — invoked by orchestrator FSM)
        │   ├── 📚 RAG Service   (8002)  ← Qdrant vector store
        │   ├── 🛍️  Recommender  (8004)  ← PostgreSQL product catalogue
        │   ├── 💳 Checkout      (8006)  ← Stripe payments
        │   └── 🔄 Fallback      (8009)  ← graceful error responses
        │
        └── ESSENTIAL INFRASTRUCTURE  (always active)
            ├── 🤝 Handoff    (8007)  ← bot→human via Microsoft Teams
            └── 📝 Transcript (8008)  ← message persistence in PostgreSQL
```

### Service map

| Layer | Service | Port | Role |
|-------|---------|------|------|
| **Core** | Orchestrator | 8001 | Central FSM — intent detection, session management, skill routing |
| **Core** | Tenant Manager | 8003 | Tenant CRUD, per-tenant config (AI/FSM/channels/skills), JWT issuance |
| **Core** | Model Adapter | 8005 | Unified LLM API — chat completions + embeddings, provider-agnostic |
| **Essential Infra** | Handoff | 8007 | Bot→human transfer — Teams Adaptive Cards, bot pause/resume |
| **Essential Infra** | Transcript | 8008 | Message + lead persistence in PostgreSQL, email export |
| **Skill** | RAG Service | 8002 | Document ingestion (MD/TXT/JSON) + RAG query pipeline |
| **Skill** | Recommender | 8004 | Intent-driven product recommendations from PostgreSQL catalogue |
| **Skill** | Checkout | 8006 | Booking intents + Stripe Checkout sessions |
| **Skill** | Fallback | 8009 | Emergency graceful-error responses |
| **Channel** | Telegram Gateway | 8010 | Telegram Bot adapter — multi-tenant, `/tenant`, `/reset` commands |
| **Channel** | Widget | 3000 | Preact embeddable widget, Shadow DOM, hot-reload dev server |

### Data stores

| Store | Used for |
|-------|----------|
| **PostgreSQL 16** | Tenant config, products, conversations, leads, booking intents (per-tenant schema + RLS) |
| **Redis 7** | Session state, tenant config cache, handoff locks, Telegram tenant preferences |
| **Qdrant** | Per-tenant vector collections (`{tenant_id}_docs`) for RAG |

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | ≥ 4.28 |
| Python | ≥ 3.12 |
| Node.js | ≥ 20 (widget only) |
| LM Studio | any — optional, for local LLM |

### 1. Clone & configure

```bash
git clone https://github.com/bochetech/nia.git && cd nia
cp .env.example .env
# Set at minimum: JWT_SECRET (any random string)
```

### 2. Start the full stack

```bash
make dev
```

Builds and starts all services in Docker (~3 min on first run).

### 3. Run migrations & seed demo data

```bash
make migrate
make seed
```

Creates `demo_turismo` tenant, loads products and ingests the knowledge base into Qdrant.

### 4. Open interactive docs

| Service | Swagger UI |
|---------|-----------|
| Orchestrator | http://localhost:8001/docs |
| RAG Service | http://localhost:8002/docs |
| Tenant Manager | http://localhost:8003/docs |
| Recommender | http://localhost:8004/docs |
| Model Adapter | http://localhost:8005/docs |
| Checkout | http://localhost:8006/docs |
| Handoff | http://localhost:8007/docs |
| Transcript | http://localhost:8008/docs |
| Fallback | http://localhost:8009/docs |
| Telegram Gateway | http://localhost:8010/docs |
| Traefik dashboard | http://localhost:8080 |
| Qdrant dashboard | http://localhost:6333/dashboard |

### 5. Widget demo page

```bash
make demo        # serves demo.html at http://localhost:8088
```

---

## Project Structure

```
nia/
├── docker-compose.yml        # Full dev stack — all services + infra
├── .env.example              # All environment variables with defaults
├── Makefile                  # Developer shortcuts
├── pyproject.toml            # Python project config (shared lib)
├── conftest.py               # Shared pytest fixtures
│
├── shared/                   # Internal Python library (used by all services)
│   ├── config/base.py        # BaseServiceSettings
│   ├── db/connection.py      # Async SQLAlchemy engine + session factory
│   ├── db/redis_client.py    # Redis client + RedisKeys namespace
│   ├── models/domain.py      # Shared Pydantic DTOs and enums
│   ├── security/jwt.py       # JWT create/verify (widget + admin tokens)
│   ├── security/tenant.py    # TenantCtx dependency (extracts tenant from JWT)
│   └── utils/                # logging, responses, sanitizer, health router
│
├── services/                 # All microservices (flat layout — taxonomy via comments)
│   │
│   │  ── Core ──────────────────────────────────────────────────────────
│   ├── orchestrator/         # FSM engine, intent detection, skill routing   :8001
│   ├── tenant-manager/       # Tenant CRUD, config, intents, transitions      :8003
│   ├── model-adapter/        # LLM provider abstraction (LMStudio/Vertex/OAI) :8005
│   │
│   │  ── Essential Infrastructure ──────────────────────────────────────
│   ├── handoff/              # Bot→human handoff via Teams Adaptive Cards     :8007
│   ├── transcript/           # Message & lead persistence, email export        :8008
│   │
│   │  ── Skills ─────────────────────────────────────────────────────────
│   ├── rag-service/          # Qdrant ingest + RAG query pipeline              :8002
│   ├── recommender/          # Intent-driven product recommendations           :8004
│   ├── checkout/             # Booking intents + Stripe Checkout sessions      :8006
│   └── fallback/             # Emergency graceful-error responses              :8009
│
│   Note: Channels (Telegram Gateway, Widget) live in services/ and packages/widget/
│   Services are kept flat — taxonomy is expressed in docker-compose.yml comments,
│   FastAPI descriptions and the Postman collection.
│
├── packages/
│   └── widget/               # Preact embeddable chat widget (~3 KB gzip)
│       ├── src/embed.tsx     # Entry point — Shadow DOM mount
│       ├── src/components/   # Widget, MessageList, InputBar, LeadForm…
│       ├── src/hooks/        # useChat, useSession
│       └── src/api/          # HTTP client, JWT handling
│
├── infra/
│   ├── traefik/traefik.yml   # Reverse proxy routing rules
│   └── db/
│       ├── init/             # PostgreSQL init SQL (extensions, public schema)
│       └── migrations/       # Alembic async migrations
│
├── data/seed/                # Demo tenant, product and knowledge base files
│   ├── tenants/
│   ├── products/
│   └── knowledge/
│       ├── demo_turismo/     # Tourism knowledge base (MD files)
│       └── moda_imagen/      # StyleSense fashion knowledge base (MD files)
│
├── stubs/
│   └── teams/server.js       # Local Microsoft Teams webhook simulator
│
├── scripts/
│   └── seed.sh               # Seeds data through service APIs
│
└── docs/
    ├── NIA_Postman_Collection.json        # Import into Postman
    ├── NIA-Environment-Development.json   # Postman dev environment
    ├── NIA-Environment-Production.json    # Postman prod environment
    ├── openapi/                           # OpenAPI JSON specs (all 10 services)
    └── NIA-Blueprint-Part*.md             # Architecture blueprints
```

---

## Environment Variables

Copy `.env.example` → `.env` and adjust as needed.

### Core

| Variable | Description | Default |
|----------|-------------|---------|
| `ENV` | `development` \| `production` | `development` |
| `JWT_SECRET` | ⚠️ Secret for signing all JWT tokens — **must change** | — |
| `LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` | `INFO` |
| `JSON_LOGS` | Emit structured JSON logs | `false` |

### Databases

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_DSN` | Async PostgreSQL DSN | `postgresql+asyncpg://nia_user:nia_secret@postgres:5432/nia_dev` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `QDRANT_URL` | Qdrant HTTP URL | `http://qdrant:6333` |

### LLM Providers

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_PROVIDER` | `lmstudio` \| `vertexai` \| `openai` | `lmstudio` |
| `LM_STUDIO_BASE_URL` | LM Studio base URL | `http://host.docker.internal:1234` |
| `LM_STUDIO_CHAT_MODEL` | Chat model identifier in LM Studio | — |
| `LM_STUDIO_EMBED_MODEL` | Embedding model identifier | — |
| `VERTEX_AI_PROJECT` | GCP project ID | — |
| `VERTEX_AI_LOCATION` | GCP region | `us-central1` |
| `VERTEX_AI_CHAT_MODEL` | Gemini model for chat | `gemini-1.5-flash` |
| `VERTEX_AI_EMBED_MODEL` | Vertex embedding model | `text-embedding-004` |
| `OPENAI_API_KEY` | OpenAI API key | — |

### Integrations

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe live/test secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_CURRENCY` | Payment currency (default: `clp`) |
| `TEAMS_WEBHOOK_URL` | Microsoft Teams incoming webhook URL |
| `TEAMS_TIMEOUT_MINUTES` | Auto-close handoff after N minutes (default: 15) |
| `TEAMS_MAX_WAIT_MINUTES` | Max time bot waits for agent before resuming (default: 5) |

---

## Multi-Tenancy

Each tenant is fully isolated:

- **PostgreSQL schema** — `tenant_{id}` with Row Level Security
- **Qdrant collection** — `{tenant_id}_docs` for their knowledge base
- **Redis namespace** — `tenant:{id}:config`, `session:{tenant}:{session}`
- **Scoped JWTs** — `tenant_id` claim validated on every orchestrator request
- **Custom branding** — color, logo, welcome message, suggested questions
- **Custom AI config** — system prompt override, model, temperature, max tokens
- **Custom FSM** — intents, transitions and skill configs per tenant

### Default tenants (seeded)

| Tenant ID | Description |
|-----------|-------------|
| `demo_turismo` | Tourism operator demo — activities, bookings, FAQ |
| `moda_imagen` | StyleSense fashion advisor — product catalog, style guide |

### Tenant config layers (all via API)

```
Tenant
  ├── ai_config         — system prompt, model, temperature
  ├── ui_config         — branding, welcome message, suggested questions
  ├── fsm_config        — timeouts, lead capture settings, discovery turns
  ├── intents[]         — intent definitions with LLM classification examples
  ├── transitions[]     — (intent, from_state) → (action, to_state, static_message?)
  ├── skill_configs{}   — per-skill params (rag top_k, recommender filters…)
  ├── teams_config      — handoff webhook, keywords, escalation settings
  ├── telegram_config   — bot token, webhook secret
  ├── email_config      — SMTP, transcript auto-send
  └── payment_config    — Stripe currency, checkout expiry
```

---

## FSM Conversation States

```
IDLE
  └─▶ GREETING       (on first message)
        └─▶ DISCOVERY      (collecting context)
              ├─▶ FAQ_ANSWER       (faq action → RAG Service)
              ├─▶ RECOMMENDATION   (recommend action → Recommender)
              │     └─▶ CHECKOUT   (checkout action → Stripe)
              │           └─▶ CONFIRMED
              └─▶ HANDOFF    (human_request → Handoff service)
                    └─▶ RESOLVED

  Any state ──▶ IDLE  (out_of_scope → static_reply)
```

All transitions are **fully configurable per tenant** via `PUT /api/tenants/{id}/transitions`.

---

## LLM Providers

Switch at runtime with `MODEL_PROVIDER` env var — no code changes required.

| Provider | Env value | Notes |
|----------|-----------|-------|
| LM Studio | `lmstudio` | Local dev. Requires LM Studio on host port 1234 |
| Vertex AI | `vertexai` | Production. Requires `VERTEX_AI_PROJECT` + service account |
| OpenAI | `openai` | Requires `OPENAI_API_KEY` |

---

## Telegram Channel

### Bot commands

| Command | Action |
|---------|--------|
| `/start` | Welcome message for the active tenant |
| `/tenant` | Inline keyboard to switch between available tenants |
| `/tenant <id>` | Switch directly to a specific tenant |
| `/reset` | Clear session and start a new conversation |

Tenant preference persisted in Redis `tg_tenant_pref:{chat_id}` (TTL 30 days).

### Webhook registration

```bash
curl -X POST http://localhost:8010/setup/{tenant_id} \
  -H "Content-Type: application/json" \
  -d '{"public_url": "https://your-domain.com"}'
```

For local development, use the Cloudflare tunnel profile:

```bash
docker compose --profile dev up cloudflared
# Public URL appears in: docker compose logs cloudflared
```

---

## Make Targets

```bash
make dev              # Build & start full Docker Compose stack
make down             # Stop all containers
make logs             # Tail logs from all services
make logs-<service>   # Tail logs for one service  e.g. make logs-orchestrator
make demo             # Start widget demo page → http://localhost:8088

make migrate          # Run Alembic DB migrations (upgrade head)
make seed             # Seed demo tenant, products & knowledge base

make test             # Run all tests (Python + Widget)
make test-py          # Python tests only (pytest)
make test-widget      # Widget tests only (vitest)

make lint             # Ruff (Python) + tsc (TypeScript)
make build            # Build widget bundle → packages/widget/dist/
make install          # npm install + pip install -e shared/
make clean            # Remove build artefacts

make shell-db         # psql inside postgres container
make shell-redis      # redis-cli inside redis container
```

---

## API & Postman

All services expose Swagger UI at `/docs` and OpenAPI JSON at `/openapi.json`.

Pre-generated OpenAPI specs for all 10 services are in `docs/openapi/`.

**Import into Postman:**
1. `docs/NIA_Postman_Collection.json` — full collection organized by taxonomy layer
2. `docs/NIA-Environment-Development.json` — sets all base URLs to `localhost`

Default credentials: `admin@nia.local` / `changeme`

---

## Extending NIA

### Adding a new Skill

1. Copy `services/fallback/` as starting point
2. Implement `POST /v1/<skill>/...` with `app = FastAPI(description="**[Skill]** ...")`
3. Add to `docker-compose.yml` under the Skills section
4. Register the `action` name in orchestrator FSM
5. Add a transition: `PUT /api/tenants/{id}/transitions` with `"action": "<skill>"`

### Adding a new Channel

1. Copy `services/telegram-gateway/` as starting point
2. Ingest user messages → call `POST http://nia_orchestrator:8001/v1/chat` with a widget JWT
3. Add `app = FastAPI(description="**[Channel]** ...")` 
4. Add to `docker-compose.yml` under the Channels section

---

## License

Proprietary — © 2026 NIA Platform. All rights reserved.
