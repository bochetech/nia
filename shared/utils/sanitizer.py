"""
Sanitización de inputs para prevenir prompt injection y XSS.
"""
from __future__ import annotations

import re
import unicodedata

# Patrones de prompt injection conocidos
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|all|above|prior)\s+(instructions?|prompts?|context)", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\s+)", re.I),
    re.compile(r"new\s+role\s*:", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*\|?\s*(system|user|assistant)\s*\|?\s*>", re.I),
    re.compile(r"\[INST\]|\[\/INST\]|\[SYS\]|\[\/SYS\]"),
    re.compile(r"###\s*(instruction|system|prompt|human|assistant)", re.I),
    re.compile(r"override\s+your\s+(training|instructions?|system)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?(instructions?|rules?|constraints?)", re.I),
    re.compile(r"forget\s+(everything|all|your)\s+(you\s+know|previous|training|instructions?)", re.I),
    re.compile(r"print\s+(your\s+)?(system|initial|original)\s+(prompt|instructions?)", re.I),
    re.compile(r"reveal\s+your\s+(system|initial|original)\s+(prompt|instructions?)", re.I),
    re.compile(r"what\s+(are|were)\s+your\s+(exact\s+)?(system|original)\s+(instructions?|prompts?)", re.I),
]

# Límites de tamaño
MAX_USER_MESSAGE_LENGTH = 2_000
MAX_ENTITY_VALUE_LENGTH = 200


def sanitize_user_message(text: str) -> tuple[str, bool]:
    """
    Sanitiza un mensaje de usuario.
    Retorna (sanitized_text, is_suspicious).
    Si is_suspicious=True, el orquestador debe loguear y potencialmente bloquear.
    """
    # 1. Normalizar unicode (NFKC colapsa lookalike chars)
    text = unicodedata.normalize("NFKC", text)

    # 2. Truncar
    text = text[:MAX_USER_MESSAGE_LENGTH]

    # 3. Eliminar caracteres de control (excepto newline y tab)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    # 4. Detectar patrones de injection
    is_suspicious = any(pattern.search(text) for pattern in _INJECTION_PATTERNS)

    return text.strip(), is_suspicious


def sanitize_entity_value(value: str) -> str:
    """Sanitiza valores de entidades extraídas (nombres, fechas, etc.)."""
    value = unicodedata.normalize("NFKC", value)
    value = value[:MAX_ENTITY_VALUE_LENGTH]
    # Eliminar caracteres que no sean alfanuméricos, espacios, guiones, puntos, comas
    value = re.sub(r"[^\w\s\-.,/áéíóúüñÁÉÍÓÚÜÑ@+]", "", value, flags=re.UNICODE)
    return value.strip()


def sanitize_html_input(text: str) -> str:
    """
    Escapa caracteres HTML para prevenir XSS en outputs que van a HTML.
    Complementa la sanitización del frontend.
    """
    html_escape_table = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    return "".join(html_escape_table.get(c, c) for c in text)


def is_valid_tenant_id(tenant_id: str) -> bool:
    """Valida formato de tenant_id: solo alfanumérico + guion bajo, 3-50 chars."""
    return bool(re.match(r"^[a-z0-9_]{3,50}$", tenant_id))


def is_valid_session_id(session_id: str) -> bool:
    """Valida formato UUID v4."""
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        session_id,
        re.I,
    ))
