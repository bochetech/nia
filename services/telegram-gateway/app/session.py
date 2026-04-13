"""
session.py — Gestión de sesiones para el canal Telegram.

Estrategia:
- El session_id se deriva deterministicamente del chat_id + tenant_id
  para que conversaciones del mismo usuario sean continuas entre reinicios.
- El JWT de widget se genera con el mismo master secret que usa tenant-manager,
  así el orchestrator puede verificarlo sin cambios.
"""
import hashlib

from shared.security.jwt import create_widget_token


def chat_id_to_session_id(chat_id: int, tenant_id: str) -> str:
    """
    Genera un session_id determinista y estable desde chat_id + tenant_id.
    Formato: tg_{hash8} — nunca colisiona con sesiones de widget (s_...).
    """
    raw = f"telegram:{tenant_id}:{chat_id}"
    h = hashlib.sha256(raw.encode()).hexdigest()
    return f"tg_{h[:24]}"


def create_channel_token(
    chat_id: int,
    tenant_id: str,
    jwt_secret: str,
    ttl_minutes: int = 60,
) -> tuple[str, str]:
    """
    Crea un JWT de widget para que el gateway llame al orchestrator.
    Devuelve (token, session_id).
    """
    session_id = chat_id_to_session_id(chat_id, tenant_id)

    # Reutilizamos create_widget_token — el orchestrator lo verifica igual
    # que los tokens del widget JS
    token = create_widget_token(
        session_id=session_id,
        tenant_id=tenant_id,
        secret=jwt_secret,
        page_url=f"telegram://chat/{chat_id}",
        user_agent="NIA-Telegram-Gateway/1.0",
        ttl_minutes=ttl_minutes,
    )
    return token, session_id
