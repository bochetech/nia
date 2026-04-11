# NIA — Nodo de Inteligencia Activa para Turismo SaaS
## Blueprint Técnico Completo — Parte 2 de 5
**Versión:** 1.0.0 · **Fecha:** Abril 2026

---

# SECCIÓN 4 — Dominios y Microservicios Propuestos

## 4.1 Principios de Descomposición

Se aplica **decomposición por bounded context** (DDD), no por capas técnicas. Cada servicio tiene responsabilidad única, base de datos propia (o schema separado en el monorepo de DB) y se comunica vía API REST o eventos Pub/Sub. No se sobreingenierea: en MVP, Orchestrator y Checkout pueden ser un mismo proceso, separándose en fase 2.

---

## 4.2 Catálogo de Microservicios

### MS-01: Tenant Manager Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Gestión del ciclo de vida de tenants: onboarding, configuración, branding, límites y claves API |
| **Inputs** | Solicitudes CRUD de tenants vía Admin API; eventos de onboarding |
| **Outputs** | TenantContext (cacheado en Redis); configuraciones de widget; branding tokens |
| **APIs expuestas** | `POST /tenants`, `GET /tenants/{id}`, `PATCH /tenants/{id}/config`, `GET /tenants/{id}/widget-config` |
| **Eventos publicados** | `tenant.created`, `tenant.config_updated`, `tenant.suspended` |
| **Base de datos** | PostgreSQL (schema `tenant_mgmt`) + Redis (cache de config por TTL 5min) |
| **Dependencias** | Secret Manager (API keys), PostgreSQL, Redis |
| **Escalabilidad** | Stateless, múltiples réplicas. Config cacheada → baja carga DB. Cloud Run mínimo 1 instancia activa |
| **Tecnología** | Python 3.12 + FastAPI |

---

### MS-02: Conversation Orchestrator Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Motor central de orquestación: gestión de estado conversacional (FSM), routing de mensajes, coordinación entre RAG / Recommender / Checkout / Handoff |
| **Inputs** | Mensajes del widget (REST + WebSocket); eventos de Pub/Sub (handoff.resolved, payment.confirmed) |
| **Outputs** | Respuestas del bot (streaming SSE); actualizaciones de estado de sesión; leads capturados |
| **APIs expuestas** | `POST /conversations`, `POST /conversations/{id}/messages`, `GET /conversations/{id}`, `GET /conversations/{id}/state`, `POST /conversations/{id}/lead` |
| **Eventos publicados** | `conversation.started`, `conversation.message_received`, `conversation.ended`, `lead.captured`, `handoff.requested`, `fallback.detected` |
| **Base de datos** | Redis (session state + FSM), PostgreSQL (persistencia de sesiones cerradas) |
| **Dependencias** | Tenant Manager, RAG Service, Recommendation Engine, Checkout Service, Handoff Service, Model Provider Adapter |
| **Escalabilidad** | Horizontal vía Cloud Run. Sessions en Redis permiten cualquier instancia atender cualquier request. WebSocket via session affinity o Redis Pub/Sub relay |
| **Tecnología** | Python 3.12 + FastAPI + asyncio. FSM con `transitions` library |

**Diagrama de la FSM conversacional (simplificado):**
```
[IDLE] → lead_capture → [PRE_CHAT]
[PRE_CHAT] → lead_submitted → [GREETING]
[GREETING] → intent_detected → [DISCOVERY]
[DISCOVERY] → intent_clear → [RECOMMENDING]
[RECOMMENDING] → product_selected → [CHECKOUT_INIT]
[RECOMMENDING] → needs_clarification → [DISCOVERY]
[CHECKOUT_INIT] → details_confirmed → [AWAITING_PAYMENT]
[AWAITING_PAYMENT] → payment_confirmed → [CONFIRMED]
[AWAITING_PAYMENT] → payment_failed → [CHECKOUT_RETRY]
[*] → escalation_triggered → [HANDOFF_ACTIVE]
[HANDOFF_ACTIVE] → handoff_resolved → [previous_state]
[CONFIRMED] → post_chat → [CLOSED]
```

---

### MS-03: RAG Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Respuestas fundamentadas en documentos del tenant: retrieval, reranking, generación y validación de groundedness |
| **Inputs** | Query textual + tenant_id + contexto conversacional |
| **Outputs** | Respuesta generada + fragmentos fuente + score de confianza + metadatos de trazabilidad |
| **APIs expuestas** | `POST /query`, `POST /ingest`, `GET /collections/{tenant_id}`, `DELETE /collections/{tenant_id}/documents/{doc_id}` |
| **Eventos consumidos** | `catalog.ingested`, `knowledge.document_updated` |
| **Base de datos** | Qdrant (vectores por colección de tenant) + PostgreSQL (metadatos de documentos) + GCS (documentos fuente) |
| **Dependencias** | Model Provider Adapter (embeddings + generation), Qdrant, PostgreSQL, GCS |
| **Escalabilidad** | Stateless. Qdrant escala horizontal. Embeddings en batch para ingesta masiva |
| **Tecnología** | Python 3.12 + FastAPI + LangChain (solo para RAG pipeline, no para orquestación completa) |

---

### MS-04: Recommendation Engine

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Recibir intención del usuario y retornar productos rankeados, con validación de disponibilidad, idioma y capacidad en tiempo real |
| **Inputs** | Intent + entities (fecha, pax, actividad, presupuesto) + tenant_id |
| **Outputs** | Lista rankeada de productos con score, disponibilidad validada y razón de recomendación |
| **APIs expuestas** | `POST /recommend`, `POST /availability/validate`, `GET /products/{tenant_id}` |
| **Eventos publicados** | `recommendation.generated`, `availability.checked` |
| **Base de datos** | PostgreSQL (catálogo de productos), Redis (caché de disponibilidad 5min) |
| **Dependencias** | Tenant Manager, Availability Connector (externo), Model Provider Adapter (para señales semánticas opcionales) |
| **Escalabilidad** | Stateless, horizontal. Caché agresiva de disponibilidad para reducir llamadas externas |
| **Tecnología** | Python 3.12 + FastAPI + NumPy (scoring vectorial) |

---

### MS-05: Catalog Ingestion Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Recibir nuevos productos/experiencias vía webhook o API, validarlos, categorizarlos con IA y actualizarlos en base de datos y RAG |
| **Inputs** | Payload JSON de producto (webhook POST) o llamada directa API |
| **Outputs** | Producto categorizado y persistido; evento Pub/Sub; respuesta al sistema origen |
| **APIs expuestas** | `POST /catalog/ingest`, `POST /catalog/batch-ingest`, `GET /catalog/status/{job_id}` |
| **Eventos publicados** | `catalog.ingested`, `catalog.ingest_failed` |
| **Base de datos** | PostgreSQL (productos) + Cola: Pub/Sub para procesamiento async |
| **Dependencias** | Model Provider Adapter (categorización), RAG Service (actualizar embeddings), PostgreSQL |
| **Escalabilidad** | Procesamiento async vía Pub/Sub worker. Cloud Run Jobs para batch |
| **Tecnología** | Python 3.12 + FastAPI + pydantic (validación de schema) |

---

### MS-06: Checkout Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Gestionar el flujo transaccional: construcción de booking intent, sesión de checkout, integración con payment gateway y confirmación |
| **Inputs** | BookingIntent (producto, fechas, pax, datos de contacto) + tenant_id + session_id |
| **Outputs** | CheckoutSession con payment URL; confirmación de pago; número de reserva |
| **APIs expuestas** | `POST /checkout/sessions`, `GET /checkout/sessions/{id}`, `POST /checkout/sessions/{id}/confirm`, `POST /webhooks/payment` |
| **Eventos publicados** | `payment.initiated`, `payment.confirmed`, `payment.failed`, `booking.confirmed` |
| **Base de datos** | PostgreSQL (checkout_sessions, payment_attempts, bookings) |
| **Dependencias** | Payment Gateway (Stripe/Transbank), Orchestrator (notificación de estado), Email Service |
| **Escalabilidad** | Idempotencia en confirmación de pago (webhook puede llegar múltiple). Cloud Run |
| **Tecnología** | Python 3.12 + FastAPI. Idempotency keys en PostgreSQL |

---

### MS-07: Handoff Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Gestionar el escalado de sesión a agente humano: detección de trigger, creación de caso en Teams, relay bidireccional de mensajes, y resolución |
| **Inputs** | Trigger de escalación (tipo, razón, contexto de sesión) + mensajes del agente desde Teams |
| **Outputs** | Caso creado en Teams; mensajes del agente relayed al widget; estado de handoff |
| **APIs expuestas** | `POST /handoffs`, `GET /handoffs/{id}`, `POST /handoffs/{id}/resolve`, `POST /webhooks/teams` (incoming) |
| **Eventos publicados** | `handoff.escalated`, `handoff.agent_message`, `handoff.resolved`, `handoff.expired` |
| **Base de datos** | PostgreSQL (handoff_cases) + Redis (estado activo de handoff) |
| **Dependencias** | MS Teams Bot Framework / Graph API, Orchestrator (relay), Transcript Service |
| **Escalabilidad** | Concurrencia manejada por Redis locks. Expiración automática de handoffs sin respuesta |
| **Tecnología** | Python 3.12 + FastAPI |

---

### MS-08: Transcript Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Persistencia y exportación de transcripciones completas de conversación |
| **Inputs** | Evento `conversation.ended` con ID de sesión; solicitud de exportación del usuario |
| **Outputs** | Transcript formateado (JSON, HTML, PDF); email enviado al usuario |
| **APIs expuestas** | `GET /transcripts/{session_id}`, `POST /transcripts/{session_id}/export`, `GET /transcripts/{session_id}/download` |
| **Eventos consumidos** | `conversation.ended` |
| **Base de datos** | PostgreSQL (transcripts), GCS (archivos exportados) |
| **Dependencias** | Email Provider (Mailhog/SendGrid), GCS |
| **Tecnología** | Python 3.12 + FastAPI + WeasyPrint (PDF generation) |

---

### MS-09: Fallback Tracker Service

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Detectar, registrar y notificar queries que el sistema no pudo resolver satisfactoriamente |
| **Inputs** | Eventos `fallback.detected` + configuración de notificación del tenant |
| **Outputs** | Registro en DB; notificación periódica a canal Teams; reporte para análisis |
| **APIs expuestas** | `GET /fallbacks/{tenant_id}`, `POST /fallbacks/{tenant_id}/notify`, `PATCH /fallbacks/{id}/resolved` |
| **Eventos consumidos** | `fallback.detected` |
| **Base de datos** | PostgreSQL (fallback_queries) + BigQuery (análisis) |
| **Dependencias** | MS Teams (canal de notificación), BigQuery |
| **Tecnología** | Python 3.12 + FastAPI + Cloud Scheduler (notificaciones periódicas) |

---

### MS-10: Model Provider Adapter

(Descrito en detalle en Sección 0.6)

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Abstracción unificada de acceso a LLM y embeddings, con model routing y cost tracking |
| **Inputs** | Solicitudes de chat completion / embedding con task_type (simple/complex/transactional) |
| **Outputs** | Respuesta del modelo + tokens usados + latencia + proveedor usado |
| **APIs expuestas** | `POST /chat`, `POST /embed`, `POST /stream`, `GET /models`, `GET /usage/{tenant_id}` |
| **Eventos publicados** | `llm.call_completed` (con tokens, costo estimado, latencia) |
| **Base de datos** | Redis (caché semántica) + PostgreSQL (cost_usage_metrics) |
| **Dependencias** | LM Studio (dev) / Vertex AI (prod) |
| **Tecnología** | Python 3.12 + FastAPI |

---

### MS-11: FinOps & Observability Collector

| Atributo | Detalle |
|---|---|
| **Responsabilidad** | Agregar métricas de costo, uso de tokens, latencia y calidad de IA por tenant y por conversación |
| **Inputs** | Eventos `llm.call_completed`, `conversation.ended`, `recommendation.generated` |
| **Outputs** | Métricas en BigQuery; alertas cuando tenant supera umbral; dashboards Looker/Grafana |
| **Base de datos** | BigQuery (warehouse de costos y métricas) + Pub/Sub (streaming de eventos) |
| **Dependencias** | BigQuery, Cloud Monitoring, todos los servicios (via OTEL) |
| **Tecnología** | OpenTelemetry Collector + BigQuery + Cloud Monitoring |

---

# SECCIÓN 5 — Diseño Multi-Tenant

## 5.1 Estrategia de Aislamiento

**Decisión: Shared Database + Schema-per-Tenant + Row-Level Security (RLS)**

**Justificación:**
- **Database-per-tenant** fue descartado: costo de Cloud SQL por instancia es prohibitivo a escala de docenas/cientos de tenants. El management overhead (migraciones, monitoring) es cuadratico con el número de tenants.
- **Shared schema** puro fue descartado: RLS en PostgreSQL es robusto, pero sin aislamiento de schema el riesgo de cross-tenant leak en queries complejas es mayor y la auditoría más difícil.
- **Schema-per-tenant** es el equilibrio elegido: un schema `tenant_{id}` por cada tenant para tablas operacionales sensibles (sessions, transcripts, leads), y tablas globales con RLS para entidades compartidas (tenants, products, knowledge_sources). Una conexión de pool puede conectarse a cualquier schema con `SET search_path = tenant_{id}`.

**Para el Vector Store (Qdrant):** Colección dedicada por tenant: `{tenant_id}_knowledge`, `{tenant_id}_products`. El aislamiento es total a nivel de colección.

**Para Redis:** Namespacing por prefijo de clave: `tenant:{tenant_id}:session:{session_id}`.

---

## 5.2 Separación por Tenant

| Dimensión | Estrategia | Detalle |
|---|---|---|
| **Datos operacionales** | Schema PostgreSQL por tenant | `tenant_{id}.sessions`, `tenant_{id}.leads`, `tenant_{id}.transcripts` |
| **Catálogo de productos** | Schema + RLS | `products` con columna `tenant_id` + RLS policy `WHERE tenant_id = current_setting('app.tenant_id')` |
| **Conocimiento (RAG)** | Colección Qdrant por tenant | `{tenant_id}_knowledge` — completamente aislada |
| **Configuración** | Tabla `tenant_configs` con RLS | Branding tokens, lead fields, límites, conectores |
| **Branding** | JSON en `tenant_configs.ui_config` | Colors, logo URL, font, welcome message |
| **Conectores externos** | Tabla `tenant_connectors` cifrada | API keys de payment gateway, availability API, Teams config |
| **Caché Redis** | Prefijo `tenant:{id}:` | Session state, semantic cache, rate limit counters |
| **Secretos** | Secret Manager: `nia/{env}/tenant/{id}/{secret}` | Completamente segregados por path |
| **Logs** | Label `tenant_id` en Cloud Logging | Filtro y retención configurables por tenant |
| **Archivos fuente RAG** | GCS bucket: `nia-knowledge/{tenant_id}/` | IAM con Service Account por tenant si se requiere |

---

## 5.3 Onboarding de Nuevos Tenants

```
Proceso de Onboarding (automático vía API):

1. POST /api/v1/tenants
   └─► Crea registro en tabla `tenants`
   └─► Genera tenant_id (UUID v4)
   └─► Genera API key (256-bit random, almacenada en Secret Manager)

2. Provisioning automático (worker async vía Pub/Sub: tenant.created)
   └─► Crea schema PostgreSQL: CREATE SCHEMA tenant_{id}
   └─► Aplica migraciones del schema (tablas base)
   └─► Crea colecciones Qdrant: {id}_knowledge, {id}_products
   └─► Crea bucket GCS path: gs://nia-knowledge/{id}/
   └─► Configura RLS policies en tablas compartidas
   └─► Crea TenantConfig con valores por defecto
   └─► Carga dataset de conocimiento por defecto (si se provee)

3. POST /api/v1/tenants/{id}/config
   └─► Configura branding (colores, logo, fuente)
   └─► Configura campos de lead capture
   └─► Configura límites de tokens/conversación

4. POST /api/v1/tenants/{id}/knowledge/ingest
   └─► Ingesta documentos iniciales de conocimiento

5. Verificación
   └─► GET /api/v1/tenants/{id}/health
   └─► Retorna: DB ✅, VectorStore ✅, Config ✅, Widget ready ✅

Tiempo estimado de onboarding: < 2 minutos (Supuesto)
```

---

## 5.4 Versionado de Configuraciones

```sql
-- Tabla de historial de configuraciones
CREATE TABLE tenant_config_history (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    version      INTEGER NOT NULL,
    config_data  JSONB NOT NULL,
    changed_by   UUID,             -- admin user ID
    changed_at   TIMESTAMPTZ DEFAULT now(),
    change_reason TEXT,
    is_current   BOOLEAN DEFAULT false,
    UNIQUE(tenant_id, version)
);

-- La tabla tenant_configs siempre tiene el estado actual
-- tenant_config_history tiene el historial completo
-- Rollback: UPDATE tenant_configs + INSERT nuevo registro en history
```

**Versión actual siempre accesible en caché Redis.** Cambios de configuración invalidan el caché del tenant específico.

---

## 5.5 Límites de Personalización por Tenant

| Dimensión | Configurable | Límite mínimo | Límite máximo |
|---|---|---|---|
| Colores del widget | ✅ Primary, secondary, accent | — | — |
| Logo | ✅ URL | — | — |
| Fuente tipográfica | ✅ Google Fonts key | — | — |
| Mensaje de bienvenida | ✅ Multi-idioma | — | — |
| Campos de lead capture | ✅ Nombre, email, tel, custom | 0 campos | 8 campos |
| Idiomas soportados | ✅ Lista | 1 | 10 |
| Tokens por conversación | ✅ por plan | 2,000 | 50,000 |
| Conversaciones por mes | ✅ por plan | — | Según plan |
| Documentos RAG | ✅ por plan | 10 docs | 500 docs |
| Conectores externos | ✅ | — | Según plan |
| Flujo conversacional custom | ❌ | — | — |
| Sistema de prompts base | ❌ (modificable solo por NIA ops) | — | — |

---

## 5.6 Seguridad Multi-Tenant

- **Tenant context injection**: En cada request autenticado, el middleware extrae `tenant_id` del JWT y lo inyecta como parámetro de sesión PostgreSQL (`SET LOCAL app.tenant_id = '{id}'`). Las políticas RLS aplican automáticamente.
- **Cross-tenant validation**: Cada servicio valida explícitamente que los recursos solicitados pertenecen al tenant autenticado. No se confía solo en RLS como única defensa.
- **Colecciones Qdrant**: El servicio RAG solo acepta queries con `tenant_id` validado. No existe endpoint público de búsqueda cross-tenant.
- **Namespacing Redis**: Todos los patrones de clave incluyen `tenant:{id}:`. El código nunca usa claves sin prefijo de tenant.
- **Auditoría**: Toda acción administrativa sobre un tenant queda en `audit_events` con `tenant_id`, `actor_id`, `action`, `before`/`after` state.

---

# SECCIÓN 6 — Modelo de Datos

## 6.1 Entidades Principales

### Tenant

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(63) UNIQUE NOT NULL,  -- ej: "parque-andino"
    name            VARCHAR(255) NOT NULL,
    plan            VARCHAR(50) NOT NULL DEFAULT 'starter',  -- starter|professional|enterprise
    status          VARCHAR(20) NOT NULL DEFAULT 'provisioning', -- provisioning|active|suspended|deleted
    api_key_hash    VARCHAR(256) NOT NULL,  -- bcrypt hash; la clave real en Secret Manager
    timezone        VARCHAR(64) NOT NULL DEFAULT 'America/Santiago',
    default_language VARCHAR(10) NOT NULL DEFAULT 'es',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ,             -- soft delete
    metadata        JSONB DEFAULT '{}'
);
-- Propósito: Entidad raíz del sistema multi-tenant
-- Auditoría: updated_at actualizado por trigger; soft delete
```

### TenantConfig

```sql
CREATE TABLE tenant_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL DEFAULT 1,
    ui_config       JSONB NOT NULL DEFAULT '{}',
    -- ui_config: { primary_color, secondary_color, logo_url, font_family,
    --              welcome_message, chat_title, avatar_url }
    lead_config     JSONB NOT NULL DEFAULT '{}',
    -- lead_config: { enabled, fields: [{name, type, required, validation}],
    --               gdpr_consent_text }
    rag_config      JSONB NOT NULL DEFAULT '{}',
    -- rag_config: { confidence_threshold, max_tokens_response, fallback_message }
    limits_config   JSONB NOT NULL DEFAULT '{}',
    -- limits_config: { max_tokens_per_conversation, max_conversations_month,
    --                  max_docs, handoff_enabled }
    teams_config_id UUID REFERENCES teams_integration_configs(id),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id)
);
```

### KnowledgeSource

```sql
CREATE TABLE knowledge_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(255) NOT NULL,
    source_type     VARCHAR(50) NOT NULL,  -- pdf|markdown|url|faq|manual
    storage_path    TEXT,                  -- GCS path o URL
    status          VARCHAR(20) DEFAULT 'pending',  -- pending|processing|active|failed|outdated
    chunk_count     INTEGER DEFAULT 0,
    embedding_model VARCHAR(100),
    version         INTEGER DEFAULT 1,
    last_indexed_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    checksum        VARCHAR(64),           -- SHA-256 del contenido para detectar cambios
    metadata        JSONB DEFAULT '{}'
);
-- Relación: 1 tenant → N knowledge sources
-- Versionado: version++ en cada re-ingesta. Qdrant payload incluye source_id+version
```

### TourismProduct

```sql
CREATE TABLE tourism_products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    external_id     VARCHAR(255),          -- ID en sistema externo (PMS/CRS)
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    category        VARCHAR(100) NOT NULL, -- aventura|relax|gastronomia|cultural|naturaleza
    subcategory     VARCHAR(100),
    description     TEXT,
    short_desc      VARCHAR(500),
    base_price      NUMERIC(10,2),
    currency        VARCHAR(3) DEFAULT 'CLP',
    duration_minutes INTEGER,
    max_capacity    INTEGER,
    min_age         INTEGER,
    languages       VARCHAR(10)[] DEFAULT '{}',  -- ['es','en','pt']
    tags            TEXT[] DEFAULT '{}',
    images          JSONB DEFAULT '[]',
    status          VARCHAR(20) DEFAULT 'active',  -- active|inactive|draft
    ai_metadata     JSONB DEFAULT '{}',
    -- ai_metadata: { auto_categories, auto_tags, embedding_generated_at, categorization_model }
    availability_connector_ref VARCHAR(255), -- referencia al sistema de disponibilidad
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, slug)
);
```

### ExperienceMetadata

```sql
CREATE TABLE experience_metadata (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES tourism_products(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    difficulty_level VARCHAR(20),  -- easy|moderate|hard|extreme
    physical_requirements TEXT,
    included_items   TEXT[],
    excluded_items   TEXT[],
    meeting_point    TEXT,
    cancellation_policy VARCHAR(50),  -- flexible|moderate|strict
    cancellation_hours INTEGER DEFAULT 48,
    weather_dependent BOOLEAN DEFAULT false,
    min_group_size   INTEGER DEFAULT 1,
    recommended_ages VARCHAR(50),
    certifications   TEXT[],
    extra_attributes JSONB DEFAULT '{}'
);
```

### ConversationSession

```sql
CREATE TABLE conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    channel         VARCHAR(20) NOT NULL DEFAULT 'widget',  -- widget|api
    status          VARCHAR(30) NOT NULL DEFAULT 'active',
    -- active|pre_chat|greeting|discovery|recommending|checkout|confirmed|handoff|closed
    fsm_state       VARCHAR(50) NOT NULL DEFAULT 'idle',
    user_profile_id UUID REFERENCES user_profiles(id),
    lead_id         UUID REFERENCES leads(id),
    started_at      TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ,
    last_active_at  TIMESTAMPTZ DEFAULT now(),
    message_count   INTEGER DEFAULT 0,
    tokens_used     INTEGER DEFAULT 0,
    estimated_cost_usd NUMERIC(10,6) DEFAULT 0,
    page_url        TEXT,
    user_agent      TEXT,
    metadata        JSONB DEFAULT '{}'
);
```

### ConversationMessage

```sql
CREATE TABLE conversation_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES conversation_sessions(id),
    tenant_id       UUID NOT NULL,
    role            VARCHAR(10) NOT NULL,  -- user|assistant|system
    content         TEXT NOT NULL,
    tokens          INTEGER DEFAULT 0,
    rag_sources     JSONB DEFAULT '[]',    -- [{source_id, chunk_id, score, text_excerpt}]
    intent          VARCHAR(100),
    confidence      NUMERIC(4,3),
    recommendations JSONB DEFAULT '[]',   -- [{product_id, score, reason}]
    created_at      TIMESTAMPTZ DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);
```

### LeadCapture

```sql
CREATE TABLE leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    session_id      UUID REFERENCES conversation_sessions(id),
    name            VARCHAR(255),
    email           VARCHAR(255),
    phone           VARCHAR(30),
    custom_fields   JSONB DEFAULT '{}',
    gdpr_consent    BOOLEAN DEFAULT false,
    gdpr_consent_at TIMESTAMPTZ,
    source          VARCHAR(50) DEFAULT 'widget',
    status          VARCHAR(20) DEFAULT 'new',  -- new|contacted|converted|disqualified
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
-- PII: email y phone deben cifrarse a nivel de aplicación (AES-256)
-- o usar pgcrypto en PostgreSQL
```

### UserProfile

```sql
CREATE TABLE user_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    lead_id         UUID REFERENCES leads(id),
    session_count   INTEGER DEFAULT 1,
    last_seen_at    TIMESTAMPTZ DEFAULT now(),
    preferred_language VARCHAR(10),
    inferred_interests TEXT[],
    device_fingerprint VARCHAR(256),  -- hash, no PII directo
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### RecommendationContext

```sql
CREATE TABLE recommendation_contexts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES conversation_sessions(id),
    tenant_id       UUID NOT NULL,
    input_intent    VARCHAR(100),
    input_entities  JSONB NOT NULL DEFAULT '{}',
    -- {date, pax_count, activity_type, budget_range, language_preference, physical_level}
    products_evaluated INTEGER,
    products_available INTEGER,
    top_recommendations JSONB NOT NULL DEFAULT '[]',
    -- [{product_id, score, availability_status, rank_reason}]
    user_selected_id UUID REFERENCES tourism_products(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### AvailabilitySnapshot

```sql
CREATE TABLE availability_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    product_id      UUID NOT NULL REFERENCES tourism_products(id),
    check_date      DATE NOT NULL,
    checked_at      TIMESTAMPTZ DEFAULT now(),
    slots           JSONB NOT NULL DEFAULT '[]',
    -- [{time, available_spots, language, guide_name}]
    source          VARCHAR(50),  -- api|mock|manual
    ttl_seconds     INTEGER DEFAULT 300,
    is_stale        BOOLEAN DEFAULT false
);
```

### BookingIntent

```sql
CREATE TABLE booking_intents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL,
    tenant_id       UUID NOT NULL,
    product_id      UUID NOT NULL REFERENCES tourism_products(id),
    selected_date   DATE,
    selected_time   TIME,
    pax_count       INTEGER,
    contact_name    VARCHAR(255),
    contact_email   VARCHAR(255),
    contact_phone   VARCHAR(30),
    special_requests TEXT,
    total_amount    NUMERIC(10,2),
    currency        VARCHAR(3),
    status          VARCHAR(20) DEFAULT 'pending',  -- pending|confirmed|cancelled
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### CheckoutSession

```sql
CREATE TABLE checkout_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    booking_intent_id UUID NOT NULL REFERENCES booking_intents(id),
    session_id      UUID NOT NULL,
    payment_provider VARCHAR(50),  -- stripe|transbank|mercadopago
    provider_session_id VARCHAR(255),
    payment_url     TEXT,
    amount          NUMERIC(10,2),
    currency        VARCHAR(3),
    status          VARCHAR(20) DEFAULT 'created',
    -- created|pending|paid|failed|expired|refunded
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### PaymentAttempt

```sql
CREATE TABLE payment_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkout_session_id UUID NOT NULL REFERENCES checkout_sessions(id),
    tenant_id       UUID NOT NULL,
    attempt_number  INTEGER NOT NULL DEFAULT 1,
    provider_payment_id VARCHAR(255),
    status          VARCHAR(20),  -- pending|succeeded|failed
    amount          NUMERIC(10,2),
    currency        VARCHAR(3),
    error_code      VARCHAR(100),
    error_message   TEXT,
    raw_response    JSONB,        -- respuesta completa del proveedor (para debugging)
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### HandoffCase

```sql
CREATE TABLE handoff_cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    session_id      UUID NOT NULL REFERENCES conversation_sessions(id),
    trigger_type    VARCHAR(50) NOT NULL,  -- complaint|unresolved|explicit_request|timeout
    trigger_reason  TEXT,
    agent_teams_id  VARCHAR(255),          -- ID del agente asignado en Teams
    teams_thread_id VARCHAR(255),
    teams_channel_id VARCHAR(255),
    status          VARCHAR(20) DEFAULT 'pending',
    -- pending|assigned|active|resolved|expired
    context_summary TEXT,                 -- resumen de la conversación enviado al agente
    bot_paused_at   TIMESTAMPTZ DEFAULT now(),
    assigned_at     TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,          -- TTL de handoff activo (ej: 30min sin respuesta)
    resolution_notes TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### Transcript

```sql
CREATE TABLE transcripts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES conversation_sessions(id),
    tenant_id       UUID NOT NULL,
    format          VARCHAR(10) DEFAULT 'json',  -- json|html|pdf
    storage_path    TEXT,                        -- GCS path del archivo generado
    exported_to_email VARCHAR(255),
    exported_at     TIMESTAMPTZ,
    message_count   INTEGER,
    duration_seconds INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### FallbackQuery

```sql
CREATE TABLE fallback_queries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    session_id      UUID,
    query_text      TEXT NOT NULL,
    detected_at     TIMESTAMPTZ DEFAULT now(),
    fallback_reason VARCHAR(50),  -- low_confidence|out_of_domain|no_retrieval|timeout
    rag_score       NUMERIC(4,3),
    notified_at     TIMESTAMPTZ,   -- cuándo se notificó a Teams
    resolved        BOOLEAN DEFAULT false,
    resolution_type VARCHAR(50),   -- doc_added|prompt_updated|accepted_as_invalid
    resolved_at     TIMESTAMPTZ
);
```

### TeamsIntegrationConfig

```sql
CREATE TABLE teams_integration_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    bot_app_id      VARCHAR(255),
    bot_app_password_secret VARCHAR(255),  -- path en Secret Manager
    handoff_channel_id VARCHAR(255),
    fallback_channel_id VARCHAR(255),
    fallback_notify_frequency VARCHAR(20) DEFAULT 'daily',  -- realtime|daily|weekly
    handoff_enabled BOOLEAN DEFAULT true,
    fallback_notify_enabled BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id)
);
```

### AuditEvent

```sql
CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,
    actor_id        UUID,
    actor_type      VARCHAR(30),  -- admin_user|api_key|system
    action          VARCHAR(100) NOT NULL,  -- tenant.created, config.updated, etc.
    resource_type   VARCHAR(100),
    resource_id     UUID,
    before_state    JSONB,
    after_state     JSONB,
    ip_address      INET,
    user_agent      TEXT,
    occurred_at     TIMESTAMPTZ DEFAULT now(),
    metadata        JSONB DEFAULT '{}'
);
-- Tabla global, inmutable. No update ni delete. Solo insert.
-- Índices en: tenant_id, actor_id, action, occurred_at
```

### CostUsageMetric

```sql
CREATE TABLE cost_usage_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    session_id      UUID,
    service         VARCHAR(50) NOT NULL,  -- llm_chat|llm_embed|rag_retrieval
    model_used      VARCHAR(100),
    provider        VARCHAR(50),           -- lmstudio|vertexai|openai
    tokens_input    INTEGER DEFAULT 0,
    tokens_output   INTEGER DEFAULT 0,
    estimated_cost_usd NUMERIC(10,8) DEFAULT 0,
    latency_ms      INTEGER,
    task_type       VARCHAR(20),           -- simple|complex|transactional
    cache_hit       BOOLEAN DEFAULT false,
    recorded_at     TIMESTAMPTZ DEFAULT now()
);
-- Esta tabla se archiva a BigQuery periódicamente para análisis
-- Se usa para dashboards de FinOps y alertas de umbral
```

---

# SECCIÓN 7 — APIs RESTful HATEOAS (Nivel Richardson 3)

## 7.1 Principios de Diseño

- **Versioning**: URL path versioning `/api/v1/`. Cambios breaking → nueva versión.
- **Tenant context**: Header obligatorio `X-Tenant-ID` en endpoints de negocio. API management routes usan tenant del JWT.
- **Autenticación**: JWT Bearer en header `Authorization`. API Keys para integración máquina-a-máquina.
- **Idempotencia**: Endpoints `POST` de checkout y booking aceptan header `Idempotency-Key`.
- **Paginación**: Cursor-based pagination con `limit`, `cursor`, `has_more`, `next_cursor`.
- **HATEOAS**: Cada respuesta incluye `_links` con `self`, `related`, y acciones posibles según estado.
- **Errores**: RFC 7807 Problem Details (`type`, `title`, `status`, `detail`, `instance`).
- **Content-Type**: `application/json` por defecto; `application/vnd.nia+json; version=1` para negociación de versión.

---

## 7.2 Formato de Respuesta Estándar

```json
{
  "data": { /* payload principal */ },
  "meta": {
    "request_id": "req_01JXYZ...",
    "timestamp": "2026-04-10T12:00:00Z",
    "version": "1"
  },
  "_links": {
    "self": { "href": "/api/v1/resource/id", "method": "GET" },
    "next_action": { "href": "/api/v1/resource/id/action", "method": "POST" }
  }
}
```

**Error format (RFC 7807):**
```json
{
  "type": "https://nia.io/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "El campo 'email' no tiene un formato válido",
  "instance": "/api/v1/leads",
  "errors": [
    { "field": "email", "code": "invalid_format", "message": "Email inválido" }
  ]
}
```

---

## 7.3 Endpoints por Dominio

### Gestión de Tenants

```
POST   /api/v1/tenants                      → Crear tenant
GET    /api/v1/tenants/{id}                 → Obtener tenant
PATCH  /api/v1/tenants/{id}                 → Actualizar tenant
DELETE /api/v1/tenants/{id}                 → Soft delete
GET    /api/v1/tenants/{id}/health          → Estado de aprovisionamiento
POST   /api/v1/tenants/{id}/suspend         → Suspender tenant
POST   /api/v1/tenants/{id}/reactivate      → Reactivar tenant
GET    /api/v1/tenants                      → Listar tenants (super admin)
```

**Ejemplo POST /api/v1/tenants:**
```json
// Request
{
  "name": "Parque Aventura Andina",
  "slug": "parque-andina",
  "plan": "professional",
  "timezone": "America/Santiago",
  "default_language": "es"
}

// Response 201 Created
{
  "data": {
    "id": "ten_01JXYZ...",
    "slug": "parque-andina",
    "status": "provisioning",
    "api_key": "nia_live_...",   // Solo se retorna UNA vez en la creación
    "created_at": "2026-04-10T12:00:00Z"
  },
  "_links": {
    "self": { "href": "/api/v1/tenants/ten_01JXYZ", "method": "GET" },
    "config": { "href": "/api/v1/tenants/ten_01JXYZ/config", "method": "GET" },
    "health": { "href": "/api/v1/tenants/ten_01JXYZ/health", "method": "GET" }
  }
}
```

---

### Configuración de Branding

```
GET    /api/v1/tenants/{id}/config          → Obtener configuración completa
PATCH  /api/v1/tenants/{id}/config          → Actualizar configuración
GET    /api/v1/tenants/{id}/config/history  → Historial de versiones
POST   /api/v1/tenants/{id}/config/rollback → Revertir a versión anterior
GET    /api/v1/widget-config/{tenant_id}    → Config pública para widget (sin auth)
```

**Ejemplo PATCH /api/v1/tenants/{id}/config:**
```json
// Request
{
  "ui_config": {
    "primary_color": "#1A5276",
    "secondary_color": "#F39C12",
    "logo_url": "https://cdn.parque-andina.cl/logo.svg",
    "font_family": "Inter",
    "welcome_message": "Hola 👋 Soy el asistente de Parque Aventura Andina",
    "chat_title": "Asistente Parque Andina"
  }
}

// Response 200
{
  "data": { "version": 3, "updated_at": "2026-04-10T12:05:00Z" },
  "_links": {
    "self": { "href": "/api/v1/tenants/ten_01JXYZ/config", "method": "GET" },
    "widget_config": { "href": "/api/v1/widget-config/ten_01JXYZ", "method": "GET" }
  }
}
```

---

### Configuración de Lead Capture

```
GET    /api/v1/tenants/{id}/config/leads    → Obtener config de leads
PATCH  /api/v1/tenants/{id}/config/leads    → Actualizar config de leads
```

```json
// PATCH payload
{
  "lead_config": {
    "enabled": true,
    "fields": [
      { "name": "full_name", "label": "Nombre completo", "type": "text", "required": true },
      { "name": "email",     "label": "Correo electrónico", "type": "email", "required": true },
      { "name": "phone",     "label": "Teléfono", "type": "tel", "required": false },
      { "name": "pax_count", "label": "¿Cuántas personas?", "type": "number", "required": false }
    ],
    "gdpr_consent_text": "Acepto el tratamiento de mis datos para recibir información.",
    "submit_label": "Comenzar chat"
  }
}
```

---

### Productos Turísticos

```
POST   /api/v1/catalog/products             → Crear/actualizar producto
GET    /api/v1/catalog/products             → Listar productos del tenant (con filtros)
GET    /api/v1/catalog/products/{id}        → Obtener producto
PATCH  /api/v1/catalog/products/{id}        → Actualizar producto
DELETE /api/v1/catalog/products/{id}        → Desactivar producto
POST   /api/v1/catalog/ingest               → Ingesta por webhook
POST   /api/v1/catalog/batch-ingest         → Ingesta masiva (async, retorna job_id)
GET    /api/v1/catalog/ingest/jobs/{job_id} → Estado de job de ingesta
```

**GET /api/v1/catalog/products** (con filtros y paginación):
```
GET /api/v1/catalog/products?
    category=aventura&
    language=es&
    min_price=50000&
    max_price=150000&
    available_date=2026-04-20&
    limit=20&
    cursor=eyJ...

// Response 200
{
  "data": [
    {
      "id": "prod_01...",
      "name": "Rafting Grado III",
      "category": "aventura",
      "base_price": 85000,
      "currency": "CLP",
      "duration_minutes": 120,
      "languages": ["es", "en"],
      "status": "active"
    }
  ],
  "meta": { "total_returned": 20, "has_more": true, "next_cursor": "eyJ..." },
  "_links": {
    "self": { "href": "/api/v1/catalog/products?...", "method": "GET" },
    "next": { "href": "/api/v1/catalog/products?cursor=eyJ...", "method": "GET" }
  }
}
```

---

### Recomendación y Disponibilidad

```
POST   /api/v1/recommendations              → Obtener recomendaciones
POST   /api/v1/availability/check           → Verificar disponibilidad de producto
GET    /api/v1/availability/{product_id}    → Disponibilidad de los próximos 7 días
```

**POST /api/v1/recommendations:**
```json
// Request
{
  "intent": "booking_intent",
  "entities": {
    "activity_type": "rafting",
    "date": "2026-04-19",
    "pax_count": 4,
    "language_preference": "es",
    "budget_max": 100000
  },
  "session_id": "ses_01...",
  "limit": 3
}

// Response 200
{
  "data": {
    "recommendations": [
      {
        "product_id": "prod_01...",
        "name": "Rafting Grado III",
        "score": 0.94,
        "rank": 1,
        "available": true,
        "available_slots": [
          { "time": "09:00", "spots_left": 6, "guide_language": "es" },
          { "time": "14:00", "spots_left": 2, "guide_language": "es" }
        ],
        "price_per_person": 85000,
        "rank_reason": "Alta coincidencia con actividad solicitada, disponibilidad confirmada, idioma disponible",
        "_links": {
          "product": { "href": "/api/v1/catalog/products/prod_01", "method": "GET" },
          "checkout": { "href": "/api/v1/checkout/sessions", "method": "POST" }
        }
      }
    ],
    "availability_checked_at": "2026-04-10T12:00:05Z"
  },
  "_links": {
    "self": { "href": "/api/v1/recommendations", "method": "POST" }
  }
}
```

---

### Conversaciones

```
POST   /api/v1/conversations                         → Iniciar sesión de conversación
GET    /api/v1/conversations/{id}                    → Obtener estado de sesión
POST   /api/v1/conversations/{id}/messages           → Enviar mensaje (streaming via SSE)
GET    /api/v1/conversations/{id}/messages           → Historial de mensajes
POST   /api/v1/conversations/{id}/lead               → Capturar lead (pre-chat)
POST   /api/v1/conversations/{id}/close              → Cerrar conversación
GET    /api/v1/conversations/{id}/state              → Estado FSM actual
```

**POST /api/v1/conversations:**
```json
// Request
{
  "tenant_id": "ten_01...",
  "channel": "widget",
  "metadata": { "page_url": "https://parque-andina.cl/actividades", "referrer": "google" }
}

// Response 201
{
  "data": {
    "session_id": "ses_01...",
    "fsm_state": "pre_chat",
    "lead_capture_required": true,
    "lead_config": { "fields": [...] }
  },
  "_links": {
    "self": { "href": "/api/v1/conversations/ses_01", "method": "GET" },
    "lead": { "href": "/api/v1/conversations/ses_01/lead", "method": "POST" },
    "messages": { "href": "/api/v1/conversations/ses_01/messages", "method": "POST" }
  }
}
```

**POST /api/v1/conversations/{id}/messages (con SSE streaming):**
```json
// Request
{
  "content": "Quiero hacer rafting el próximo sábado para 4 personas",
  "role": "user"
}

// Response: text/event-stream
data: {"type":"thinking","content":""}
data: {"type":"token","content":"Excelente"}
data: {"type":"token","content":" elección."}
data: {"type":"recommendation","data":{"products":[...]}}
data: {"type":"done","session_state":"recommending","tokens_used":234}
```

---

### Checkout Conversacional

```
POST   /api/v1/checkout/sessions                        → Crear checkout session
GET    /api/v1/checkout/sessions/{id}                   → Estado del checkout
POST   /api/v1/checkout/sessions/{id}/confirm           → Confirmar datos de booking
GET    /api/v1/checkout/sessions/{id}/payment-url       → Obtener URL de pago
POST   /api/v1/webhooks/payment/{provider}              → Webhook de confirmación de pago
```

**POST /api/v1/checkout/sessions:**
```json
// Request
{
  "session_id": "ses_01...",
  "product_id": "prod_01...",
  "selected_date": "2026-04-19",
  "selected_time": "09:00",
  "pax_count": 4,
  "contact": {
    "name": "María González",
    "email": "maria@email.com",
    "phone": "+56912345678"
  }
}
// Headers: Idempotency-Key: idem_01...

// Response 201
{
  "data": {
    "checkout_session_id": "chk_01...",
    "booking_intent_id": "bkn_01...",
    "total_amount": 340000,
    "currency": "CLP",
    "payment_url": "https://pay.stripe.com/c/...",
    "expires_at": "2026-04-10T12:30:00Z",
    "status": "pending"
  },
  "_links": {
    "self": { "href": "/api/v1/checkout/sessions/chk_01", "method": "GET" },
    "payment": { "href": "https://pay.stripe.com/c/...", "method": "GET" }
  }
}
```

---

### Transcripciones y Exportación

```
GET    /api/v1/transcripts/{session_id}              → Obtener transcripción (JSON)
POST   /api/v1/transcripts/{session_id}/export       → Exportar transcripción por email
GET    /api/v1/transcripts/{session_id}/download     → Descargar como PDF/HTML
```

---

### Handoff a Teams

```
POST   /api/v1/handoffs                              → Escalar a agente humano
GET    /api/v1/handoffs/{id}                         → Estado del handoff
POST   /api/v1/handoffs/{id}/resolve                 → Marcar handoff como resuelto
POST   /api/v1/webhooks/teams/incoming               → Mensajes entrantes de Teams
GET    /api/v1/handoffs?tenant_id=...&status=active  → Listar handoffs activos
```

---

### Fallback Queries

```
GET    /api/v1/fallbacks?tenant_id=...&resolved=false    → Listar fallbacks
PATCH  /api/v1/fallbacks/{id}                            → Marcar como resuelto
POST   /api/v1/fallbacks/notify                          → Trigger manual de notificación
GET    /api/v1/fallbacks/stats?tenant_id=...&period=7d   → Estadísticas
```

---

### Métricas de Costo y Trazabilidad

```
GET    /api/v1/metrics/cost?tenant_id=...&period=30d     → Costo total por periodo
GET    /api/v1/metrics/cost/breakdown?tenant_id=...      → Desglose por modelo/servicio
GET    /api/v1/metrics/conversations?tenant_id=...       → Métricas de conversaciones
GET    /api/v1/metrics/recommendations?tenant_id=...     → Métricas de recomendaciones
GET    /api/v1/metrics/rag?tenant_id=...                 → Métricas de RAG (precision, recall)
GET    /api/v1/audit?tenant_id=...&from=...&to=...       → Log de auditoría
```

**Ejemplo GET /api/v1/metrics/cost:**
```json
{
  "data": {
    "tenant_id": "ten_01...",
    "period": "2026-04-01/2026-04-10",
    "total_cost_usd": 12.45,
    "total_conversations": 342,
    "cost_per_conversation_usd": 0.036,
    "cache_hit_rate": 0.42,
    "breakdown": [
      { "model": "gemini-1.5-flash", "calls": 980, "tokens_in": 485000, "tokens_out": 120000, "cost_usd": 8.20 },
      { "model": "gemini-1.5-pro", "calls": 45, "tokens_in": 87000, "tokens_out": 25000, "cost_usd": 4.25 }
    ]
  }
}
```
