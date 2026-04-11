"""
Abstract base class para model providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str   # system | user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float = 0.3
    max_tokens: int = 1024
    stream: bool = False
    tenant_id: str | None = None
    session_id: str | None = None


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class EmbedRequest(BaseModel):
    texts: list[str]
    tenant_id: str | None = None


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    provider: str
    latency_ms: float = 0.0


class ModelProviderAdapter(ABC):
    """Interfaz que todos los proveedores deben implementar."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]: ...

    @abstractmethod
    async def embed(self, request: EmbedRequest) -> EmbedResponse: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
