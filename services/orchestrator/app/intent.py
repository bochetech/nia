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

from app.flow_defaults import DEFAULT_INTENTS, DEFAULT_SKILLS
from app.settings import OrchestratorSettings
from shared.models.domain import (
    EntityField,
    IntentDefinition,
    IntentEntities,
    IntentType,
    SkillConfig,
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ── Legacy hardcoded prompt (fallback when no IntentDefinitions exist) ────────

INTENT_SYSTEM_PROMPT = """Eres un clasificador de intenciones para un asistente de turismo.
El usuario está hablando CON ESTE NEGOCIO — cualquier pronombre implícito ("¿dónde están?", "¿cuánto cuesta?", "¿tienen X?") se refiere al negocio y sus servicios turísticos.
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

def _build_entity_schema_block(skills: list[SkillConfig]) -> str:
    """
    Build the JSON entities block for the LLM prompt from the skill configs.
    Merges all entity fields from all skills into a single flat schema.
    If no skills have entity schemas, falls back to the legacy hardcoded fields.
    """
    # Collect all unique entity fields across all skills
    fields: dict[str, EntityField] = {}
    for skill in skills:
        if skill.enabled:
            for field in skill.entity_schema:
                if field.name not in fields:
                    fields[field.name] = field

    if not fields:
        # Fallback to legacy hardcoded entities
        return """{
    "activity_type": "<tipo de actividad o null>",
    "date": "<fecha en formato YYYY-MM-DD o null>",
    "pax_count": <número de personas o null>,
    "language_preference": "<idioma preferido o null>",
    "budget_max": <presupuesto máximo en la moneda local o null>,
    "physical_level": "<low|moderate|high o null>",
    "duration_preference_hours": <horas preferidas o null>,
    "time_of_day": "<morning|afternoon|evening o null>"
  }"""

    # Build dynamic schema from entity fields
    lines = []
    for name, field in fields.items():
        type_hint = field.type
        if field.type == "enum" and field.enum_values:
            type_hint = "|".join(field.enum_values)

        desc = field.description
        if field.examples:
            examples_hint = ", ".join(f'"{e}"' for e in field.examples[:2])
            desc += f" (ej: {examples_hint})"

        null_or_type = f"<{type_hint} o null>"
        if field.type in ("integer", "float"):
            lines.append(f'    "{name}": {null_or_type}')
        else:
            lines.append(f'    "{name}": "{null_or_type}"')

    return "{\n" + ",\n".join(lines) + "\n  }"


def _build_preparation_hints(skills: list[SkillConfig]) -> str:
    """
    Build additional preparation instructions from skill configs.
    Returns a block of text with instructions for entity extraction.
    """
    hints = []
    for skill in skills:
        if skill.enabled and skill.preparation_prompt:
            hints.append(f"- Para {skill.action}: {skill.preparation_prompt}")
    if not hints:
        return ""
    return "\n\nInstrucciones de extracción de entidades:\n" + "\n".join(hints)


def build_intent_prompt(
    intents: list[IntentDefinition],
    skills: list[SkillConfig] | None = None,
    tenant_name: str | None = None,
) -> str:
    """
    Construye el system prompt para el LLM a partir de las IntentDefinitions
    configuradas por el tenant.  Genera un prompt estructurado con:
      - lista de intent keys válidos
      - guía de clasificación con descripción y ejemplos
      - formato JSON de salida con entidades dinámicas desde skill configs
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

    # Build entity schema from skill configs
    skill_list = skills or []
    entity_block = _build_entity_schema_block(skill_list)
    preparation_hints = _build_preparation_hints(skill_list)

    return f"""Eres un clasificador de intenciones para el asistente virtual de {tenant_name or "un negocio"}.
El usuario está hablando CON ESTE NEGOCIO — cualquier pronombre implícito ("¿dónde están?", "¿cuánto cuesta?", \
"¿tienen X?") se refiere a {tenant_name or "el negocio"} y sus productos o servicios.
Analiza el mensaje del usuario y responde SOLO con un objeto JSON válido con esta estructura exacta:
{{
  "intent": "<DEBES usar EXACTAMENTE uno de estos valores: {keys_str}>",
  "confidence": <número entre 0.0 y 1.0>,
  "entities": {entity_block}
}}

REGLA CRÍTICA: El campo "intent" SOLO puede contener uno de estos valores exactos (sin variaciones):
{chr(10).join(f'  - "{k}"' for k in keys)}

Guía de clasificación (evalúa en este orden de prioridad):
{guide_block}{preparation_hints}

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


def _resolve_skills(tenant_config: dict | None) -> list[SkillConfig]:
    """
    Resolve the skill configs to use for entity extraction.
    Priority: tenant fsm_config.skills → DEFAULT_SKILLS.
    """
    if tenant_config:
        raw_skills = tenant_config.get("fsm_config", {}).get("skills", [])
        if raw_skills:
            return [
                SkillConfig(**s) if isinstance(s, dict) else s
                for s in raw_skills
            ]
    return DEFAULT_SKILLS


def get_skill_config(action: str, tenant_config: dict | None = None) -> SkillConfig | None:
    """
    Get the SkillConfig for a specific action, for the given tenant.
    Returns None if no config found for that action.
    Used by FSM handlers to access response_templates and entity_schema.
    """
    skills = _resolve_skills(tenant_config)
    for skill in skills:
        if skill.action == action and skill.enabled:
            return skill
    return None


async def detect_intent(
    message: str,
    conversation_history: list[dict],
    settings: OrchestratorSettings,
    tenant_id: str | None = None,
    tenant_config: dict | None = None,
) -> tuple[IntentType | str, float, IntentEntities, dict[str, Any]]:
    """
    Detecta intent y extrae entidades del mensaje.
    Retorna (intent_key, confidence, legacy_entities, raw_entities).

    - legacy_entities: IntentEntities with known fields (backwards compat)
    - raw_entities: dict with ALL extracted fields (including custom ones from skill configs)

    intent_key is str (the IntentDefinition.key) when using dynamic intents,
    or IntentType when using legacy mode.  The FSM handles both cases.
    """
    # ── Build the prompt ──────────────────────────────────────────────────
    intent_defs = _resolve_intents(tenant_config)
    skill_defs = _resolve_skills(tenant_config)
    valid_keys = {i.key for i in intent_defs if i.enabled}

    tenant_name = (tenant_config or {}).get("ui_config", {}).get("chat_title") or None
    system_prompt = build_intent_prompt(intent_defs, skill_defs, tenant_name=tenant_name)
    logger.debug(
        "intent_prompt_built",
        tenant_id=tenant_id,
        intent_count=len(valid_keys),
        skill_count=len([s for s in skill_defs if s.enabled]),
        mode="dynamic" if tenant_config and tenant_config.get("fsm_config", {}).get("intents") else "default",
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Incluir últimos 3 turnos para contexto
    for msg in conversation_history[-3:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    # Build a json_schema response_format to force structured output.
    # This constrains the model to only use the valid intent keys via enum.
    valid_keys_list = sorted(valid_keys) if valid_keys else ["unclear"]
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "intent_classification",
            "schema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": valid_keys_list},
                    "confidence": {"type": "number"},
                    "entities": {"type": "object"},
                },
                "required": ["intent", "confidence", "entities"],
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.model_adapter_url}/v1/chat/completions",
                json={
                    "messages": messages,
                    "temperature": settings.intent_detection_temperature,
                    "max_tokens": settings.intent_max_tokens,
                    "tenant_id": tenant_id,
                    "enable_thinking": False,
                    "response_format": response_format,
                },
            )
            resp.raise_for_status()
            resp_data = resp.json()["data"]
            content = resp_data.get("content", "")
            intent_input_tokens = resp_data.get("input_tokens", 0)
            intent_output_tokens = resp_data.get("output_tokens", 0)
            intent_tokens = intent_input_tokens + intent_output_tokens

            # Reasoning models (Gemma 4, DeepSeek-R1, etc.) may return an empty
            # `content` because all tokens were consumed by the internal thinking
            # block. Fall back to `reasoning_content` which often contains the JSON.
            if not content or not content.strip():
                content = resp_data.get("reasoning_content", "")
                if content:
                    logger.debug("intent_using_reasoning_content", tenant_id=tenant_id)

        parsed = _parse_intent_response(content)
        intent_str = parsed.get("intent", "unclear")
        confidence = float(parsed.get("confidence", 0.5))
        entities_raw = parsed.get("entities", {})

        # Promote top-level language_preference into entities so it flows
        # downstream into session.metadata via raw_entities
        lang = parsed.get("language_preference")
        if lang and isinstance(lang, str) and lang.lower() not in ("null", "none", ""):
            entities_raw["language_preference"] = lang.lower()

        # ── Validate intent key against configured intents ────────────
        if intent_str not in valid_keys:
            # Try fuzzy match: look for a valid key that is a substring of
            # the returned value, or vice versa (e.g. "location_query" → "faq_query")
            fuzzy_match = _fuzzy_match_intent(intent_str, valid_keys)
            if fuzzy_match:
                logger.info(
                    "intent_fuzzy_matched",
                    tenant_id=tenant_id,
                    detected=intent_str,
                    mapped_to=fuzzy_match,
                )
                intent_str = fuzzy_match
            else:
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

        # Build legacy IntentEntities (only known fields) for backwards compat
        known_fields = set(IntentEntities.model_fields.keys())
        legacy_data = {k: v for k, v in entities_raw.items() if v is not None and k in known_fields}
        entities = IntentEntities(**legacy_data)

        # Raw entities dict keeps ALL extracted fields (including custom ones)
        raw_entities = {k: v for k, v in entities_raw.items() if v is not None}

        logger.debug(
            "intent_detected",
            intent=intent_str,
            confidence=confidence,
            entities=raw_entities,
        )
        return intent_typed, confidence, entities, raw_entities, intent_tokens, intent_input_tokens, intent_output_tokens

    except Exception as exc:
        logger.warning("intent_detection_failed", error=str(exc))
        try:
            return IntentType.UNCLEAR, 0.0, IntentEntities(), {}, 0, 0, 0
        except Exception:
            return "unclear", 0.0, IntentEntities(), {}, 0, 0, 0  # type: ignore[return-value]


def _fuzzy_match_intent(detected: str, valid_keys: set[str]) -> str | None:
    """
    Attempts to map a non-matching intent string to the closest valid key.
    Strategy:
      1. Exact substring match (e.g. "faq" in "location_query" → "faq_query")
      2. Semantic keyword mapping for common LLM hallucinations
    Returns the matched key or None.
    """
    detected_lower = detected.lower()

    # 1. Check if any valid key is a substring of detected (or vice versa)
    for key in valid_keys:
        if key in detected_lower or detected_lower in key:
            return key

    # 2. Keyword-based semantic mapping
    keyword_map: list[tuple[str, str]] = [
        # FAQ / location / info related
        ("location", "faq_query"),
        ("address", "faq_query"),
        ("hours", "faq_query"),
        ("schedule", "faq_query"),
        ("info", "faq_query"),
        ("where", "faq_query"),
        ("price", "faq_query"),
        ("cost", "faq_query"),
        ("include", "faq_query"),
        ("policy", "faq_query"),
        ("direction", "faq_query"),
        ("contact", "faq_query"),
        # Booking / purchase related
        ("book", "booking_intent"),
        ("reserv", "booking_intent"),
        ("purchas", "booking_intent"),
        ("buy", "booking_intent"),
        ("ticket", "booking_intent"),
        # Recommendation / product related
        ("recommend", "product_inquiry"),
        ("product", "product_inquiry"),
        ("activit", "product_inquiry"),
        ("tour", "product_inquiry"),
        ("option", "product_inquiry"),
        # Human request
        ("human", "human_request"),
        ("agent", "human_request"),
        ("asesor", "human_request"),
        # Complaint
        ("complaint", "complaint"),
        ("complain", "complaint"),
        ("problem", "complaint"),
    ]

    for keyword, target_key in keyword_map:
        if keyword in detected_lower and target_key in valid_keys:
            return target_key

    return None


def _parse_intent_response(content: str) -> dict:
    """Extrae el JSON del response del LLM (puede tener texto extra)."""
    content = content.strip()

    # Eliminar markdown code fences que producen los modelos de razonamiento
    # (Gemma 4, DeepSeek-R1, etc.): ```json\n{...}\n``` o ```\n{...}\n```
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
        content = content.strip()

    # Intentar parsear directo
    try:
        return json.loads(content)
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
