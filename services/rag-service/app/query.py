"""
RAG query pipeline: embed → retrieve → rerank → groundedness → generate.
"""
from __future__ import annotations

import hashlib
import json
import time

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.settings import RAGSettings
from shared.db.redis_client import RedisKeys, get_redis
from shared.models.domain import RAGChunkSource, RAGQueryResult
from shared.utils.logging import get_logger

logger = get_logger(__name__)

FALLBACK_ANSWER = (
    "No tengo información precisa sobre eso en mi base de conocimiento. "
    "¿Te gustaría que te conecte con uno de nuestros asesores?"
)

SYSTEM_PROMPT_TEMPLATE = """Eres NIA, el asistente virtual de {tenant_name}.
Responde ÚNICAMENTE con la información proporcionada en el contexto de abajo.
Si la respuesta no está en el contexto, di exactamente: "No tengo información precisa sobre eso."
Responde en el mismo idioma que la pregunta. Sé conciso y amigable.
No inventes precios, fechas ni detalles que no estén en el contexto.

CONTEXTO:
{context}
"""


async def query_rag(
    *,
    query: str,
    tenant_id: str,
    collection_name: str,
    tenant_name: str,
    settings: RAGSettings,
    qdrant_client: AsyncQdrantClient,
) -> RAGQueryResult:
    """
    Pipeline completo de query RAG:
    1. Semantic cache lookup
    2. Embed query
    3. Retrieve chunks from Qdrant
    4. Rerank
    5. Groundedness check
    6. Generate answer
    7. Cache resultado
    """
    t_start = time.perf_counter()

    # 1. Semantic cache
    query_hash = hashlib.md5(f"{tenant_id}:{query.lower().strip()}".encode()).hexdigest()
    if settings.semantic_cache_enabled:
        cached = await _check_semantic_cache(tenant_id, query_hash)
        if cached:
            logger.info("rag_cache_hit", tenant_id=tenant_id)
            cached["cached"] = True
            return RAGQueryResult(**cached)

    # 2. Embed query
    t_embed_start = time.perf_counter()
    query_embedding = await _embed_query(query, tenant_id, settings)
    latency_retrieval_ms = (time.perf_counter() - t_embed_start) * 1000

    # 3. Retrieve from Qdrant
    t_search_start = time.perf_counter()
    search_results = await qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=settings.top_k_retrieval,
        query_filter=Filter(
            must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))]
        ),
        with_payload=True,
    )
    latency_retrieval_ms += (time.perf_counter() - t_search_start) * 1000

    if not search_results:
        logger.info("rag_no_results", tenant_id=tenant_id, query=query[:80])
        return _fallback_result(query, settings, latency_retrieval_ms)

    # Filtrar por threshold
    relevant = [r for r in search_results if r.score >= settings.min_confidence_threshold]
    if not relevant:
        logger.info(
            "rag_below_threshold",
            max_score=max(r.score for r in search_results),
            threshold=settings.min_confidence_threshold,
        )
        return _fallback_result(query, settings, latency_retrieval_ms)

    # 4. Rerank simple por score (top_k_after_rerank)
    top_chunks = sorted(relevant, key=lambda r: r.score, reverse=True)[:settings.top_k_after_rerank]

    chunk_sources = [
        RAGChunkSource(
            doc_id=r.payload.get("doc_id", ""),
            doc_name=r.payload.get("doc_name", ""),
            chunk_index=r.payload.get("chunk_index", 0),
            section=r.payload.get("section"),
            retrieval_score=r.score,
            rerank_score=r.score,
            text_excerpt=r.payload.get("text", "")[:200],
        )
        for r in top_chunks
    ]

    # 5. Construir contexto
    context_parts = []
    for i, r in enumerate(top_chunks, 1):
        text = r.payload.get("text", "")
        doc_name = r.payload.get("doc_name", "Documento")
        context_parts.append(f"[Fuente {i}: {doc_name}]\n{text}")
    context = "\n\n---\n\n".join(context_parts)

    # 6. Generate
    t_gen_start = time.perf_counter()
    answer, generation_model = await _generate_answer(
        query=query,
        context=context,
        tenant_name=tenant_name,
        settings=settings,
        tenant_id=tenant_id,
    )
    latency_generation_ms = (time.perf_counter() - t_gen_start) * 1000

    # 7. Groundedness check
    groundedness = "passed"
    if settings.groundedness_check_enabled:
        is_grounded = _check_groundedness(answer, context)
        groundedness = "passed" if is_grounded else "failed"
        if not is_grounded:
            logger.warning("rag_groundedness_failed", tenant_id=tenant_id)
            answer = FALLBACK_ANSWER

    result = RAGQueryResult(
        query=query,
        answer=answer,
        confidence_score=top_chunks[0].score if top_chunks else 0.0,
        chunks_used=chunk_sources,
        groundedness_check=groundedness,
        retrieval_model=settings.lm_studio_embed_model if settings.model_provider == "lmstudio" else settings.vertex_ai_embed_model,
        generation_model=generation_model,
        latency_retrieval_ms=latency_retrieval_ms,
        latency_generation_ms=latency_generation_ms,
        is_fallback=False,
    )

    # 8. Cache resultado
    if settings.semantic_cache_enabled:
        await _store_semantic_cache(tenant_id, query_hash, result)

    return result


# ─────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────

async def _embed_query(query: str, tenant_id: str, settings: RAGSettings) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.model_adapter_url}/v1/embed",
            json={"texts": [query], "tenant_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]["embeddings"][0]


async def _generate_answer(
    *,
    query: str,
    context: str,
    tenant_name: str,
    settings: RAGSettings,
    tenant_id: str,
) -> tuple[str, str]:
    """Genera la respuesta final usando el model-adapter."""
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        tenant_name=tenant_name,
        context=context,
    )
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
        "tenant_id": tenant_id,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.model_adapter_url}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        return data["content"], data["model"]


def _check_groundedness(answer: str, context: str) -> bool:
    """
    Heurística básica de groundedness:
    Verifica que ninguna oración de la respuesta sea completamente inventada.
    En producción esto sería otro LLM call o un clasificador.
    """
    if "no tengo información" in answer.lower():
        return True  # La respuesta reconoce la ausencia

    # Si la respuesta es muy corta, probablemente es válida
    if len(answer) < 50:
        return True

    # Verificar que al menos algunas palabras clave de la respuesta aparecen en el contexto
    answer_words = set(answer.lower().split())
    context_words = set(context.lower().split())
    overlap = answer_words & context_words
    # Al menos 20% de las palabras de la respuesta deben aparecer en el contexto
    return len(overlap) / max(len(answer_words), 1) >= 0.20


def _fallback_result(query: str, settings: RAGSettings, latency_ms: float) -> RAGQueryResult:
    return RAGQueryResult(
        query=query,
        answer=FALLBACK_ANSWER,
        confidence_score=0.0,
        chunks_used=[],
        groundedness_check="skipped",
        retrieval_model="n/a",
        generation_model="n/a",
        latency_retrieval_ms=latency_ms,
        latency_generation_ms=0.0,
        is_fallback=True,
    )


async def _check_semantic_cache(tenant_id: str, query_hash: str) -> dict | None:
    try:
        redis = await get_redis()
        key = RedisKeys.semantic_cache(tenant_id, query_hash)
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("semantic_cache_read_error", error=str(exc))
    return None


async def _store_semantic_cache(tenant_id: str, query_hash: str, result: RAGQueryResult) -> None:
    try:
        redis = await get_redis()
        key = RedisKeys.semantic_cache(tenant_id, query_hash)
        await redis.setex(key, 3600, result.model_dump_json())
    except Exception as exc:
        logger.warning("semantic_cache_write_error", error=str(exc))
