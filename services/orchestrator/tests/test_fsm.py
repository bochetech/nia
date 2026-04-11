"""
Tests for orchestrator FSM state transitions.
Run: pytest services/orchestrator/tests/ -v --asyncio-mode=auto
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.fsm import ConversationFSM, FSMState, FSMEvent, FSMTransitionResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fsm() -> ConversationFSM:
    return ConversationFSM(tenant_id="test-tenant", session_id="sess_001")


# ── Initial state ─────────────────────────────────────────────────────────────

def test_fsm_initial_state(fsm):
    """FSM should start in 'idle' state."""
    assert fsm.state == FSMState.IDLE


# ── Greeting transitions ──────────────────────────────────────────────────────

def test_idle_to_greeting_on_greet(fsm):
    """IDLE + GREET → GREETING."""
    result = fsm.transition(FSMEvent.GREET)
    assert result.new_state == FSMState.GREETING
    assert result.success is True


def test_greeting_to_discovery_on_ask_intent(fsm):
    """GREETING + ASK_INTENT → DISCOVERY."""
    fsm.transition(FSMEvent.GREET)
    result = fsm.transition(FSMEvent.ASK_INTENT)
    assert result.new_state == FSMState.DISCOVERY


# ── Discovery → Recommendation ───────────────────────────────────────────────

def test_discovery_to_recommendation_on_recommend(fsm):
    """DISCOVERY + RECOMMEND → RECOMMENDATION."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    result = fsm.transition(FSMEvent.RECOMMEND)
    assert result.new_state == FSMState.RECOMMENDATION


# ── Handoff path ──────────────────────────────────────────────────────────────

def test_any_state_to_handoff_on_escalate(fsm):
    """Any state + ESCALATE → HANDOFF."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    result = fsm.transition(FSMEvent.ESCALATE)
    assert result.new_state == FSMState.HANDOFF


def test_handoff_to_resolved_on_close(fsm):
    """HANDOFF + CLOSE → RESOLVED."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    fsm.transition(FSMEvent.ESCALATE)
    result = fsm.transition(FSMEvent.CLOSE)
    assert result.new_state == FSMState.RESOLVED


# ── Booking / Checkout path ───────────────────────────────────────────────────

def test_recommendation_to_checkout_on_book(fsm):
    """RECOMMENDATION + BOOK → CHECKOUT."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    fsm.transition(FSMEvent.RECOMMEND)
    result = fsm.transition(FSMEvent.BOOK)
    assert result.new_state == FSMState.CHECKOUT


def test_checkout_to_confirmed_on_payment_success(fsm):
    """CHECKOUT + PAYMENT_SUCCESS → CONFIRMED."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    fsm.transition(FSMEvent.RECOMMEND)
    fsm.transition(FSMEvent.BOOK)
    result = fsm.transition(FSMEvent.PAYMENT_SUCCESS)
    assert result.new_state == FSMState.CONFIRMED


def test_checkout_to_discovery_on_payment_failed(fsm):
    """CHECKOUT + PAYMENT_FAILED → DISCOVERY (offer retry/alternatives)."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    fsm.transition(FSMEvent.RECOMMEND)
    fsm.transition(FSMEvent.BOOK)
    result = fsm.transition(FSMEvent.PAYMENT_FAILED)
    assert result.new_state == FSMState.DISCOVERY


# ── Fallback / Error ──────────────────────────────────────────────────────────

def test_invalid_transition_returns_failure(fsm):
    """Transitioning from IDLE with PAYMENT_SUCCESS should return failure."""
    result = fsm.transition(FSMEvent.PAYMENT_SUCCESS)
    assert result.success is False
    assert fsm.state == FSMState.IDLE  # State unchanged


def test_resolved_is_terminal(fsm):
    """RESOLVED state should not allow further transitions."""
    fsm.transition(FSMEvent.GREET)
    fsm.transition(FSMEvent.ASK_INTENT)
    fsm.transition(FSMEvent.ESCALATE)
    fsm.transition(FSMEvent.CLOSE)
    assert fsm.state == FSMState.RESOLVED
    result = fsm.transition(FSMEvent.GREET)
    assert result.success is False


# ── FSMTransitionResult ───────────────────────────────────────────────────────

def test_transition_result_has_expected_fields(fsm):
    """FSMTransitionResult should expose new_state, success, actions."""
    result = fsm.transition(FSMEvent.GREET)
    assert hasattr(result, "new_state")
    assert hasattr(result, "success")
    assert hasattr(result, "actions")
    assert isinstance(result.actions, list)
