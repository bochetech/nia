"""
formatter.py — Convierte respuestas del orchestrator NIA a mensajes Telegram.

Telegram soporta Markdown v1, MarkdownV2 y HTML.
Usamos Markdown v1 (parse_mode="Markdown") por simplicidad.
"""
from __future__ import annotations

import re


def _escape_md(text: str) -> str:
    """Escapa caracteres especiales para Markdown básico de Telegram."""
    # Solo escapamos los que rompen el formato en modo Markdown
    return text.replace("_", r"\_").replace("*", r"\*").replace("`", r"\`")


def format_text_response(text: str, parse_mode: str = "Markdown") -> str:
    """
    Limpia y adapta el texto del orchestrator para Telegram.
    - Convierte **bold** a *bold* (Telegram usa * no **)
    - Limita a 4096 caracteres (límite de Telegram)
    """
    # Convertir markdown estilo web (**bold**) a Telegram (*bold*)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Convertir # encabezados a *bold*
    text = re.sub(r"^#{1,3}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Limitar longitud
    if len(text) > 4096:
        text = text[:4090] + "…"
    return text


def build_recommendation_buttons(recommendations: list[dict]) -> list[list[dict]]:
    """
    Convierte la lista de recomendaciones en botones inline de Telegram.
    Máximo 3 por fila, máximo 6 recomendaciones.
    """
    buttons = []
    row = []
    for i, rec in enumerate(recommendations[:6]):
        name = rec.get("name", "Opción")[:32]  # Telegram limita labels
        price = rec.get("base_price", 0)
        currency = rec.get("currency", "USD")
        label = f"{name} — {currency} {price:,.0f}"

        # Usamos callback_data para que el usuario pueda seleccionar
        row.append({
            "text": label,
            "callback_data": f"rec:{rec.get('product_id', i)}",
        })
        if len(row) == 1:  # Una por fila para legibilidad
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)
    return buttons


def build_checkout_button(checkout_url: str) -> list[list[dict]]:
    """Botón inline que abre la URL de checkout en el navegador."""
    return [[{
        "text": "💳 Ir al pago",
        "url": checkout_url,
    }]]


def build_reply_payload(
    chat_id: int,
    nia_response: dict,
    parse_mode: str = "Markdown",
) -> list[dict]:
    """
    Construye la lista de payloads a enviar a la Telegram Bot API.
    Puede ser 1 mensaje de texto + 1 mensaje con botones si hay recomendaciones.

    Retorna lista de dicts {method, payload} para enviar en secuencia.
    """
    messages = []
    text = format_text_response(nia_response.get("response", ""), parse_mode)

    # ── Mensaje principal de texto ──
    base = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }

    recommendations = nia_response.get("recommendations") or []
    checkout_url = nia_response.get("checkout_url")

    if recommendations:
        buttons = build_recommendation_buttons(recommendations)
        base["reply_markup"] = {"inline_keyboard": buttons}
    elif checkout_url:
        base["reply_markup"] = {"inline_keyboard": build_checkout_button(checkout_url)}

    messages.append({"method": "sendMessage", "payload": base})

    # ── Si hay handoff activo, avisar ──
    if nia_response.get("handoff_triggered"):
        messages.append({
            "method": "sendMessage",
            "payload": {
                "chat_id": chat_id,
                "text": "🔔 Te estamos conectando con un agente humano. En breve alguien te atenderá.",
                "parse_mode": parse_mode,
            },
        })

    return messages
