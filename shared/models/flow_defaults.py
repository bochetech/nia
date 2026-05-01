"""
Flujo de transiciones e intents default del orquestador NIA.

DEFAULT_INTENTS  → intents que el LLM puede clasificar (si el tenant no configura los suyos).
DEFAULT_TRANSITIONS → tabla FSM que conecta cada intent con una acción/skill.

Se usan cuando el tenant NO tiene una configuración personalizada en
fsm_config.intents / fsm_config.transitions.
"""

from shared.models.domain import EntityField, FlowTransition, IntentDefinition, SkillConfig

# ──────────────────────────────────────────────────────────────────
# Intents por defecto  (los 8 originales de NIA)
# ──────────────────────────────────────────────────────────────────

DEFAULT_INTENTS: list[IntentDefinition] = [
    IntentDefinition(
        key="human_request",
        name="Solicitud de agente humano",
        description="El usuario pide explícitamente hablar con una persona, agente o asesor humano.",
        examples=[
            "Quiero hablar con alguien",
            "¿Puedo hablar con un humano?",
            "Necesito un asesor",
            "Pásame con una persona real",
        ],
        priority=10,
    ),
    IntentDefinition(
        key="nps_response",
        name="Respuesta NPS",
        description="El usuario responde con un número (1-5) o calificación a una encuesta de satisfacción.",
        examples=[
            "5",
            "3 estrellas",
            "Le doy un 4",
            "Mi puntuación es 2",
        ],
        priority=9,
    ),
    IntentDefinition(
        key="complaint",
        name="Queja",
        description="El usuario expresa queja, frustración o insatisfacción con el servicio.",
        examples=[
            "Esto es inaceptable",
            "Estoy muy molesto con el servicio",
            "Quiero hacer un reclamo",
            "La experiencia fue pésima",
        ],
        priority=8,
    ),
    IntentDefinition(
        key="booking_intent",
        name="Intención de reserva",
        description="Intención clara de reservar, comprar o confirmar una actividad o servicio.",
        examples=[
            "Quiero reservar un tour",
            "Me gustaría comprar entradas para mañana",
            "Reserva para 4 personas el sábado",
        ],
        priority=5,
    ),
    IntentDefinition(
        key="product_inquiry",
        name="Consulta de producto",
        description="Preguntas sobre qué actividades/productos existen, cuáles recomiendas, o precios generales.",
        examples=[
            "¿Qué actividades tienen?",
            "¿Cuáles son sus mejores tours?",
            "¿Cuánto cuesta la excursión?",
            "Recomiéndame algo para hacer",
        ],
        priority=4,
    ),
    IntentDefinition(
        key="faq_query",
        name="Pregunta frecuente",
        description="Preguntas sobre horarios, ubicación, políticas, qué incluye, cómo llegar u otra información factual.",
        examples=[
            "¿Cuál es el horario de apertura?",
            "¿Dónde están ubicados?",
            "¿Qué incluye el tour?",
            "¿Cómo llego desde Santiago?",
        ],
        priority=3,
    ),
    IntentDefinition(
        key="out_of_scope",
        name="Fuera de dominio",
        description="Temas no relacionados con el negocio del tenant (turismo, actividades, etc.).",
        examples=[
            "¿Quién ganó el partido de fútbol?",
            "Ayúdame con mi tarea de matemáticas",
            "¿Cuál es la capital de Francia?",
        ],
        priority=1,
    ),
    IntentDefinition(
        key="unclear",
        name="Intención ambigua",
        description="Mensaje ambiguo que no encaja claramente en ninguna otra categoría. Incluye saludos simples.",
        examples=[
            "Hola",
            "hmm no sé",
            "ok",
            "Sí",
        ],
        priority=0,
    ),
]

DEFAULT_TRANSITIONS: list[FlowTransition] = [
    # ── Solicitud explícita de hablar con humano ──────────────────────────────
    FlowTransition(
        intent="human_request",
        from_states=[],
        to_state="handoff_active",
        action="handoff",
    ),

    # ── Respuesta NPS (solo desde post_chat) ─────────────────────────────────
    FlowTransition(
        intent="nps_response",
        from_states=["post_chat"],
        to_state="closed",
        action="nps",
    ),

    # ── Queja ─────────────────────────────────────────────────────────────────
    # El handler de complaint evalúa internamente si escala a handoff.
    FlowTransition(
        intent="complaint",
        from_states=[],
        to_state="__same__",       # el handler decide el estado final
        action="complaint",
    ),

    # ── Fuera de dominio ──────────────────────────────────────────────────────
    FlowTransition(
        intent="out_of_scope",
        from_states=[],
        to_state="__same__",
        action="static_reply",
        static_message=(
            "Lo siento, eso está fuera de mis capacidades. "
            "Puedo ayudarte con información sobre nuestras actividades turísticas y reservas."
        ),
    ),

    # ── Pregunta de conocimiento → RAG ────────────────────────────────────────
    FlowTransition(
        intent="faq_query",
        from_states=[],
        to_state="faq_answer",
        action="faq",
    ),

    # ── Intención de reserva → Recommender ───────────────────────────────────
    FlowTransition(
        intent="booking_intent",
        from_states=[],
        to_state="recommending",
        action="recommend",
    ),

    # ── Consulta de producto → Recommender ───────────────────────────────────
    FlowTransition(
        intent="product_inquiry",
        from_states=[],
        to_state="recommending",
        action="recommend",
    ),

    # ── Intención ambigua → pedir más detalles ────────────────────────────────
    FlowTransition(
        intent="unclear",
        from_states=[],
        to_state="discovery",
        action="discovery",
    ),
]


# ──────────────────────────────────────────────────────────────────
# Skill configs por defecto  (turismo)
# ──────────────────────────────────────────────────────────────────

DEFAULT_SKILLS: list[SkillConfig] = [
    # ── Skills con acción sistémica real ────────────────────────────────────
    SkillConfig(
        action="faq",
        name="FAQ — Base de conocimiento",
        description=(
            "Consulta semánticamente la base de conocimiento del tenant indexada en Qdrant "
            "y genera una respuesta fundamentada con el LLM (RAG completo: retrieval + reranking + generation). "
            "Úsalo para preguntas informativas: ubicación, políticas, descripción de productos/experiencias, etc. "
            "Si la confianza de recuperación es baja, devuelve el fallback_message de RAG Config "
            "y suma al contador de preguntas sin respuesta (puede disparar handoff automático)."
        ),
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "error": "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?",
        },
    ),
    SkillConfig(
        action="recommend",
        name="Recomendador de productos",
        description=(
            "Llama al Recommender service que consulta la tabla products en PostgreSQL "
            "y devuelve un ranking filtrado por entidades extraídas del mensaje (fecha, tipo, presupuesto, personas). "
            "Úsalo cuando el usuario pide sugerencias, comparaciones o quiere elegir entre opciones. "
            "Si no hay entidades suficientes, devuelve el top-K genérico del catálogo. "
            "Nota: En el futuro este skill se conectará a Bokun/Fareharbor — el cambio irá en el Recommender service, no aquí."
        ),
        entity_schema=[
            EntityField(
                name="activity_type",
                type="string",
                description="Tipo de actividad o experiencia que busca el usuario",
                required=False,
                examples=["tour de vinos", "visita guiada", "experiencia gastronómica"],
            ),
            EntityField(
                name="date",
                type="date",
                description="Fecha deseada en formato YYYY-MM-DD. Convierte fechas relativas ('mañana', 'el sábado').",
                required=False,
                examples=["2025-03-15", "mañana"],
            ),
            EntityField(
                name="pax_count",
                type="integer",
                description="Número de personas que participarán",
                required=False,
                examples=["2", "4", "un grupo de 6"],
            ),
            EntityField(
                name="budget_max",
                type="float",
                description="Presupuesto máximo en moneda local",
                required=False,
                examples=["50000", "100"],
            ),
            EntityField(
                name="time_of_day",
                type="enum",
                description="Momento preferido del día",
                required=False,
                enum_values=["morning", "afternoon", "evening"],
            ),
        ],
        preparation_prompt=(
            "Extrae las preferencias del usuario para buscar actividades. "
            "Convierte fechas relativas (mañana, próximo fin de semana) a YYYY-MM-DD. "
            "Extrae el número de personas y presupuesto máximo si se mencionan."
        ),
        response_templates={
            "success": "Te recomiendo estas opciones:",
            "empty": "No encontré actividades que coincidan exactamente. ¿Te gustaría que amplíe la búsqueda?",
            "error": "Estoy teniendo dificultades para acceder al catálogo. ¿Puedes intentarlo de nuevo?",
            "followup": "¿Te interesa alguna de estas opciones? Puedo darte más detalles.",
        },
    ),
    SkillConfig(
        action="handoff",
        name="Escalar a asesor humano",
        description=(
            "Crea un caso en el Handoff service (POST /v1/handoff/cases) con el resumen del contexto "
            "de la conversación y pausa el bot. "
            "Úsalo cuando el usuario pide explícitamente hablar con una persona, o como destino de "
            "escalado automático por quejas repetidas o preguntas sin respuesta. "
            "El Handoff service puede notificar a Chatwoot, Microsoft Teams u otros canales según configuración."
        ),
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "connecting": "Te estoy conectando con uno de nuestros asesores. Por favor espera un momento. 🙏",
            "unavailable": "Entiendo que prefieres hablar con una persona, pero la atención humana no está disponible ahora. ¿Puedo intentar ayudarte yo?",
        },
    ),
    SkillConfig(
        action="nps",
        name="Encuesta NPS",
        description=(
            "Captura una puntuación numérica (1–5) del usuario al finalizar la conversación. "
            "Parsea el número del mensaje, lo guarda en la sesión (session.nps_score) "
            "y cierra la conversación (estado CLOSED). "
            "Nota: Se activa automáticamente si nps_enabled=true en FSM Config al cerrar sesión. "
            "Los mensajes de pregunta, agradecimiento e instrucción son totalmente configurables."
        ),
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "ask": "¿Podrías calificar tu experiencia del 1 al 5? (1 = muy malo, 5 = excelente)",
            "thanks_high": "¡Muchas gracias por tu puntuación! 🙏 Ha sido un placer. ¡Hasta pronto!",
            "thanks_low": "Gracias por tu opinión, la tendremos en cuenta para mejorar. ¡Hasta pronto!",
            "invalid": "Por favor responde con un número del 1 al 5.",
        },
    ),
    # ── Bokun integration skill ─────────────────────────────────────────────
    SkillConfig(
        action="bokun",
        name="Bokun — Experiencias y disponibilidad",
        description=(
            "Consulta el catálogo de actividades en Bokun (GET /activity.json/active-ids + detalles) "
            "y la disponibilidad real en tiempo real (POST /activity.json/{id}/availabilities). "
            "Úsalo cuando el usuario pregunta por tours, experiencias, qué actividades hay disponibles "
            "o quiere saber la disponibilidad para una fecha concreta. "
            "Si el usuario especificó una fecha, filtra mostrando solo experiencias con slots abiertos."
        ),
        entity_schema=[
            EntityField(
                name="date",
                type="date",
                description="Fecha deseada en formato YYYY-MM-DD. Convierte fechas relativas ('mañana', 'el sábado').",
                required=False,
                examples=["2026-06-15", "mañana", "el próximo sábado"],
            ),
            EntityField(
                name="pax_count",
                type="integer",
                description="Número de personas",
                required=False,
                examples=["2", "4"],
            ),
            EntityField(
                name="activity_type",
                type="string",
                description="Tipo de actividad o experiencia buscada",
                required=False,
                examples=["tour de vinos", "cata", "visita guiada"],
            ),
        ],
        preparation_prompt=(
            "Extrae la fecha deseada y el número de personas del mensaje del usuario. "
            "Convierte fechas relativas (mañana, próximo sábado, en 3 días) a formato YYYY-MM-DD."
        ),
        response_templates={
            "success": "Aquí tienes las experiencias disponibles:",
            "empty": "No encontré disponibilidad para esa fecha. ¿Quieres probar con otra fecha?",
            "error": "No pude consultar la disponibilidad en este momento. ¿Puedes intentarlo de nuevo?",
        },
    ),
]
