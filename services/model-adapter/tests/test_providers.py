"""
Tests for model-adapter providers.
Run: pytest services/model-adapter/tests/test_providers.py -v
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.lmstudio import LMStudioProvider
from app.providers.base import ChatMessage, ChatRequest, EmbedRequest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def provider():
    return LMStudioProvider(
        base_url="http://localhost:1234",
        chat_model="google/gemma-4-e4b",
        embed_model="text-embedding-nomic-embed-text-v1.5",
    )


def _mock_ok(json_data: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = json_data
    m.raise_for_status = MagicMock()
    return m


# ── _split_messages ───────────────────────────────────────────────────────────

def test_split_messages_extracts_system_prompt(provider):
    req = ChatRequest(messages=[
        ChatMessage(role="system", content="Eres NIA."),
        ChatMessage(role="user", content="Hola"),
    ])
    sys_prompt, conv = provider._split_messages(req)
    assert sys_prompt == "Eres NIA."
    assert conv == [{"role": "user", "content": "Hola"}]


def test_split_messages_no_system(provider):
    req = ChatRequest(messages=[ChatMessage(role="user", content="Hola")])
    sys_prompt, conv = provider._split_messages(req)
    assert sys_prompt is None
    assert len(conv) == 1


def test_split_messages_multi_turn(provider):
    req = ChatRequest(messages=[
        ChatMessage(role="system", content="Eres NIA."),
        ChatMessage(role="user", content="Hola"),
        ChatMessage(role="assistant", content="¡Hola!"),
        ChatMessage(role="user", content="¿Tours?"),
    ])
    sys_prompt, conv = provider._split_messages(req)
    assert sys_prompt == "Eres NIA."
    assert len(conv) == 3
    assert conv[2] == {"role": "user", "content": "¿Tours?"}


# ── Single-turn → /api/v1/chat nativo ────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_turn_uses_native_api(provider):
    """Single-turn debe llamar a /api/v1/chat con input como string."""
    fake = {
        "model_instance_id": "google/gemma-4-e4b",
        "output": [{"type": "message", "content": "El tour cuesta $349 USD."}],
        "stats": {"input_tokens": 20, "total_output_tokens": 15},
    }
    req = ChatRequest(messages=[
        ChatMessage(role="system", content="Eres NIA."),
        ChatMessage(role="user", content="¿Cuánto cuesta el tour?"),
    ])
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_ok(fake)
        result = await provider.chat(req)

    call = mock_post.call_args
    assert call[0][0] == "/api/v1/chat"
    payload = call[1]["json"]
    assert payload["system_prompt"] == "Eres NIA."
    assert payload["input"] == "¿Cuánto cuesta el tour?"   # string, no lista
    assert result.content == "El tour cuesta $349 USD."
    assert result.input_tokens == 20
    assert result.output_tokens == 15


@pytest.mark.asyncio
async def test_single_turn_no_system_omits_system_prompt(provider):
    """Sin system message, el payload no debe incluir system_prompt."""
    fake = {
        "model_instance_id": "google/gemma-4-e4b",
        "output": [{"type": "message", "content": "¡Hola!"}],
        "stats": {"input_tokens": 5, "total_output_tokens": 3},
    }
    req = ChatRequest(messages=[ChatMessage(role="user", content="Hola")])
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_ok(fake)
        await provider.chat(req)

    payload = mock_post.call_args[1]["json"]
    assert "system_prompt" not in payload
    assert payload["input"] == "Hola"


# ── Multi-turn → /v1/chat/completions OpenAI-compat ──────────────────────────

@pytest.mark.asyncio
async def test_multi_turn_uses_openai_compat(provider):
    """Historial multi-turno debe usar /v1/chat/completions con messages array."""
    fake = {
        "model": "google/gemma-4-e4b",
        "choices": [{"message": {"role": "assistant", "content": "Hay 3 opciones."}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
    }
    req = ChatRequest(messages=[
        ChatMessage(role="system", content="Eres NIA."),
        ChatMessage(role="user", content="Hola"),
        ChatMessage(role="assistant", content="¡Hola!"),
        ChatMessage(role="user", content="¿Hay tours?"),
    ])
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_ok(fake)
        result = await provider.chat(req)

    call = mock_post.call_args
    assert call[0][0] == "/v1/chat/completions"
    payload = call[1]["json"]
    assert payload["messages"][0] == {"role": "system", "content": "Eres NIA."}
    assert payload["messages"][-1] == {"role": "user", "content": "¿Hay tours?"}
    assert result.content == "Hay 3 opciones."
    assert result.input_tokens == 30
    assert result.output_tokens == 10


# ── Retry en error HTTP ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_retries_on_503(provider):
    """Debe reintentar 3 veces ante HTTP 5xx y lanzar RetryError."""
    from tenacity import RetryError

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service unavailable", request=MagicMock(), response=mock_resp
    )
    req = ChatRequest(messages=[ChatMessage(role="user", content="Hola")])

    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(RetryError):
            await provider.chat(req)

    assert mock_post.call_count == 3


# ── Embed → /v1/embeddings ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_embed_uses_openai_compat_endpoint(provider):
    """Embeddings deben usar /v1/embeddings (OpenAI-compat)."""
    fake = {"data": [{"embedding": [0.1, 0.2, 0.3, 0.4], "index": 0}]}
    req = EmbedRequest(texts=["tour ruta maya"])
    with patch.object(provider._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _mock_ok(fake)
        result = await provider.embed(req)

    assert mock_post.call_args[0][0] == "/v1/embeddings"
    assert result.embeddings[0] == pytest.approx([0.1, 0.2, 0.3, 0.4])


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_uses_native_api(provider):
    """Health check usa GET /api/v1/models."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        assert await provider.health_check() is True
    assert mock_get.call_args[0][0] == "/api/v1/models"


@pytest.mark.asyncio
async def test_health_check_returns_false_on_error(provider):
    """Health check retorna False si hay error de conexión."""
    with patch.object(provider._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        assert await provider.health_check() is False


# ── Factory ───────────────────────────────────────────────────────────────────

def test_factory_creates_lmstudio_provider():
    """factory debe retornar LMStudioProvider cuando MODEL_PROVIDER=lmstudio."""
    import app.providers.factory as factory_mod
    from app.providers.factory import create_provider
    from app.settings import ModelAdapterSettings
    from unittest.mock import patch as mpatch

    with mpatch.dict("os.environ", {
        "MODEL_PROVIDER": "lmstudio",
        "LM_STUDIO_BASE_URL": "http://localhost:1234",
        "LM_STUDIO_CHAT_MODEL": "google/gemma-4-e4b",
        "LM_STUDIO_EMBED_MODEL": "text-embedding-nomic-embed-text-v1.5",
    }):
        factory_mod._provider_instance = None
        settings = ModelAdapterSettings()
        prov = create_provider(settings)
        factory_mod._provider_instance = None

    assert isinstance(prov, LMStudioProvider)
    assert prov._base_url == "http://localhost:1234"

