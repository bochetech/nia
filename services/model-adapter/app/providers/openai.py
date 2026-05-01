"""
OpenAI provider — usa la API oficial de OpenAI (o cualquier servidor OpenAI-compat).

Chat:       POST /v1/chat/completions  con  messages=[{role, content}]
Embeddings: POST /v1/embeddings
Health:     GET  /v1/models
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


class OpenAIProvider(ModelProviderAdapter):
    """Provider para OpenAI y servidores OpenAI-compatible (/v1/chat/completions)."""

    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embed_model: str,
        api_key: str = "",
        timeout: int = 120,
    ) -> None:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )
        self._chat_model = chat_model
        self._embed_model = embed_model

    @property
    def name(self) -> str:
        return "openai"

    def _build_messages(self, request: ChatRequest) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in request.messages]

    # ── Chat ─────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def chat(self, request: ChatRequest) -> ChatResponse:
        t0 = time.perf_counter()
        payload: dict = {
            "model": self._chat_model,
            "messages": self._build_messages(request),
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
            logger.error("openai_chat_error", error=str(exc))
            raise

        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000

        content = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        model_id = data.get("model", self._chat_model)

        logger.info(
            "openai_chat_ok",
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
        payload: dict = {
            "model": self._chat_model,
            "messages": self._build_messages(request),
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

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
                    if content := data["choices"][0].get("delta", {}).get("content"):
                        yield content
                except (json.JSONDecodeError, KeyError):
                    continue

    # ── Embed ─────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        t0 = time.perf_counter()
        payload = {"model": self._embed_model, "input": request.texts}
        try:
            resp = await self._client.post("/v1/embeddings", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("openai_embed_error", error=str(exc))
            raise

        data = resp.json()
        latency_ms = (time.perf_counter() - t0) * 1000
        embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
        return EmbedResponse(
            embeddings=embeddings,
            model=data.get("model", self._embed_model),
            provider=self.name,
            latency_ms=latency_ms,
        )

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/v1/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False
