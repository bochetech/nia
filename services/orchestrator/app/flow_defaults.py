"""
Flujo de transiciones e intents default del orquestador NIA.

DEFAULT_INTENTS  → intents que el LLM puede clasificar (si el tenant no configura los suyos).
DEFAULT_TRANSITIONS → tabla FSM que conecta cada intent con una acción/skill.

Se usan cuando el tenant NO tiene una configuración personalizada en
fsm_config.intents / fsm_config.transitions.
"""

from shared.models.domain import FlowTransition, IntentDefinition

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
