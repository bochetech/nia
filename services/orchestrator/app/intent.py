"""
Intent detection via LLM structured output.
Extrae intent + entidades del mensaje del usuario.

Supports two modes:
  1. Dynamic intents  — built from tenant's fsm_config.intents (IntentDefinition list)
  2. Legacy intents   — uses the hardcoded INTENT_SYSTEM_PROMPT (IntentType enum)
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.flow_defaults import DEFAULT_INTENTS
from app.settings import OrchestratorSettings
from shared.models.domain import IntentDefinition, IntentEntities, IntentType
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ── Legacy hardcoded prompt (fallback when no IntentDefinitions exist) ────────

INTENT_SYSTEM_PROMPT = """Eres un clasificador de intenciones para un asistente de turismo.
Analiza el mensaje del usuario y responde SOLO con un objeto JSON válido con esta estructura exacta:
{
  "intent": "<uno de: booking_intent|faq_query|complaint|out_of_scope|unclear|product_inquiry|human_request|nps_response>",
  "confidence": <número entre 0.0 y 1.0>,
  "entities": {
    "activity_type": "<tipo de actividad o null>",
    "date": "<fecha en formato YYYY-MM-DD o null>",
    "pax_count": <número de personas o null>,
    "language_preference": "<idioma preferido o null>",
    "budget_max": <presupuesto máximo en la moneda local o null>,
    "physical_level": "<low|moderate|high o null>",
    "duration_preference_hours": <horas preferidas o null>,
    "time_of_day": "<morning|afternoon|evening o null>"
  }
}

Guía de clasificación:
- human_request: el usuario pide explícitamente hablar con una persona, agente o asesor humano.
- nps_response: el usuario responde con un número (1-5) o calificación a una encuesta.
- booking_intent: intención clara de reservar, comprar o confirmar una actividad.
- product_inquiry: preguntas sobre qué actividades existen, cuáles recomiendas, precios.
- faq_query: preguntas sobre horarios, ubicación, políticas, qué incluye, cómo llegar.
- complaint: queja, frustración, insatisfacción con el servicio.
- out_of_scope: temas no relacionados con turismo/actividades.
- unclear: mensaje ambiguo que no encaja claramente en ninguna categoría.

Responde ÚNICAMENTE el JSON, sin explicaciones adicionales."""


# ── Dynamic prompt builder ────────────────────────────────────────────────────

def build_intent_prompt(intents: list[IntentDefinition]) -> str:
    """
    Construye el system prompt para el LLM a partir de las IntentDefinitions
    configuradas por el tenant.  Genera un prompt estructurado con:
      - lista de intent keys válidos
      - guía de clasificación con descripción y ejemplos
      - formato JSON de salida
    """
    # Solo intents habilitados, ordenados por prioridad (mayor primero)
    active = sorted(
        [i for i in intents if i.enabled],
        key=lambda i: i.priority,
        reverse=True,
    )

    if not active:
        return INTENT_SYSTEM_PROMPT  # fallback

    keys = [i.key for i in active]
    keys_str = "|".join(keys)

    guide_lines: list[str] = []
    for i in active:
        line = f"- {i.key}: {i.description}"
        if i.examples:
            examples_str = "; ".join(f'"{e}"' for e in i.examples[:3])
            line += f" Ejemplos: {examples_str}."
        guide_lines.append(line)

    guide_block = "\n".join(guide_lines)

    return f"""Eres un clasificador de intenciones para un asistente virtual.
Analiza el mensaje del usuario y responde SOLO con un objeto JSON válido con esta estructura exacta:
{{
  "intent": "<uno de: {keys_str}>",
  "confidence": <número entre 0.0 y 1.0>,
  "entities": {{
    "activity_type": "<tipo de actividad o null>",
    "date": "<fecha en formato YYYY-MM-DD o null>",
    "pax_count": <número de personas o null>,
    "language_preference": "<idioma preferido o null>",
    "budget_max": <presupuesto máximo en la moneda local o null>",
    "physical_level": "<low|moderate|high o null>",
    "duration_preference_hours": <horas preferidas o null>,
    "time_of_day": "<morning|afternoon|evening o null>"
  }}
}}

Guía de clasificación (evalúa en este orden de prioridad):
{guide_block}

Responde ÚNICAMENTE el JSON, sin explicaciones adicionales."""


# ── Public API ────────────────────────────────────────────────────────────────

def _resolve_intents(tenant_config: dict | None) -> list[IntentDefinition]:
    """
    Resolve the intents to use for classification.
    Priority: tenant fsm_config.intents → DEFAULT_INTENTS → legacy prompt.
    """
    if tenant_config:
        raw_intents = tenant_config.get("fsm_config", {}).get("intents", [])
        if raw_intents:
            return [
                IntentDefinition(**i) if isinstance(i, dict) else i
                for i in raw_intents
            ]
    return DEFAULT_INTENTS


async def detect_intent(
    message: str,
    conversation_history: list[dict],
    settings: OrchestratorSettings,
    tenant_id: str | None = None,
    tenant_config: dict | None = None,
) -> tuple[IntentType | str, float, IntentEntities]:
    """
    Detecta intent y extrae entidades del mensaje.
    Retorna (intent_key, confidence, entities).

    intent_key is str (the IntentDefinition.key) when using dynamic intents,
    or IntentType when using legacy mode.  The FSM handles both cases.
    """
    # ── Build the prompt ──────────────────────────────────────────────────
    intent_defs = _resolve_intents(tenant_config)
    valid_keys = {i.key for i in intent_defs if i.enabled}

    system_prompt = build_intent_prompt(intent_defs)
    logger.debug(
        "intent_prompt_built",
        tenant_id=tenant_id,
        intent_count=len(valid_keys),
        mode="dynamic" if tenant_config and tenant_config.get("fsm_config", {}).get("intents") else "default",
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Incluir últimos 3 turnos para contexto
    for msg in conversation_history[-3:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": settings.intent_detection_temperature,
                    "max_tokens": settings.intent_max_tokens,
                    "tenant_id": tenant_id,
                },
            )
            resp.raise_for_status()
            content = resp.json()["data"]["content"]

        parsed = _parse_intent_response(content)
        intent_str = parsed.get("intent", "unclear")
        confidence = float(parsed.get("confidence", 0.5))
        entities_raw = parsed.get("entities", {})

        # ── Validate intent key against configured intents ────────────
        if intent_str not in valid_keys:
            logger.warning(
                "intent_not_in_config",
                tenant_id=tenant_id,
                detected=intent_str,
                valid=sorted(valid_keys),
            )
            intent_str = "unclear"

        # ── Try to map to IntentType for backwards compat ─────────────
        try:
            intent_typed = IntentType(intent_str)
        except ValueError:
            # Custom intent — return as plain string
            intent_typed = intent_str  # type: ignore[assignment]

        entities = IntentEntities(**{k: v for k, v in entities_raw.items() if v is not None})

        logger.debug(
            "intent_detected",
            intent=intent_str,
            confidence=confidence,
            entities=entities.model_dump(exclude_none=True),
        )
        return intent_typed, confidence, entities

    except Exception as exc:
        logger.warning("intent_detection_failed", error=str(exc))
        try:
            return IntentType.UNCLEAR, 0.0, IntentEntities()
        except Exception:
            return "unclear", 0.0, IntentEntities()  # type: ignore[return-value]


def _parse_intent_response(content: str) -> dict:
    """Extrae el JSON del response del LLM (puede tener texto extra)."""
    # Intentar parsear directo
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass

    # Buscar JSON dentro del texto
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"intent": "unclear", "confidence": 0.0, "entities": {}}
