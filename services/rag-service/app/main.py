"""
RAG Service — FastAPI entry point.
Puerto: 8002
"""
import json as _json
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
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
        "Ingestion and retrieval-augmented generation for tenant knowledge bases. "
        "Supports plain text, Markdown and JSON documents."
    ),
    version="1.0.0",
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
