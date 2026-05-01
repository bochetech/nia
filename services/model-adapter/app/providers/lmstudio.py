"""
LM Studio provider — usa la API OpenAI-compat de LM Studio.

Todas las llamadas de chat van a:
    POST /v1/chat/completions  (OpenAI-compat)
    → soporta response_format para structured output (json_schema)

Para structured output (intent detection): response_format con json_schema + enum.

Embeddings: POST /v1/embeddings  (OpenAI-compat)
Health:     GET  /api/v1/models
"""
from __future__ import annotations

import json
import re
import time
from typing import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    ModelProviderAdapter,
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ── Thinking stripper ────────────────────────────────────────────────────────
_THINK_TAG_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_THINK_BLOCK_RE = re.compile(
    r"^(Thinking Process|Think|Razonamiento|Pensamiento)\s*:.*?\n\n",
    re.DOTALL | re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    """Remove inline chain-of-thought blocks that gemma-4-e2b may prepend."""
    text = _THINK_TAG_RE.sub("", text)
    text = _THINK_BLOCK_RE.sub("", text)
    return text.strip()


class LMStudioProvider(ModelProviderAdapter):
    """
    Conecta con LM Studio.
    Base URL raíz: http://host.docker.internal:1234  (sin /v1)
    """

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        timeout: int = 120,
    ) -> None:
        self._chat_model = chat_model
        self._embed_model = embed_model
        self._timeout = timeout
        # Resolve hostname → IPv4 only to avoid httpcore "Happy Eyeballs" trying
        # IPv6 concurrently. LM Studio only listens on IPv4, and Docker's internal
        # IPv6 routing to host.docker.internal is unreliable, which causes random
        # "All connection attempts failed" errors when IPv6 gets tried first.
        self._base_url = self._resolve_ipv4(base_url.rstrip("/"))
        # Persistent client used for health checks only
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
        )

    @staticmethod
    def _resolve_ipv4(url: str) -> str:
        """Replace the hostname in url with its first IPv4 address."""
        import socket
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port, socket.AF_INET, socket.SOCK_STREAM)
            ipv4 = infos[0][4][0]
            netloc = f"{ipv4}:{parsed.port}" if parsed.port else ipv4
            resolved = urlunparse(parsed._replace(netloc=netloc))
            logger.info("lmstudio_resolved_ipv4", original=url, resolved=resolved)
            return resolved
        except Exception as exc:
            logger.warning("lmstudio_resolve_failed", url=url, error=str(exc))
            return url

    @property
    def name(self) -> str:
        return "lmstudio"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _split_messages(self, request: ChatRequest) -> tuple[str | None, list[dict]]:
        """
        Separa el system prompt del historial de conversación.
        Retorna (system_prompt | None, conversation_turns).
        """
        system_prompt: str | None = None
        conversation: list[dict] = []

        for msg in request.messages:
            if msg.role == "system":
                system_prompt = (system_prompt + "\n" + msg.content) if system_prompt else msg.content
            else:
                conversation.append({"role": msg.role, "content": msg.content})

        return system_prompt, conversation

    def _is_single_turn(self, conversation: list[dict]) -> bool:
        """True si la conversación es solo un mensaje de usuario (sin historial)."""
        return len(conversation) == 1 and conversation[0]["role"] == "user"

    # ── Chat ─────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1.5, min=2, max=12))
    async def chat(self, request: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        # Always use OpenAI-compat /v1/chat/completions — it works reliably even
        # after embed calls (the native /api/v1/chat can get stale connection errors
        # when the httpx connection pool is reused after a /v1/embeddings call).
        return await self._chat_openai_compat(request, t0)

    async def _chat_openai_compat(self, request: ChatRequest, t0: float) -> ChatResponse:
        """Uses the OpenAI-compat /v1/chat/completions endpoint.
        This is now the primary path for ALL chat calls — it works reliably
        even after embed calls, unlike the native /api/v1/chat endpoint.
        When response_format is set (json_schema), it's passed through for
        structured output support.
        Uses a fresh per-request httpx client to avoid stale connection issues
        that occur when the persistent client is reused after an embed call.
        """
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        payload: dict = {
            "model": self._chat_model,
            "messages": messages,
            "stream": False,
        }
        # Only include response_format when explicitly set (don't send null)
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            # Fresh client per-request avoids stale connection pool after embed
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            ) as client:
                resp = await client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("lmstudio_compat_error", error=str(exc))
            raise

        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000
        choice = (data.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "")
        # Strip any inline thinking/reasoning block that gemma-4-e2b may prepend
        # (e.g. "<think>...</think>" or "Thinking Process:\n...\n\n")
        content = _strip_thinking(content)
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model_id = data.get("model", self._chat_model)

        logger.info(
            "lmstudio_compat_ok",
            model=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(latency_ms),
        )
        return ChatResponse(
            content=content,
            model=model_id,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming SSE via /api/v1/chat (native endpoint, supports reasoning: off).

        For multi-turn conversations the history is serialised into the system_prompt
        block because the native API's array-input format returns empty output for
        multi-turn (confirmed via curl testing).
        """
        system_prompt, conversation = self._split_messages(request)

        if self._is_single_turn(conversation):
            input_text = conversation[0]["content"]
            effective_system = system_prompt
        else:
            history_turns = conversation[:-1]
            last_user_msg = conversation[-1]["content"]

            history_lines: list[str] = []
            for msg in history_turns:
                role_label = "Usuario" if msg["role"] == "user" else "Asistente"
                history_lines.append(f"{role_label}: {msg['content']}")

            history_block = "\n".join(history_lines)
            effective_system = (
                f"{system_prompt}\n\n### Historial de conversación\n{history_block}"
                if system_prompt
                else f"### Historial de conversación\n{history_block}"
            )
            input_text = last_user_msg

        payload: dict = {
            "model": self._chat_model,
            "input": input_text,
            "stream": True,
        }
        if effective_system:
            payload["system_prompt"] = effective_system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if not request.enable_thinking:
            payload["reasoning"] = "off"

        async with self._client.stream("POST", "/api/v1/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                chunk = line[6:].strip()
                if chunk in ("[DONE]", ""):
                    break
                try:
                    data = json.loads(chunk)
                    # Formato nativo streaming: {"type": "message.delta", "content": "texto"}
                    if data.get("type") == "message.delta":
                        if text := data.get("content", ""):
                            yield text
                except (json.JSONDecodeError, KeyError):
                    continue

    # ── Embed ────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        t0 = time.perf_counter()
        payload = {
            "model": self._embed_model,
            "input": request.texts,
        }
        try:
            # Fresh client per-request for same reason as chat
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            ) as client:
                resp = await client.post("/v1/embeddings", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("lmstudio_embed_error", error=str(exc))
            raise

        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000
        embeddings = [
            item["embedding"]
            for item in sorted(data["data"], key=lambda x: x["index"])
        ]

        return EmbedResponse(
            embeddings=embeddings,
            model=self._embed_model,
            provider=self.name,
            latency_ms=latency_ms,
        )

    # ── Health / lifecycle ────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/api/v1/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()


