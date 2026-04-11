"""
Intent detection via LLM structured output.
Extrae intent + entidades del mensaje del usuario.
"""
from __future__ import annotations

import json
import re

import httpx

from app.settings import OrchestratorSettings
from shared.models.domain import IntentEntities, IntentType
from shared.utils.logging import get_logger

logger = get_logger(__name__)

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


async def detect_intent(
    message: str,
    conversation_history: list[dict],
    settings: OrchestratorSettings,
    tenant_id: str | None = None,
) -> tuple[IntentType, float, IntentEntities]:
    """
    Detecta intent y extrae entidades del mensaje.
    Retorna (intent_type, confidence, entities).
    """
    messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]

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

        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.UNCLEAR

        entities = IntentEntities(**{k: v for k, v in entities_raw.items() if v is not None})

        logger.debug(
            "intent_detected",
            intent=intent,
            confidence=confidence,
            entities=entities.model_dump(exclude_none=True),
        )
        return intent, confidence, entities

    except Exception as exc:
        logger.warning("intent_detection_failed", error=str(exc))
        return IntentType.UNCLEAR, 0.0, IntentEntities()


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
