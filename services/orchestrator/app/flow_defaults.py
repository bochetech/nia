"""
Flujo de transiciones default del orquestador NIA.

Estas transiciones replican exactamente el comportamiento hardcodeado original
de _route_by_intent() en fsm.py. Se usan cuando el tenant NO tiene una tabla
de transiciones personalizada en fsm_config.transitions.

Estructura de cada transición:
  intent       → IntentType.value que dispara la transición
  from_states  → estados FSM desde los que aplica ([] = cualquier estado)
  to_state     → estado FSM resultante
  action       → qué hace el orquestador (ver FlowTransition.action en domain.py)
"""

from shared.models.domain import FlowTransition

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
