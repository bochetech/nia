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
    SlotFillingConfig,
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


def _build_skill_trace(
    *,
    action: str,
    intent: str,
    from_state: str,
    to_state: str,
    skill: "SkillConfig | None",
    entities: "IntentEntities",
    raw_entities: "dict[str, Any] | None",
    action_taken: str,
    missing_required: "list | None" = None,
    latency_ms: float | None = None,
) -> dict:
    """Build an enriched skill_call trace payload.

    action_taken values:
      - "execute"               — skill ran normally
      - "clarification_asked"   — entity gate triggered, asked user for missing fields
      - "unavailable"           — skill disabled (e.g. handoff_enabled=False)
    """
    # Resolve entity values: merge raw_entities (custom fields) with typed entities
    entities_dict: dict[str, Any] = {}
    if skill and skill.entity_schema:
        resolved = {**(raw_entities or {}), **{k: v for k, v in entities.model_dump().items() if v is not None}}
        for field in skill.entity_schema:
            entities_dict[field.name] = resolved.get(field.name)

    payload: dict[str, Any] = {
        "type": "skill_call",
        "action": action,
        "skill_name": skill.name if skill else None,
        "intent": intent,
        "from_state": from_state,
        "to_state": to_state,
        "action_taken": action_taken,
        "entities_resolved": entities_dict if entities_dict else None,
        "missing_required": [f.name for f in (missing_required or [])],
    }
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 1)
    return payload


def _resolve_fsm_state(
    to_state: str,
    current_state: ConversationFSMState | str,
) -> ConversationFSMState | str:
    """
    Resolve a target state string to either:
    - The corresponding ConversationFSMState enum value (if it exists)
    - The raw string (for custom tenant-defined states)
    - The current state if to_state is "__same__" or empty
    """
    if to_state == "__same__" or not to_state:
        return current_state
    try:
        return ConversationFSMState(to_state)
    except ValueError:
        # Custom state defined by tenant — use as-is
        return to_state


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
        suggested_replies: list[str] | None = None,
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
        # Quick-reply chips sent to the widget after the bot message
        self.suggested_replies: list[str] = suggested_replies or []


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
    intent, confidence, entities, raw_entities, intent_tokens, intent_input_tokens, intent_output_tokens = await detect_intent(
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

    # Persist detected language so downstream handlers can use it
    detected_lang = (raw_entities or {}).get("language_preference")
    if detected_lang:
        session.metadata = session.metadata or {}
        session.metadata["language"] = detected_lang

    # Helper to get intent as plain string
    intent_value = intent.value if isinstance(intent, IntentType) else str(intent)

    # Publish LLM call trace for intent detection
    if intent_tokens:
        await _publish_trace(tenant_id, session_id, {
            "type": "llm_call",
            "purpose": "intent_detection",
            "tokens": intent_tokens,
            "input_tokens": intent_input_tokens,
            "output_tokens": intent_output_tokens,
            "model": "intent-classifier",
        })

    # Publish intent detection trace event
    await _publish_trace(tenant_id, session_id, {
        "type": "intent_detected",
        "intent": intent_value,
        "confidence": confidence,
        "fsm_state": session.fsm_state.value if isinstance(session.fsm_state, ConversationFSMState) else str(session.fsm_state),
    })

    # 6. Slot filling intercept — must run BEFORE normal routing.
    prev_state = session.fsm_state.value if isinstance(session.fsm_state, ConversationFSMState) else str(session.fsm_state)
    #    If a previous turn started slot filling (session.metadata["slot_filling"]),
    #    we resume it instead of re-routing. The user is still in state A; we only
    #    transition to state B once all required slots are collected.
    session.metadata = session.metadata or {}
    if session.metadata.get("slot_filling"):
        sf_ctx = session.metadata["slot_filling"]
        original_intent = sf_ctx.get("intent", "")
        # Decide whether this message continues slot filling or abandons it:
        #   - same intent OR unclear   → continue collecting
        #   - different intent + high confidence → user changed topic, abort
        #   - different intent + low confidence  → likely a slot answer, continue
        intent_changed = intent_value not in (original_intent, "unclear")
        if intent_changed and confidence >= 0.7:
            logger.info(
                "slot_filling_aborted_intent_change",
                tenant_id=tenant_id,
                from_intent=original_intent,
                to_intent=intent_value,
                confidence=confidence,
            )
            del session.metadata["slot_filling"]
            await save_session(session)
            # Fall through to normal routing with the new intent
        else:
            result = await _continue_slot_filling(
                message=clean_message,
                intent_value=intent_value,
                raw_entities=raw_entities,
                entities=entities,
                session=session,
                tenant_config=tenant_config,
                settings=settings,
            )
            _append_turn(session, user_msg=clean_message, assistant_msg=result.response_text, intent=intent_value)
            await save_session(session)
            asyncio.create_task(_publish_trace(tenant_id, session_id, {
                "type": "fsm_transition",
                "from": prev_state,
                "to": result.new_state.value if isinstance(result.new_state, ConversationFSMState) else str(result.new_state),
                "handoff": result.handoff_triggered,
                "action": result.metadata.get("action") if result.metadata else None,
            }))
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

    # 7. Routing por intent
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

    # 8. Guardar turno en historial de la sesión (en Redis)
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

    # 9. Fire-and-forget: persistir mensajes en transcript service
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
        # Normalize from_states: "__any__" is a UI-only sentinel → treat as wildcard
        effective_from = [s for s in t.from_states if s != "__any__"]
        # State match: exact > wildcard > no match
        if effective_from and current_state not in effective_from:
            continue
        state_score = 2 if (effective_from and current_state in effective_from) else 1  # 1 = wildcard
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

    # Helper: publish enriched skill_call trace (best-effort, fire-and-forget)
    async def _emit_skill_trace(
        action_taken: str,
        missing_required: list | None = None,
        latency_ms: float | None = None,
    ) -> None:
        payload = _build_skill_trace(
            action=matched.action,
            intent=intent_value,
            from_state=current_state,
            to_state=matched.to_state,
            skill=skill,
            entities=entities,
            raw_entities=raw_entities,
            action_taken=action_taken,
            missing_required=missing_required,
            latency_ms=latency_ms,
        )
        await _publish_trace(session.tenant_id, session.session_id, payload)

    if matched.action == "handoff":
        if limits_config.get("handoff_enabled", True):
            await _emit_skill_trace("execute")
            return await _trigger_handoff(
                session,
                trigger_type="explicit_request",
                reason=f"El usuario solicitó explícitamente hablar con un humano. Mensaje: {message[:200]}",
                settings=settings,
                skill=skill,
            )
        await _emit_skill_trace("unavailable")
        unavailable_msg = (
            skill.response_templates.get("unavailable") if skill else None
        ) or "Entiendo que prefieres hablar con una persona, pero el servicio de atención humana no está disponible en este momento. ¿Puedo intentar ayudarte yo?"
        return FSMResult(
            response_text=unavailable_msg,
            new_state=session.fsm_state,
            session=session,
        )

    if matched.action == "nps":
        await _emit_skill_trace("execute")
        return await _handle_nps(message=message, session=session, skill=skill)

    if matched.action == "complaint":
        await _emit_skill_trace("execute")
        return await _handle_complaint(session, settings, message, skill=skill)

    if matched.action == "faq":
        t0 = time.time()
        result = await _handle_faq(
            query=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
            skill=skill,
        )
        await _emit_skill_trace("execute", latency_ms=(time.time() - t0) * 1000)
        return _apply_guidance(result, matched)

    if matched.action == "recommend":
        # ── Slot filling gate (generic — works for any action with slot_filling config) ──
        if matched.slot_filling and skill and skill.entity_schema:
            sf_result = await _init_slot_filling_if_needed(
                message=message,
                matched=matched,
                skill=skill,
                raw_entities=raw_entities,
                entities=entities,
                session=session,
                tenant_config=tenant_config,
                settings=settings,
                emit_trace=_emit_skill_trace,
            )
            if sf_result is not None:
                return sf_result

        t0 = time.time()
        result = await _handle_recommendation_flow(
            message=message,
            entities=entities,
            raw_entities=raw_entities,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        await _emit_skill_trace("execute", latency_ms=(time.time() - t0) * 1000)
        return _apply_guidance(result, matched)

    if matched.action == "static_reply":
        # Resolver estado final (__same__ = mantener estado actual, o custom state)
        final_state = _resolve_fsm_state(matched.to_state, session.fsm_state)
        # For static_reply the bot_prompt IS the message (or prepends it)
        text = matched.static_message or "No tengo información sobre eso."
        if matched.bot_prompt:
            text = f"{matched.bot_prompt}\n\n{text}"
        await _emit_skill_trace("execute")
        return FSMResult(
            response_text=text,
            new_state=final_state,
            session=session,
            suggested_replies=matched.suggested_replies or [],
        )

    if matched.action == "discovery":
        t0 = time.time()
        result = await _handle_discovery(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
        )
        await _emit_skill_trace("execute", latency_ms=(time.time() - t0) * 1000)
        return _apply_guidance(result, matched)

    if matched.action == "conversational" or matched.action.startswith("conversational__"):
        t0 = time.time()
        result = await _handle_conversational(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        await _emit_skill_trace("execute", latency_ms=(time.time() - t0) * 1000)
        return _apply_guidance(result, matched)

    if matched.action == "bokun":
        t0 = time.time()
        if matched.slot_filling and skill and skill.entity_schema:
            sf_result = await _init_slot_filling_if_needed(
                message=message,
                matched=matched,
                skill=skill,
                raw_entities=raw_entities,
                entities=entities,
                session=session,
                tenant_config=tenant_config,
                settings=settings,
                emit_trace=_emit_skill_trace,
            )
            if sf_result is not None:
                return sf_result
        result = await _handle_bokun_skill(
            message=message,
            entities=entities,
            session=session,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        await _emit_skill_trace("execute", latency_ms=(time.time() - t0) * 1000)
        return _apply_guidance(result, matched)

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


# ── Slot filling helpers ───────────────────────────────────────────────────────

async def _init_slot_filling_if_needed(
    *,
    message: str,
    matched: FlowTransition,
    skill: SkillConfig,
    raw_entities: dict[str, Any],
    entities: IntentEntities,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    emit_trace,
) -> FSMResult | None:
    """
    Checks whether any required EntityField of the skill is missing from the current message.
    If so, initializes the slot filling context in session.metadata and asks the first question.
    Returns an FSMResult (self-loop) if slot filling was triggered, or None if all slots are present.

    Called only when the matched transition has slot_filling configured.
    """
    sf_config: SlotFillingConfig = matched.slot_filling  # type: ignore[assignment]

    # Merge extracted entities: raw_entities (custom) + typed IntentEntities
    resolved = {**(raw_entities or {}), **{k: v for k, v in entities.model_dump().items() if v is not None}}

    # Find required fields that are missing in this message
    missing = [
        f for f in skill.entity_schema
        if getattr(f, "required", False) and not resolved.get(f.name)
    ]
    if not missing:
        return None  # All required slots present — proceed to action

    intent_value = matched.intent

    # Build ordered queue of pending field names (preserve entity_schema order)
    pending = [f.name for f in missing]

    # Initialize slot filling state in session
    session.metadata = session.metadata or {}
    session.metadata["slot_filling"] = {
        "intent": intent_value,
        "action": matched.action,
        "to_state": matched.to_state,
        "transition": matched.model_dump(),      # serialize full transition for later execution
        "strategy": sf_config.strategy,
        "max_retries": sf_config.max_retries,
        "on_exhausted": sf_config.on_exhausted,
        "collected": resolved,                   # entities already gathered this turn
        "pending": pending,                      # ordered list of fields still needed
        "retries": {name: 0 for name in pending},
    }

    # Build field map for quick lookup
    field_map = {f.name: f for f in skill.entity_schema}

    logger.info(
        "slot_filling_initiated",
        tenant_id=session.tenant_id,
        action=matched.action,
        strategy=sf_config.strategy,
        pending=pending,
    )
    await emit_trace("clarification_asked", missing_required=missing)

    # Ask based on strategy
    if sf_config.strategy == "all_at_once":
        question = await _build_slot_question_all_at_once(pending, field_map, session, settings)
    else:  # one_by_one (default)
        question = await _build_slot_question_one(pending[0], field_map, session, settings)

    return FSMResult(
        response_text=question,
        new_state=session.fsm_state,  # stay in state A
        session=session,
    )


async def _continue_slot_filling(
    *,
    message: str,
    intent_value: str,
    raw_entities: dict[str, Any],
    entities: IntentEntities,
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
) -> FSMResult:
    """
    Continues an active slot filling session.
    Tries to extract the current pending field(s) from the user message.
    On completion (all slots filled), executes the original action.
    """
    sf_ctx = session.metadata["slot_filling"]
    strategy = sf_ctx["strategy"]
    max_retries = sf_ctx["max_retries"]
    on_exhausted = sf_ctx["on_exhausted"]
    pending: list[str] = sf_ctx["pending"]
    collected: dict = sf_ctx["collected"]
    retries: dict = sf_ctx["retries"]

    # Reconstruct the matched transition and skill
    matched = FlowTransition(**sf_ctx["transition"])
    skill = get_skill_config(matched.action, tenant_config)
    field_map = {f.name: f for f in (skill.entity_schema if skill else [])}

    # Merge newly extracted entities into collected
    newly_extracted = {**(raw_entities or {}), **{k: v for k, v in entities.model_dump().items() if v is not None}}

    if strategy == "all_at_once":
        # Try to extract all pending fields from the message
        filled = [name for name in pending if newly_extracted.get(name)]
        for name in filled:
            collected[name] = newly_extracted[name]
            pending.remove(name)
    else:
        # one_by_one: only care about the first pending field
        current_field = pending[0]
        extracted_value = newly_extracted.get(current_field)

        if extracted_value:
            collected[current_field] = extracted_value
            pending.pop(0)
            retries.pop(current_field, None)
        else:
            # Not extracted — increment retry counter
            retries[current_field] = retries.get(current_field, 0) + 1
            if retries[current_field] >= max_retries:
                field = field_map.get(current_field)
                if on_exhausted == "handoff":
                    del session.metadata["slot_filling"]
                    return await _trigger_handoff(
                        session,
                        trigger_type="slot_filling_exhausted",
                        reason=f"No se pudo obtener el campo '{current_field}' tras {max_retries} intentos.",
                        settings=settings,
                    )
                elif on_exhausted == "abort":
                    del session.metadata["slot_filling"]
                    abort_msg = "Entiendo que quizás no es el momento. Si necesitas ayuda después, aquí estaré. 😊"
                    return FSMResult(
                        response_text=abort_msg,
                        new_state=session.fsm_state,
                        session=session,
                    )
                else:  # use_default
                    default_val = getattr(field, "default", None) if field else None
                    if default_val is not None:
                        collected[current_field] = default_val
                    pending.pop(0)
                    retries.pop(current_field, None)
                    logger.info(
                        "slot_filling_used_default",
                        tenant_id=session.tenant_id,
                        field=current_field,
                        default=default_val,
                    )

    # Update context
    sf_ctx["pending"] = pending
    sf_ctx["collected"] = collected
    sf_ctx["retries"] = retries

    # ── All slots collected → execute the action ──────────────────────────────
    if not pending:
        del session.metadata["slot_filling"]
        logger.info(
            "slot_filling_completed",
            tenant_id=session.tenant_id,
            action=matched.action,
            collected_fields=list(collected.keys()),
        )
        await _publish_trace(session.tenant_id, session.session_id, {
            "type": "slot_filling_completed",
            "action": matched.action,
            "collected": list(collected.keys()),
        })
        # Execute the original action with all collected entities
        merged_entities = IntentEntities(**{
            k: collected.get(k) for k in IntentEntities.model_fields if k in collected
        })
        return await _dispatch_action(
            message=message,
            matched=matched,
            skill=skill,
            entities=merged_entities,
            raw_entities=collected,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            intent_value=sf_ctx["intent"],
        )

    # ── Still pending → ask next question ────────────────────────────────────
    if strategy == "all_at_once":
        question = await _build_slot_question_all_at_once(pending, field_map, session, settings)
    else:
        question = await _build_slot_question_one(pending[0], field_map, session, settings)

    return FSMResult(
        response_text=question,
        new_state=session.fsm_state,  # stay in state A
        session=session,
    )


async def _build_slot_question_one(
    field_name: str,
    field_map: dict,
    session: SessionState,
    settings: OrchestratorSettings,
) -> str:
    """Returns the question to ask for a single missing field.
    Uses EntityField.question if set, otherwise asks the LLM to generate one."""
    field = field_map.get(field_name)
    if field and field.question:
        return field.question

    # LLM generates the question from the field description
    description = field.description if field else field_name.replace("_", " ")
    user_lang = (session.metadata or {}).get("language", "")
    lang_hint = f" Respond in {user_lang}." if user_lang else ""
    prompt = (
        f"You are a friendly assistant.{lang_hint} "
        f"Ask the user a short, natural question to obtain: {description}. "
        "One sentence only, no markdown."
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.5,
                    "max_tokens": 60,
                    "enable_thinking": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            return data["data"]["content"].strip()
    except Exception:
        return f"¿Podrías indicarme {field_name.replace('_', ' ')}?"


async def _build_slot_question_all_at_once(
    pending: list[str],
    field_map: dict,
    session: SessionState,
    settings: OrchestratorSettings,
) -> str:
    """Returns a single question asking for all pending fields at once."""
    parts = []
    for name in pending:
        field = field_map.get(name)
        if field and field.question:
            parts.append(field.question)
        else:
            parts.append(f"¿{name.replace('_', ' ')}?")

    if len(parts) == 1:
        return parts[0]

    # Join naturally: "¿fecha? ¿y cuántas personas?"
    return "Para continuar necesito algunos datos: " + " / ".join(parts)


async def _dispatch_action(
    *,
    message: str,
    matched: FlowTransition,
    skill: SkillConfig | None,
    entities: IntentEntities,
    raw_entities: dict[str, Any],
    session: SessionState,
    tenant_config: dict,
    settings: OrchestratorSettings,
    intent_value: str,
) -> FSMResult:
    """
    Executes the action for a matched transition after slot filling is complete.
    Mirrors the dispatch logic in _route_by_intent but reusable post-slot-filling.
    """
    tenant_name = tenant_config.get("ui_config", {}).get("chat_title", "el asistente")
    limits_config = tenant_config.get("limits_config", {})

    if matched.action == "recommend":
        result = await _handle_recommendation_flow(
            message=message,
            entities=entities,
            raw_entities=raw_entities,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        return _apply_guidance(result, matched)

    if matched.action == "faq":
        result = await _handle_faq(
            query=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            tenant_name=tenant_name,
            skill=skill,
        )
        return _apply_guidance(result, matched)

    if matched.action == "conversational" or matched.action.startswith("conversational__"):
        result = await _handle_conversational(
            message=message,
            session=session,
            tenant_config=tenant_config,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        return _apply_guidance(result, matched)

    if matched.action == "bokun":
        result = await _handle_bokun_skill(
            message=message,
            entities=entities,
            session=session,
            settings=settings,
            skill=skill,
            to_state=matched.to_state,
        )
        return _apply_guidance(result, matched)

    # Fallback — execute discovery
    result = await _handle_discovery(
        message=message,
        session=session,
        tenant_config=tenant_config,
        settings=settings,
        tenant_name=tenant_name,
    )
    return result


def _apply_guidance(result: FSMResult, transition: FlowTransition) -> FSMResult:
    """
    If the matched transition has a bot_prompt or suggested_replies,
    apply them to the FSMResult:
      - bot_prompt is prepended to the action's response text
      - suggested_replies are attached for the widget to render as chips
    """
    if transition.bot_prompt:
        result.response_text = f"{transition.bot_prompt}\n\n{result.response_text}"
    if transition.suggested_replies:
        result.suggested_replies = transition.suggested_replies
    return result


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
                    "enable_thinking": False,
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

    # Resolve target FSM state (supports custom tenant states)
    new_state = _resolve_fsm_state(to_state, session.fsm_state)

    await transition_state(session, new_state)
    return FSMResult(
        response_text=answer,
        new_state=new_state,
        session=session,
    )


async def _rewrite_query_with_context(
    message: str,
    session: SessionState,
    settings: OrchestratorSettings,
    tenant_name: str | None = None,
) -> str:
    """
    Reescribe queries con pronombres implícitos en preguntas autónomas que el RAG
    pueda resolver. Usa dos fuentes de contexto (en orden de disponibilidad):

    1. tenant_name — contexto implícito siempre disponible: el usuario está hablando
       con el agente de este negocio, por lo que "¿dónde están?" → "¿dónde está {tenant_name}?"
    2. historial reciente — si hay conversación previa, ayuda a resolver referencias
       como "eso", "ese tour", "la segunda opción", etc.

    Solo actúa si el mensaje es corto (≤ 15 palabras). Falla silenciosamente.
    """
    if len(message.split()) > 15:
        return message

    # Fast-path: if message already names the business explicitly, skip LLM rewrite
    if tenant_name and tenant_name.lower() in message.lower():
        return message

    # Construir bloque de contexto
    context_parts: list[str] = []

    if tenant_name:
        context_parts.append(f"El usuario está hablando con el agente de: {tenant_name}")

    history = session.conversation_history or []
    # Use last 2 full turns (4 messages) for context — enough to resolve follow-ups
    # Truncate assistant messages to 200 chars to keep the prompt lean
    if history:
        recent = history[-4:]
        history_lines: list[str] = []
        for m in recent:
            role = m.role if hasattr(m, "role") else m.get("role", "user")
            content = m.content if hasattr(m, "content") else m.get("content", "")
            label = "Usuario" if role == "user" else "Asistente"
            history_lines.append(f"{label}: {content[:200]}")
        context_parts.append(f"Historial reciente:\n" + "\n".join(history_lines))

    if not context_parts:
        return message

    # Fast-path #2: No conversation history and message is a simple short query.
    # Instead of calling the LLM (which may exhaust all tokens on thinking),
    # just resolve the implicit business reference directly.
    if not history and tenant_name:
        msg_lower = message.lower()
        # Detect location / directions / hours queries and expand them directly
        if any(kw in msg_lower for kw in ("queda", "ubicad", "dirección", "dirección", "donde", "dónde", "ubicación")):
            rewritten = f"¿Cuál es la dirección o ubicación de {tenant_name}?"
            logger.info("query_rewritten_direct", original=message, rewritten=rewritten, tenant_id=session.tenant_id)
            return rewritten
        if any(kw in msg_lower for kw in ("llego", "llegar", "transporte", "cómo ir", "como ir", "acceso", "ruta")):
            rewritten = f"¿Cómo llego a {tenant_name}? ¿Cuál es su dirección?"
            logger.info("query_rewritten_direct", original=message, rewritten=rewritten, tenant_id=session.tenant_id)
            return rewritten
        if any(kw in msg_lower for kw in ("hora", "horario", "abren", "cierran", "abierto", "cerrado", "cuando", "cuándo")):
            rewritten = f"¿Cuáles son los horarios de {tenant_name}?"
            logger.info("query_rewritten_direct", original=message, rewritten=rewritten, tenant_id=session.tenant_id)
            return rewritten
        # Generic case: append tenant name for grounding
        rewritten = f"{message} {tenant_name}"
        logger.info("query_rewritten_direct", original=message, rewritten=rewritten, tenant_id=session.tenant_id)
        return rewritten

    context_block = "\n\n".join(context_parts)

    negocio = tenant_name or "el negocio"
    rewrite_prompt = (
        f"{context_block}\n\n"
        "Reescribe el siguiente mensaje del usuario en una pregunta completa y autónoma "
        "que pueda entenderse sin contexto previo (resuelve pronombres implícitos y referencias al negocio).\n"
        "Reglas importantes:\n"
        f"- Si pregunta por cómo llegar, direcciones o transporte → reescribe como '¿Cómo llego a {negocio}? ¿Cuál es su dirección?'\n"
        f"- Si pregunta por ubicación o dirección → reescribe como '¿Cuál es la dirección o ubicación de {negocio}?'\n"
        f"- Si pregunta por horarios o cuándo abren → reescribe como '¿Cuáles son los horarios de {negocio}?'\n"
        "- Si el mensaje ya es claro y completo por sí solo, devuélvelo exactamente igual.\n"
        "- SIEMPRE responde en el MISMO IDIOMA que el mensaje del usuario.\n"
        "Responde ÚNICAMENTE con la pregunta reescrita, sin explicaciones.\n\n"
        f"Mensaje: {message}\n\n"
        "Pregunta reescrita:"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": rewrite_prompt}],
                    "temperature": 0.0,
                    "max_tokens": 600,  # gemma-4-e2b uses ~200-300 tokens for thinking before content
                    "enable_thinking": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rewritten = data["data"]["content"].strip().strip('"')

            # Sanity check: reject if the model leaked a thinking block
            # (gemma-4-e2b sometimes ignores "Reply with ONLY" instructions)
            thinking_leaks = ("thinking process", "think:", "<think>", "razonamiento:")
            if any(rewritten.lower().startswith(p) for p in thinking_leaks):
                logger.warning("query_rewrite_thinking_leak", original=message)
                return message

            # Reject if suspiciously long (3x original word count = hallucination)
            if len(rewritten.split()) > max(len(message.split()) * 3, 20):
                logger.warning("query_rewrite_too_long", original=message, rewritten=rewritten[:80])
                return message

            if rewritten and rewritten != message:
                logger.info(
                    "query_rewritten",
                    original=message,
                    rewritten=rewritten,
                    tenant_id=session.tenant_id,
                )
            return rewritten or message
    except Exception as exc:
        logger.warning("query_rewrite_failed", error=str(exc))
        return message


async def _generate_greeting(
    *,
    tenant_name: str,
    session: SessionState,
    settings: OrchestratorSettings,
    lang_hint: str = "",
) -> str:
    """Genera un saludo de bienvenida en el idioma del usuario via LLM."""
    prompt = (
        f"You are the virtual assistant of {tenant_name}. "
        f"Write a short, friendly welcome greeting introducing yourself and asking how you can help.{lang_hint} "
        "Keep it to 1-2 sentences. No markdown."
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 80,
                    "enable_thinking": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            return data["data"]["content"].strip()
    except Exception:
        return f"👋 Hi! I'm the assistant of {tenant_name}. How can I help you today?"


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

    # Reescribir la query para resolver pronombres/referencias implícitas.
    # El tenant_name actúa como contexto implícito aun sin historial:
    # "¿dónde están?" → "¿dónde está {tenant_name}?"
    rag_query = await _rewrite_query_with_context(
        message, session, settings, tenant_name=tenant_name
    )
    user_language = (session.metadata or {}).get("language")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.rag_service_url}/v1/rag/query",
                json={
                    "query": rag_query,
                    "tenant_id": session.tenant_id,
                    "collection_name": collection_name,
                    "tenant_name": tenant_name,
                    "user_language": user_language,
                },
            )
            resp.raise_for_status()
            rag_result = resp.json()["data"]
            # Debug: log raw rag result to help diagnose empty / fallback answers
            logger.debug("rag_query_result", tenant_id=session.tenant_id, rag_result=rag_result)
        answer = rag_result.get("answer", "")
        is_fallback = rag_result.get("is_fallback", True)
    except Exception as exc:
        logger.warning("discovery_rag_failed", error=str(exc))
        answer = ""
        is_fallback = True

    if is_fallback or not answer.strip():
        # RAG no encontró contexto útil → usar fallback del tenant config o genérico
        # El fallback genérico lo genera el LLM para respetar el idioma del usuario
        configured_fallback = rag_config.get("fallback_message")
        if configured_fallback:
            answer = configured_fallback
        else:
            user_lang = (session.metadata or {}).get("language", "")
            lang_hint = f" Respond in {user_lang}." if user_lang else ""
            answer = await _generate_greeting(
                tenant_name=tenant_name,
                session=session,
                settings=settings,
                lang_hint=lang_hint,
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

    # Rewrite short/ambiguous queries to be self-contained before sending to RAG
    rag_query = await _rewrite_query_with_context(query, session, settings, tenant_name=tenant_name)
    user_language = (session.metadata or {}).get("language")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Pasar los últimos turnos de conversación para que el RAG tenga contexto
            recent_history = [
                {"role": t.role, "content": t.content}
                for t in (session.conversation_history or [])[-6:]
            ]
            resp = await client.post(
                f"{settings.rag_service_url}/v1/rag/query",
                json={
                    "query": rag_query,
                    "tenant_id": session.tenant_id,
                    "collection_name": collection_name,
                    "tenant_name": tenant_name,
                    "history": recent_history or None,
                    "user_language": user_language,
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

    # If RAG returns an empty or whitespace-only answer, treat it as a fallback
    if not (isinstance(answer, str) and answer.strip()):
        logger.info("rag_empty_answer_detected", tenant_id=session.tenant_id, session_id=session.session_id)
        is_fallback = True
        # Prefer a friendly fallback message instead of empty string
        answer = error_msg

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
    to_state: str = "__same__",
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
    # Respect the transition's configured to_state.
    # Fall back to current session state (not hardcoded RECOMMENDING) when unset.
    final_state = _resolve_fsm_state(to_state, session.fsm_state)
    await transition_state(session, final_state)

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
        new_state=final_state,
        session=session,
        recommendations=rec_result,
    )


# ─────────────────────────────────────────────────────────────────
# Bokun skill — external activity catalogue + real-time availability
# ─────────────────────────────────────────────────────────────────

async def _handle_bokun_skill(
    *,
    message: str,
    entities: "IntentEntities",
    session: "SessionState",
    settings: "OrchestratorSettings",
    skill: "SkillConfig | None" = None,
    to_state: str = "__same__",
) -> "FSMResult":
    """
    Calls the Bokun skill service to list activities and/or check availability.

    Logic:
    - If the user provided a date (entities.date) → query availabilities for each
      active activity and surface those with open slots.
    - If no date → just list all active activities with their details.

    The FSM calls this handler when intent is `booking_query`, `availability_check`,
    or a custom skill action set to "bokun".
    """
    tpl = skill.response_templates if skill else {}
    error_msg = tpl.get(
        "error",
        "En este momento no puedo consultar la disponibilidad. ¿Puedes intentarlo de nuevo en un momento?",
    )
    empty_msg = tpl.get("empty", "No encontré experiencias disponibles para las fechas solicitadas.")
    success_msg = tpl.get("success", "Encontré estas experiencias disponibles:")

    bokun_url = settings.bokun_url
    currency = settings.bokun_default_currency
    lang = settings.bokun_default_lang

    # ── Case 1: user has a date → check availabilities ────────────────────────
    if entities.date:
        date_str = str(entities.date)  # already "YYYY-MM-DD" from intent extraction

        # First, get the list of active activity IDs
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                ids_resp = await client.get(
                    f"{bokun_url}/v1/bokun/activities",
                    params={"lang": lang, "currency": currency, "limit": 20},
                )
                ids_resp.raise_for_status()
                activities_data = ids_resp.json()["data"]["activities"]
        except Exception as exc:
            logger.error("bokun_list_failed", error=str(exc))
            return FSMResult(response_text=error_msg, new_state=session.fsm_state, session=session)

        if not activities_data:
            return FSMResult(response_text=empty_msg, new_state=session.fsm_state, session=session)

        # Check availability for each activity on the requested date
        available: list[dict] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for act in activities_data:
                activity_id = act.get("id")
                if not activity_id:
                    continue
                try:
                    avail_resp = await client.post(
                        f"{bokun_url}/v1/bokun/activities/{activity_id}/availabilities",
                        json={
                            "start_date": date_str,
                            "end_date": date_str,
                            "currency": currency,
                            "lang": lang,
                            "include_sold_out": False,
                        },
                    )
                    avail_resp.raise_for_status()
                    avail_data = avail_resp.json()["data"]
                    # NIA bokun service returns {"slots": [...], "count": N}
                    slots = avail_data.get("slots", [])
                    if slots:
                        available.append({"activity": act, "slots": slots})
                except Exception as exc:
                    logger.warning("bokun_avail_failed", activity_id=activity_id, error=str(exc))

        if not available:
            return FSMResult(
                response_text=f"No encontré disponibilidad para el {date_str}. ¿Quieres intentar con otra fecha?",
                new_state=session.fsm_state,
                session=session,
            )

        lines = [f"{success_msg} ({date_str})\n"]
        for i, item in enumerate(available[:5], 1):
            act = item["activity"]
            name = act.get("title") or act.get("name") or f"Experiencia {act.get('id')}"
            slots = item["slots"]
            time_labels = [s.get("startTimeLabel") or s.get("startTime", "") for s in slots[:3] if s.get("startTimeLabel") or s.get("startTime")]
            slot_summary = ", ".join(time_labels) if time_labels else f"{len(slots)} horario(s)"
            lines.append(f"**{i}. {name}** — {slot_summary}")
        lines.append("\n¿Te gustaría reservar alguna de estas experiencias?")

    # ── Case 2: no date → just list active activities ─────────────────────────
    else:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{bokun_url}/v1/bokun/activities",
                    params={"lang": lang, "currency": currency, "limit": 10},
                )
                resp.raise_for_status()
                activities_data = resp.json()["data"]["activities"]
        except Exception as exc:
            logger.error("bokun_list_failed", error=str(exc))
            return FSMResult(response_text=error_msg, new_state=session.fsm_state, session=session)

        if not activities_data:
            return FSMResult(response_text=empty_msg, new_state=session.fsm_state, session=session)

        lines = [f"{success_msg}\n"]
        for i, act in enumerate(activities_data[:8], 1):
            name = act.get("title") or act.get("name") or f"Experiencia {act.get('id')}"
            desc = act.get("shortDescription") or act.get("description") or ""
            excerpt = desc[:120].rstrip() + ("…" if len(desc) > 120 else "")
            price_info = ""
            price_money = act.get("nextDefaultPriceMoney") or {}
            if price_money.get("amount"):
                amount = f"{price_money['amount']:,.0f}" if isinstance(price_money["amount"], (int, float)) else price_money["amount"]
                price_info = f" — desde {amount} {price_money.get('currency', currency)}"
            elif act.get("lowestPrice"):
                price_info = f" — desde {act['lowestPrice']} {act.get('currency', currency)}"
            lines.append(f"**{i}. {name}**{price_info}")
            if excerpt:
                lines.append(f"   {excerpt}")
        lines.append("\n¿Para qué fecha quieres ver disponibilidad?")

    final_state = _resolve_fsm_state(to_state, session.fsm_state)
    await transition_state(session, final_state)

    logger.info(
        "bokun_skill_answered",
        tenant_id=session.tenant_id,
        date=str(entities.date) if entities.date else None,
        activities_shown=len(lines) - 2,  # rough count
    )

    return FSMResult(
        response_text="\n".join(lines),
        new_state=final_state,
        session=session,
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
