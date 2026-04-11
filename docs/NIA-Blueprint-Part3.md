# NIA — Nodo de Inteligencia Activa para Turismo SaaS
## Blueprint Técnico Completo — Parte 3 de 5
**Versión:** 1.0.0 · **Fecha:** Abril 2026

---

# SECCIÓN 8 — Diseño del Flujo Conversacional

## 8.1 Principios del Diseño

1. **Determinismo donde sea posible**: Pre-chat, validación de formularios, checkout y confirmaciones usan lógica determinística. El LLM se usa solo donde el lenguaje natural agrega valor real.
2. **FSM como fuente de verdad**: El estado de la conversación vive en una máquina de estados finitos (FSM) serializada en Redis. Cualquier instancia del Orchestrator puede reanudar cualquier conversación.
3. **Fail-safe**: Cualquier fallo del LLM, RAG o servicios downstream tiene un comportamiento de fallback definido explícitamente.
4. **Auditabilidad**: Cada transición de estado queda registrada con timestamp, evento disparador y datos relevantes.

---

## 8.2 Estados de la FSM

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FSM de Conversación NIA                                │
└─────────────────────────────────────────────────────────────────────────────┘

Estado              Descripción                             Salida posible
────────────────────────────────────────────────────────────────────────────────
IDLE                Sesión creada, no iniciada              → PRE_CHAT | GREETING
PRE_CHAT            Mostrando formulario de lead capture    → GREETING (tras submit)
GREETING            Bot envía saludo inicial (sin LLM)      → DISCOVERY
DISCOVERY           Descubriendo intención del usuario      → RECOMMENDING | FAQ_ANSWER | HANDOFF
FAQ_ANSWER          Respondiendo pregunta operativa (RAG)   → DISCOVERY | RECOMMENDING
RECOMMENDING        Presentando y refinando recomendaciones → PRODUCT_SELECTED | DISCOVERY | HANDOFF
PRODUCT_SELECTED    Usuario eligió un producto              → CHECKOUT_INIT
CHECKOUT_INIT       Recopilando datos de booking            → AWAITING_PAYMENT | DISCOVERY
AWAITING_PAYMENT    URL de pago enviada, esperando webhook  → CONFIRMED | PAYMENT_FAILED
PAYMENT_FAILED      Fallo en el pago, ofrecer retry         → AWAITING_PAYMENT | CLOSED
CONFIRMED           Pago exitoso, enviando confirmación     → POST_CHAT
POST_CHAT           Ofreciendo transcripción, despedida     → CLOSED
HANDOFF_ACTIVE      Agente humano está manejando la sesión  → [estado previo] | CLOSED
CLOSED              Conversación terminada                  → (terminal)
```

---

## 8.3 Definición de Cada Etapa del Flujo

### IDLE → PRE_CHAT

**Trigger**: Widget carga por primera vez para el tenant.
**Lógica (determinística)**:
- Verificar `tenant_config.lead_config.enabled`
- Si `enabled = true` → Transición a PRE_CHAT y mostrar formulario
- Si `enabled = false` → Transición directa a GREETING
**Datos persistidos**: `session.started_at`, `session.page_url`, `session.user_agent`
**Error handling**: Si `tenant_config` no carga → mostrar widget en modo degradado con mensaje de error amigable.

---

### PRE_CHAT — Captura de Lead

**Trigger**: Widget renderiza formulario de lead capture.
**Lógica (determinística, sin LLM)**:
- Renderizar campos según `lead_config.fields`
- Validar cada campo: formato email (regex), formato tel, campos required
- Mostrar consentimiento GDPR si `gdpr_consent_text` configurado
- Al submit: `POST /api/v1/conversations/{id}/lead`
- Persistir lead en DB y asociar a sesión
- Transición a GREETING

**Validaciones cliente:**
```
email     → /^[^\s@]+@[^\s@]+\.[^\s@]+$/
phone     → /^\+?[\d\s\-()]{8,15}$/
full_name → length >= 2, only letters/spaces
```

**Validaciones servidor:**
- Re-validar todos los campos (nunca confiar solo en client-side)
- Verificar que el tenant existe y está activo
- Rate limit: máximo 3 leads por IP por hora por tenant

**Datos persistidos**: `leads` (name, email, phone, custom_fields, gdpr_consent_at), `session.lead_id`

---

### GREETING

**Trigger**: Lead capturado (o PRE_CHAT omitido).
**Lógica (determinística, sin LLM)**:
- Cargar `ui_config.welcome_message` del tenant
- Personalizar con nombre del usuario si lead fue capturado
- Template: `"Hola {name} 👋 {welcome_message}. ¿En qué puedo ayudarte hoy?"`
- Enviar mensaje del bot
- Transición inmediata a DISCOVERY (esperando input del usuario)

**Sin LLM**: El saludo es 100% template. Ahorra tokens y evita variabilidad.

---

### DISCOVERY — Descubrimiento de Intención

**Trigger**: Primer mensaje del usuario (o mensaje después de respuesta de bot).
**Lógica (LLM liviano + lógica determinística)**:

```
Paso 1: Clasificación de intención (LLM liviano: Gemini Flash / llama-3.2-3b)
   → Categorías: booking_intent | faq_query | complaint | out_of_scope | unclear

Paso 2: Extracción de entidades (si booking_intent):
   → activity_type, date, pax_count, language_pref, budget_hint, duration_pref

Paso 3: Routing según intención:
   booking_intent + entidades suficientes → RECOMMENDING
   booking_intent + entidades insuficientes → preguntar clarificación (continuar en DISCOVERY)
   faq_query → FAQ_ANSWER (invocar RAG)
   complaint → evaluar si escalar a HANDOFF
   out_of_scope → responder que no puede ayudar con eso, redirigir
   unclear → solicitar reformulación
```

**Prompt de clasificación de intención (ejemplo):**
```
System: Eres un clasificador de intenciones para un centro turístico.
        Clasifica el mensaje del usuario en una de estas categorías:
        booking_intent, faq_query, complaint, out_of_scope, unclear
        Extrae entidades si aplica.
        Responde SOLO con JSON, sin texto adicional.
        Contexto del tenant: {tenant_name} - {tenant_description}

User: {user_message}

Expected response:
{
  "intent": "booking_intent",
  "confidence": 0.95,
  "entities": {
    "activity_type": "rafting",
    "date": "2026-04-19",
    "pax_count": 4
  }
}
```

**Sin LLM cuando**: El mensaje contiene palabras clave determinísticas (ej: "horario", "precio", "cómo llegar") → ir directo a FAQ_ANSWER sin clasificación LLM.

**Fallback en DISCOVERY**: Si confianza < 0.6 → solicitar reformulación. Máximo 2 reintentos. Al tercer intento fallido → registrar `fallback.detected` y ofrecer handoff.

**Datos persistidos**: `messages` (intent, confidence, entities), `session.fsm_state = "discovery"`

---

### FAQ_ANSWER — Respuesta Operativa via RAG

**Trigger**: Intención clasificada como `faq_query`.
**Lógica (RAG + LLM)**:

```
1. Construir query RAG: mensaje usuario + contexto previo relevante
2. Invocar RAG Service:
   - Retrieval en colección del tenant (Qdrant)
   - Reranking de resultados
   - Verificar score >= CONFIDENCE_THRESHOLD (0.65)
3. Si score >= threshold:
   - Generar respuesta fundamentada con LLM (con fuentes)
   - Adjuntar fragmentos de fuente en metadata del mensaje
4. Si score < threshold:
   - Respuesta: "No tengo información precisa sobre eso."
   - Registrar fallback_query
   - Ofrecer handoff si disponible
5. Transición: DISCOVERY (continuar conversación) o RECOMMENDING si detecta booking_intent en seguimiento
```

**Guardrails RAG (ver Sección 10 para detalle)**:
- Respuesta solo si hay evidencia en documentos del tenant
- Verificar groundedness antes de enviar
- Nunca inventar precios, fechas ni políticas

---

### RECOMMENDING — Motor de Recomendación

**Trigger**: `booking_intent` con entidades suficientes.
**Lógica (híbrida: reglas + semántica + validación en tiempo real)**:

```
1. Invocar Recommendation Engine con entities del intent
2. Motor filtra, rankea y valida disponibilidad
3. Presentar máximo 3 recomendaciones al usuario con:
   - Nombre, descripción breve
   - Precio
   - Horarios disponibles ese día
   - Duración
   - "¿Te interesa alguna de estas opciones?"
4. Si usuario selecciona → PRODUCT_SELECTED
5. Si usuario pide más opciones → Re-invocar con parámetros ajustados
6. Si usuario pide detalles → FAQ_ANSWER con producto específico
7. Si usuario rechaza todas → preguntar qué necesita, DISCOVERY
8. Si no hay productos disponibles → informar + registrar fallback + ofrecer contacto
```

**Estado en Redis:**
```json
{
  "state": "recommending",
  "last_recommendations": ["prod_01", "prod_02", "prod_03"],
  "recommendation_context_id": "rec_01..."
}
```

---

### CHECKOUT_INIT → AWAITING_PAYMENT

**Trigger**: Usuario seleccionó producto (determinístico, no LLM).
**Lógica (determinística)**:

```
1. Confirmar selección: "Elegiste Rafting Grado III el sábado 19 a las 9:00 AM para 4 personas."
2. Solicitar datos de contacto si no están en lead (nombre, email, phone)
3. Mostrar resumen con precio total
4. Solicitar confirmación del usuario: "¿Todo correcto? [Confirmar / Cambiar algo]"
5. Tras confirmación:
   - POST /api/v1/checkout/sessions (con Idempotency-Key)
   - Obtener payment_url
   - Enviar link de pago en el chat
   - FSM → AWAITING_PAYMENT
6. Iniciar timeout: 15 minutos para completar pago
```

**Manejo de objeciones (LLM moderado)**:
- Si usuario dice "¿Es seguro pagar aquí?" → respuesta del RAG sobre políticas de pago
- Si usuario dice "¿Puedo cancelar?" → respuesta del RAG sobre política de cancelación
- Si usuario dice "¿Tienen descuento?" → respuesta determinística según config del tenant

---

### AWAITING_PAYMENT → CONFIRMED o PAYMENT_FAILED

**Trigger**: Webhook de payment gateway.
**Lógica (determinística)**:

```
payment.succeeded webhook:
  - Actualizar CheckoutSession.status = "paid"
  - Crear número de reserva (formato: {tenant_slug}-{año}-{random_6})
  - Enviar email de confirmación al usuario
  - Notificar al sistema del tenant (webhook outgoing si configurado)
  - FSM → CONFIRMED

payment.failed webhook:
  - Actualizar PaymentAttempt.status = "failed"
  - Si attempt_number < 3: FSM → PAYMENT_FAILED, ofrecer reintentar
  - Si attempt_number >= 3: FSM → HANDOFF o CLOSED
```

---

### HANDOFF_ACTIVE

**(Ver Sección 11 para diseño detallado)**

**Trigger**: Complaint, `out_of_scope` repetido, solicitud explícita del usuario, checkout fallido.
- Bot se pausa: no responde mensajes del usuario (excepto acusar recibo)
- Operador responde desde Teams
- Mensajes del operador se reflejan en el chat del usuario en tiempo real
- Al resolver: FSM vuelve al estado previo o a CLOSED

---

### POST_CHAT → CLOSED

**Trigger**: Conversación exitosa (CONFIRMED) o cierre manual.
**Lógica (determinística)**:
```
1. Mensaje de despedida con número de reserva (si aplica)
2. "¿Quieres recibir el registro de esta conversación en tu correo?"
3. Si acepta: POST /api/v1/transcripts/{id}/export
4. FSM → CLOSED
5. Persistir transcript completo en PostgreSQL
6. Emitir evento conversation.ended → Pub/Sub
7. Limpiar sesión Redis (TTL 1 hora por si el usuario recarga)
```

---

## 8.4 Manejo de Errores y Reintentos

| Error | Comportamiento | Reintento |
|---|---|---|
| LLM no responde (timeout) | Respuesta genérica de "dame un momento" + retry automático | Hasta 2 veces, luego fallback determinístico |
| RAG score bajo | Respuesta "no sé" honesta + registrar fallback | Sin reintento automático |
| Servicio de disponibilidad caído | Mostrar producto sin validación en tiempo real, advertencia al usuario | 1 reintento con backoff 500ms |
| Webhook de pago no llega en 15min | Expirar checkout, notificar al usuario, mantener sesión abierta | N/A |
| Teams no disponible | Handoff falla silenciosamente; registrar intento; continuar con bot | Reintentar notificación cada 5min por 30min |
| FSM en estado inválido | Log error + RESET a DISCOVERY | N/A |
| Rate limit excedido | Respuesta 429 al widget, mensaje amigable al usuario | Backoff con timer visible |

---

# SECCIÓN 9 — Motor de Recomendación y Validación en Tiempo Real

## 9.1 Señales de Entrada

| Señal | Fuente | Tipo | Peso |
|---|---|---|---|
| Tipo de actividad solicitada | Intent del usuario | Texto | Alto |
| Fecha solicitada | Entidades extraídas | Fecha | Alto |
| Número de personas | Entidades extraídas | Numérico | Alto |
| Presupuesto indicado | Entidades extraídas | Numérico | Medio |
| Preferencia de idioma | Entidades extraídas + perfil | Texto | Alto |
| Nivel físico indicado | Entidades extraídas | Categórico | Medio |
| Historial de sesión | ConversationSession | Contextual | Bajo |
| Disponibilidad en tiempo real | API de disponibilidad | Binario | Crítico (filtro) |
| Popularidad del producto | Métricas históricas | Numérico | Bajo |
| Margen de precio | TourismProduct | Numérico | Muy bajo |

---

## 9.2 Pipeline del Motor (Pseudocódigo)

```python
async def recommend(intent_data: IntentData, tenant_id: str) -> List[Recommendation]:

    # FASE 1: FILTRADO DURO (determinístico, reglas)
    # ─────────────────────────────────────────────
    candidates = await db.get_active_products(tenant_id=tenant_id)

    # Filtrar por tipo de actividad (obligatorio si especificado)
    if intent_data.activity_type:
        candidates = [p for p in candidates
                      if intent_data.activity_type.lower() in p.tags + [p.category, p.subcategory]]

    # Filtrar por idioma (obligatorio)
    if intent_data.language_preference:
        candidates = [p for p in candidates
                      if intent_data.language_preference in p.languages]

    # Filtrar por capacidad mínima
    if intent_data.pax_count:
        candidates = [p for p in candidates
                      if p.max_capacity >= intent_data.pax_count]

    # Filtrar por presupuesto (si se indicó)
    if intent_data.budget_max:
        pax = intent_data.pax_count or 1
        candidates = [p for p in candidates
                      if p.base_price * pax <= intent_data.budget_max * 1.1]  # 10% tolerancia

    # Si no quedan candidatos tras filtros duros → retornar empty + motivo
    if not candidates:
        return RecommendationResult(products=[], reason="no_products_match_criteria")

    # FASE 2: VALIDACIÓN DE DISPONIBILIDAD EN TIEMPO REAL
    # ────────────────────────────────────────────────────
    # Paralelizar validación de disponibilidad para todos los candidatos
    availability_tasks = [
        check_availability(product_id=p.id, date=intent_data.date, pax=intent_data.pax_count)
        for p in candidates
    ]
    availability_results = await asyncio.gather(*availability_tasks, return_exceptions=True)

    available_candidates = []
    for product, avail in zip(candidates, availability_results):
        if isinstance(avail, Exception):
            # Si availability API falla, marcar como "disponibilidad no verificada"
            # pero NO descartar el producto (degraded mode)
            product.availability_status = "unverified"
            available_candidates.append((product, []))
        elif avail.has_slots:
            product.availability_status = "available"
            available_candidates.append((product, avail.slots))
        # Si no tiene slots, se descarta silenciosamente

    # FASE 3: SCORING (scoring híbrido)
    # ────────────────────────────────────
    scored = []
    for product, slots in available_candidates:
        score = calculate_score(product, intent_data, slots)
        scored.append((product, slots, score))

    # FASE 4: RANKING Y RETORNO TOP-K
    # ────────────────────────────────
    scored.sort(key=lambda x: x[2], reverse=True)
    top_k = scored[:3]

    return RecommendationResult(
        products=[
            Recommendation(
                product=p,
                slots=slots,
                score=score,
                rank_reason=explain_score(p, intent_data, score)
            )
            for p, slots, score in top_k
        ],
        availability_checked_at=datetime.utcnow()
    )


def calculate_score(product, intent, slots) -> float:
    """
    Scoring transparente, determinístico, auditable.
    NO usa LLM para el ranking final.
    """
    score = 0.0

    # Factor 1: Relevancia semántica de la actividad (0-0.40)
    # Si el tipo de actividad coincide exactamente: 0.40
    # Si es subcategoría relacionada: 0.25
    # Si solo tiene tags relacionados: 0.10
    if intent.activity_type:
        if intent.activity_type == product.category:
            score += 0.40
        elif intent.activity_type in product.tags:
            score += 0.25

    # Factor 2: Disponibilidad confirmada (0 o 0.30)
    if product.availability_status == "available":
        score += 0.30
    elif product.availability_status == "unverified":
        score += 0.15  # penalizar parcialmente

    # Factor 3: Idioma exacto disponible en slots (0 o 0.15)
    if intent.language_preference and slots:
        if any(s.guide_language == intent.language_preference for s in slots):
            score += 0.15

    # Factor 4: Ajuste de precio (0-0.10)
    if intent.budget_max and product.base_price:
        pax = intent.pax_count or 1
        total = product.base_price * pax
        if total <= intent.budget_max * 0.8:
            score += 0.10  # muy dentro del presupuesto
        elif total <= intent.budget_max:
            score += 0.05

    # Factor 5: Capacidad disponible (0-0.05)
    if slots:
        max_spots = max(s.spots_left for s in slots)
        if max_spots >= (intent.pax_count or 1) * 2:
            score += 0.05   # mucha disponibilidad

    return round(score, 4)
```

---

## 9.3 Validación de Disponibilidad en Tiempo Real

```python
async def check_availability(product_id: str, date: date, pax: int) -> AvailabilityResult:
    """
    1. Verificar caché Redis (TTL 5 minutos)
    2. Si cache miss → llamar API externa del tenant
    3. Si API externa falla → devolver AvailabilityResult(has_slots=False, error=True)
    4. Guardar resultado en caché
    """
    cache_key = f"availability:{product_id}:{date}:{pax}"
    cached = await redis.get(cache_key)
    if cached:
        return AvailabilityResult.from_json(cached)

    try:
        connector = await get_availability_connector(product_id)
        result = await connector.check(date=date, pax=pax, timeout=3.0)
        await redis.setex(cache_key, 300, result.to_json())  # TTL 5min
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Availability check timeout for {product_id}")
        return AvailabilityResult(has_slots=False, error=True, error_type="timeout")
    except Exception as e:
        logger.error(f"Availability check error for {product_id}: {e}")
        return AvailabilityResult(has_slots=False, error=True, error_type="api_error")
```

**En desarrollo (mock)**: `AVAILABILITY_MOCK=true` → el `check_availability` retorna datos del fixture `data/seed/availability_mock.json` sin llamar a ninguna API externa.

---

## 9.4 Controles de Calidad y Fallback

| Situación | Comportamiento | Efecto en UX |
|---|---|---|
| 0 productos tras filtros | Informar que no hay opciones exactas, ampliar criterio o contactar | No mostrar productos inviables |
| Disponibilidad no verificada | Mostrar producto con aviso "disponibilidad no confirmada" | Transparencia, no bloquear |
| Score máximo < 0.3 | Aun así mostrar, pero con "opción alternativa" en lugar de "recomendación" | Honestidad |
| API de disponibilidad en degraded mode | Mostrar productos con flag, actualizar al confirmar en checkout | Continuidad de servicio |
| Todos los slots para la fecha están llenos | Sugerir fecha alternativa (próxima disponibilidad) | UX proactiva |

---

# SECCIÓN 10 — Sistema RAG con Delimitación Estricta

## 10.1 Fuentes Documentales Soportadas

| Tipo | Formatos | Descripción |
|---|---|---|
| Documentos operativos | PDF, DOCX, Markdown | Políticas, reglamentos, guías de instalaciones |
| FAQs | JSON estructurado, Markdown | Preguntas frecuentes con respuestas validadas |
| Páginas web del tenant | HTML vía URL | Información del sitio oficial |
| Horarios y tarifas | CSV, JSON, Markdown | Tablas de precios y horarios |
| Descripción de instalaciones | Markdown, TXT | Detalles de cada área |
| Políticas de cancelación | PDF, Markdown | Condiciones de reserva |

---

## 10.2 Pipeline de Ingesta

```
DOCUMENTO FUENTE
      │
      ▼
[1. EXTRACCIÓN DE TEXTO]
   └─► PDF → PyMuPDF / pdfplumber
   └─► HTML → BeautifulSoup (limpiar navegación, footers, ads)
   └─► DOCX → python-docx
   └─► Markdown → directo
      │
      ▼
[2. PRE-PROCESAMIENTO]
   └─► Eliminar caracteres especiales, normalizar whitespace
   └─► Detectar idioma (langdetect)
   └─► Calcular checksum SHA-256 (detectar cambios)
   └─► Extraer metadata: título, fecha, sección, tipo
      │
      ▼
[3. CHUNKING SEMÁNTICO]
   └─► Estrategia: RecursiveCharacterTextSplitter
   └─► chunk_size: 512 tokens (aproximado)
   └─► chunk_overlap: 64 tokens
   └─► Separadores respetados: ["\n\n", "\n", ". ", " "]
   └─► Chunks mínimos: 100 tokens (descartar chunks triviales)
   └─► Metadata por chunk: doc_id, chunk_index, section, page_number
      │
      ▼
[4. GENERACIÓN DE EMBEDDINGS]
   └─► Modelo dev: nomic-embed-text-v1.5 (via LM Studio)
   └─► Modelo prod: text-embedding-004 (Vertex AI)
   └─► Dimensión: 768 (nomic) / 768 (text-embedding-004) — compatible
   └─► Batch: 50 chunks por llamada para eficiencia
   └─► Retry: 3 intentos con backoff exponencial
      │
      ▼
[5. ALMACENAMIENTO EN QDRANT]
   └─► Colección: {tenant_id}_knowledge
   └─► Payload almacenado por punto:
       { doc_id, chunk_index, text, section, source_type,
         doc_version, tenant_id, language, created_at }
   └─► Índice HNSW (eficiencia de búsqueda)
      │
      ▼
[6. ACTUALIZACIÓN DE METADATOS]
   └─► knowledge_sources: status="active", chunk_count=N, last_indexed_at=now()
   └─► Emitir evento: knowledge.document_indexed
```

---

## 10.3 Estrategia de Retrieval y Reranking

```
QUERY DEL USUARIO
      │
      ▼
[1. QUERY EXPANSION (opcional, LLM ligero)]
   └─► Generar paráfrasis de la query para mejorar recall
   └─► Solo si query < 10 palabras y muy ambigua
      │
      ▼
[2. BÚSQUEDA VECTORIAL (Qdrant)]
   └─► Embed query con mismo modelo de ingesta
   └─► Búsqueda similarity (cosine) en colección del tenant
   └─► top_k = 8 candidatos
   └─► Filtro obligatorio: tenant_id = {tenant_id} (isolación garantizada)
   └─► Filtro opcional: language = {preferred_language}
      │
      ▼
[3. RERANKING (cross-encoder liviano)]
   └─► Modelo: cross-encoder/ms-marco-MiniLM-L-6-v2 (local, ~80MB)
   └─► Reordena los 8 candidatos por relevancia semántica real
   └─► Selecciona top_k = 3 tras reranking
   └─► Registrar scores originales y scores post-reranking
      │
      ▼
[4. VALIDACIÓN DE GROUNDEDNESS]
   └─► Verificar que al menos 1 chunk tiene score >= CONFIDENCE_THRESHOLD (0.65)
   └─► Si no → activar "no sé" protocol
      │
      ▼
[5. CONSTRUCCIÓN DEL CONTEXTO RAG]
   └─► Concatenar chunks seleccionados con separadores claros
   └─► Incluir metadata: [Fuente: {nombre_doc}, Sección: {sección}]
   └─► Limitar contexto total a max_context_tokens (1500 tokens)
      │
      ▼
[6. GENERACIÓN (LLM)]
   └─► Ver prompt strategy abajo
      │
      ▼
[7. VALIDACIÓN POST-GENERACIÓN]
   └─► Verificar que la respuesta menciona información presente en los chunks
   └─► Si respuesta contiene datos inventados (precios, fechas, nombres) → descartar y responder "no sé"
   └─► Heurística: la respuesta NO puede contener números que no aparecen en los chunks
```

---

## 10.4 Prompt Strategy RAG

```python
RAG_SYSTEM_PROMPT = """
Eres un asistente de {tenant_name}, un centro turístico.
Tu función es responder preguntas sobre las instalaciones, servicios, políticas y experiencias
que ofrece {tenant_name}.

REGLAS ABSOLUTAS:
1. SOLO puedes responder con información que aparezca en los fragmentos de contexto proporcionados.
2. Si la información no está en el contexto, di exactamente: "No tengo información precisa sobre eso en nuestra base de conocimiento. ¿Te gustaría hablar con uno de nuestros asesores?"
3. NUNCA inventes precios, fechas, nombres de personas, ni condiciones.
4. NUNCA respondas sobre temas ajenos a {tenant_name} (clima general, política, tecnología, etc.).
5. Si el contexto es ambiguo, di que no estás seguro y sugiere verificar directamente.
6. Responde siempre en {language}.
7. Sé conciso pero completo. Máximo 3 párrafos por respuesta.

CONTEXTO DISPONIBLE:
{retrieved_chunks}

PREGUNTA DEL USUARIO:
{user_query}
"""
```

**Guardrails adicionales en el prompt:**
```python
GUARDRAILS = [
    "No menciones a la competencia ni compares con otros centros turísticos.",
    "No hagas promesas que no están en el contexto.",
    "Si se pregunta sobre algo de salud o emergencias, siempre recomendar contacto directo.",
    "No proceses solicitudes de acceso a datos de otros usuarios.",
]
```

---

## 10.5 Política de Respuesta: Protocolo "No Sé"

```
Condición de "no sé":
  - score máximo del mejor chunk < CONFIDENCE_THRESHOLD (0.65)
  - OU query claramente fuera del dominio del tenant
  - OU respuesta generada contiene datos no presentes en chunks

Respuesta estándar:
  "No tengo información precisa sobre eso en nuestra base de conocimiento.
   [Opción A: si handoff habilitado] ¿Te gustaría que te conecte con uno de nuestros asesores?
   [Opción B: si handoff deshabilitado] Puedes contactarnos directamente en {contact_info}."

Acción del sistema:
  - Registrar FallbackQuery (query_text, rag_score, session_id, tenant_id)
  - Si tenant tiene Teams config y fallback_notify_enabled: incluir en próximo batch de notificación
```

---

## 10.6 Scoring de Confianza y Trazabilidad

Cada respuesta RAG incluye en metadata:
```json
{
  "rag_metadata": {
    "confidence_score": 0.78,
    "chunks_used": [
      {
        "doc_id": "doc_01...",
        "doc_name": "Política de Cancelación.pdf",
        "chunk_index": 3,
        "section": "Condiciones de Reembolso",
        "retrieval_score": 0.82,
        "rerank_score": 0.91,
        "text_excerpt": "Las cancelaciones realizadas con más de 48 horas de anticipación..."
      }
    ],
    "retrieval_model": "text-embedding-004",
    "generation_model": "gemini-1.5-flash",
    "query_expanded": false,
    "groundedness_check": "passed"
  }
}
```

---

## 10.7 Versionado y Refresh de Documentos

- **Detección de cambios**: Al reingestar un documento, comparar checksum SHA-256. Si es idéntico, no re-embedear.
- **Versionado**: `knowledge_sources.version` incrementa. En Qdrant, los puntos del documento anterior se mantienen hasta que la nueva versión está completamente indexada (transición atómica por batch delete + insert).
- **Refresh automático (Supuesto)**: Cloud Scheduler job diario que verifica si las URLs configuradas tienen contenido actualizado. Si detecta cambio, dispara re-ingesta.
- **Refresh manual**: `POST /api/v1/tenants/{id}/knowledge/{doc_id}/refresh`

---

# SECCIÓN 11 — Handoff Bidireccional con MS Teams

## 11.1 Criterios de Escalado a Humano

| Trigger | Tipo | Descripción |
|---|---|---|
| Queja explícita | Semántico (LLM) | Usuario expresa insatisfacción con tono de queja |
| `out_of_scope` repetido | Determinístico | 2+ mensajes sin poder resolver |
| Solicitud explícita | Determinístico | "Quiero hablar con una persona", "quiero un asesor" |
| Checkout fallido x3 | Determinístico | 3 intentos de pago fallidos |
| Timeout en AWAITING_PAYMENT | Determinístico | Sin pago en 15 minutos |
| Error crítico del sistema | Determinístico | Excepciones no manejadas en el flujo |
| Configuración del tenant | Configurable | Umbral de confianza RAG mínimo configurable |

---

## 11.2 Flujo Completo de Handoff (Secuencia)

```
Usuario                    Orchestrator              Handoff Service           MS Teams
   │                            │                          │                      │
   │ "Quiero hablar con         │                          │                      │
   │  una persona"              │                          │                      │
   │──────────────────────────►│                          │                      │
   │                            │ classify: escalation     │                      │
   │                            │ trigger                  │                      │
   │                            │──────────────────────────►                     │
   │                            │                          │ 1. Crear HandoffCase  │
   │                            │                          │    (status: pending)  │
   │                            │                          │                      │
   │                            │                          │ 2. Generar resumen    │
   │                            │                          │    de conversación   │
   │                            │                          │    (LLM liviano)     │
   │                            │                          │                      │
   │                            │                          │ 3. POST Teams:       │
   │                            │                          │    Adaptive Card     │
   │                            │                          │──────────────────────►
   │                            │                          │                      │ Card muestra:
   │                            │                          │                      │ - Nombre usuario
   │                            │                          │                      │ - Resumen chat
   │                            │                          │                      │ - Botón "Atender"
   │◄──────────────────────────│                          │                      │
   │ "Un asesor te atenderá     │                          │                      │
   │  en breve. Estamos         │                          │                      │
   │  notificando..."           │                          │                      │
   │                            │                          │                      │
   │  [Bot se pausa - no        │                          │                      │
   │   responde más mensajes    │                          │                      │
   │   hasta resolver]          │                          │                      │
   │                            │                          │                      │
   │                            │                          │ ◄─────────── Agente hace click
   │                            │                          │              "Atender" en card
   │                            │                          │                      │
   │                            │                          │ 4. Actualizar case:   │
   │                            │                          │    status: assigned   │
   │                            │                          │    agent_teams_id: X  │
   │                            │                          │                      │
   │◄──────────────────────────│                          │                      │
   │ "¡Hola! Soy María, te     │                          │                      │
   │  estoy atendiendo..."      │                          │                      │
   │ (mensaje del agente)       │                          │                      │
   │                            │                          │                      │
   │ "Hola María, mi consulta   │                          │                      │
   │  es sobre el descuento..." │                          │                      │
   │──────────────────────────►│                          │                      │
   │                            │ relay message            │                      │
   │                            │──────────────────────────►                     │
   │                            │                          │ 5. POST Teams:       │
   │                            │                          │    message to thread │
   │                            │                          │──────────────────────►
   │                            │                          │                      │ Agente escribe
   │                            │                          │                      │ en Teams thread
   │                            │                          │◄─────────────────────│
   │                            │                          │ 6. Incoming webhook   │
   │                            │                          │    (Teams → NIA)     │
   │                            │                          │                      │
   │◄──────────────────────────│                          │                      │
   │ Respuesta del agente       │                          │                      │
   │ (relay al chat)            │                          │                      │
   │                            │                          │                      │
   │                            │                          │ 7. Agente hace click │
   │                            │                          │    "Resolver"        │
   │                            │                          │◄─────────────────────│
   │                            │                          │ 8. POST /handoffs/   │
   │                            │                          │    {id}/resolve       │
   │                            │                          │                      │
   │                            │◄─────────────────────────                      │
   │                            │ handoff.resolved event   │                      │
   │                            │ FSM → previous state     │                      │
   │                            │ o CLOSED                 │                      │
   │◄──────────────────────────│                          │                      │
   │ "¿Hay algo más en que     │                          │                      │
   │  pueda ayudarte?"          │                          │                      │
```

---

## 11.3 Adaptive Card de Teams para Handoff

```json
{
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "🔔 Nueva consulta pendiente - Parque Aventura Andina",
      "weight": "Bolder",
      "size": "Medium"
    },
    {
      "type": "FactSet",
      "facts": [
        { "title": "Usuario", "value": "María González" },
        { "title": "Email", "value": "maria@email.com" },
        { "title": "Motivo", "value": "Solicitud explícita de asesor" },
        { "title": "Duración del chat", "value": "4 minutos, 12 mensajes" },
        { "title": "Hora", "value": "10 de abril 2026, 10:35 AM" }
      ]
    },
    {
      "type": "TextBlock",
      "text": "**Resumen de la conversación:**",
      "weight": "Bolder"
    },
    {
      "type": "TextBlock",
      "text": "El usuario consultó sobre disponibilidad para rafting el sábado 19 para 4 personas. Se presentaron 3 opciones, seleccionó Rafting Grado III pero solicitó un descuento por grupo familiar que el sistema no pudo ofrecer.",
      "wrap": true
    }
  ],
  "actions": [
    {
      "type": "Action.Submit",
      "title": "✅ Atender ahora",
      "data": { "action": "accept_handoff", "handoff_id": "hdff_01..." }
    },
    {
      "type": "Action.Submit",
      "title": "👁 Ver conversación completa",
      "data": { "action": "view_transcript", "session_id": "ses_01..." }
    }
  ]
}
```

---

## 11.4 Integración Técnica con MS Teams

**Protocolo**: MS Teams Bot Framework SDK + Incoming Webhooks para notificaciones; Graph API para gestión de threads si se requiere mayor control.

**Configuración por tenant (en Secret Manager):**
```
nia/{env}/tenant/{id}/teams_bot_app_id       → App ID del bot registrado
nia/{env}/tenant/{id}/teams_bot_app_password → Bot password
nia/{env}/tenant/{id}/teams_handoff_webhook  → Incoming webhook URL del canal
nia/{env}/tenant/{id}/teams_fallback_webhook → Incoming webhook URL para fallbacks
```

**Validación de mensajes entrantes de Teams:**
- Verificar token HMAC en header `Authorization` de los webhooks entrantes
- Validar que el `tenant_id` en el webhook corresponde al handoff activo
- Rate limit: máximo 100 mensajes/minuto del canal Teams por tenant

**Manejo de concurrencia:**
- Redis lock `handoff_lock:{session_id}` para garantizar que solo un agente toma el handoff
- TTL del lock: 5 segundos (tiempo de respuesta a la aceptación del agente)

**Expiración de handoff sin respuesta:**
- Si no hay agente en `handoff_config.response_timeout_minutes` (default: 15 min):
  - Actualizar HandoffCase.status = "expired"
  - Notificar al usuario: "Nuestros asesores no están disponibles en este momento. Te contactaremos a tu email."
  - Enviar email al lead (si capturado) con resumen
  - FSM → CLOSED

---

## 11.5 Notificación de Fallback Queries a Teams

**Diferente al handoff**: Es una notificación periódica (batch), no en tiempo real.

```
Proceso:
1. Cloud Scheduler ejecuta job según frecuencia (daily/weekly) configurada por tenant
2. Fallback Tracker Service consulta FallbackQueries no resueltas del periodo
3. Agrupa por similitud semántica (evitar repeticiones obvias)
4. Genera digest con: query, frecuencia, fecha última ocurrencia
5. Envía card a Teams con formato:

┌─────────────────────────────────────────────────────┐
│ 📊 Resumen semanal de preguntas sin respuesta       │
│ Parque Aventura Andina - Semana del 7-13 abril      │
├─────────────────────────────────────────────────────┤
│ 1. "¿Tienen estacionamiento para vans?" (8 veces)   │
│ 2. "¿Aceptan grupos de empresas?" (5 veces)         │
│ 3. "¿Tienen actividades para niños de 5 años?" (4)  │
├─────────────────────────────────────────────────────┤
│ [Agregar respuestas a la base de conocimiento]       │
│ [Ver todas en portal NIA]                            │
└─────────────────────────────────────────────────────┘
```

**Acción del equipo**: Accede al Admin Portal NIA → Sección Fallbacks → Agrega respuestas → Dispara re-ingesta al RAG.
