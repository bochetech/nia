"""
LM Studio provider — usa la API más apropiada según el contexto:

• Single-turn (un solo mensaje de usuario):
    POST /api/v1/chat  con  input=<string>  y  system_prompt=<string>
    → respuesta: output[0].content

• Multi-turn (historial de conversación):
    POST /v1/chat/completions  con  messages=[{role, content}]  (OpenAI-compat)
    → respuesta: choices[0].message.content

Embeddings: POST /v1/embeddings  (OpenAI-compat)
Health:     GET  /api/v1/models
"""
from __future__ import annotations

import json
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
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embed_model = embed_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
        )

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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def chat(self, request: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        system_prompt, conversation = self._split_messages(request)

        if self._is_single_turn(conversation):
            # API nativa v1: input como string, system_prompt top-level
            payload: dict = {
                "model": self._chat_model,
                "input": conversation[0]["content"],
                "stream": False,
            }
            if system_prompt:
                payload["system_prompt"] = system_prompt
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            # Nota: la API nativa v1 no soporta max_tokens ni max_prediction_tokens

            try:
                resp = await self._client.post("/api/v1/chat", json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("lmstudio_chat_error", error=str(exc))
                raise

            data = resp.json()
            latency_ms = (time.perf_counter() - t0) * 1000

            # Formato nativo: {"output": [{"type": "message", "content": "..."}], "stats": {...}}
            output_blocks = data.get("output", [])
            content = next(
                (b["content"] for b in output_blocks if b.get("type") == "message"), ""
            )
            stats = data.get("stats", {})
            input_tokens = stats.get("input_tokens", 0)
            output_tokens = stats.get("total_output_tokens", 0)
            model_id = data.get("model_instance_id", self._chat_model)

        else:
            # OpenAI-compat: historial multi-turno con messages array
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(conversation)

            payload = {
                "model": self._chat_model,
                "messages": messages,
                "stream": False,
            }
            if request.temperature is not None:
                payload["temperature"] = request.temperature
            if request.max_tokens is not None:
                payload["max_tokens"] = request.max_tokens

            try:
                resp = await self._client.post("/v1/chat/completions", json=payload)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("lmstudio_chat_error", error=str(exc))
                raise

            data = resp.json()
            latency_ms = (time.perf_counter() - t0) * 1000

            # Formato OpenAI-compat: {"choices": [{"message": {"content": "..."}}], "usage": {...}}
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            model_id = data.get("model", self._chat_model)

        logger.info(
            "lmstudio_chat_ok",
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
        """Streaming SSE. Single-turn: /api/v1/chat. Multi-turn: /v1/chat/completions."""
        system_prompt, conversation = self._split_messages(request)

        if self._is_single_turn(conversation):
            payload: dict = {
                "model": self._chat_model,
                "input": conversation[0]["content"],
                "stream": True,
            }
            if system_prompt:
                payload["system_prompt"] = system_prompt
            if request.temperature is not None:
                payload["temperature"] = request.temperature
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

        else:
            # OpenAI-compat streaming para multi-turno
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(conversation)

            payload = {
                "model": self._chat_model,
                "messages": messages,
                "stream": True,
            }
            if request.temperature is not None:
                payload["temperature"] = request.temperature

            async with self._client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                        delta = data["choices"][0].get("delta", {})
                        if content := delta.get("content"):
                            yield content
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
            resp = await self._client.post("/v1/embeddings", json=payload)
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


