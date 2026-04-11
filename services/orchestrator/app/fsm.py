"""
FSM (Finite State Machine) del orquestador NIA.
Implementa las transiciones de estado para la conversación.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.intent import detect_intent
from app.session import get_or_create_session, save_session, transition_state
from app.settings import OrchestratorSettings
from shared.models.domain import (
    ConversationFSMState,
    ConversationTurn,
    IntentEntities,
    IntentType,
    RecommendationResult,
    SessionState,
)
from shared.utils.logging import get_logger
from shared.utils.sanitizer import sanitize_user_message

logger = get_logger(__name__)

MAX_HISTORY_TURNS = 10  # Máximo de turnos a mantener en Redis


class FSMResult:
    """Resultado de procesar un mensaje en el FSM."""
    def __init__(
        self,
        response_text: str,
        new_state: ConversationFSMState,
        session: SessionState,
        recommendations: RecommendationResult | None = None,
        rag_answer: str | None = None,
        handoff_triggered: bool = False,
        checkout_url: str | None = None,
        show_lead_form: bool = False,
        metadata: dict[str, Any] | None = None,
    ):
        self.response_text = response_text
        self.new_state = new_state
        self.session = session
        self.recommendations = recommendations
        self.rag_answer = rag_answer
        self.handoff_triggered = handoff_triggered
        self.checkout_url = checkout_url
        self.show_lead_form = show_lead_form
        self.metadata = metadata or {}


async def process_message(
    *,
    message: str,
    tenant_id: str,
    session_id: str,
    tenant_config: dict,
    settings: OrchestratorSettings,
) -> FSMResult:
    """
    Punto de entrada del FSM.
    Carga la sesión, detecta intent, transiciona el estado y genera respuesta.
    """
    # 1. Sanitizar input
    clean_message, is_suspicious = sanitize_user_message(message)
    if is_suspicious:
        logger.warning(
            "suspicious_message",
            tenant_id=tenant_id,
            session_id=session_id,
            snippet=message[:80],
        )

    # 2. Cargar sesión
    session = await get_or_create_session(tenant_id, session_id)

    # 3. Si hay handoff activo, no procesar (el bot está pausado)
    if session.fsm_state == ConversationFSMState.HANDOFF_ACTIVE:
        return FSMResult(
            response_text="En este momento un asesor humano está atendiendo tu consulta. Por favor espera.",
            new_state=ConversationFSMState.HANDOFF_ACTIVE,
            session=session,
            handoff_triggered=False,
        )

    # 4. Captura de lead (si no está capturado y el lead form está habilitado)
    lead_config = tenant_config.get("lead_config", {})
    if (
        lead_config.get("enabled", True)
        and not session.lead_captured
        and session.fsm_state == ConversationFSMState.IDLE
    ):
        await transition_state(session, ConversationFSMState.PRE_CHAT)
        return FSMResult(
            response_text=tenant_config.get("ui_config", {}).get("welcome_message", "Hola 👋 ¿En qué puedo ayudarte?"),
            new_state=ConversationFSMState.PRE_CHAT,
            session=session,
            show_lead_form=True,
        )

    # 5. Detectar intent usando historial real
    history = _build_history_for_intent(session)
    intent, confidence, entities = await detect_intent(
        message=clean_message,
        conversation_history=history,
        settings=settings,
        tenant_id=tenant_id,
    )

    session.last_intent = intent
    session.last_entities = entities.model_dump(exclude_none=True)
    session.messages_count += 1

    # 6. Routing por intent
    result = await _route_by_intent(
        message=clean_message,
        intent=intent,
        confidence=confidence,
        entities=entities,
        session=session,
        tenant_config=tenant_config,
        settings=settings,
    )

    # 7. Guardar turno en historial de la sesión (en Redis)
    _append_turn(session, user_msg=clean_message, assistant_msg=result.response_text, intent=intent)
    await save_session(session)

    # 8. Fire-and-forget: persistir mensajes en transcript service
    asyncio.create_task(
        _persist_transcript(
            tenant_id=tenant_id,
            session_id=session_id,
            user_message=clean_message,
            assistant_message=result.response_text,
            intent=intent.value,
            confidence=confidence,
            settings=settings,
        )
    )

    return result


async def _route_by_intent(
    *,
    message: str,
    intent: IntentType,
    confidence: float,
    entities: IntentEntities,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
) -> FSMResult:
    tenant_id = session.tenant_id
    rag_config = tenant_config.get("rag_config", {})
    limits_config = tenant_config.get("limits_config", {})
    tenant_name = tenant_config.get("ui_config", {}).get("chat_title", "el centro de turismo")

    # Solicitud explícita de hablar con humano
    if intent == IntentType.HUMAN_REQUEST:
        if limits_config.get("handoff_enabled", True):
            return await _trigger_handoff(
                session,
                trigger_type="explicit_request",
                reason=f"El usuario solicitó explícitamente hablar con un humano. Mensaje: {message[:200]}",
                settings=settings,
            )
        return FSMResult(
            response_text="Entiendo que prefieres hablar con una persona, pero el servicio de atención humana no está disponible en este momento. ¿Puedo intentar ayudarte yo?",
            new_state=session.fsm_state,
            session=session,
        )

    # Respuesta NPS (en estado POST_CHAT)
    if intent == IntentType.NPS_RESPONSE or session.fsm_state == ConversationFSMState.POST_CHAT:
        return await _handle_nps(message=message, session=session)

    if intent == IntentType.COMPLAINT:
        return await _handle_complaint(session, settings, message)

    if intent == IntentType.OUT_OF_SCOPE:
        return FSMResult(
            response_text="Lo siento, eso está fuera de mis capacidades. Puedo ayudarte con información sobre nuestras actividades turísticas y reservas.",
            new_state=session.fsm_state,
            session=session,
        )

    if intent == IntentType.FAQ_QUERY:
        return await _handle_faq(
            query=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
        )

    if intent in (IntentType.BOOKING_INTENT, IntentType.PRODUCT_INQUIRY):
        return await _handle_recommendation_flow(
            message=message,
            entities=entities,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
        )

    # UNCLEAR — respuesta genérica + continúa en estado actual
    return FSMResult(
        response_text=(
            "Entiendo. ¿Puedes darme más detalles? Por ejemplo, ¿qué tipo de actividad buscas, "
            "para cuántas personas y en qué fecha?"
        ),
        new_state=ConversationFSMState.DISCOVERY,
        session=session,
    )


async def _handle_faq(
    *,
    query: str,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    tenant_name: str,
) -> FSMResult:
    """Consulta al RAG service."""
    rag_config = tenant_config.get("rag_config", {})
    collection_name = f"nia_tenant_{session.tenant_id}_knowledge"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.rag_service_url}/v1/rag/query",
                json={
                    "query": query,
                    "tenant_id": session.tenant_id,
                    "collection_name": collection_name,
                    "tenant_name": tenant_name,
                },
            )
            resp.raise_for_status()
            rag_result = resp.json()["data"]
    except Exception as exc:
        logger.error("rag_call_failed", error=str(exc))
        return FSMResult(
            response_text=rag_config.get("fallback_message", "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?"),
            new_state=ConversationFSMState.FAQ_ANSWER,
            session=session,
        )

    answer = rag_result.get("answer", "")
    is_fallback = rag_result.get("is_fallback", False)

    if is_fallback:
        # Incrementar contador de no resueltos
        session.metadata = getattr(session, "metadata", {}) or {}
        unresolved_count = session.metadata.get("unresolved_count", 0) + 1
        session.metadata["unresolved_count"] = unresolved_count
        await save_session(session)

        if unresolved_count >= settings.unresolved_threshold and tenant_config.get("limits_config", {}).get("handoff_enabled", True):
            return await _trigger_handoff(session, "unresolved", "Múltiples preguntas sin respuesta en la base de conocimiento", settings)

    await transition_state(session, ConversationFSMState.FAQ_ANSWER)
    return FSMResult(
        response_text=answer,
        new_state=ConversationFSMState.FAQ_ANSWER,
        session=session,
        rag_answer=answer,
    )


async def _handle_recommendation_flow(
    *,
    message: str,
    entities: IntentEntities,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
) -> FSMResult:
    """Llama al recommender y construye respuesta con productos."""
    tenant_schema = f"tenant_{session.tenant_id}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{settings.recommender_url}/v1/recommendations",
                json={
                    "tenant_id": session.tenant_id,
                    "tenant_schema": tenant_schema,
                    "entities": entities.model_dump(mode="json"),
                    "top_k": 3,
                },
            )
            resp.raise_for_status()
            rec_result = RecommendationResult(**resp.json()["data"])
    except Exception as exc:
        logger.error("recommender_call_failed", error=str(exc))
        return FSMResult(
            response_text="Estoy teniendo dificultades para acceder al catálogo. ¿Puedes intentarlo de nuevo en un momento?",
            new_state=session.fsm_state,
            session=session,
        )

    if not rec_result.recommendations:
        return FSMResult(
            response_text="En este momento no encontré actividades que coincidan exactamente con lo que buscas. ¿Te gustaría que amplíe la búsqueda?",
            new_state=ConversationFSMState.DISCOVERY,
            session=session,
        )

    # Guardar contexto de recomendación en sesión
    session.last_recommendations = [r.product_id for r in rec_result.recommendations]
    await transition_state(session, ConversationFSMState.RECOMMENDING)

    # Construir texto de respuesta
    lines = ["Te recomiendo estas opciones:"]
    for item in rec_result.recommendations:
        price_str = f"${item.base_price:,.0f} {item.currency}"
        avail_str = f"✅ Disponible" if item.availability_status == "available" else "📅 Consultar disponibilidad"
        lines.append(f"\n**{item.rank}. {item.name}**")
        lines.append(f"   💰 {price_str} | ⏱ {item.duration_minutes or '?'} min | {avail_str}")
        if item.available_slots:
            times = ", ".join(s.time for s in item.available_slots[:2])
            lines.append(f"   🕐 Horarios: {times}")

    lines.append("\n¿Te interesa alguna de estas opciones? Puedo darte más detalles o ayudarte a reservar.")

    return FSMResult(
        response_text="\n".join(lines),
        new_state=ConversationFSMState.RECOMMENDING,
        session=session,
        recommendations=rec_result,
    )


async def _handle_complaint(
    session: SessionState,
    settings: OrchestratorSettings,
    message: str,
) -> FSMResult:
    """Registra queja y evalúa si hacer handoff."""
    session.metadata = getattr(session, "metadata", {}) or {}
    complaint_count = session.metadata.get("complaint_count", 0) + 1
    session.metadata["complaint_count"] = complaint_count
    await save_session(session)

    if complaint_count >= settings.complaint_handoff_threshold:
        return await _trigger_handoff(
            session,
            trigger_type="complaint",
            reason=f"Cliente expresó queja. Mensaje: {message[:200]}",
            settings=settings,
        )

    return FSMResult(
        response_text="Lamento mucho la inconveniencia. ¿Puedes contarme más sobre lo que ocurrió para poder ayudarte mejor?",
        new_state=session.fsm_state,
        session=session,
    )


async def _trigger_handoff(
    session: SessionState,
    trigger_type: str,
    reason: str,
    settings: OrchestratorSettings,
) -> FSMResult:
    """Inicia el handoff al servicio de handoff."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.handoff_url}/v1/handoff/cases",
                json={
                    "tenant_id": session.tenant_id,
                    "session_id": session.session_id,
                    "trigger_type": trigger_type,
                    "trigger_reason": reason,
                    "context_summary": _build_context_summary(session),
                },
            )
            resp.raise_for_status()
            handoff_case = resp.json()["data"]
            session.handoff_case_id = handoff_case["id"]
    except Exception as exc:
        logger.error("handoff_trigger_failed", error=str(exc))

    await transition_state(session, ConversationFSMState.HANDOFF_ACTIVE)
    return FSMResult(
        response_text=(
            "Te estoy conectando con uno de nuestros asesores que podrá ayudarte mejor. "
            "Por favor espera un momento mientras revisamos tu caso. 🙏"
        ),
        new_state=ConversationFSMState.HANDOFF_ACTIVE,
        session=session,
        handoff_triggered=True,
    )


async def _handle_nps(*, message: str, session: SessionState) -> FSMResult:
    """Captura la puntuación NPS (1-5) del usuario."""
    score = None
    for char in message:
        if char.isdigit() and 1 <= int(char) <= 5:
            score = int(char)
            break

    if score:
        session.nps_score = score
        await save_session(session)
        thanks = "¡Muchas gracias por tu puntuación! 🙏" if score >= 4 else "Gracias por tu opinión, la tendremos muy en cuenta para mejorar."
        await transition_state(session, ConversationFSMState.CLOSED)
        return FSMResult(
            response_text=f"{thanks} Ha sido un placer acompañarte. ¡Hasta pronto!",
            new_state=ConversationFSMState.CLOSED,
            session=session,
        )

    return FSMResult(
        response_text="Por favor, responde con un número del 1 al 5 para calificar tu experiencia. (1 = muy malo, 5 = excelente)",
        new_state=ConversationFSMState.POST_CHAT,
        session=session,
    )


def _trigger_post_chat(session: SessionState) -> FSMResult:
    """Inicia el estado POST_CHAT con pregunta NPS."""
    return FSMResult(
        response_text=(
            "Ha sido un placer ayudarte 😊\n\n"
            "¿Podrías calificar tu experiencia con NIA del 1 al 5? "
            "(1 = muy malo, 5 = excelente)"
        ),
        new_state=ConversationFSMState.POST_CHAT,
        session=session,
    )


def _append_turn(session: SessionState, *, user_msg: str, assistant_msg: str, intent: IntentType) -> None:
    """Añade el par user/assistant al historial de la sesión (limitado a MAX_HISTORY_TURNS)."""
    session.conversation_history.append(ConversationTurn(role="user", content=user_msg, intent=intent.value))
    session.conversation_history.append(ConversationTurn(role="assistant", content=assistant_msg))
    # Mantener solo los últimos MAX_HISTORY_TURNS * 2 mensajes
    max_msgs = MAX_HISTORY_TURNS * 2
    if len(session.conversation_history) > max_msgs:
        session.conversation_history = session.conversation_history[-max_msgs:]


async def _persist_transcript(
    *,
    tenant_id: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
    intent: str,
    confidence: float,
    settings: OrchestratorSettings,
) -> None:
    """Persiste ambos mensajes del turno en el transcript service (fire-and-forget)."""
    base_url = settings.transcript_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Mensaje del usuario
            await client.post(
                f"{base_url}/v1/transcripts/messages",
                json={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "role": "user",
                    "content": user_message,
                    "intent": intent,
                    "confidence": confidence,
                },
            )
            # Respuesta del asistente
            await client.post(
                f"{base_url}/v1/transcripts/messages",
                json={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "role": "assistant",
                    "content": assistant_message,
                    "intent": intent,
                    "confidence": confidence,
                },
            )
    except Exception as exc:
        # Nunca bloquear el flujo principal por errores de transcript
        logger.warning("transcript_persist_failed", error=str(exc), tenant_id=tenant_id, session_id=session_id)


def _build_context_summary(session: SessionState) -> str:
    parts = [
        f"Sesión: {session.session_id}",
        f"Mensajes: {session.messages_count}",
        f"Último intent: {session.last_intent}",
    ]
    if session.last_recommendations:
        parts.append(f"Productos vistos: {', '.join(session.last_recommendations[:3])}")
    return " | ".join(parts)


def _build_history_for_intent(session: SessionState) -> list[dict]:
    """Construye historial de los últimos 3 turnos para el intent detector."""
    return [{"role": t.role, "content": t.content} for t in session.conversation_history[-6:]]
