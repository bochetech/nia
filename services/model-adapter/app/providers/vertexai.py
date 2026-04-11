"""
Vertex AI provider — implementa ModelProviderAdapter contra Gemini.
"""
from __future__ import annotations

import time
from typing import AsyncIterator

from app.providers.base import (
    ChatRequest,
    ChatResponse,
    EmbedRequest,
    EmbedResponse,
    ModelProviderAdapter,
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)


class VertexAIProvider(ModelProviderAdapter):
    """
    Conecta con Vertex AI Gemini.
    Requiere GOOGLE_APPLICATION_CREDENTIALS configurado.
    """

    def __init__(
        self,
        project: str,
        location: str,
        chat_model: str,
        pro_model: str,
        embed_model: str,
    ) -> None:
        self._project = project
        self._location = location
        self._chat_model = chat_model
        self._pro_model = pro_model
        self._embed_model = embed_model
        self._client = None
        self._embed_client = None

    def _ensure_clients(self) -> None:
        if self._client is None:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                from vertexai.language_models import TextEmbeddingModel

                vertexai.init(project=self._project, location=self._location)
                self._client = GenerativeModel
                self._embed_client = TextEmbeddingModel
            except ImportError as exc:
                raise RuntimeError("google-cloud-aiplatform not installed") from exc

    @property
    def name(self) -> str:
        return "vertexai"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        self._ensure_clients()
        import asyncio

        t0 = time.perf_counter()

        # Construir historial y mensaje final
        messages = request.messages
        system_msg = next((m.content for m in messages if m.role == "system"), None)
        history = []
        user_messages = [m for m in messages if m.role != "system"]

        # En Vertex AI, los mensajes alternan user/model
        for i, msg in enumerate(user_messages[:-1]):
            history.append({
                "role": "user" if msg.role == "user" else "model",
                "parts": [msg.content],
            })

        last_user_msg = user_messages[-1].content if user_messages else ""

        from vertexai.generative_models import GenerationConfig, GenerativeModel

        model_name = self._pro_model if len(request.messages) > 10 else self._chat_model
        model = GenerativeModel(
            model_name,
            system_instruction=system_msg,
        )

        gen_config = GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )

        chat = model.start_chat(history=history)  # type: ignore[arg-type]
        response = await asyncio.to_thread(
            chat.send_message,
            last_user_msg,
            generation_config=gen_config,
        )

        latency_ms = (time.perf_counter() - t0) * 1000
        content = response.text
        usage = response.usage_metadata

        logger.info(
            "vertexai_chat_ok",
            model=model_name,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            latency_ms=round(latency_ms),
        )

        return ChatResponse(
            content=content,
            model=model_name,
            provider=self.name,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            latency_ms=latency_ms,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        self._ensure_clients()
        import asyncio

        messages = request.messages
        system_msg = next((m.content for m in messages if m.role == "system"), None)
        user_messages = [m for m in messages if m.role != "system"]
        last_user_msg = user_messages[-1].content if user_messages else ""
        history = [
            {"role": "user" if m.role == "user" else "model", "parts": [m.content]}
            for m in user_messages[:-1]
        ]

        from vertexai.generative_models import GenerationConfig, GenerativeModel

        model_name = self._chat_model
        model = GenerativeModel(model_name, system_instruction=system_msg)
        gen_config = GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )
        chat = model.start_chat(history=history)  # type: ignore[arg-type]

        # Vertex AI streaming es síncrono — lo envolvemos
        def _stream():
            return chat.send_message(
                last_user_msg,
                generation_config=gen_config,
                stream=True,
            )

        stream = await asyncio.to_thread(_stream)
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        self._ensure_clients()
        import asyncio

        t0 = time.perf_counter()

        from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

        model = TextEmbeddingModel.from_pretrained(self._embed_model)
        inputs = [TextEmbeddingInput(text=t, task_type="RETRIEVAL_DOCUMENT") for t in request.texts]

        embeddings_result = await asyncio.to_thread(model.get_embeddings, inputs)
        embeddings = [e.values for e in embeddings_result]

        latency_ms = (time.perf_counter() - t0) * 1000

        return EmbedResponse(
            embeddings=embeddings,
            model=self._embed_model,
            provider=self.name,
            latency_ms=latency_ms,
        )

    async def health_check(self) -> bool:
        try:
            self._ensure_clients()
            return True
        except Exception:
            return False
