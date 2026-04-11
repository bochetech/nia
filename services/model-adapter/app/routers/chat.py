"""Router de chat — /chat/completions y /chat/stream."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.providers.base import ChatRequest, ChatResponse
from app.providers.factory import create_provider
from app.settings import get_settings
from shared.utils.logging import get_logger
from shared.utils.responses import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _get_provider():
    return create_provider(get_settings())


@router.post(
    "/completions",
    response_model=APIResponse[ChatResponse],
    summary="Chat completion (non-streaming)",
)
async def chat_completions(request: ChatRequest) -> APIResponse[ChatResponse]:
    provider = _get_provider()
    try:
        result = await provider.chat(request)
    except Exception as exc:
        logger.error("chat_completion_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Model provider error: {exc}",
        ) from exc

    return APIResponse(data=result)


@router.post(
    "/stream",
    summary="Chat completion (streaming SSE)",
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    provider = _get_provider()

    async def event_generator():
        try:
            async for chunk in provider.stream_chat(request):
                yield f"data: {chunk}\n\n"
        except Exception as exc:
            logger.error("chat_stream_failed", error=str(exc))
            yield f"data: [ERROR] {exc}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
