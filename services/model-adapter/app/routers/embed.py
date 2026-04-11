"""Router de embeddings — /embed."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.providers.base import EmbedRequest, EmbedResponse
from app.providers.factory import create_provider
from app.settings import get_settings
from shared.utils.logging import get_logger
from shared.utils.responses import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/embed", tags=["embeddings"])


@router.post(
    "",
    response_model=APIResponse[EmbedResponse],
    summary="Generate text embeddings",
)
async def embed_texts(request: EmbedRequest) -> APIResponse[EmbedResponse]:
    if not request.texts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="texts list cannot be empty",
        )
    if len(request.texts) > 256:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 256 texts per request",
        )

    provider = create_provider(get_settings())
    try:
        result = await provider.embed(request)
    except Exception as exc:
        logger.error("embed_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {exc}",
        ) from exc

    return APIResponse(data=result)
