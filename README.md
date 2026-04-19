# NIA — Nodo de Inteligencia Activa

> Plataforma conversacional con IA que permite a cualquier negocio desplegar un asistente virtual inteligente, personalizable y multi-canal, gestionado desde un panel de administración visual.

---

## Visión del Producto

NIA es una plataforma que resuelve un problema concreto: **un negocio necesita un asistente virtual que entienda su dominio, responda con su tono, venda sus productos, escale a humanos cuando corresponda, y se gestione sin tocar código.**

El sistema está diseñado para que múltiples negocios (tenants) convivan en la misma plataforma, cada uno con su propia identidad, conocimiento, flujo conversacional y canales de contacto.

---

## ¿Qué Hace NIA? — Descripción Funcional

### El Problema

Un negocio quiere ofrecer atención automatizada a sus clientes a través de su web, Telegram, o un sistema de soporte como Chatwoot. Pero necesita que el bot:

1. **Sepa de qué habla** — conozca los productos, servicios, preguntas frecuentes y políticas del negocio
2. **Hable con la voz de la marca** — tono, idioma, estilo y personalidad configurables
3. **Guíe la conversación** — no sea un simple Q&A, sino que siga un flujo lógico (saludo → descubrimiento → recomendación → compra)
4. **Sepa cuándo pedir ayuda** — escale a un agente humano cuando el usuario lo pida o la IA no pueda resolver
5. **Capture leads** — recoja datos de contacto cuando sea natural en la conversación
6. **Venda** — pueda generar un enlace de pago cuando el usuario esté listo para comprar
7. **Se gestione visualmente** — sin necesidad de programar ni entender la IA por dentro

### Actores del Sistema

| Actor | Quién es | Qué hace en NIA |
|-------|----------|------------------|
| **Usuario final** | Cliente o visitante del negocio | Conversa con el asistente a través del widget web, Telegram o Chatwoot |
| **Administrador del negocio** | Dueño, gerente o equipo de marketing | Configura su asistente desde el panel: personalidad, flujo, conocimiento, canales, productos |
| **Agente humano** | Equipo de soporte del negocio | Recibe conversaciones escaladas en Teams o Chatwoot, responde al usuario a través del bot |
| **Superadmin de plataforma** | Operador de NIA | Crea y gestiona los tenants (negocios), monitorea la salud de la plataforma |

### Experiencia del Usuario Final

El usuario final interactúa con NIA a través de **tres canales posibles**:

1. **Widget web** — Un botón flotante en la web del negocio que abre un chat. Se incrusta con una línea de código. Tiene la marca del negocio (colores, logo, mensaje de bienvenida). Ofrece botones de respuesta rápida para guiar al usuario.

2. **Telegram** — Un bot de Telegram vinculado al negocio. El usuario escribe como en cualquier chat. Comandos especiales permiten cambiar de tenant o reiniciar la conversación.

3. **Chatwoot** — Integración con la plataforma de soporte Chatwoot. Los mensajes del usuario llegan al bot automáticamente; si escala, el agente humano continúa en el mismo hilo.

**Flujo típico de una conversación:**

```
Usuario abre el chat
    ↓
Bot saluda con el mensaje de bienvenida del negocio
    ↓
Usuario hace una pregunta o expresa una necesidad
    ↓
Bot identifica la intención (FAQ, buscar producto, querer comprar, hablar con humano…)
    ↓
Según la intención y el estado actual de la conversación:
    ├── Responde con información del knowledge base (FAQ)
    ├── Recomienda productos relevantes del catálogo
    ├── Genera un enlace de pago (checkout)
    ├── Escala a un agente humano (handoff a Teams o Chatwoot)
    └── Responde con un mensaje de cortesía si no entiende
    ↓
La conversación continúa hasta que el usuario resuelve su necesidad
    ↓
El transcript completo queda guardado (con datos de lead si se capturaron)
```

### Experiencia del Administrador del Negocio

El administrador gestiona todo desde un **panel web visual** (dashboard). No necesita conocimientos técnicos.

#### Panel de Configuración

El administrador puede personalizar:

- **Identidad del asistente** — nombre, personalidad, tono de voz (ej: "Eres Sofía, asesora de viajes amable y entusiasta")
- **Modelo de IA** — qué modelo de lenguaje usa, qué tan creativo o conservador es (temperatura)
- **Mensaje de bienvenida** — lo primero que ve el usuario al abrir el chat
- **Preguntas sugeridas** — botones que aparecen al inicio para guiar al usuario
- **Colores y marca** — color primario del widget, logo, nombre visible

#### Editor Visual de Flujo Conversacional

Esta es la pieza central del panel. Un **editor visual de nodos y conexiones** donde el administrador define:

- **Estados** — los momentos de la conversación (Saludo, Descubrimiento, Recomendación, Checkout, Handoff, etc.)
- **Intenciones** — lo que el usuario puede querer en cada momento (preguntar FAQ, pedir recomendación, querer comprar, hablar con humano)
- **Transiciones** — las reglas: "Si el usuario está en Descubrimiento y su intención es comprar → ejecutar la acción de checkout y mover a estado Checkout"
- **Acciones** — qué hace el bot en cada transición (responder con FAQ, recomendar productos, generar pago, escalar a humano)
- **Mensajes estáticos** — respuestas fijas para ciertas transiciones (ej: "Enseguida te conecto con un agente")
- **Respuestas rápidas** — botones sugeridos que aparecen después de cada respuesta del bot

El editor muestra los estados como tarjetas arrastrables y las transiciones como flechas de colores entre ellas. Se puede hacer click en cualquier flecha para editarla. Los cambios se ven en tiempo real en el canvas.

#### Gestión del Conocimiento (Knowledge Base)

El administrador sube documentos (Markdown, texto, JSON) que contienen el conocimiento del negocio:

- Descripción de servicios y productos
- Preguntas frecuentes
- Políticas (devoluciones, horarios, precios)
- Guías y tutoriales

NIA procesa estos documentos, los divide en fragmentos y los indexa en un buscador semántico. Cuando un usuario hace una pregunta de FAQ, el bot busca en estos documentos la información más relevante y genera una respuesta natural basada en ellos.

#### Configuración de Habilidades (Skills)

Cada habilidad del bot se configura por separado:

- **FAQ / RAG** — cuántos fragmentos buscar, qué tan relevantes deben ser
- **Recomendador** — filtros por categoría, rango de precios, número máximo de productos
- **Checkout** — moneda, tiempo de expiración del enlace de pago
- **Personalidades conversacionales** — prompts específicos por habilidad (ej: el recomendador puede ser más persuasivo que el FAQ)

#### Gestión de Canales

El administrador activa y configura los canales de comunicación:

- **Widget web** — obtiene el código para incrustar en su sitio
- **Telegram** — introduce el token de su bot de Telegram
- **Chatwoot** — configura la conexión con su instancia de Chatwoot

#### Analíticas

El panel muestra métricas de uso:

- Número de conversaciones por período
- Distribución de intenciones (qué preguntan más los usuarios)
- Tiempos de respuesta
- Tasa de resolución vs. escalamiento a humano

#### Consola de Depuración

Una herramienta para probar el bot en tiempo real desde el propio panel. El administrador puede chatear con su asistente y ver las respuestas tal como las vería un usuario final.

### Experiencia del Agente Humano (Handoff)

Cuando el bot detecta que necesita ayuda humana (el usuario lo pide o la IA no puede resolver):

1. **En Microsoft Teams** — el agente recibe una tarjeta con el contexto de la conversación (quién es el usuario, qué preguntó, historial). Responde directamente en Teams y el mensaje llega al usuario a través del chat original.

2. **En Chatwoot** — la conversación aparece en el inbox del agente en Chatwoot. El agente responde desde la interfaz de Chatwoot como con cualquier otro ticket.

En ambos casos:
- El bot se pausa mientras el humano atiende
- Si el agente no responde en un tiempo configurable, el bot retoma la conversación
- El historial completo (bot + humano) queda en el transcript

### Multi-Tenancy — Múltiples Negocios en Una Plataforma

NIA está diseñada para operar como SaaS. Cada negocio (tenant) tiene:

- Su propia **identidad y marca**
- Su propio **knowledge base** (documentos)
- Su propio **catálogo de productos**
- Su propio **flujo conversacional** (estados, intenciones, transiciones)
- Sus propios **canales** configurados
- Sus propias **configuraciones de IA** (modelo, temperatura, prompts)
- Sus propias **analíticas**
- **Aislamiento total** — un tenant nunca ve datos de otro

El superadmin puede crear tantos tenants como necesite desde el panel.

### Capacidades Funcionales — Resumen

| Capacidad | Descripción |
|-----------|-------------|
| **Conversación guiada por flujo** | El bot sigue un grafo de estados y transiciones, no improvisa |
| **Comprensión de lenguaje natural** | Usa LLMs para clasificar intenciones y generar respuestas |
| **Base de conocimiento** | Responde FAQ basándose en documentos reales del negocio (RAG) |
| **Recomendación de productos** | Sugiere productos del catálogo según lo que el usuario busca |
| **Pagos** | Genera enlaces de pago (Stripe) cuando el usuario quiere comprar |
| **Escalamiento a humanos** | Transfiere a un agente en Teams o Chatwoot cuando es necesario |
| **Captura de leads** | Recoge nombre, email, teléfono cuando es natural en la conversación |
| **Multi-canal** | Mismo bot disponible en widget web, Telegram y Chatwoot |
| **Multi-tenant** | Múltiples negocios en la misma plataforma, totalmente aislados |
| **Personalización visual** | Colores, logo, mensajes, tono de voz — todo configurable sin código |
| **Editor visual de flujos** | Drag & drop para diseñar el flujo conversacional |
| **Analíticas** | Métricas de uso, intenciones, tiempos de respuesta |
| **Transcripts** | Historial completo de cada conversación guardado |
| **Testing automatizado** | Framework para probar conversaciones y optimizar prompts automáticamente |

---

## Table of Contents — Documentación Técnica

- [Architecture](#architecture)
- [Service Map](#service-map)
- [Admin Dashboard — Technical Details](#admin-dashboard--technical-details)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Multi-Tenancy — Technical](#multi-tenancy--technical)
- [FSM Conversation Flow — Technical](#fsm-conversation-flow--technical)
- [LLM Providers](#llm-providers)
- [Channels — Technical](#channels--technical)
- [Conversation Testing Framework](#conversation-testing-framework)
- [Make Targets](#make-targets)
- [API & Postman](#api--postman)
- [Extending NIA](#extending-nia)
- [License](#license)

---

## Architecture

NIA is a monorepo of independent microservices + a Next.js admin dashboard, organized in five layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│  ADMIN UI  (Next.js 15, port 3001)                                     │
│  🎛️  Dashboard · Tenant config · Visual flow editor · Analytics        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │  REST API
┌────────────────────────────────────▼───────────────────────────────────┐
│  CHANNELS  (user-facing adapters)                                      │
│  ✈️  Telegram Gateway (8010)  ·  🌐 Widget JS (Preact, port 3000)     │
│  💬 Chatwoot (via Handoff webhooks)                                    │
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
            ├── 🤝 Handoff    (8007)  ← bot→human via Teams + Chatwoot
            └── 📝 Transcript (8008)  ← message persistence in PostgreSQL
```

---

## Service Map

| Layer | Service | Port | Role |
|-------|---------|------|------|
| **Admin** | Dashboard (Next.js) | 3001 | Visual tenant management, flow editor, analytics |
| **Core** | Orchestrator | 8001 | Central FSM — intent detection, session management, skill routing |
| **Core** | Tenant Manager | 8003 | Tenant CRUD, per-tenant config (AI/FSM/channels/skills), JWT issuance |
| **Core** | Model Adapter | 8005 | Unified LLM API — chat completions + embeddings, provider-agnostic |
| **Essential Infra** | Handoff | 8007 | Bot→human transfer — Teams Adaptive Cards + Chatwoot webhooks |
| **Essential Infra** | Transcript | 8008 | Message & lead persistence in PostgreSQL, email export |
| **Skill** | RAG Service | 8002 | Document ingestion (MD/TXT/JSON) + RAG query pipeline |
| **Skill** | Recommender | 8004 | Intent-driven product recommendations from PostgreSQL catalogue |
| **Skill** | Checkout | 8006 | Booking intents + Stripe Checkout sessions |
| **Skill** | Fallback | 8009 | Emergency graceful-error responses |
| **Channel** | Telegram Gateway | 8010 | Telegram Bot adapter — multi-tenant, `/tenant`, `/reset` commands |
| **Channel** | Widget | 3000 | Preact embeddable widget, Shadow DOM, hot-reload dev server |
| **Channel** | Chatwoot | — | Inbound via webhook on Handoff service (`/webhooks/chatwoot/{tenant_id}`) |

### Data Stores

| Store | Used for |
|-------|----------|
| **PostgreSQL 16** | Tenant config, products, conversations, leads, booking intents (per-tenant schema + RLS) |
| **Redis 7** | Session state, tenant config cache, handoff locks, Telegram tenant preferences |
| **Qdrant** | Per-tenant vector collections (`{tenant_id}_docs`) for RAG |

---

## Admin Dashboard — Technical Details

The admin dashboard is a full-featured **Next.js 15 App Router** application (`apps/admin/`, port 3001) built with:

- **React 19** + **TypeScript**
- **shadcn/ui** component library (Radix primitives + Tailwind CSS)
- **TanStack Query** for data fetching + cache
- **ReactFlow** for the visual conversation flow editor
- **Recharts** for analytics charts
- **NextAuth v5** for authentication
- Apple Human Interface Guidelines (HIG) inspired design system

### Dashboard Pages

| Page | Route | Description |
|------|-------|-------------|
| **Overview** | `/dashboard` | Tenant list with quick stats, create/delete tenants |
| **Configuration** | `/dashboard/tenants/[id]/config` | AI config (system prompt, model, temperature), UI config (branding, colors, welcome message), FSM settings, bot persona |
| **Conversation Flow** | `/dashboard/tenants/[id]/fsm` | Visual drag-and-drop flow editor with ReactFlow — custom nodes (state cards), custom edges (color-coded by action, parallel offset), slide-in panel for editing transitions, live preview, intent & state CRUD |
| **Skills** | `/dashboard/tenants/[id]/skills` | Per-skill configuration (RAG top_k, recommender filters, checkout currency, custom conversational personas) |
| **Knowledge** | `/dashboard/tenants/[id]/knowledge` | RAG document management — upload, list, delete knowledge base files |
| **Channels** | `/dashboard/tenants/[id]/channels` | Channel configuration — Telegram bot token, Chatwoot settings, widget embed code |
| **Analytics** | `/dashboard/tenants/[id]/analytics` | Conversation metrics, intent distribution, response times, session charts |
| **Debug Console** | `/dashboard/tenants/[id]/debug` | Live chat testing against the bot, view raw orchestrator responses |

### Conversation Flow Editor Features

- **Custom state nodes** — clean Apple-style cards with 4 source + 4 target handles (hidden until hover)
- **Custom edges** — bezier curves colored by action type, perpendicular offset algorithm for parallel edges between same nodes
- **Slide-in panel** — 380px right panel for editing transitions (Route → When → Then → Bot Message → Quick Replies)
- **Live preview** — edge color and label update in real-time as you edit a transition
- **Wildcard support** — "★ Any State" node for global transitions
- **Ghost nodes** — states referenced in transitions but not yet created shown as dashed outlines
- **Layout persistence** — node positions and viewport saved to localStorage
- **Circular auto-layout** — intelligent initial positioning for new graphs

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Docker Desktop | ≥ 4.28 |
| Python | ≥ 3.12 |
| Node.js | ≥ 20 |
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

### 4. Start the admin dashboard

```bash
cd apps/admin && npm install && npm run dev
```

Open http://localhost:3001 — login with `admin@nia.local` / `changeme`.

### 5. Open interactive API docs

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
| Admin Dashboard | http://localhost:3001 |
| Traefik dashboard | http://localhost:8080 |
| Qdrant dashboard | http://localhost:6333/dashboard |

### 6. Widget demo page

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
├── apps/
│   └── admin/                # Next.js 15 admin dashboard (:3001)
│       ├── src/
│       │   ├── app/          # App Router pages
│       │   │   ├── (dashboard)/dashboard/
│       │   │   │   ├── page.tsx                    # Tenant overview
│       │   │   │   └── tenants/[tenantId]/
│       │   │   │       ├── config/page.tsx         # AI + UI + FSM config
│       │   │   │       ├── fsm/page.tsx            # Visual flow editor (ReactFlow)
│       │   │   │       ├── skills/page.tsx         # Skill configuration
│       │   │   │       ├── knowledge/page.tsx      # RAG document management
│       │   │   │       ├── channels/page.tsx       # Channel setup
│       │   │   │       ├── analytics/page.tsx      # Metrics & charts
│       │   │   │       └── debug/page.tsx          # Live debug console
│       │   │   ├── api/          # NextAuth API routes
│       │   │   └── login/        # Login page
│       │   ├── components/
│       │   │   ├── ui/           # shadcn/ui primitives (Button, Card, Select…)
│       │   │   └── layout/       # Sidebar, header
│       │   ├── hooks/            # use-api.ts (TanStack Query hooks for all APIs)
│       │   ├── lib/              # api.ts (typed client), utils.ts (ACTION_LABELS, colors)
│       │   └── middleware.ts     # Auth middleware
│       ├── package.json
│       ├── tailwind.config.js
│       └── next.config.js
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
├── services/                 # All microservices (flat layout)
│   │
│   │  ── Core ──────────────────────────────────────────────────────────
│   ├── orchestrator/         # FSM engine, intent detection, skill routing   :8001
│   ├── tenant-manager/       # Tenant CRUD, config, intents, transitions     :8003
│   ├── model-adapter/        # LLM provider abstraction (LMStudio/Vertex/OAI):8005
│   │
│   │  ── Essential Infrastructure ──────────────────────────────────────
│   ├── handoff/              # Bot→human handoff via Teams + Chatwoot        :8007
│   ├── transcript/           # Message & lead persistence, email export      :8008
│   │
│   │  ── Skills ─────────────────────────────────────────────────────────
│   ├── rag-service/          # Qdrant ingest + RAG query pipeline            :8002
│   ├── recommender/          # Intent-driven product recommendations         :8004
│   ├── checkout/             # Booking intents + Stripe Checkout sessions    :8006
│   ├── fallback/             # Emergency graceful-error responses            :8009
│   │
│   │  ── Channels ──────────────────────────────────────────────────────
│   └── telegram-gateway/     # Telegram Bot adapter, multi-tenant            :8010
│
├── packages/
│   └── widget/               # Preact embeddable chat widget (~3 KB gzip)
│       ├── src/embed.tsx     # Entry point — Shadow DOM mount
│       ├── src/components/   # Widget, MessageList, InputBar, LeadForm…
│       ├── src/hooks/        # useChat, useSession
│       └── src/api/          # HTTP client, JWT handling
│
├── tests/
│   └── conversation_testing/ # Automated conversation testing framework
│       ├── config.py         # Test configuration
│       ├── models.py         # Test models & schemas
│       ├── evaluators/       # LLM-based response evaluators
│       ├── scenarios/        # Test scenario definitions
│       ├── runners/          # Test execution engine
│       ├── auto_improvement/ # Automatic prompt optimization
│       ├── fixtures/         # Test data fixtures
│       ├── reports/          # Generated test reports
│       └── run_conversation_tests.py  # CLI entrypoint
│
├── infra/
│   ├── traefik/traefik.yml   # Reverse proxy routing rules
│   └── db/
│       ├── init/             # PostgreSQL init SQL (extensions, public schema)
│       ├── migrations/       # Alembic async migrations
│       └── seed/             # Database seed SQL
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
    └── NIA-Blueprint-Part*.md             # Architecture blueprints (5 parts)
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

### Admin Dashboard

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXTAUTH_SECRET` | NextAuth session signing secret | — |
| `NEXTAUTH_URL` | Public URL of admin app | `http://localhost:3001` |
| `NIA_API_URL` | Tenant Manager base URL | `http://localhost:8003` |

---

## Multi-Tenancy — Technical

Each tenant is fully isolated:

- **PostgreSQL schema** — `tenant_{id}` with Row Level Security
- **Qdrant collection** — `{tenant_id}_docs` for their knowledge base
- **Redis namespace** — `tenant:{id}:config`, `session:{tenant}:{session}`
- **Scoped JWTs** — `tenant_id` claim validated on every orchestrator request
- **Custom branding** — color, logo, welcome message, suggested questions
- **Custom AI config** — system prompt override, model, temperature, max tokens
- **Custom FSM** — intents, transitions and skill configs per tenant

### Default Tenants (seeded)

| Tenant ID | Description |
|-----------|-------------|
| `demo_turismo` | Tourism operator demo — activities, bookings, FAQ |
| `moda_imagen` | StyleSense fashion advisor — product catalog, style guide |

### Tenant Config Layers (all via API + Admin UI)

```
Tenant
  ├── ai_config         — system prompt, model, temperature
  ├── ui_config         — branding, welcome message, suggested questions
  ├── fsm_config        — timeouts, lead capture settings, discovery turns
  ├── intents[]         — intent definitions with LLM classification examples
  ├── transitions[]     — (intent, from_state) → (action, to_state, static_message?)
  ├── skill_configs{}   — per-skill params (rag top_k, recommender filters…)
  ├── teams_config      — handoff webhook, keywords, escalation settings
  ├── chatwoot_config   — Chatwoot base URL, API token, inbox ID, HMAC secret
  ├── telegram_config   — bot token, webhook secret
  ├── email_config      — SMTP, transcript auto-send
  └── payment_config    — Stripe currency, checkout expiry
```

---

## FSM Conversation Flow — Technical

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

All transitions are **fully configurable per tenant** via:
- **Admin Dashboard** → Conversation Flow visual editor (drag & drop)
- **API** → `PUT /api/tenants/{id}/transitions`

### Visual Flow Editor

The Conversation Flow page provides a full visual editor built with ReactFlow:

- Drag nodes to rearrange states
- Drag from handle to handle to create new transitions
- Click any edge to edit its route, intent trigger, action, bot prompt, and quick replies
- Color-coded edges show action type at a glance (green = FAQ, blue = recommend, purple = checkout…)
- Changes reflect live on the canvas before saving

---

## LLM Providers

Switch at runtime with `MODEL_PROVIDER` env var — no code changes required.

| Provider | Env value | Notes |
|----------|-----------|-------|
| LM Studio | `lmstudio` | Local dev. Requires LM Studio on host port 1234 |
| Vertex AI | `vertexai` | Production. Requires `VERTEX_AI_PROJECT` + service account |
| OpenAI | `openai` | Requires `OPENAI_API_KEY` |

---

## Channels — Technical

### Embeddable Widget

Preact-based chat widget (~3 KB gzip) that mounts inside a Shadow DOM:

```html
<script src="http://localhost:3000/nia-widget.js"
        data-tenant="demo_turismo"
        data-api="http://localhost:8001"></script>
```

Features: auto-JWT, lead capture form, suggested replies, typing indicator, markdown rendering, custom branding.

### Telegram

| Command | Action |
|---------|--------|
| `/start` | Welcome message for the active tenant |
| `/tenant` | Inline keyboard to switch between available tenants |
| `/tenant <id>` | Switch directly to a specific tenant |
| `/reset` | Clear session and start a new conversation |

Tenant preference persisted in Redis `tg_tenant_pref:{chat_id}` (TTL 30 days).

**Webhook registration:**

```bash
curl -X POST http://localhost:8010/setup/{tenant_id} \
  -H "Content-Type: application/json" \
  -d '{"public_url": "https://your-domain.com"}'
```

For local development, use the Cloudflare tunnel:

```bash
docker compose --profile dev up cloudflared
# Public URL appears in: docker compose logs cloudflared
```

### Chatwoot

NIA integrates with [Chatwoot](https://www.chatwoot.com/) as a channel via the Handoff service:

1. Configure `chatwoot_config` on the tenant (base URL, API token, inbox ID, HMAC secret)
2. Set the Chatwoot webhook URL to: `http://<handoff-host>:8007/webhooks/chatwoot/{tenant_id}`
3. Incoming Chatwoot messages are forwarded to the orchestrator; bot replies are sent back via Chatwoot API
4. HMAC-SHA256 signature verification on all webhook payloads

### Microsoft Teams

Bot→human handoff via Teams Adaptive Cards:

- Agent receives rich cards with conversation context
- Reply in Teams → message forwarded back to user
- Auto-close after configurable timeout
- Bot pause/resume during active handoff

---

## Conversation Testing Framework

Located in `tests/conversation_testing/`, this is an automated testing framework for validating bot conversations:

```bash
python tests/conversation_testing/run_conversation_tests.py
```

Features:

- **Scenario-based testing** — define multi-turn conversation flows with expected outcomes
- **LLM-based evaluation** — evaluators that use LLM to judge response quality, relevance, and tone
- **Auto-improvement** — `auto_improvement/auto_optimizer.py` automatically tunes prompts based on test failures
- **Reports** — generated test reports with pass/fail metrics
- **Configurable** — separate config for different tenants and environments

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

### Adding a New Skill

1. Copy `services/fallback/` as starting point
2. Implement `POST /v1/<skill>/...` with `app = FastAPI(description="**[Skill]** ...")`
3. Add to `docker-compose.yml` under the Skills section
4. Register the `action` name in orchestrator FSM
5. Add a transition via the Admin Dashboard flow editor or API

### Adding a New Channel

1. Copy `services/telegram-gateway/` as starting point
2. Ingest user messages → call `POST http://nia_orchestrator:8001/v1/chat` with a widget JWT
3. Add `app = FastAPI(description="**[Channel]** ...")`
4. Add to `docker-compose.yml` under the Channels section

### Adding an Admin Dashboard Page

1. Create a new page at `apps/admin/src/app/(dashboard)/dashboard/tenants/[tenantId]/<page>/page.tsx`
2. Add the route to `TENANT_NAV` in `apps/admin/src/components/layout/sidebar.tsx`
3. Add API hooks in `apps/admin/src/hooks/use-api.ts` if needed
4. Follow the Apple HIG design system: `rounded-xl`, `shadow-apple`, `border-slate-200`, primary `#007AFF`

---

## Tech Stack

### Backend (Python)

| Library | Purpose |
|---------|---------|
| FastAPI | HTTP framework for all microservices |
| SQLAlchemy 2.0 (async) | PostgreSQL ORM with per-tenant schemas |
| Pydantic v2 | Data validation & serialization |
| Redis (aioredis) | Session state, config cache, pub/sub |
| Qdrant Client | Vector store for RAG |
| LangChain | Document splitting for RAG ingestion |
| PyJWT | Token creation & verification |
| httpx | Async HTTP client (service-to-service) |
| Uvicorn | ASGI server |

### Frontend — Admin Dashboard (TypeScript)

| Library | Purpose |
|---------|---------|
| Next.js 15 | React framework (App Router) |
| React 19 | UI library |
| TanStack Query v5 | Data fetching, caching, mutations |
| TanStack Table v8 | Data tables |
| ReactFlow v11 | Visual flow diagram editor |
| Recharts v2 | Analytics charts |
| shadcn/ui | Component library (Radix + Tailwind) |
| NextAuth v5 | Authentication |
| Zustand v5 | Client state management |
| Zod | Schema validation |
| React Hook Form | Form management |

### Frontend — Widget (TypeScript)

| Library | Purpose |
|---------|---------|
| Preact | Lightweight UI (~3 KB) |
| Vite | Build tool & dev server |
| Shadow DOM | Style isolation |

### Infrastructure

| Tool | Purpose |
|------|---------|
| Docker Compose | Local dev orchestration |
| Traefik | Reverse proxy & routing |
| PostgreSQL 16 | Primary database |
| Redis 7 | Cache & session store |
| Qdrant | Vector database |
| Cloudflared | Dev tunnel for webhooks |

---

## License

Proprietary — © 2026 NIA Platform. All rights reserved.
