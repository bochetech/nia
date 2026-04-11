# NIA — Nodo de Inteligencia Activa para Turismo SaaS
## Blueprint Técnico Completo — Parte 1 de 5
**Versión:** 1.0.0 · **Fecha:** Abril 2026 · **Estado:** DRAFT para revisión de ingeniería

---

# SECCIÓN 0 — Arquitectura de Desarrollo Local y Estrategia de Depuración

## 0.1 Principio Rector

La solución NIA adopta un modelo de dos perspectivas obligatorias:

1. **Entorno local de desarrollo y depuración** completamente funcional, usando **LM Studio** como proveedor de IA local (modelo compatible con API OpenAI), sin dependencia de créditos cloud ni latencia de red.
2. **Entorno objetivo productivo cloud-native** sobre GCP, donde cada componente local tiene un equivalente gestionado.

El cambio entre entornos se realiza **únicamente cambiando variables de entorno**. No se rehace ningún código ni arquitectura. La capa de abstracción `ModelProviderAdapter` garantiza este desacoplamiento.

---

## 0.2 Diagrama de Arquitectura Local (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ENTORNO DE DESARROLLO LOCAL                         │
│                                                                         │
│  ┌──────────────┐    ┌─────────────────────────────────────────────┐   │
│  │  Browser     │    │           Docker Compose Network            │   │
│  │  :3000       │    │                                             │   │
│  │  (Widget     │    │  ┌──────────────┐   ┌───────────────────┐  │   │
│  │  Dev Server) │◄───┼──│  API Gateway │   │  Conversation     │  │   │
│  └──────────────┘    │  │  (Nginx/     │   │  Orchestrator     │  │   │
│                      │  │  Traefik)    │   │  :8001            │  │   │
│  ┌──────────────┐    │  │  :8080       │──►│  (FastAPI)        │  │   │
│  │  Admin UI    │◄───┼──│              │   └────────┬──────────┘  │   │
│  │  :3001       │    │  └──────────────┘            │             │   │
│  └──────────────┘    │                              │             │   │
│                      │  ┌──────────────┐   ┌────────▼──────────┐  │   │
│  ┌──────────────┐    │  │  RAG Service │◄──│  Model Provider   │  │   │
│  │  LM Studio   │◄───┼──│  :8002       │   │  Adapter :8005    │  │   │
│  │  :1234       │    │  │  (FastAPI)   │   │  (abstracción)    │  │   │
│  │  (LLM local) │    │  └──────┬───────┘   └───────────────────┘  │   │
│  └──────────────┘    │         │                     │             │   │
│                      │  ┌──────▼───────┐   ┌────────▼──────────┐  │   │
│                      │  │  Qdrant      │   │  LM Studio Client │  │   │
│                      │  │  Vector DB   │   │  → localhost:1234  │  │   │
│                      │  │  :6333       │   └───────────────────┘  │   │
│                      │  └──────────────┘                          │   │
│                      │                                             │   │
│                      │  ┌──────────────┐   ┌───────────────────┐  │   │
│                      │  │  PostgreSQL  │   │  Redis            │  │   │
│                      │  │  :5432       │   │  :6379            │  │   │
│                      │  └──────────────┘   └───────────────────┘  │   │
│                      │                                             │   │
│                      │  ┌──────────────┐   ┌───────────────────┐  │   │
│                      │  │  Tenant Mgr  │   │  Webhook Mock     │  │   │
│                      │  │  Service     │   │  (Mockoon/        │  │   │
│                      │  │  :8003       │   │  WireMock) :9090  │  │   │
│                      │  └──────────────┘   └───────────────────┘  │   │
│                      │                                             │   │
│                      │  ┌──────────────┐   ┌───────────────────┐  │   │
│                      │  │  Mailhog     │   │  Teams Mock       │  │   │
│                      │  │  SMTP :1025  │   │  Stub :9091       │  │   │
│                      │  │  UI :8025    │   │                   │  │   │
│                      │  └──────────────┘   └───────────────────┘  │   │
│                      └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 0.3 Componentes Ejecutables Localmente

| Componente | Imagen Docker | Puerto(s) | Obligatorio | Equivalente GCP |
|---|---|---|---|---|
| API Gateway (Traefik) | `traefik:v3` | 8080, 8090 (dashboard) | ✅ | Cloud API Gateway |
| Conversation Orchestrator | `nia/orchestrator:dev` | 8001 | ✅ | Cloud Run |
| RAG Service | `nia/rag:dev` | 8002 | ✅ | Cloud Run |
| Tenant Manager | `nia/tenant-mgr:dev` | 8003 | ✅ | Cloud Run |
| Recommendation Engine | `nia/recommender:dev` | 8004 | ✅ | Cloud Run |
| Model Provider Adapter | `nia/model-adapter:dev` | 8005 | ✅ | Cloud Run (→ Vertex AI) |
| PostgreSQL | `postgres:16-alpine` | 5432 | ✅ | Cloud SQL |
| Redis | `redis:7-alpine` | 6379 | ✅ | Memorystore |
| Qdrant | `qdrant/qdrant:latest` | 6333, 6334 | ✅ | Vertex AI Vector Search |
| LM Studio | Nativo (host) | 1234 | ✅ dev / ❌ prod | Vertex AI Gemini |
| Mailhog | `mailhog/mailhog` | 1025, 8025 | ✅ dev | SendGrid / Cloud Pub/Sub |
| Webhook Mock (Mockoon) | `mockoon/cli` | 9090 | ⚙️ opcional | Real webhooks |
| Teams Mock Stub | `nia/teams-stub:dev` | 9091 | ⚙️ opcional | MS Teams Graph API |
| Widget Dev Server | `node:20-alpine` | 3000 | ✅ | Cloud CDN / Firebase Hosting |
| Admin UI | `node:20-alpine` | 3001 | ⚙️ opcional | Firebase Hosting |

---

## 0.4 docker-compose.yml Propuesto

```yaml
# docker-compose.yml — NIA Development Stack
version: "3.9"

networks:
  nia-net:
    driver: bridge

volumes:
  postgres_data:
  qdrant_data:
  redis_data:

services:

  # ── Reverse Proxy / API Gateway ──────────────────────────────────────
  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:8080"
    ports:
      - "8080:8080"
      - "8090:8080"    # Traefik dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [nia-net]

  # ── PostgreSQL ────────────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: nia_dev
      POSTGRES_USER: nia_user
      POSTGRES_PASSWORD: nia_secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nia_user -d nia_dev"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks: [nia-net]

  # ── Redis ─────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks: [nia-net]

  # ── Qdrant Vector DB ──────────────────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:v1.9.2
    ports:
      - "6333:6333"   # REST API
      - "6334:6334"   # gRPC
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    networks: [nia-net]

  # ── Model Provider Adapter ────────────────────────────────────────────
  model-adapter:
    build:
      context: ./services/model-adapter
      dockerfile: Dockerfile.dev
    environment:
      ENV: development
      MODEL_PROVIDER: lmstudio               # | vertexai | openai
      LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1
      LMSTUDIO_CHAT_MODEL: llama-3.2-3b-instruct
      LMSTUDIO_EMBEDDING_MODEL: text-embedding-nomic-embed-text-v1.5
      LOG_LEVEL: DEBUG
    ports:
      - "8005:8005"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks: [nia-net]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.model-adapter.rule=PathPrefix(`/internal/model`)"

  # ── RAG Service ───────────────────────────────────────────────────────
  rag-service:
    build:
      context: ./services/rag
      dockerfile: Dockerfile.dev
    environment:
      ENV: development
      QDRANT_HOST: qdrant
      QDRANT_PORT: 6333
      MODEL_ADAPTER_URL: http://model-adapter:8005
      POSTGRES_DSN: postgresql://nia_user:nia_secret@postgres:5432/nia_dev
      REDIS_URL: redis://redis:6379
      CHUNK_SIZE: 512
      CHUNK_OVERLAP: 64
      RETRIEVAL_TOP_K: 8
      RERANK_TOP_K: 3
      CONFIDENCE_THRESHOLD: 0.65
      LOG_LEVEL: DEBUG
    ports:
      - "8002:8002"
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_started
      model-adapter:
        condition: service_started
    networks: [nia-net]
    volumes:
      - ./services/rag:/app           # hot reload
      - ./data/seed:/app/seed         # dataset semilla

  # ── Tenant Manager ────────────────────────────────────────────────────
  tenant-manager:
    build:
      context: ./services/tenant-manager
      dockerfile: Dockerfile.dev
    environment:
      ENV: development
      POSTGRES_DSN: postgresql://nia_user:nia_secret@postgres:5432/nia_dev
      REDIS_URL: redis://redis:6379
      SECRET_KEY: dev-super-secret-key-change-in-prod
      LOG_LEVEL: DEBUG
    ports:
      - "8003:8003"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./services/tenant-manager:/app
    networks: [nia-net]

  # ── Recommendation Engine ─────────────────────────────────────────────
  recommender:
    build:
      context: ./services/recommender
      dockerfile: Dockerfile.dev
    environment:
      ENV: development
      POSTGRES_DSN: postgresql://nia_user:nia_secret@postgres:5432/nia_dev
      REDIS_URL: redis://redis:6379
      MODEL_ADAPTER_URL: http://model-adapter:8005
      AVAILABILITY_MOCK: "true"          # usa mock local de disponibilidad
      LOG_LEVEL: DEBUG
    ports:
      - "8004:8004"
    volumes:
      - ./services/recommender:/app
    networks: [nia-net]

  # ── Conversation Orchestrator ─────────────────────────────────────────
  orchestrator:
    build:
      context: ./services/orchestrator
      dockerfile: Dockerfile.dev
    environment:
      ENV: development
      POSTGRES_DSN: postgresql://nia_user:nia_secret@postgres:5432/nia_dev
      REDIS_URL: redis://redis:6379
      MODEL_ADAPTER_URL: http://model-adapter:8005
      RAG_SERVICE_URL: http://rag-service:8002
      RECOMMENDER_URL: http://recommender:8004
      TENANT_MANAGER_URL: http://tenant-manager:8003
      TEAMS_STUB_URL: http://teams-stub:9091
      SMTP_HOST: mailhog
      SMTP_PORT: 1025
      SMTP_USE_TLS: "false"
      JWT_SECRET: dev-jwt-secret
      LOG_LEVEL: DEBUG
    ports:
      - "8001:8001"
    depends_on:
      - postgres
      - redis
      - model-adapter
      - rag-service
    volumes:
      - ./services/orchestrator:/app
    networks: [nia-net]
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.orchestrator.rule=PathPrefix(`/api/v1`)"

  # ── MS Teams Mock Stub ────────────────────────────────────────────────
  teams-stub:
    build:
      context: ./stubs/teams
    environment:
      STUB_MODE: record_replay    # record | replay | passthrough
    ports:
      - "9091:9091"
    networks: [nia-net]

  # ── Webhook Mock (Mockoon) ────────────────────────────────────────────
  webhook-mock:
    image: mockoon/cli:latest
    command: --data /data/mocks.json --port 9090
    ports:
      - "9090:9090"
    volumes:
      - ./stubs/mockoon:/data
    networks: [nia-net]

  # ── Mailhog (SMTP Dev) ────────────────────────────────────────────────
  mailhog:
    image: mailhog/mailhog:latest
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # Web UI
    networks: [nia-net]

  # ── Widget Dev Server ─────────────────────────────────────────────────
  widget-dev:
    build:
      context: ./packages/widget
      dockerfile: Dockerfile.dev
    environment:
      VITE_API_BASE_URL: http://localhost:8080/api/v1
      VITE_TENANT_ID: tenant_seed_001
    ports:
      - "3000:3000"
    volumes:
      - ./packages/widget:/app
      - /app/node_modules
    networks: [nia-net]
```

---

## 0.5 Variables de Entorno por Ambiente

```bash
# .env.development  ──────────────────────────────────────
ENV=development
MODEL_PROVIDER=lmstudio
LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
LMSTUDIO_CHAT_MODEL=llama-3.2-3b-instruct
LMSTUDIO_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5
LMSTUDIO_API_KEY=lm-studio        # cualquier valor, LM Studio no valida

POSTGRES_DSN=postgresql://nia_user:nia_secret@localhost:5432/nia_dev
REDIS_URL=redis://localhost:6379
QDRANT_HOST=localhost
QDRANT_PORT=6333

TEAMS_INTEGRATION_ENABLED=false
TEAMS_STUB_URL=http://localhost:9091

AVAILABILITY_MOCK=true
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false

SEMANTIC_CACHE_ENABLED=false       # desactivar caché semántica en dev
COST_TRACKING_ENABLED=true         # activar tracking aunque sea local

# .env.staging  ──────────────────────────────────────────
ENV=staging
MODEL_PROVIDER=vertexai
VERTEX_PROJECT_ID=nia-staging-proj
VERTEX_LOCATION=us-central1
VERTEX_CHAT_MODEL=gemini-1.5-flash-002
VERTEX_EMBEDDING_MODEL=text-embedding-004

POSTGRES_DSN=${SECRET:cloudsql_dsn_staging}
REDIS_URL=${SECRET:redis_url_staging}

TEAMS_INTEGRATION_ENABLED=true
AVAILABILITY_MOCK=false

# .env.production  ───────────────────────────────────────
ENV=production
MODEL_PROVIDER=vertexai
VERTEX_CHAT_MODEL=gemini-1.5-pro-002     # modelo robusto para transacciones
VERTEX_FAST_MODEL=gemini-1.5-flash-002   # modelo ligero para consultas simples
SEMANTIC_CACHE_ENABLED=true
COST_TRACKING_ENABLED=true
```

---

## 0.6 Abstracción del Proveedor de Modelo (ModelProviderAdapter)

```python
# services/model-adapter/app/providers/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str   # system | user | assistant
    content: str

@dataclass
class EmbeddingResult:
    vector: list[float]
    model: str
    tokens_used: int

@dataclass
class ChatCompletionResult:
    content: str
    model: str
    tokens_input: int
    tokens_output: int
    finish_reason: str
    latency_ms: float

class ModelProviderAdapter(ABC):
    """
    Interfaz unificada para cualquier proveedor de LLM.
    Los servicios NUNCA llaman directamente al SDK de un proveedor específico.
    Siempre usan esta abstracción.
    """

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        tenant_id: str | None = None,
        task_type: str = "general",  # "simple" | "complex" | "transactional"
    ) -> ChatCompletionResult:
        ...

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        tenant_id: str | None = None,
    ) -> list[EmbeddingResult]:
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        tenant_id: str | None = None,
    ) -> AsyncIterator[str]:
        ...


# services/model-adapter/app/providers/lmstudio.py

import httpx
import time
from .base import ModelProviderAdapter, ChatMessage, ChatCompletionResult, EmbeddingResult

class LMStudioProvider(ModelProviderAdapter):
    """
    Proveedor para LM Studio en desarrollo local.
    Compatible con OpenAI API format (v1).
    """
    def __init__(self, base_url: str, chat_model: str, embedding_model: str, api_key: str = "lm-studio"):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=120.0,   # LM Studio puede ser lento en hardware modesto
        )

    async def chat_completion(self, messages, temperature=0.3, max_tokens=1024, **kwargs) -> ChatCompletionResult:
        start = time.monotonic()
        payload = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = await self.client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        elapsed = (time.monotonic() - start) * 1000
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return ChatCompletionResult(
            content=choice["message"]["content"],
            model=data.get("model", self.chat_model),
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=elapsed,
        )

    async def embed(self, texts: list[str], **kwargs) -> list[EmbeddingResult]:
        payload = {"model": self.embedding_model, "input": texts}
        resp = await self.client.post("/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data["data"]:
            results.append(EmbeddingResult(
                vector=item["embedding"],
                model=self.embedding_model,
                tokens_used=data.get("usage", {}).get("prompt_tokens", 0) // len(texts),
            ))
        return results

    async def stream_chat(self, messages, **kwargs):
        payload = {
            "model": self.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        async with self.client.stream("POST", "/chat/completions", json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    import json
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta


# services/model-adapter/app/providers/factory.py

import os
from .base import ModelProviderAdapter
from .lmstudio import LMStudioProvider

def create_provider() -> ModelProviderAdapter:
    provider = os.environ.get("MODEL_PROVIDER", "lmstudio")
    if provider == "lmstudio":
        return LMStudioProvider(
            base_url=os.environ["LMSTUDIO_BASE_URL"],
            chat_model=os.environ["LMSTUDIO_CHAT_MODEL"],
            embedding_model=os.environ["LMSTUDIO_EMBEDDING_MODEL"],
        )
    elif provider == "vertexai":
        from .vertexai import VertexAIProvider
        return VertexAIProvider(
            project=os.environ["VERTEX_PROJECT_ID"],
            location=os.environ["VERTEX_LOCATION"],
            chat_model=os.environ["VERTEX_CHAT_MODEL"],
            fast_model=os.environ.get("VERTEX_FAST_MODEL", os.environ["VERTEX_CHAT_MODEL"]),
            embedding_model=os.environ["VERTEX_EMBEDDING_MODEL"],
        )
    else:
        raise ValueError(f"Proveedor desconocido: {provider}")
```

---

## 0.7 Estrategia de Hot Reload

Todos los servicios Python usan `uvicorn --reload` montando el directorio de código como volumen en Docker. Los servicios Node/Vite usan `vite --watch`. No se requiere rebuild de imagen para cambios de código.

```dockerfile
# Dockerfile.dev — patrón común para servicios Python
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# NO se copia código fuente: se monta como volumen en docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
```

---

## 0.8 Dataset Semilla para Pruebas

```
data/seed/
├── tenants/
│   └── tenant_seed_001.json        # tenant de prueba: "Parque Aventura Andina"
├── products/
│   ├── rafting_basico.json
│   ├── canopy_profesional.json
│   ├── trekking_nevado.json
│   └── spa_termales.json
├── knowledge/
│   ├── politicas_generales.md
│   ├── horarios_instalaciones.md
│   ├── preguntas_frecuentes.md
│   └── politicas_cancelacion.md
├── conversations/
│   └── golden_set.json             # conversaciones de referencia para test
└── leads/
    └── leads_sample.json
```

**Carga automática del dataset semilla:**
```bash
# Script de inicialización
./scripts/seed.sh   # Ejecuta tras docker-compose up
# → Crea tenant de prueba
# → Ingesta documentos al RAG
# → Carga catálogo de productos
# → Verifica conectividad con LM Studio
```

---

## 0.9 Estrategia de Testing Local

| Tipo de Test | Herramienta | Qué verifica | Comando |
|---|---|---|---|
| Unit tests servicios | pytest + pytest-asyncio | Lógica de negocio aislada | `pytest tests/unit` |
| Integration tests | pytest + httpx | Contratos entre servicios | `pytest tests/integration` |
| Widget tests | Vitest + Testing Library | Componentes UI | `npm run test` |
| E2E conversacional | Playwright | Flujo completo widget→backend | `npm run test:e2e` |
| RAG accuracy | pytest + golden set | Precision/Recall sobre doc semilla | `pytest tests/rag` |
| Prompt tests | promptfoo | Calidad de prompts vs LM Studio | `promptfoo eval` |
| Handoff tests | pytest mock Teams stub | Flujo handoff completo | `pytest tests/handoff` |
| Fallback tests | pytest | Detección de queries no resueltas | `pytest tests/fallback` |
| Checkout tests | pytest | FSM de checkout completo | `pytest tests/checkout` |
| Load test básico | Locust | Throughput local mínimo | `locust -f tests/load/locustfile.py` |

**Ejemplo de prueba del flujo conversacional:**
```python
# tests/integration/test_conversation_flow.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_full_conversation_rafting(async_client: httpx.AsyncClient, seed_tenant):
    # 1. Iniciar sesión
    resp = await async_client.post("/api/v1/conversations", json={
        "tenant_id": "tenant_seed_001",
        "channel": "widget",
        "metadata": {"page_url": "https://example.com/aventuras"}
    })
    assert resp.status_code == 201
    session_id = resp.json()["data"]["session_id"]

    # 2. Enviar mensaje de intent
    resp = await async_client.post(f"/api/v1/conversations/{session_id}/messages", json={
        "content": "Quiero hacer rafting el próximo sábado para 4 personas",
        "role": "user"
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["intent_detected"] in ["booking_intent", "product_inquiry"]
    assert len(data["recommendations"]) >= 1

    # 3. Verificar que recomienda solo productos del tenant
    for rec in data["recommendations"]:
        assert rec["tenant_id"] == "tenant_seed_001"
        assert rec["availability_validated"] is True
```

---

## 0.10 Depuración End-to-End

```bash
# Ver logs de todos los servicios en tiempo real
docker compose logs -f --tail=100

# Ver solo logs del orchestrator (la mayoría de la lógica de negocio)
docker compose logs -f orchestrator

# Inspeccionar estado de sesión en Redis
docker compose exec redis redis-cli KEYS "session:*"
docker compose exec redis redis-cli GET "session:{session_id}"

# Consultar colecciones Qdrant directamente
curl http://localhost:6333/collections
curl http://localhost:6333/collections/tenant_seed_001_knowledge/points/scroll

# Conectar a PostgreSQL
docker compose exec postgres psql -U nia_user -d nia_dev

# Ver emails enviados (transcripciones, leads)
open http://localhost:8025   # Mailhog UI

# Probar LM Studio directamente
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.2-3b-instruct","messages":[{"role":"user","content":"test"}]}'

# Probar endpoint RAG
curl http://localhost:8002/api/v1/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant_seed_001" \
  -d '{"query":"¿Cuáles son los horarios de atención?","top_k":3}'
```

---

# SECCIÓN 1 — Resumen Ejecutivo

## 1.1 Qué es NIA

**NIA — Nodo de Inteligencia Activa** es una plataforma SaaS B2B multi-tenant de IA conversacional especializada en ventas y atención turística. Se despliega como un widget embebible sobre cualquier sitio web de un centro turístico y actúa como un conserje digital inteligente que asiste a los visitantes desde el descubrimiento de experiencias hasta la confirmación del pago.

NIA no es un chatbot genérico ni una integración de ChatGPT con prompts básicos. Es un sistema orquestado con múltiples capas especializadas:

- **Motor conversacional** con gestión de estado y flujo de compra estructurado.
- **Motor RAG delimitado por dominio**: la IA responde estrictamente sobre el conocimiento del centro turístico.
- **Motor de recomendación** que valida disponibilidad, idioma y capacidad en tiempo real antes de sugerir.
- **Checkout conversacional** integrado con sistema de pagos.
- **Handoff bidireccional** con MS Teams cuando el agente humano debe intervenir.
- **Arquitectura multi-tenant** donde cada centro turístico opera en completo aislamiento.

## 1.2 Propósito

Eliminar la fricción entre el interés del visitante y la conversión en reserva, operando 24/7 con calidad de experiencia de alto estándar, reduciendo la carga sobre el equipo de atención humana y generando datos estructurados para decisiones de negocio.

## 1.3 Problemas que Resuelve

| Problema del centro turístico | Cómo NIA lo resuelve |
|---|---|
| El equipo de ventas no puede atender consultas las 24h | NIA opera permanentemente con calidad consistente |
| Los visitantes no encuentran el producto adecuado | Motor de recomendación personalizado con validación real |
| Las reservas abandonadas por fricción en el proceso | Checkout conversacional guiado paso a paso |
| Preguntas respondidas erróneamente (alucinaciones) | RAG estrictamente delimitado al dominio del centro |
| Pérdida de leads por falta de captura estructurada | Pre-chat configurable con validación de campos |
| Escalado manual a humano ineficiente | Handoff a Teams con contexto completo de la sesión |
| No hay registro estructurado de interacciones | Trazabilidad completa de cada conversación |
| El chatbot interfiere con el diseño del sitio | Widget con Shadow DOM completamente aislado |
| Costos de IA descontrolados | FinOps: caché semántica, model routing, límites por tenant |
| Nuevo producto tarda semanas en estar disponible | Ingesta automática vía webhook con categorización por IA |

## 1.4 Capacidades Principales

1. **Ingesta dinámica de catálogo** vía webhook/API con categorización automática por IA.
2. **Recomendación inteligente** con señales contextuales y validación en tiempo real.
3. **RAG dominio-acotado** con guardrails, scoring de confianza y trazabilidad de fuentes.
4. **Checkout conversacional** con manejo de estado, objeciones y confirmación de pago.
5. **Handoff bidireccional** con MS Teams (escalado y respuesta del agente reflejada en chat).
6. **Captura de leads** configurable por tenant.
7. **Exportación de transcripciones** al email del usuario.
8. **Fallback tracking**: queries no resueltas notificadas a Teams para mejora continua.
9. **Multi-tenancy completo**: datos, conocimiento, branding y configuración por tenant.
10. **Widget embebible** agnóstico, con Shadow DOM y theming por tenant.
11. **Operación cloud-native en GCP** con serverless y servicios gestionados.
12. **FinOps integrado**: model routing, caché semántica, límites de tokens por tenant.

## 1.5 Propuesta de Valor para un Centro Turístico SaaS

- **Incremento en conversión**: el flujo conversacional guiado reduce abandono en el funnel de reserva.
- **Reducción de carga operativa**: hasta el 70% de consultas resueltas sin intervención humana (Supuesto, basado en benchmarks de plataformas similares).
- **Time-to-market de nuevos productos**: de días a minutos mediante ingesta automática.
- **Datos estructurados**: cada interacción genera insights accionables para marketing y producto.
- **Escalabilidad sin costo marginal lineal**: arquitectura serverless escala con demanda sin contratar más agentes.
- **Diferenciación competitiva**: experiencia premium que proyecta la calidad del centro turístico.

---

# SECCIÓN 2 — Mapa de Requerimientos

## 2.1 Tabla de Requerimientos Mapeados

| ID | Requerimiento | Capacidad Funcional | Componente Responsable | Tipo Integración | Criticidad | Riesgos | Observaciones |
|---|---|---|---|---|---|---|---|
| R1.1 | Ingesta y categorización dinámica de catálogo | Procesamiento automático de nuevos productos | Catalog Ingestion Service + RAG Pipeline | Webhook entrante / API REST | 🔴 Alta | Latencia de categorización; calidad del modelo para taxonomías turísticas | Se debe definir el schema de producto base |
| R1.2 | Motor de recomendación con validación en RT | Recomendación contextual + validación disponibilidad | Recommendation Engine + Availability Connector | API interna + API externa (PMS/disponibilidad) | 🔴 Alta | Disponibilidad del sistema externo; latencia RT afecta UX | Mock de disponibilidad en dev obligatorio |
| R1.3 | Checkout conversacional | Flujo de compra guiado por IA | Conversation Orchestrator + Checkout Service | Payment Gateway (ej. Stripe/Transbank) | 🔴 Alta | Fallos de pago en mitad del flujo; estado inconsistente | FSM de estados obligatoria |
| R1.4 | RAG delimitado por dominio | Respuestas fundamentadas en doc del tenant | RAG Service + Vector Store | Interna | 🔴 Alta | Alucinaciones fuera de dominio; calidad de chunking | Guardrails de groundedness obligatorios |
| R2.1 | Handoff bidireccional MS Teams | Escalado a humano + respuesta en chat | Handoff Service + Teams Integration | MS Teams Bot Framework / Graph API | 🔴 Alta | Latencia bidireccional; estado de sesión durante handoff | Stub local obligatorio en dev |
| R2.2 | Captura de leads configurable | Pre-chat con campos configurables por tenant | Lead Capture Module (parte del Orchestrator) | Interna | 🟡 Media | Datos incompletos; resistencia del usuario | Admin UI para config sin código |
| R2.3 | Exportación de transcripciones | Email con transcripción completa al usuario | Transcript Service + Email Provider | SMTP / SendGrid | 🟡 Media | Entregabilidad de email; datos PII en tránsito | GDPR/política de retención aplica |
| R3.1 | Arquitectura multi-tenant | Aislamiento completo entre centros turísticos | Tenant Manager + row-level security | Interna | 🔴 Alta | Cross-tenant data leak; misconfiguration | Schema por tenant o RLS en PostgreSQL |
| R3.2 | API RESTful HATEOAS nivel 3 | Plataforma gobernada por API | API Gateway + todos los servicios | REST/HTTPS | 🟡 Media | Complejidad de hypermedia; overhead de diseño | Genera valor real en admin y partners |
| R3.3 | Trazabilidad y mejora continua | Registro de queries fallidas + notificación Teams | Fallback Tracker + Observability Layer | MS Teams webhook / BigQuery | 🟡 Media | Volumen de fallbacks puede saturar Teams | Frecuencia configurable (diaria/semanal) |
| R4.1 | Interfaz premium con microinteracciones | UX de alta gama orientada a conversión | Widget (Frontend) | CDN | 🟡 Media | Percepción subjetiva; deuda técnica CSS | Guía de estilo y tokens de diseño necesarios |
| R4.2 | Widget embebible con Shadow DOM | Aislamiento total en sitio anfitrión | Widget (Frontend) | Script tag | 🔴 Alta | Compatibilidad CSP; fonts no cargadas por Shadow DOM | Testar en CMS populares (WordPress, Wix) |
| R5.1 | Infraestructura cloud-native GCP | Alta disponibilidad, serverless | GCP: Cloud Run, Pub/Sub, CloudSQL, etc. | GCP APIs | 🔴 Alta | Vendor lock-in parcial; costo inesperado | Terraform para IaC |
| R5.2 | FinOps: control de costos IA | Model routing + caché + límites por tenant | FinOps Layer (transversal) | Interna + Vertex AI | 🔴 Alta | Costo descontrolado por tenant; degradación de calidad con modelos ligeros | Dashboards de costo por tenant obligatorios |
| RLOC.1 | Ejecución local con LM Studio | Dev environment sin cloud | Model Provider Adapter + Docker Compose | LM Studio REST API local | 🔴 Alta | Hardware insuficiente; modelos no compatibles | Requisito mínimo: 16GB RAM, GPU opcional |
| RLOC.2 | Abstracción de proveedor de modelo | Cambio transparente local↔cloud | Model Provider Adapter | Interna | 🔴 Alta | Divergencia de capabilities entre modelos | Pruebas de compatibilidad obligatorias |

---

# SECCIÓN 3 — Arquitectura de Alto Nivel

## 3.1 Diagrama Lógico (Descripción Textual)

```
═══════════════════════════════════════════════════════════════════════
                    CANALES DE ENTRADA
═══════════════════════════════════════════════════════════════════════

  [Sitio Web del Tenant]          [Admin Portal NIA]
         │                               │
  <Widget embebible>              <Admin SPA React>
  Shadow DOM, script tag          Gestión tenant/config/datos
         │                               │
         └──────────────┬────────────────┘
                        │ HTTPS/WSS
                        ▼
═══════════════════════════════════════════════════════════════════════
                    PERÍMETRO DE SEGURIDAD
═══════════════════════════════════════════════════════════════════════
          [Cloud Armor / WAF] + [Cloud CDN]
                        │
                        ▼
═══════════════════════════════════════════════════════════════════════
                    API GATEWAY LAYER
═══════════════════════════════════════════════════════════════════════
         [Cloud API Gateway / Apigee]
         ├── Rate limiting por tenant
         ├── JWT validation
         ├── Tenant resolution (X-Tenant-ID → TenantContext)
         ├── Request routing
         └── CORS / TLS termination
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
═══════════════════════════════════════════════════════════════════════
                DOMINIO DE ORQUESTACIÓN CONVERSACIONAL
═══════════════════════════════════════════════════════════════════════

[Conversation Orchestrator Service]  ←── WebSocket / SSE para streaming
│
├── Session Manager (Redis)          ← estado de sesión, FSM de conversación
├── Intent Classifier                ← LLM liviano o reglas
├── Context Builder                  ← historial + tenant config + RAG context
├── Lead Capture Module              ← pre-chat configurable
├── Conversation FSM                 ← estados: greeting→discovery→recommend→checkout→done
│
├──────────► [RAG Service] ──────────────────────────────────────────────┐
│            ├── Document Retriever (Qdrant)                              │
│            ├── Reranker                                                  │
│            ├── Groundedness Validator                                    │
│            └── Response Generator (via Model Adapter)                   │
│                                                                          │
├──────────► [Recommendation Engine]                                      │
│            ├── Intent Parser                                             │
│            ├── Product Filter (PostgreSQL)                               │
│            ├── Availability Validator (real-time)                        │
│            ├── Language/Capacity Checker                                 │
│            └── Ranker (scoring híbrido)                                  │
│                                                                          │
├──────────► [Checkout Service]                                            │
│            ├── Booking Intent Builder                                    │
│            ├── Checkout Session Manager                                  │
│            ├── Payment Gateway Connector                                 │
│            └── Confirmation Handler                                      │
│                                                                          │
├──────────► [Handoff Service]                                             │
│            ├── Escalation Trigger                                        │
│            ├── Teams Integration (Bot Framework)                         │
│            ├── Session Pause/Resume                                      │
│            └── Bidirectional Message Relay                               │
│                                                                          │
└──────────► [Model Provider Adapter]  ←── abstracción LLM               │
             ├── dev:  LM Studio (localhost:1234)                          │
             └── prod: Vertex AI Gemini                                    │
                                                                          │
═══════════════════════════════════════════════════════════════════════   │
            DOMINIO MULTI-TENANT Y CONFIGURACIÓN                          │
═══════════════════════════════════════════════════════════════════════   │
                                                                          │
[Tenant Manager Service]                                                  │
├── Tenant CRUD + Onboarding                                              │
├── TenantConfig (branding, leads, limits)                                │
├── Tenant Context Cache (Redis)                                          │
└── API Key management                                                    │
                                                                          │
[Catalog Ingestion Service]                                               │
├── Webhook receiver                                                      │
├── Product schema validator                                              │
├── AI-powered categorization                                             │
└── Knowledge base update trigger ────────────────────────────────────► ┘
                                                                          
═══════════════════════════════════════════════════════════════════════
            CAPA DE DATOS Y CONOCIMIENTO
═══════════════════════════════════════════════════════════════════════

[PostgreSQL / Cloud SQL]             [Qdrant / Vertex AI Vector Search]
├── Tenants, Configs                 ├── Colección por tenant
├── Products, Experiences            ├── Embeddings de documentos
├── Sessions, Leads                  └── Embeddings de FAQs y productos
├── Transcripts, Handoffs
├── Audit Events
└── Cost Metrics

[Redis / Memorystore]                [Cloud Storage / GCS]
├── Session state                    ├── Documentos fuente (PDF, MD)
├── Semantic cache                   ├── Transcripts exportados
├── Rate limit counters              └── Assets del widget
└── Tenant config cache

[BigQuery]                           [Cloud Pub/Sub]
├── Analytics warehouse              ├── catalog.ingested
├── Cost tracking                    ├── conversation.ended
└── Fallback queries analysis        ├── handoff.escalated
                                     └── fallback.detected

═══════════════════════════════════════════════════════════════════════
            CAPA DE OBSERVABILIDAD
═══════════════════════════════════════════════════════════════════════

[Cloud Logging] + [Cloud Monitoring] + [Error Reporting]
[OpenTelemetry Collector] → traces, metrics, logs
[Grafana / Looker Studio] → dashboards operativos y de producto

═══════════════════════════════════════════════════════════════════════
            INTEGRACIONES EXTERNAS
═══════════════════════════════════════════════════════════════════════

[MS Teams]          [Payment Gateway]    [Email Provider]   [PMS/CRS]
Bot Framework       Stripe/Transbank     SendGrid/SES        Booking APIs
Graph API           Webhooks             SMTP                REST/SOAP
```

---

## 3.2 Flujo End-to-End (Camino Feliz)

```
1. Usuario visita sitio web del tenant
   └─► Widget carga vía <script> → Shadow DOM inicializado

2. Widget solicita config al API Gateway
   └─► GET /api/v1/widget-config/{tenant_id}
   └─► Respuesta: branding, campos lead capture, idioma

3. Pre-chat Lead Capture (si configurado)
   └─► Usuario completa nombre, email, teléfono
   └─► POST /api/v1/leads → validación + persistencia

4. Inicio de conversación
   └─► POST /api/v1/conversations → session_id generado
   └─► Redis: session creada con FSM en estado "greeting"

5. Saludo inicial del bot
   └─► Template de bienvenida del tenant (sin LLM call)

6. Usuario expresa intención
   "Quiero hacer rafting el próximo sábado para 4 adultos"
   └─► POST /api/v1/conversations/{id}/messages

7. Orchestrator procesa mensaje
   a. Intent Classification (modelo ligero)
      └─► intent: "booking_intent", entities: {activity:"rafting", date:"sábado", pax:4}
   b. RAG query si hay preguntas sobre condiciones
   c. Recommendation Engine invocado
      └─► Filtra productos: tipo=aventura, actividad=rafting
      └─► Valida disponibilidad en tiempo real
      └─► Valida idioma guías (si aplica)
      └─► Rankea por score
      └─► Retorna top 3 recomendaciones disponibles

8. Bot presenta recomendaciones
   └─► Respuesta con tarjetas de producto + disponibilidad confirmada
   └─► FSM → estado "recommendation_presented"

9. Usuario selecciona opción
   └─► FSM → estado "product_selected"
   └─► Checkout Service: BookingIntent creado

10. Checkout conversacional
    └─► Bot solicita datos de contacto adicionales
    └─► Bot presenta resumen del pedido
    └─► FSM → estado "awaiting_payment"

11. Pago
    └─► Checkout Service genera payment_url via Payment Gateway
    └─► Usuario paga en iframe/redirect
    └─► Webhook de confirmación de pago recibido
    └─► FSM → estado "confirmed"

12. Confirmación
    └─► Bot envía mensaje de confirmación con número de reserva
    └─► Email de confirmación enviado al usuario

13. Post-chat
    └─► Bot ofrece exportar transcripción
    └─► Usuario acepta → POST /api/v1/transcripts/{id}/export
    └─► Email enviado via Mailhog (dev) / SendGrid (prod)

14. Cierre de sesión
    └─► Transcript guardado en PostgreSQL
    └─► Evento conversation.ended → Pub/Sub
    └─► Analytics actualizados en BigQuery
```

---

## 3.3 Bounded Contexts / Límites de Dominio

| Bounded Context | Responsabilidad | Servicios | Integra con |
|---|---|---|---|
| **Identity & Tenancy** | Quién es el tenant, su configuración y límites | Tenant Manager | Todos |
| **Conversation** | Estado y flujo de la conversación | Orchestrator, Session | Widget, RAG, Recommender |
| **Knowledge** | Qué sabe el sistema del tenant | RAG Service, Catalog Ingestion | Vector Store, Storage |
| **Recommendation** | Qué productos son apropiados | Recommender | Availability API, Products DB |
| **Commerce** | Proceso de compra y pago | Checkout Service | Payment Gateway, Booking |
| **Human Handoff** | Escalado a agente humano | Handoff Service | MS Teams |
| **Analytics & FinOps** | Observabilidad, costos, mejora continua | Observability Layer, FinOps | BigQuery, Monitoring |
| **Content Delivery** | Widget servido al usuario | Widget, CDN | API Gateway |
