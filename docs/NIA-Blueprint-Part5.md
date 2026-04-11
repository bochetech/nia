# NIA — Nodo de Inteligencia Activa para Turismo SaaS
## Blueprint Técnico Completo — Parte 5 de 5
**Versión:** 1.0.0 · **Fecha:** Abril 2026

---

# SECCIÓN 16 — Observabilidad y Mejora Continua

## 16.1 Estrategia de Observabilidad (OpenTelemetry First)

**Decisión**: Todos los servicios instrumentan con OpenTelemetry (OTEL). El collector central envía a Cloud Logging, Cloud Monitoring y BigQuery. Esto evita vendor lock-in en observabilidad.

```
Servicios Python → OTEL SDK (traces + metrics + logs)
     │
     ▼
[OTEL Collector] (Cloud Run sidecar o standalone)
     │
     ├──► Cloud Logging (logs estructurados)
     ├──► Cloud Monitoring (métricas operativas)
     ├──► Cloud Trace (distributed tracing)
     └──► BigQuery (analytics)
```

---

## 16.2 Qué se Registra por Categoría

### Conversaciones
```json
{
  "event": "conversation.message_processed",
  "session_id": "ses_01...",
  "tenant_id": "ten_01...",
  "message_index": 5,
  "role": "assistant",
  "intent_detected": "booking_intent",
  "intent_confidence": 0.94,
  "fsm_state_before": "discovery",
  "fsm_state_after": "recommending",
  "latency_ms": 1243,
  "tokens_used": 312,
  "model_used": "gemini-1.5-flash",
  "rag_invoked": false,
  "cache_hit": false,
  "estimated_cost_usd": 0.0023,
  "timestamp": "2026-04-10T12:00:01Z"
}
```

### Decisiones del RAG
```json
{
  "event": "rag.query_processed",
  "session_id": "ses_01...",
  "tenant_id": "ten_01...",
  "query": "¿Cuáles son los horarios de atención?",
  "chunks_retrieved": 3,
  "top_chunk_score": 0.87,
  "confidence": 0.87,
  "groundedness_check": "passed",
  "response_length_chars": 243,
  "sources_used": ["doc_01:chunk_3", "doc_02:chunk_1"],
  "latency_retrieval_ms": 45,
  "latency_generation_ms": 890,
  "model_used": "gemini-1.5-flash",
  "timestamp": "2026-04-10T12:00:02Z"
}
```

### Recomendaciones
```json
{
  "event": "recommendation.generated",
  "session_id": "ses_01...",
  "tenant_id": "ten_01...",
  "input_intent": "booking_intent",
  "input_entities": {"activity": "rafting", "date": "2026-04-19", "pax": 4},
  "candidates_before_filter": 12,
  "candidates_after_filter": 4,
  "candidates_available": 3,
  "top_recommendation_id": "prod_01...",
  "top_recommendation_score": 0.94,
  "availability_api_latency_ms": 320,
  "availability_cache_hit": false,
  "user_selected_rank": 1,
  "timestamp": "2026-04-10T12:00:03Z"
}
```

### Handoffs
```json
{
  "event": "handoff.escalated",
  "handoff_id": "hdff_01...",
  "session_id": "ses_01...",
  "tenant_id": "ten_01...",
  "trigger_type": "complaint",
  "trigger_message": "Esto es inaceptable...",
  "conversation_length_messages": 8,
  "time_to_assign_seconds": null,
  "teams_notification_sent": true,
  "teams_notification_latency_ms": 240,
  "timestamp": "2026-04-10T12:05:00Z"
}
```

---

## 16.3 Métricas de Negocio

| Métrica | Descripción | Objetivo |
|---|---|---|
| **Conversion Rate** | % conversaciones que terminan en booking confirmado | > 8% (Supuesto) |
| **Lead Capture Rate** | % visitantes que completan pre-chat | > 60% |
| **Conversation Completion Rate** | % conversaciones que no se abandonan | > 75% |
| **Checkout Abandonment Rate** | % que llegan a checkout pero no pagan | < 40% |
| **Handoff Rate** | % conversaciones escaladas a humano | < 15% |
| **Handoff Resolution Rate** | % handoffs resueltos por agente | > 85% |
| **Time to Handoff Assignment** | Tiempo desde escalado hasta agente | < 5 min |
| **Revenue Generated** | Suma de ventas confirmadas atribuibles a NIA | KPI de negocio |
| **Fallback Rate** | % mensajes donde el bot no pudo responder | < 10% |

---

## 16.4 Métricas Técnicas

| Métrica | Herramienta | Alerta |
|---|---|---|
| Latencia P50/P95/P99 del Orchestrator | Cloud Monitoring | P95 > 3s → alerta |
| Error rate por servicio | Cloud Monitoring | > 1% → alerta |
| Disponibilidad de servicios | Cloud Monitoring | < 99.5% → alerta |
| Uso de CPU/memoria Cloud Run | Cloud Monitoring | > 80% → scale up |
| Conexiones activas PostgreSQL | Cloud Monitoring | > 80% del pool → alerta |
| Redis memory usage | Cloud Monitoring | > 80% → alerta |
| Pub/Sub message age | Cloud Monitoring | > 5min → alerta |
| Cloud Build success rate | Cloud Build | < 95% → revisión |

---

## 16.5 Métricas de IA

| Métrica | Descripción | Objetivo |
|---|---|---|
| **RAG Precision@3** | % chunks recuperados que son relevantes | > 80% |
| **RAG Groundedness Rate** | % respuestas que pasan la validación | > 95% |
| **Intent Classification Accuracy** | % intents correctamente clasificados | > 90% |
| **Semantic Cache Hit Rate** | % queries respondidas desde caché | > 30% |
| **Model Routing Efficiency** | % tareas asignadas al modelo correcto | > 90% |
| **Cost per Conversation** | USD promedio por conversación completa | < $0.04 |
| **Token Efficiency** | Ratio output/input tokens | Monitoreo |
| **LLM Latency P95** | Percentil 95 de latencia LLM | < 4s |

---

## 16.6 KPIs de Conversión y Precisión

```
Tablero de Conversión (semanal):
  Visitas al widget:          10,000
  Pre-chat completados:        6,200  (62%) ← Lead Capture Rate
  Conversaciones iniciadas:    6,000  (97% de pre-chats)
  Llegaron a recomendación:    3,800  (63%)
  Seleccionaron producto:      1,900  (50%)
  Llegaron a checkout:         1,500  (79%)
  Pagaron exitosamente:          900  (60%)
  ─────────────────────────────────────────
  Conversion rate total:         9.0%  (900/10,000)

Tablero de Precisión RAG (semanal):
  Queries totales:              4,200
  Respondidas con docs:         3,800  (90%)
  "No sé" (bajo confidence):     400  (10%) ← Fallback Rate
  Groundedness passed:          3,700  (97%)
  Fallbacks resueltos (doc add):  150  (37%)
```

---

## 16.7 Loop de Mejora Continua

```
1. DETECCIÓN
   └─► Fallback Tracker identifica queries sin respuesta
   └─► Semantic clustering de queries similares
   └─► Notificación semanal a Teams del tenant

2. ANÁLISIS
   └─► Equipo del centro turístico revisa fallbacks en Admin Portal
   └─► Clasifica: "Debe estar en doc" / "Fuera de scope" / "Ya está cubierto"

3. ACCIÓN
   └─► Para "Debe estar en doc":
       - Admin sube nuevo documento o actualiza existente
       - POST /api/v1/tenants/{id}/knowledge/ingest
       - Pipeline re-embeda y actualiza Qdrant
   └─► Para prompts que producen respuestas incorrectas:
       - NIA ops actualiza prompt base (no self-service de tenant)
       - Testing con golden set antes de deploy

4. VALIDACIÓN
   └─► Próxima semana: verificar que esas queries ahora tienen respuesta
   └─► Métricas: ¿Bajó el fallback rate? ¿Subió groundedness?

5. GOLDEN SET
   └─► Conjunto de queries de referencia con respuesta esperada
   └─► Evaluado automáticamente en CI/CD antes de cada deploy
   └─► Si precision cae > 5% → bloquear deploy
```

---

# SECCIÓN 17 — Roadmap de Implementación

## Fase 0 — Entorno Local Funcional (Semanas 1-3)

**Alcance:**
- Docker Compose completo con todos los servicios locales operativos
- LM Studio integrado como proveedor de IA
- Dataset semilla cargado
- Widget embebible funcionando localmente (sin theming avanzado)
- Conversación básica: pre-chat → greeting → discovery → FAQ (RAG) → cierre
- Tests E2E básicos del flujo

**Dependencias:** Equipo disponible; hardware con 16GB RAM mínimo; LM Studio instalado; modelos base descargados (llama-3.2-3b, nomic-embed)

**Riesgos:** LM Studio puede ser lento en hardware modesto sin GPU → usar modelos pequeños; Qdrant local puede requerir ajuste de memoria

**Quick wins:** Ver el widget funcionar con RAG en < 1 semana

**Criterios de salida:**
- `docker compose up` levanta todos los servicios sin error
- Widget en localhost:3000 puede iniciar conversación
- RAG responde preguntas basadas en documentos del dataset semilla
- Tests de integración pasan al 80%

---

## Fase 1 — MVP Funcional Completo (Semanas 4-10)

**Alcance:**
- Todos los flujos conversacionales completos (pre-chat, discovery, recomendación, checkout, confirmación, post-chat)
- Motor de recomendación con validación de disponibilidad (mock)
- Handoff a Teams (integración real)
- Captura y exportación de leads
- Exportación de transcripciones
- Multi-tenancy básico (2-3 tenants de prueba)
- API HATEOAS completa (todos los endpoints core)
- Widget con theming por tenant
- Admin Portal básico (config de branding y leads)
- Deploy en GCP staging (Cloud Run + Cloud SQL + Memorystore)

**Dependencias:** Fase 0 completada; credenciales MS Teams; cuenta GCP staging; proveedor de pagos (Stripe sandbox)

**Riesgos:** Integración bidireccional Teams más compleja de lo esperado; latencia de LLM en staging puede diferir de local

**Quick wins:** Primera reserva end-to-end completada (aunque sea en staging)

**Criterios de salida:**
- Flujo completo de usuario desde widget hasta confirmación de pago
- Handoff Teams funcional bidireccional
- 3 tenants operando en staging sin interferencia entre sí
- Costo por conversación < $0.08 en staging (margen para MVP)

---

## Fase 2 — Hardening y Funcionalidades Avanzadas (Semanas 11-18)

**Alcance:**
- Semantic cache implementada (objetivo: 30% hit rate)
- Model routing completo (Flash vs Pro según task_type)
- FinOps dashboard operativo
- Fallback Tracker con notificación Teams configurable
- Ingesta automática de catálogo vía webhook
- Sistema de versionado de documentos RAG
- Observabilidad completa (OTEL + Grafana + Looker Studio)
- Rate limiting granular por tenant
- Mejoras UX widget (microinteracciones, mobile full-screen)
- Admin Portal completo (catálogo, knowledge base, analytics)
- Tests de carga (Locust: 100 usuarios concurrentes)
- Onboarding de primeros 5 tenants reales

**Dependencias:** Fase 1 completada; primeros clientes confirmados; disponibilidad de conectores de availability API reales

**Riesgos:** Calidad de datos de disponibilidad de API reales puede ser inconsistente; semantic cache puede tener falsos positivos (respuestas similares pero no idénticas)

**Quick wins:** Reducción de costos con caché; primeros ingresos reales

**Criterios de salida:**
- Costo/conversación ≤ $0.04 con caché activa
- 5 tenants reales activos
- Uptime 99.5% en producción durante 30 días
- Fallback rate < 15%

---

## Fase 3 — Enterprise Grade (Semanas 19-30)

**Alcance:**
- SSO para Admin Portal (Google Workspace / Active Directory)
- Multi-región GCP (para latencia en LATAM + resiliencia)
- SLA formal para enterprise (99.9% uptime)
- CMEK (Customer Managed Encryption Keys) para tenants enterprise
- Audit log exportable (SIEM integration)
- Conectores nativos para PMS populares (ej. Rezdy, Fareharbor)
- A/B testing de flujos conversacionales
- Modelo fine-tuned para turismo (Supuesto: si el volumen de datos lo justifica)
- API de webhooks outgoing (notificaciones al sistema del tenant)
- Marketplace de conectores
- Dashboard analytics de conversión para tenant (self-service)

**Dependencias:** Fase 2 completada; suficientes conversaciones para fine-tuning (>10k); contratos enterprise

**Riesgos:** Fine-tuning puede no mejorar significativamente si el RAG está bien diseñado; conectores PMS son muy heterogéneos

**Quick wins:** Contratos enterprise; reducción de soporte por mejor onboarding

**Criterios de salida:**
- 20+ tenants activos
- Primer contrato enterprise firmado
- Costo/conversación ≤ $0.025 con fine-tuning y caché combinados

---

# SECCIÓN 18 — Backlog Inicial Priorizado

## Épica 1: Infraestructura de Desarrollo Local

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E1-1 | Como dev, quiero ejecutar todos los servicios NIA localmente con un solo comando `docker compose up` | 🔴 P0 | — | Todos los servicios arrancan y responden healthcheck en < 2 min |
| E1-2 | Como dev, quiero que el backend use LM Studio como proveedor de IA sin modificar código | 🔴 P0 | E1-1 | Cambiar `MODEL_PROVIDER=lmstudio` en .env es suficiente |
| E1-3 | Como dev, quiero tener un dataset semilla que cargue automáticamente | 🔴 P0 | E1-1 | `./scripts/seed.sh` carga tenant, productos y documentos en < 1 min |
| E1-4 | Como dev, quiero hot-reload en todos los servicios Python y el widget | 🟠 P1 | E1-1 | Cambio en código se refleja sin rebuild |

---

## Épica 2: Motor Conversacional Core

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E2-1 | Como usuario, quiero iniciar una conversación con el bot | 🔴 P0 | E1-1 | `POST /api/v1/conversations` retorna session_id en < 500ms |
| E2-2 | Como usuario, quiero enviar mensajes y recibir respuestas en streaming | 🔴 P0 | E2-1 | SSE retorna tokens en < 3s primer token |
| E2-3 | Como usuario, quiero que el bot detecte mi intención de reservar | 🔴 P0 | E2-2 | Intent "booking_intent" detectado con >85% accuracy en golden set |
| E2-4 | Como sistema, quiero que la FSM persista en Redis | 🔴 P0 | E2-1 | Estado se recupera tras restart del servicio |
| E2-5 | Como usuario, quiero respuestas sobre el centro turístico (FAQ RAG) | 🔴 P0 | E1-3 | Responde preguntas del dataset semilla con score > 0.65 |
| E2-6 | Como sistema, quiero que las respuestas RAG sean solo del dominio del tenant | 🔴 P0 | E2-5 | 0 respuestas sobre temas externos en test de 50 queries |

---

## Épica 3: Captura de Leads

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E3-1 | Como admin, quiero configurar los campos del pre-chat | 🟠 P1 | E2-1 | `PATCH /api/v1/tenants/{id}/config` actualiza lead_config |
| E3-2 | Como usuario, quiero completar el formulario de pre-chat | 🟠 P1 | E3-1 | Lead persiste en DB con datos validados |
| E3-3 | Como sistema, quiero validar formato de email y teléfono | 🟠 P1 | E3-2 | Campos inválidos retornan error específico |

---

## Épica 4: Motor de Recomendación

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E4-1 | Como usuario, quiero recibir recomendaciones de productos relevantes | 🔴 P0 | E2-3 | Top 3 productos rankeados retornados en < 2s |
| E4-2 | Como sistema, quiero validar disponibilidad antes de recomendar | 🔴 P0 | E4-1 | Solo se recomiendan productos con disponibilidad confirmada o aviso |
| E4-3 | Como sistema, quiero filtrar por idioma y capacidad | 🔴 P0 | E4-1 | Productos sin idioma/capacidad requerida excluidos |
| E4-4 | Como admin, quiero ingresar productos al catálogo | 🟠 P1 | — | `POST /api/v1/catalog/products` persiste producto correctamente |

---

## Épica 5: Checkout Conversacional

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E5-1 | Como usuario, quiero seleccionar un producto y avanzar al checkout | 🔴 P0 | E4-1 | FSM transiciona a CHECKOUT_INIT tras selección |
| E5-2 | Como usuario, quiero obtener una URL de pago | 🔴 P0 | E5-1 | `POST /api/v1/checkout/sessions` retorna payment_url en < 2s |
| E5-3 | Como sistema, quiero confirmar el pago via webhook | 🔴 P0 | E5-2 | Webhook de Stripe actualiza estado y FSM → CONFIRMED |
| E5-4 | Como usuario, quiero recibir confirmación con número de reserva | 🟠 P1 | E5-3 | Bot envía mensaje con número de reserva tras pago exitoso |
| E5-5 | Como sistema, quiero manejar idempotencia en checkout | 🟠 P1 | E5-2 | Doble envío del mismo Idempotency-Key no crea 2 sesiones |

---

## Épica 6: Handoff MS Teams

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E6-1 | Como sistema, quiero detectar quejas y escalar a humano | 🟠 P1 | E2-3 | Trigger detectado en < 1s; bot se pausa |
| E6-2 | Como sistema, quiero notificar a Teams con adaptive card | 🟠 P1 | E6-1 | Card llega al canal Teams en < 5s con resumen de conversación |
| E6-3 | Como agente, quiero responder desde Teams y que el usuario lo vea | 🟠 P1 | E6-2 | Mensaje en Teams aparece en widget en < 3s |
| E6-4 | Como sistema, quiero que el handoff expire si no hay respuesta | 🟡 P2 | E6-2 | Tras timeout configurable, usuario recibe mensaje de no disponible |

---

## Épica 7: Widget Frontend

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E7-1 | Como desarrollador del sitio anfitrión, quiero integrar el widget con 1 línea de código | 🔴 P0 | E2-1 | `<script data-tenant-id="...">` funciona en sitio de prueba |
| E7-2 | Como usuario, quiero que el widget no rompa los estilos del sitio | 🔴 P0 | E7-1 | Shadow DOM aisla CSS; no hay conflictos en WordPress de prueba |
| E7-3 | Como admin, quiero que el widget refleje los colores de mi marca | 🟠 P1 | E7-1 | Cambio de `primary_color` en config se refleja en widget en < 5min |
| E7-4 | Como usuario mobile, quiero usar el widget en pantalla completa | 🟠 P1 | E7-1 | En <480px el widget ocupa 100vw×100dvh |
| E7-5 | Como usuario, quiero exportar mi transcripción por email | 🟡 P2 | E5-4 | Email llega a Mailhog (dev) / inbox real (prod) con transcripción |

---

## Épica 8: Multi-Tenancy

| # | Historia | Prioridad | Dependencias | Criterio de Aceptación |
|---|---|---|---|---|
| E8-1 | Como sistema, quiero crear un nuevo tenant automáticamente | 🔴 P0 | E1-1 | `POST /api/v1/tenants` crea schema DB + colección Qdrant en < 2min |
| E8-2 | Como sistema, quiero que datos de un tenant no sean accesibles por otro | 🔴 P0 | E8-1 | Test cross-tenant: query con tenant A nunca retorna datos de tenant B |
| E8-3 | Como admin, quiero ver y editar la configuración de mi tenant | 🟠 P1 | E8-1 | Admin Portal muestra y guarda config correctamente |

---

# SECCIÓN 19 — Riesgos y Mitigaciones

## 19.1 Riesgos Funcionales

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El bot no puede resolver >20% de las queries (RAG calidad insuficiente) | Media | Alto | Invertir en curación del dataset semilla; pipeline de fallback sólido; proceso de mejora continua desde el primer tenant |
| Recomendaciones inviables (disponibilidad desincronizada) | Alta | Alto | Caché de disponibilidad con TTL corto; advertencia al usuario si no verificada; confirmar en checkout |
| Checkout abandonado por fricción del flujo | Media | Alto | A/B testing de flujo; minimizar pasos; progress indicator conversacional |
| Usuarios omiten el pre-chat (ad-blocker, JS desactivado) | Baja | Bajo | Degraded mode: widget funciona sin pre-chat si lead_capture es opcional |

---

## 19.2 Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| LM Studio en dev es muy lento (sin GPU) | Alta | Medio | Usar modelos quantizados Q4; documentar requisitos mínimos de hardware; aceptar latencia >3s en dev |
| Divergencia de comportamiento entre modelo local y Vertex AI | Media | Alto | Golden set de evaluación ejecutado contra ambos proveedores en CI; documentar diferencias |
| Shadow DOM incompatible con sitio anfitrión específico | Media | Medio | Testing en top 5 CMS; lista de problemas conocidos y workarounds; soporte de onboarding |
| Webhook Teams no llega (firewall corporativo) | Media | Medio | Documentar requisitos de red; fallback por polling si webhook no disponible |
| Cross-tenant data leak en PostgreSQL | Baja | Crítico | Defense in depth: JWT + RLS + validación en código; tests de penetración antes de prod |

---

## 19.3 Riesgos Operacionales

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Equipo desconoce GCP | Media | Medio | Capacitación en GCP fundamentals; IaC con Terraform para no depender de configuración manual |
| Migración de schema en producción sin downtime | Alta | Alto | Migrations con herramienta (Alembic); estrategia Blue/Green; siempre backward compatible primero |
| Tenant con datos de mala calidad en RAG | Alta | Medio | Validación en ingesta; advertencia al admin si documento muy corto o sin contenido relevante |
| Carga inesperada en evento masivo (temporada alta) | Media | Alto | Auto-scaling Cloud Run; load testing antes de temporadas; alertas de capacidad |

---

## 19.4 Riesgos de Costos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Tenant con uso anómalo (bot abuse, bucle de mensajes) | Media | Alto | Rate limiting por sesión; max tokens por conversación; circuit breaker si costo/hora supera umbral |
| Modelo Pro usado en tareas simples (bug en routing) | Baja | Medio | Test unitario del model router; alertas si % Pro > 15% |
| Semantic cache con muchos false negatives (no cachea) | Media | Bajo | Ajustar threshold; monitorear hit rate semanal |
| Vertex AI precios cambian | Baja | Medio | Abstracción de proveedor permite cambiar a OpenAI o Anthropic en días |

---

## 19.5 Riesgos de Seguridad

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Prompt injection exitosa por usuario malicioso | Baja | Medio | Sanitización de input; guardrails en prompt; LLM no ejecuta acciones críticas solo por texto |
| API key de tenant expuesta | Baja | Alto | Nunca en código; Secret Manager; rotación bajo demanda; alertas de acceso anómalo |
| PII en logs | Media | Medio | Masking de PII en el logger middleware; log scrubbing pipeline en Cloud Logging |
| DDoS en endpoint del widget | Media | Medio | Cloud Armor; rate limiting por IP; el endpoint widget-config es estático y cacheable |

---

## 19.6 Riesgos de Calidad de Datos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Tenant no tiene documentos de calidad suficiente para RAG | Alta | Alto | Kit de onboarding con plantillas de documentos; sesión de kickoff para carga inicial de conocimiento |
| Productos sin datos de disponibilidad en tiempo real | Alta | Medio | Mock de disponibilidad en MVP; marcar productos sin conector como "consultar disponibilidad" |
| Catálogo desactualizado (producto eliminado no removido) | Media | Medio | Soft delete en productos; validación de estado activo en recomendador |

---

## 19.7 Riesgos de UX y Adopción

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Usuarios no confían en pagar via widget de chat | Media | Alto | Checkout redirect a página segura del proveedor (no iframe); indicadores de seguridad visibles |
| Widget percibido como intrusivo | Media | Medio | Configurable: auto-open desactivado por defecto; positioning configurable |
| Staff del centro turístico no usa Teams activamente | Media | Medio | Documentar proceso; capacitación en onboarding; escalada por email como fallback |
| Tenant espera personalización del flujo conversacional (no incluido) | Alta | Medio | Documentar claramente qué es configurable y qué no; roadmap de personalización en Fase 3 |

---

# SECCIÓN 20 — Recomendación Final

## 20.1 Arquitectura Sugerida: Por Qué Esta y No Otra

**La arquitectura propuesta para NIA combina tres principios que no deben sacrificarse:**

### Principio 1: Local-first development
El equipo de ingeniería debe poder trabajar sin depender de créditos cloud desde el día 1. LM Studio + Docker Compose resuelve esto completamente. Cualquier arquitectura que fuerce dependencia de Vertex AI desde el inicio generará costos innecesarios, ralentizará el ciclo de desarrollo y acoplará el diseño a un proveedor desde el inicio.

### Principio 2: Complejidad justificada progresivamente
En MVP, el Orchestrator puede ser un servicio único. La separación en 11 microservicios es el estado objetivo, no el punto de partida. Comenzar con un monolito modular que respete las interfaces API definidas permite avanzar rápido y refactorizar cuando el volumen lo justifique.

**Recomendación concreta**: En Fase 0 y 1, consolidar en 3 servicios:
- `nia-core` (Orchestrator + RAG + Recommender + Checkout)
- `nia-tenant` (Tenant Manager + Catalog Ingestion)
- `nia-integrations` (Handoff + Transcript + Fallback)

Refactorizar a los 11 microservicios en Fase 2 cuando haya tráfico real que justifique la separación.

### Principio 3: RAG como capacidad diferencial
El RAG bien diseñado (con guardrails estrictos y pipeline de mejora continua) es la capacidad que más directamente impacta la percepción del cliente sobre la calidad del sistema. Invertir en el pipeline de ingesta, la curación del dataset semilla y el protocolo de "no sé" honesto genera más confianza que cualquier funcionalidad adicional.

---

## 20.2 Trade-offs Principales

| Trade-off | Decisión | Por qué | Costo de la alternativa |
|---|---|---|---|
| **GCP vs multi-cloud** | GCP exclusivo | Simplidad operacional, integración nativa, Vertex AI sin egress | Mayor vendor lock-in; migración costosa si GCP falla |
| **PostgreSQL vs Firestore** | PostgreSQL | Modelo relacional, transacciones ACID, RLS nativo, skill del equipo | Firestore: más simple pero sin SQL, sin RLS nativo |
| **Monolito modular vs microservicios desde día 1** | Monolito modular en Fase 0-1 | Velocidad de desarrollo; complejidad justificada progresivamente | Microservicios desde el inicio = overhead de ops sin beneficio real |
| **Shadow DOM vs iFrame** | Shadow DOM | Mejor UX, comunicación directa, sin limitaciones de iframe | iFrame: más aislado pero peor UX, comunicación via postMessage |
| **Caché semántica vs caché de respuestas exactas** | Caché semántica (Qdrant) | Mayor hit rate para queries similares pero no idénticas | Caché exacta: más simple, menor hit rate |
| **Handoff via Bot Framework vs solo Incoming Webhook** | Incoming Webhook para notificación + Graph API para threading | Balance entre simplicidad y funcionalidad bidireccional real | Solo webhook: unidireccional, no permite relay de respuestas del agente |
| **Qdrant vs Vertex AI Vector Search** | Qdrant en dev, Vertex AI en prod | Qdrant local gratuito para dev; Vertex AI gestionado para prod | Usar Qdrant también en prod: viable pero más ops |
| **LangChain vs orquestación custom** | LangChain SOLO para pipeline RAG | Evitar over-dependencia en LangChain para orquestación conversacional (FSM custom es más controlable y testeable) | LangChain para todo: abstracciones que ocultan comportamiento, difícil de debuggear |

---

## 20.3 Decisiones Más Importantes (No Negociables)

1. **La FSM del Orchestrator debe ser determinística y persistible en Redis.** No delegar el estado conversacional al LLM (stateless). Es el error arquitectónico más común y el más costoso de corregir.

2. **El Model Provider Adapter debe estar en su propio servicio/módulo desde el inicio.** Si se acopla el llamado a Vertex AI en el Orchestrator, cambiar de proveedor requiere tocar múltiples servicios.

3. **Los guardrails del RAG son no negociables.** Un sistema que alucina precios, políticas o disponibilidades destruye la confianza del usuario y del tenant en horas. El protocolo "no sé" honesto es preferible a responder mal.

4. **Multi-tenancy debe ser correcto desde el MVP.** Un cross-tenant data leak en producción es un incidente de seguridad grave. RLS + validación en código + tests específicos desde el primer día.

5. **La caché de disponibilidad es obligatoria.** Sin caché, cada mensaje del usuario en el flujo de recomendación genera N llamadas a APIs externas en paralelo. En hora punta, esto satura tanto los sistemas externos como el costo de operación.

---

## 20.4 Camino Recomendado

```
MES 1 — FUNDAMENTOS
  ✓ Docker Compose funcional con LM Studio
  ✓ Modelo de datos definido y migrado
  ✓ Conversación básica (discovery → FAQ via RAG)
  ✓ Widget embebible en localhost
  Equipo: 2 backend devs + 1 frontend dev

MES 2 — FLUJO COMPLETO
  ✓ Recomendación con mock de disponibilidad
  ✓ Checkout con Stripe sandbox
  ✓ Pre-chat / Lead capture
  ✓ Tests E2E del flujo completo
  Equipo: +1 QA

MES 3 — INTEGRACIÓN Y DEPLOY STAGING
  ✓ Handoff bidireccional Teams real
  ✓ Deploy en GCP staging (Cloud Run)
  ✓ 2 tenants reales en staging
  ✓ Observabilidad básica
  Equipo: mismo

MES 4-5 — HARDENING Y PRIMER CLIENTE
  ✓ Semantic cache
  ✓ Model routing FinOps
  ✓ Admin Portal operativo
  ✓ Primer tenant real en producción
  ✓ Costo/conversación validado ≤ $0.04

MES 6+ — ESCALA
  ✓ 5-10 tenants
  ✓ Fallback Tracker + mejora continua
  ✓ Documentación de API pública
  ✓ Onboarding self-service
```

**Equilibrio velocidad / costo / escalabilidad:**

| Dimensión | Decisión en MVP | Decisión en Escala |
|---|---|---|
| **Velocidad** | Monolito modular, menos servicios | Refactorizar cuando el volumen justifique |
| **Costo** | Modelos Flash por defecto, caché semántica desde Fase 2 | Fine-tuning + caché avanzada en Fase 3 |
| **Escalabilidad** | Cloud Run con auto-scaling, Redis para estado | Sharding de Qdrant, BigQuery para analytics, múltiples regiones |
| **Calidad** | RAG bien curado, FSM determinística | Golden set en CI, A/B testing de prompts |

---

## 20.5 El Riesgo que Más Importa Mitigar Primero

**El peor escenario no es técnico: es que el sistema responda con confianza cosas incorrectas.**

Una respuesta incorrecta sobre precios, políticas de cancelación o disponibilidad, entregada con el tono seguro de un LLM, genera:
- Reservas en condiciones que el centro no ofrece
- Frustración del usuario al llegar al destino
- Pérdida de reputación del centro turístico
- Potencial responsabilidad legal

**Mitigación**: El protocolo "no sé" honesto, los guardrails de groundedness y el proceso de mejora continua de la base de conocimiento son las capacidades más importantes que hay que construir bien desde el inicio, antes que cualquier funcionalidad adicional de conversión.

---

*Fin del Blueprint Técnico NIA v1.0.0*

---

# ÍNDICE DE ARCHIVOS

| Archivo | Contenido |
|---|---|
| `NIA-Blueprint-Part1.md` | Secciones 0-3: Arquitectura local, Resumen ejecutivo, Mapa de requerimientos, Arquitectura de alto nivel |
| `NIA-Blueprint-Part2.md` | Secciones 4-7: Microservicios, Multi-tenancy, Modelo de datos, APIs HATEOAS |
| `NIA-Blueprint-Part3.md` | Secciones 8-11: Flujo conversacional, Motor de recomendación, RAG, Handoff Teams |
| `NIA-Blueprint-Part4.md` | Secciones 12-15: Widget frontend, Seguridad, Infraestructura GCP, FinOps |
| `NIA-Blueprint-Part5.md` | Secciones 16-20: Observabilidad, Roadmap, Backlog, Riesgos, Recomendación final |
