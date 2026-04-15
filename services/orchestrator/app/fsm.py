"""
FSM (Finite State Machine) del orquestador NIA.
Implementa las transiciones de estado para la conversación.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from app.flow_defaults import DEFAULT_TRANSITIONS
from app.intent import detect_intent, get_skill_config
from app.session import get_or_create_session, save_session, transition_state
from app.settings import OrchestratorSettings
from shared.db.redis_client import get_redis
from shared.models.domain import (
    ConversationFSMState,
    ConversationTurn,
    FlowTransition,
    IntentEntities,
    IntentType,
    RecommendationResult,
    SessionState,
    SkillConfig,
)
from shared.utils.logging import get_logger
from shared.utils.sanitizer import sanitize_user_message

logger = get_logger(__name__)

MAX_HISTORY_TURNS = 10  # Máximo de turnos a mantener en Redis


async def _publish_trace(tenant_id: str, session_id: str, event: dict) -> None:
    """Publish a FSM trace event to Redis pub/sub for the live Admin Console trace overlay."""
    try:
        redis = await get_redis()
        channel = f"nia:trace:{tenant_id}:{session_id}"
        event["ts"] = time.time()
        await redis.publish(channel, json.dumps(event))
    except Exception:
        pass  # Trace is best-effort — never block the conversation



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
    #    - Sólo si lead_config.enabled está explícitamente True (default False)
    #    - Sólo si "pre_chat" no fue ocultado en fsm_config.hidden_states
    lead_config = tenant_config.get("lead_config", {})
    hidden_states = tenant_config.get("fsm_config", {}).get("hidden_states", [])
    lead_enabled = lead_config.get("enabled", False)
    pre_chat_hidden = "pre_chat" in hidden_states

    if (
        lead_enabled
        and not pre_chat_hidden
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
    intent, confidence, entities, raw_entities, intent_tokens = await detect_intent(
        message=clean_message,
        conversation_history=history,
        settings=settings,
        tenant_id=tenant_id,
        tenant_config=tenant_config,
    )

    session.last_intent = intent
    session.last_entities = raw_entities or entities.model_dump(exclude_none=True)
    session.messages_count += 1
    session.tokens_used += intent_tokens

    # Helper to get intent as plain string
    intent_value = intent.value if isinstance(intent, IntentType) else str(intent)

    # Publish intent detection trace event
    asyncio.create_task(_publish_trace(tenant_id, session_id, {
        "type": "intent_detected",
        "intent": intent_value,
        "confidence": confidence,
        "fsm_state": session.fsm_state.value if isinstance(session.fsm_state, ConversationFSMState) else str(session.fsm_state),
    }))

    # 6. Routing por intent
    prev_state = session.fsm_state.value if isinstance(session.fsm_state, ConversationFSMState) else str(session.fsm_state)
    result = await _route_by_intent(
        message=clean_message,
        intent=intent,
        confidence=confidence,
        entities=entities,
        raw_entities=raw_entities,
        session=session,
        tenant_config=tenant_config,
        settings=settings,
    )

    # 7. Guardar turno en historial de la sesión (en Redis)
    _append_turn(session, user_msg=clean_message, assistant_msg=result.response_text, intent=intent_value)
    await save_session(session)

    # Publish FSM transition trace event
    asyncio.create_task(_publish_trace(tenant_id, session_id, {
        "type": "fsm_transition",
        "from": prev_state,
        "to": result.new_state.value if isinstance(result.new_state, ConversationFSMState) else str(result.new_state),
        "handoff": result.handoff_triggered,
        "action": result.metadata.get("action") if result.metadata else None,
    }))

    # 8. Fire-and-forget: persistir mensajes en transcript service
    asyncio.create_task(
        _persist_transcript(
            tenant_id=tenant_id,
            session_id=session_id,
            user_message=clean_message,
            assistant_message=result.response_text,
            intent=intent_value,
            confidence=confidence,
            settings=settings,
        )
    )

    return result


async def _route_by_intent(
    *,
    message: str,
    intent: IntentType | str,
    confidence: float,
    entities: IntentEntities,
    raw_entities: dict[str, Any],
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
) -> FSMResult:
    """
    Despacha el mensaje al handler correcto según la tabla de transiciones.

    Orden de resolución:
      1. Si el tenant tiene transiciones en fsm_config.transitions → las usa.
      2. Si no → usa DEFAULT_TRANSITIONS (flujo original hardcodeado).

    Para cada transición se evalúa:
      - intent coincide
      - from_states vacío  O  estado actual está en from_states
      - enabled == True
    Se usa la primera transición que coincide.
    """
    # ── Cargar tabla de transiciones ──────────────────────────────────────────
    # Caso especial: si el estado actual es POST_CHAT, cualquier mensaje se
    # interpreta como respuesta NPS independientemente del intent detectado.
    if session.fsm_state == ConversationFSMState.POST_CHAT:
        skill = get_skill_config("nps", tenant_config)
        return await _handle_nps(message=message, session=session, skill=skill)

    raw_transitions: list[dict] = (
        tenant_config.get("fsm_config", {}).get("transitions") or []
    )
    if raw_transitions:
        transitions = [FlowTransition(**t) for t in raw_transitions]
        logger.debug(
            "fsm_using_custom_transitions",
            tenant_id=session.tenant_id,
            count=len(transitions),
        )
    else:
        transitions = DEFAULT_TRANSITIONS

    current_state = session.fsm_state.value if isinstance(session.fsm_state, ConversationFSMState) else session.fsm_state
    intent_value = intent.value if isinstance(intent, IntentType) else str(intent)

    # ── Buscar la transición que mejor aplica ────────────────────────────────
    #
    # Scoring de especificidad (mayor = mejor):
    #   +2  intent coincide exactamente
    #   +1  intent es wildcard (vacío) — matches anything
    #   +2  from_states incluye el estado actual
    #   +1  from_states vacío — matches any state
    #
    # Si hay empate de score, gana la última (permite que overrides del
    # usuario, que se añaden al final de la lista, superen a los defaults).
    matched: FlowTransition | None = None
    best_score = -1
    for t in transitions:
        if not t.enabled:
            continue
        # Intent match: exact > wildcard > no match
        if t.intent and t.intent != intent_value:
            continue
        intent_score = 2 if t.intent == intent_value else 1  # 1 = wildcard
        # State match: exact > wildcard > no match
        if t.from_states and current_state not in t.from_states:
            continue
        state_score = 2 if (t.from_states and current_state in t.from_states) else 1  # 1 = wildcard
        score = intent_score + state_score
        if score >= best_score:
            best_score = score
            matched = t

    if matched is not None:
        logger.debug(
            "fsm_transition_matched",
            tenant_id=session.tenant_id,
            intent=intent_value,
            state=current_state,
            matched_intent=matched.intent or "*",
            matched_action=matched.action,
            matched_to_state=matched.to_state,
            score=best_score,
        )

    if matched is None:
        # Ninguna transición coincide → intentar RAG como fallback inteligente
        logger.warning(
            "fsm_no_transition_matched",
            tenant_id=session.tenant_id,
            intent=intent_value,
            state=current_state,
        )
        tenant_name = tenant_config.get("ui_config", {}).get("chat_title", "el asistente")
        return await _handle_discovery(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
        )

    # ── Ejecutar acción ───────────────────────────────────────────────────────
    limits_config = tenant_config.get("limits_config", {})
    tenant_name = tenant_config.get("ui_config", {}).get("chat_title", "el asistente")

    # Resolve skill config for the matched action
    skill = get_skill_config(matched.action, tenant_config)

    # Publish skill_call trace (best-effort, fire-and-forget)
    asyncio.create_task(_publish_trace(session.tenant_id, session.session_id, {
        "type": "skill_call",
        "action": matched.action,
        "intent": intent_value,
        "from_state": current_state,
        "to_state": matched.to_state,
    }))

    if matched.action == "handoff":
        if limits_config.get("handoff_enabled", True):
            return await _trigger_handoff(
                session,
                trigger_type="explicit_request",
                reason=f"El usuario solicitó explícitamente hablar con un humano. Mensaje: {message[:200]}",
                settings=settings,
                skill=skill,
            )
        unavailable_msg = (
            skill.response_templates.get("unavailable") if skill else None
        ) or "Entiendo que prefieres hablar con una persona, pero el servicio de atención humana no está disponible en este momento. ¿Puedo intentar ayudarte yo?"
        return FSMResult(
            response_text=unavailable_msg,
            new_state=session.fsm_state,
            session=session,
        )

    if matched.action == "nps":
        return await _handle_nps(message=message, session=session, skill=skill)

    if matched.action == "complaint":
        return await _handle_complaint(session, settings, message, skill=skill)

    if matched.action == "faq":
        return await _handle_faq(
            query=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
            skill=skill,
        )

    if matched.action == "recommend":
        return await _handle_recommendation_flow(
            message=message,
            entities=entities,
            raw_entities=raw_entities,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
        )

    if matched.action == "static_reply":
        # Resolver estado final (__same__ = mantener estado actual)
        if matched.to_state == "__same__":
            final_state = session.fsm_state
        else:
            final_state = ConversationFSMState(matched.to_state)
        return FSMResult(
            response_text=matched.static_message or "No tengo información sobre eso.",
            new_state=final_state,
            session=session,
        )

    if matched.action == "discovery":
        return await _handle_discovery(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
        )

    if matched.action == "conversational" or matched.action.startswith("conversational__"):
        return await _handle_conversational(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )

    # Acción desconocida → fallback seguro
    logger.error(
        "fsm_unknown_action",
        tenant_id=session.tenant_id,
        action=matched.action,
        intent=intent_value,
    )
    return FSMResult(
        response_text="Ha ocurrido un error al procesar tu solicitud. Por favor, intenta de nuevo.",
        new_state=session.fsm_state,
        session=session,
    )


async def _handle_conversational(
    *,
    message: str,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    skill: SkillConfig | None = None,
    to_state: str = "__same__",
) -> FSMResult:
    """
    Responde con el LLM usando el preparation_prompt del skill como system message.
    Sin llamadas a servicios externos — ideal para skills puramente conversacionales
    creados por el administrador del tenant.
    """
    tenant_name = tenant_config.get("ui_config", {}).get("chat_title", "el asistente")
    tpl = skill.response_templates if skill else {}
    error_msg = tpl.get("error", f"Disculpa, tuve un problema al procesar tu mensaje. ¿Puedes intentarlo de nuevo?")

    # Build system prompt from skill preparation_prompt, fallback to generic
    system_prompt = (
        skill.preparation_prompt
        if skill and skill.preparation_prompt
        else f"Eres {tenant_name}, un asistente virtual amigable y útil. Responde de manera concisa y en el mismo idioma que el usuario."
    )

    # Build messages array (last 6 turns for context + current message)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    history = getattr(session, "conversation_history", []) or []
    for turn in history[-6:]:
        if hasattr(turn, "user_message"):
            messages.append({"role": "user", "content": turn.user_message})
            if turn.bot_response:
                messages.append({"role": "assistant", "content": turn.bot_response})
        elif isinstance(turn, dict):
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 512,
                    "tenant_id": session.tenant_id,
                },
            )
            resp.raise_for_status()
            resp_data = resp.json()["data"]
            answer = resp_data.get("content", "").strip()
            if not answer:
                answer = resp_data.get("reasoning_content", "").strip()
            # Accumulate LLM token usage into session
            llm_tokens = resp_data.get("input_tokens", 0) + resp_data.get("output_tokens", 0)
            session.tokens_used += llm_tokens
            if llm_tokens:
                asyncio.create_task(_publish_trace(session.tenant_id, session.session_id, {
                    "type": "llm_call",
                    "tokens": llm_tokens,
                    "input_tokens": resp_data.get("input_tokens", 0),
                    "output_tokens": resp_data.get("output_tokens", 0),
                    "model": resp_data.get("model", "unknown"),
                }))
    except Exception as exc:
        logger.error("conversational_llm_failed", error=str(exc))
        return FSMResult(
            response_text=error_msg,
            new_state=session.fsm_state,
            session=session,
        )

    if not answer:
        answer = error_msg

    # Resolve target FSM state
    if to_state == "__same__" or not to_state:
        new_state = session.fsm_state
    else:
        try:
            new_state = ConversationFSMState(to_state)
        except ValueError:
            new_state = session.fsm_state

    await transition_state(session, new_state)
    return FSMResult(
        response_text=answer,
        new_state=new_state,
        session=session,
    )


async def _handle_discovery(
    *,
    message: str,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    tenant_name: str,
) -> FSMResult:
    """
    Maneja mensajes ambiguos o de saludo usando el RAG.
    En vez de un string genérico hardcodeado, consulta la base de conocimiento
    del tenant para dar una respuesta contextual y útil.
    Si el RAG no tiene contexto suficiente, usa el LLM con el historial
    para generar una respuesta de discovery natural.
    """
    rag_config = tenant_config.get("rag_config", {})
    collection_name = f"{session.tenant_id}_docs"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.rag_service_url}/v1/rag/query",
                json={
                    "query": message,
                    "tenant_id": session.tenant_id,
                    "collection_name": collection_name,
                    "tenant_name": tenant_name,
                },
            )
            resp.raise_for_status()
            rag_result = resp.json()["data"]
        answer = rag_result.get("answer", "")
        is_fallback = rag_result.get("is_fallback", True)
    except Exception as exc:
        logger.warning("discovery_rag_failed", error=str(exc))
        answer = ""
        is_fallback = True

    if is_fallback or not answer.strip():
        # RAG no encontró contexto útil → respuesta de discovery del LLM
        answer = rag_config.get(
            "fallback_message",
            f"Hola 👋 Soy el asistente de {tenant_name}. ¿En qué puedo ayudarte hoy?",
        )

    await transition_state(session, ConversationFSMState.DISCOVERY)
    return FSMResult(
        response_text=answer,
        new_state=ConversationFSMState.DISCOVERY,
        session=session,
        rag_answer=answer if not is_fallback else None,
    )


async def _handle_faq(
    *,
    query: str,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    tenant_name: str,
    skill: SkillConfig | None = None,
) -> FSMResult:
    """Consulta al RAG service."""
    rag_config = tenant_config.get("rag_config", {})
    collection_name = f"{session.tenant_id}_docs"

    error_msg = (
        (skill.response_templates.get("error") if skill else None)
        or rag_config.get("fallback_message")
        or "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?"
    )

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
            response_text=error_msg,
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
    raw_entities: dict[str, Any] | None = None,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    skill: SkillConfig | None = None,
) -> FSMResult:
    """Llama al recommender y construye respuesta con productos."""
    tenant_schema = f"tenant_{session.tenant_id}"

    # Use raw_entities if available (includes custom fields from skill config),
    # otherwise fall back to legacy IntentEntities model.
    entities_payload = raw_entities if raw_entities else entities.model_dump(mode="json")

    # Resolve response templates from skill config
    tpl = skill.response_templates if skill else {}
    error_msg = tpl.get("error", "Estoy teniendo dificultades para acceder al catálogo. ¿Puedes intentarlo de nuevo en un momento?")
    empty_msg = tpl.get("empty", "En este momento no encontré opciones que coincidan exactamente con lo que buscas. ¿Te gustaría que amplíe la búsqueda?")
    success_msg = tpl.get("success", "Te recomiendo estas opciones:")
    followup_msg = tpl.get("followup", "¿Te interesa alguna de estas opciones? Puedo darte más detalles.")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{settings.recommender_url}/v1/recommendations",
                json={
                    "tenant_id": session.tenant_id,
                    "tenant_schema": tenant_schema,
                    "entities": entities_payload,
                    "top_k": 3,
                },
            )
            resp.raise_for_status()
            rec_result = RecommendationResult(**resp.json()["data"])
    except Exception as exc:
        logger.error("recommender_call_failed", error=str(exc))
        return FSMResult(
            response_text=error_msg,
            new_state=session.fsm_state,
            session=session,
        )

    if not rec_result.recommendations:
        return FSMResult(
            response_text=empty_msg,
            new_state=ConversationFSMState.DISCOVERY,
            session=session,
        )

    # Guardar contexto de recomendación en sesión
    session.last_recommendations = [r.product_id for r in rec_result.recommendations]
    await transition_state(session, ConversationFSMState.RECOMMENDING)

    # Construir texto de respuesta
    lines = [success_msg]
    for item in rec_result.recommendations:
        price_str = f"${item.base_price:,.0f} {item.currency}"
        avail_str = "✅ Disponible" if item.availability_status == "available" else "📅 Consultar disponibilidad"
        lines.append(f"\n**{item.rank}. {item.name}**")
        lines.append(f"   💰 {price_str} | ⏱ {item.duration_minutes or '?'} min | {avail_str}")
        if item.available_slots:
            times = ", ".join(s.time for s in item.available_slots[:2])
            lines.append(f"   🕐 Horarios: {times}")

    lines.append(f"\n{followup_msg}")

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
    skill: SkillConfig | None = None,
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
            skill=get_skill_config("handoff"),
        )

    ack_msg = (
        (skill.response_templates.get("ack") if skill else None)
        or "Lamento mucho la inconveniencia. ¿Puedes contarme más sobre lo que ocurrió para poder ayudarte mejor?"
    )
    return FSMResult(
        response_text=ack_msg,
        new_state=session.fsm_state,
        session=session,
    )


async def _trigger_handoff(
    session: SessionState,
    trigger_type: str,
    reason: str,
    settings: OrchestratorSettings,
    skill: SkillConfig | None = None,
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

    connecting_msg = (
        (skill.response_templates.get("connecting") if skill else None)
        or (
            "Te estoy conectando con uno de nuestros asesores que podrá ayudarte mejor. "
            "Por favor espera un momento mientras revisamos tu caso. 🙏"
        )
    )
    await transition_state(session, ConversationFSMState.HANDOFF_ACTIVE)
    return FSMResult(
        response_text=connecting_msg,
        new_state=ConversationFSMState.HANDOFF_ACTIVE,
        session=session,
        handoff_triggered=True,
    )


async def _handle_nps(*, message: str, session: SessionState, skill: SkillConfig | None = None) -> FSMResult:
    """Captura la puntuación NPS (1-5) del usuario."""
    tpl = skill.response_templates if skill else {}

    score = None
    for char in message:
        if char.isdigit() and 1 <= int(char) <= 5:
            score = int(char)
            break

    if score:
        session.nps_score = score
        await save_session(session)
        if score >= 4:
            thanks = tpl.get("thanks_high", "¡Muchas gracias por tu puntuación! 🙏")
        else:
            thanks = tpl.get("thanks_low", "Gracias por tu opinión, la tendremos muy en cuenta para mejorar.")
        await transition_state(session, ConversationFSMState.CLOSED)
        return FSMResult(
            response_text=f"{thanks} Ha sido un placer acompañarte. ¡Hasta pronto!",
            new_state=ConversationFSMState.CLOSED,
            session=session,
        )

    invalid_msg = tpl.get("invalid", "Por favor, responde con un número del 1 al 5 para calificar tu experiencia. (1 = muy malo, 5 = excelente)")
    return FSMResult(
        response_text=invalid_msg,
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


def _append_turn(session: SessionState, *, user_msg: str, assistant_msg: str, intent: str) -> None:
    """Añade el par user/assistant al historial de la sesión (limitado a MAX_HISTORY_TURNS)."""
    session.conversation_history.append(ConversationTurn(role="user", content=user_msg, intent=intent))
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
