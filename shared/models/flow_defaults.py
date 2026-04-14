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
    SkillConfig(
        action="recommend",
        name="Recomendador de experiencias",
        description="Busca y recomienda actividades turísticas del catálogo según las preferencias del usuario.",
        entity_schema=[
            EntityField(
                name="activity_type",
                type="string",
                description="Tipo de actividad turística que busca el usuario (tour, excursión, degustación, etc.)",
                required=False,
                examples=["tour de vinos", "excursión", "trekking", "visita guiada"],
            ),
            EntityField(
                name="date",
                type="date",
                description="Fecha deseada para la actividad en formato YYYY-MM-DD",
                required=False,
                examples=["2025-03-15", "mañana", "el próximo sábado"],
            ),
            EntityField(
                name="pax_count",
                type="integer",
                description="Número de personas que participarán",
                required=False,
                examples=["2", "4", "un grupo de 6"],
            ),
            EntityField(
                name="language_preference",
                type="string",
                description="Idioma preferido para la actividad o guía",
                required=False,
                examples=["español", "inglés", "portugués"],
            ),
            EntityField(
                name="budget_max",
                type="float",
                description="Presupuesto máximo en la moneda local",
                required=False,
                examples=["50000", "100 dólares"],
            ),
            EntityField(
                name="physical_level",
                type="enum",
                description="Nivel de exigencia física deseado",
                required=False,
                enum_values=["low", "moderate", "high"],
            ),
            EntityField(
                name="duration_preference_hours",
                type="integer",
                description="Duración preferida de la actividad en horas",
                required=False,
                examples=["2", "medio día", "día completo"],
            ),
            EntityField(
                name="time_of_day",
                type="enum",
                description="Momento del día preferido para la actividad",
                required=False,
                enum_values=["morning", "afternoon", "evening"],
            ),
        ],
        preparation_prompt=(
            "Extrae las preferencias del usuario para buscar actividades turísticas. "
            "Presta atención a fechas relativas (mañana, próximo fin de semana) y conviértelas "
            "a formato YYYY-MM-DD. Si el usuario menciona un presupuesto, extrae el número sin moneda."
        ),
        response_templates={
            "success": "Te recomiendo estas opciones:",
            "empty": "En este momento no encontré actividades que coincidan exactamente con lo que buscas. ¿Te gustaría que amplíe la búsqueda?",
            "error": "Estoy teniendo dificultades para acceder al catálogo. ¿Puedes intentarlo de nuevo en un momento?",
            "followup": "¿Te interesa alguna de estas opciones? Puedo darte más detalles o ayudarte a reservar.",
        },
    ),
    SkillConfig(
        action="faq",
        name="Preguntas frecuentes (RAG)",
        description="Consulta la base de conocimiento del tenant para responder preguntas informativas.",
        entity_schema=[],  # No necesita entidades — pasa la query completa al RAG
        preparation_prompt="",
        response_templates={
            "error": "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?",
        },
    ),
    SkillConfig(
        action="discovery",
        name="Descubrimiento / saludo",
        description="Maneja mensajes ambiguos o de saludo usando RAG y LLM para dar una respuesta contextual.",
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "fallback": "¡Hola! 👋 ¿En qué puedo ayudarte hoy? Puedo recomendarte actividades, darte información o ayudarte con reservas.",
        },
    ),
    SkillConfig(
        action="complaint",
        name="Gestión de quejas",
        description="Registra quejas del usuario y evalúa si es necesario escalar a un asesor humano.",
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "ack": "Lamento mucho la inconveniencia. ¿Puedes contarme más sobre lo que ocurrió para poder ayudarte mejor?",
        },
    ),
    SkillConfig(
        action="handoff",
        name="Escalado a humano",
        description="Transfiere la conversación a un asesor humano.",
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "connecting": "Te estoy conectando con uno de nuestros asesores que podrá ayudarte mejor. Por favor espera un momento. 🙏",
            "unavailable": "Entiendo que prefieres hablar con una persona, pero el servicio de atención humana no está disponible en este momento. ¿Puedo intentar ayudarte yo?",
        },
    ),
    SkillConfig(
        action="nps",
        name="Encuesta NPS",
        description="Captura la puntuación de satisfacción (1-5) del usuario.",
        entity_schema=[],
        preparation_prompt="",
        response_templates={
            "ask": "¿Podrías calificar tu experiencia del 1 al 5? (1 = muy malo, 5 = excelente)",
            "thanks_high": "¡Muchas gracias por tu puntuación! 🙏 Ha sido un placer acompañarte. ¡Hasta pronto!",
            "thanks_low": "Gracias por tu opinión, la tendremos muy en cuenta para mejorar. ¡Hasta pronto!",
            "invalid": "Por favor, responde con un número del 1 al 5 para calificar tu experiencia.",
        },
    ),
    SkillConfig(
        action="static_reply",
        name="Respuesta estática",
        description="Devuelve un mensaje fijo configurado en la transición, sin llamar a ningún servicio.",
        entity_schema=[],
        preparation_prompt="",
        response_templates={},
    ),
]
