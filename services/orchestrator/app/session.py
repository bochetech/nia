"""
Session state manager — persiste SessionState en Redis.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from shared.db.redis_client import RedisKeys, get_redis
from shared.models.domain import ConversationFSMState, SessionState
from shared.utils.logging import get_logger

logger = get_logger(__name__)

SESSION_TTL_SECONDS = 60 * 60 * 8  # 8 horas


async def load_session(tenant_id: str, session_id: str) -> SessionState | None:
    redis = await get_redis()
    key = RedisKeys.session(tenant_id, session_id)
    raw = await redis.get(key)
    if raw:
        return SessionState(**json.loads(raw))
    return None


async def save_session(state: SessionState) -> None:
    redis = await get_redis()
    key = RedisKeys.session(state.tenant_id, state.session_id)
    state.last_active_at = datetime.now(UTC)
    await redis.setex(key, SESSION_TTL_SECONDS, state.model_dump_json())


async def create_session(tenant_id: str, session_id: str) -> SessionState:
    state = SessionState(
        session_id=session_id,
        tenant_id=tenant_id,
        fsm_state=ConversationFSMState.IDLE,
    )
    await save_session(state)
    return state


async def get_or_create_session(tenant_id: str, session_id: str) -> SessionState:
    state = await load_session(tenant_id, session_id)
    if state is None:
        state = await create_session(tenant_id, session_id)
    return state


async def transition_state(
    state: SessionState,
    new_fsm_state: ConversationFSMState,
) -> SessionState:
    """Realiza una transición de estado FSM con logging."""
    old_state = state.fsm_state
    state.previous_fsm_state = old_state
    state.fsm_state = new_fsm_state
    await save_session(state)
    logger.info(
        "fsm_transition",
        tenant_id=state.tenant_id,
        session_id=state.session_id,
        from_state=old_state,
        to_state=new_fsm_state,
    )
    return state
