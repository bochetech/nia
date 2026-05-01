"""
RAG Service — FastAPI entry point.
Puerto: 8002
"""
import json as _json
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.ingestion import ingest_document
from app.query import query_rag
from app.settings import RAGSettings, get_settings
from shared.db.redis_client import close_redis, init_redis
from shared.models.domain import RAGQueryResult
from shared.utils.health import build_health_router
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse

settings = get_settings()
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_logs=settings.json_logs,
)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA RAG Service",
    description=(
        "**[Skill]** Retrieval-Augmented Generation for tenant knowledge bases. "
        "Ingest Markdown, plain text or JSON documents into Qdrant, "
        "then answer questions grounded in the retrieved chunks via the configured LLM. "
        "Invoked by the orchestrator when the FSM routes to the `faq` action."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "rag",
            "description": "Document ingestion, vector search and LLM-grounded answers.",
        },
        {
            "name": "ops",
            "description": "Health and readiness probes.",
        },
    ],
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(build_health_router(
    service_name=settings.service_name,
    check_redis=True,
    check_qdrant=True,
))

_qdrant: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = AsyncQdrantClient(url=settings.qdrant_url)
    return _qdrant


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - t0) * 1000))
    return response


# ─────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    collection_name: str | None = None   # defaults to "{tenant_id}_docs"
    tenant_name: str = "el asistente"
    history: list[dict] | None = None    # últimos turnos de conversación [{role, content}]
    user_language: str | None = None     # detected language (e.g. "english", "french")

    model_config = {"json_schema_extra": {"example": {
        "query": "¿Cuál es el horario de la viña?",
        "tenant_id": "demo_turismo",
    }}}


class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_created: int
    tenant_id: str
    collection_name: str


class DeleteResponse(BaseModel):
    deleted: bool
    doc_id: str
    collection_name: str


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/v1/rag/query",
    response_model=APIResponse[RAGQueryResult],
    summary="Query the RAG knowledge base",
    tags=["rag"],
)
async def rag_query(request: QueryRequest) -> APIResponse[RAGQueryResult]:
    """
    Query the knowledge base for a tenant and return an LLM-generated answer
    grounded in the retrieved chunks.

    `collection_name` defaults to `{tenant_id}_docs` if not provided.
    """
    if not request.query.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty query")

    collection = request.collection_name or f"{request.tenant_id}_docs"

    result = await query_rag(
        query=request.query,
        tenant_id=request.tenant_id,
        collection_name=collection,
        tenant_name=request.tenant_name,
        settings=settings,
        qdrant_client=get_qdrant(),
        history=request.history,
        user_language=request.user_language,
    )
    return APIResponse(data=result)


@app.post(
    "/v1/rag/ingest",
    response_model=APIResponse[IngestResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a document into the knowledge base",
    tags=["rag"],
)
async def ingest(
    tenant_id: str = Form(...),
    file: UploadFile = File(...),
    collection_name: str = Form(default=""),
) -> APIResponse[IngestResponse]:
    """
    Ingest a document into the tenant knowledge base.

    - **Plain text / Markdown** (`.txt`, `.md`): chunked by paragraph and embedded.
    - **JSON file** (`.json`): auto-detected. Each top-level object becomes one chunk.
      Supports a root array `[{...}]` or a dict with one list value `{"items": [{...}]}`.

    `collection_name` defaults to `{tenant_id}_docs`.
    """
    doc_id = str(uuid.uuid4())
    raw = await file.read()
    filename = file.filename or "document"
    effective_collection = collection_name.strip() or f"{tenant_id}_docs"

    # JSON auto-detection by filename or content-type
    is_json = filename.lower().endswith(".json") or (file.content_type or "").startswith("application/json")
    if is_json:
        try:
            data = _json.loads(raw)
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}")

        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                data = [data]

        if not isinstance(data, list):
            raise HTTPException(status_code=422, detail="JSON must be a list or contain a top-level list")

        def _obj_to_text(obj: dict, index: int) -> str:
            lines = []
            for k, v in obj.items():
                if isinstance(v, (str, int, float, bool)) and v:
                    lines.append(f"{k}: {v}")
                elif isinstance(v, list) and v:
                    lines.append(f"{k}: {', '.join(str(x) for x in v)}")
            return "\n".join(lines) if lines else f"Item {index}"

        text_blocks = [_obj_to_text(obj, i) for i, obj in enumerate(data) if isinstance(obj, dict)]
        raw = "\n\n---\n\n".join(text_blocks).encode("utf-8")
        filename = filename.replace(".json", ".txt")
        logger.info("json_ingest_parsed", items=len(data), tenant_id=tenant_id)

    chunks = await ingest_document(
        content=raw,
        filename=filename,
        doc_id=doc_id,
        tenant_id=tenant_id,
        collection_name=effective_collection,
        settings=settings,
        qdrant_client=get_qdrant(),
    )

    logger.info("ingest_complete", chunks=len(chunks), collection=effective_collection, tenant_id=tenant_id)
    return APIResponse(
        data=IngestResponse(
            doc_id=doc_id,
            filename=filename,
            chunks_created=len(chunks),
            tenant_id=tenant_id,
            collection_name=effective_collection,
        )
    )


@app.delete(
    "/v1/rag/documents/{doc_id}",
    response_model=APIResponse[DeleteResponse],
    summary="Delete all chunks for a document",
    tags=["rag"],
)
async def delete_document(
    doc_id: str,
    tenant_id: str,
    collection_name: str = "",
) -> APIResponse[DeleteResponse]:
    """
    Delete all vector chunks associated with a specific document ID.
    `collection_name` defaults to `{tenant_id}_docs`.
    """
    effective_collection = collection_name.strip() or f"{tenant_id}_docs"
    qdrant = get_qdrant()
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    await qdrant.delete(
        collection_name=effective_collection,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    logger.info("document_deleted", doc_id=doc_id, collection=effective_collection, tenant_id=tenant_id)
    return APIResponse(data=DeleteResponse(deleted=True, doc_id=doc_id, collection_name=effective_collection))


@app.get(
    "/v1/rag/documents",
    summary="List ingested documents with chunk counts",
    tags=["rag"],
)
async def list_documents(
    tenant_id: str,
    collection_name: str = "",
    limit: int = 100,
):
    """
    List all distinct documents in a tenant's collection,
    grouped by doc_id with chunk counts.
    """
    effective_collection = collection_name.strip() or f"{tenant_id}_docs"
    qdrant = get_qdrant()

    try:
        from qdrant_client.models import ScrollRequest
        # Scroll all points to aggregate by doc_id
        points, _next = await qdrant.scroll(
            collection_name=effective_collection,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        exc_str = str(exc).lower()
        # Qdrant returns a specific error when collection doesn't exist
        if "not found" in exc_str or "doesn't exist" in exc_str:
            logger.warning("collection_not_found", collection=effective_collection, tenant_id=tenant_id)
            return JSONResponse(content={
                "data": [],
                "meta": {"collection_exists": False, "collection_name": effective_collection,
                         "message": f"Collection '{effective_collection}' not found. Upload a document to create it."},
            })
        logger.error("list_documents_error", error=str(exc), collection=effective_collection, tenant_id=tenant_id)
        return JSONResponse(status_code=500, content={
            "data": [],
            "meta": {"error": str(exc), "collection_name": effective_collection},
        })

    # Group by doc_id
    docs: dict[str, dict] = {}
    for pt in points:
        payload = pt.payload or {}
        doc_id = payload.get("doc_id", "unknown")
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "filename": payload.get("doc_name", payload.get("filename", "unknown")),
                "chunks_count": 0,
                "total_tokens": 0,
                "tenant_id": payload.get("tenant_id", tenant_id),
            }
        docs[doc_id]["chunks_count"] += 1
        docs[doc_id]["total_tokens"] += payload.get("tokens", 0)

    result = sorted(docs.values(), key=lambda d: d["filename"])
    return APIResponse(data=result[:limit])


@app.get(
    "/v1/rag/documents/{doc_id}/chunks",
    summary="List chunks for a specific document",
    tags=["rag"],
)
async def list_document_chunks(
    doc_id: str,
    tenant_id: str,
    collection_name: str = "",
):
    """
    Returns all chunks for a specific document, ordered by chunk_index.
    """
    effective_collection = collection_name.strip() or f"{tenant_id}_docs"
    qdrant = get_qdrant()

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        points, _ = await qdrant.scroll(
            collection_name=effective_collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        logger.error("list_chunks_error", error=str(exc), doc_id=doc_id, collection=effective_collection)
        return JSONResponse(content={"data": [], "meta": {"error": str(exc)}})

    chunks = []
    for pt in points:
        payload = pt.payload or {}
        chunks.append({
            "chunk_id": pt.id,
            "chunk_index": payload.get("chunk_index", 0),
            "text": payload.get("text", ""),
            "tokens": payload.get("tokens", 0),
            "section": payload.get("section", ""),
        })

    chunks.sort(key=lambda c: c["chunk_index"])
    return APIResponse(data=chunks)


@app.post(
    "/v1/rag/test-query",
    summary="Test a RAG query and see retrieved chunks",
    tags=["rag"],
)
async def test_query(request: QueryRequest):
    """
    Like /v1/rag/query but returns extra debug info including
    the retrieved chunks with scores, useful for the admin console.
    """
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Empty query")

    collection = request.collection_name or f"{request.tenant_id}_docs"

    result = await query_rag(
        query=request.query,
        tenant_id=request.tenant_id,
        collection_name=collection,
        tenant_name=request.tenant_name,
        settings=settings,
        qdrant_client=get_qdrant(),
    )
    return APIResponse(data=result)


@app.on_event("startup")
async def on_startup():
    logger.info("rag_service_starting")
    init_redis(settings.redis_url)
    _ = get_qdrant()
    logger.info("rag_service_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    global _qdrant
    if _qdrant:
        await _qdrant.close()
    await close_redis()
