#!/usr/bin/env python3
"""
RAG Service Simplificado - Para demo y pruebas
Puerto: 8002
"""

from typing import List, Optional
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

app = FastAPI(
    title="NIA RAG Service (Demo)",
    description="Ingestion and retrieval-augmented generation for tourism knowledge bases",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    tenant_id: str
    collection_name: str
    tenant_name: str = "el centro de turismo"

class RAGChunkSource(BaseModel):
    doc_id: str = ""
    doc_name: str = ""
    chunk_index: int = 0
    section: Optional[str] = None
    retrieval_score: float = 0.0
    rerank_score: float = 0.0
    text_excerpt: str = ""

class RAGQueryResult(BaseModel):
    query: str
    answer: str
    confidence_score: float
    chunks_used: List[RAGChunkSource]
    groundedness_check: bool = True
    retrieval_model: str = "demo-embed-model"
    generation_model: str = "demo-llm"
    latency_retrieval_ms: float = 45.0
    latency_generation_ms: float = 800.0
    is_fallback: bool = False

class APIResponse(BaseModel):
    data: RAGQueryResult

class IngestResponse(BaseModel):
    doc_id: str
    filename: str
    chunks_created: int
    tenant_id: str

class IngestAPIResponse(BaseModel):
    data: IngestResponse

# ─────────────────────────────────────────────────────────────────
# Mock Knowledge Base
# ─────────────────────────────────────────────────────────────────

DEMO_KNOWLEDGE = {
    "rafting": {
        "answer": "Ofrecemos rafting en el río Maipo con guías certificados. Tours de medio día ($45.000) y día completo ($85.000). Incluye equipo de seguridad, transporte y almuerzo. Disponible sábados y domingos de octubre a marzo.",
        "source": "Catálogo de Aventuras - Río Maipo"
    },
    "horarios": {
        "answer": "Nuestros horarios de atención son: Lunes a Viernes 9:00 - 18:00, Sábados 9:00 - 15:00. Para emergencias durante tours: +56 9 8765 4321",
        "source": "Manual de Información General"
    },
    "precios": {
        "answer": "Tarifas principales: Rafting medio día $45.000, día completo $85.000. Trekking Cajón del Maipo $35.000. City tour Santiago $25.000. Descuentos grupales (+6 personas): 15%",
        "source": "Lista de Precios 2024"
    },
    "equipamiento": {
        "answer": "Proporcionamos todo el equipamiento necesario: cascos, chalecos salvavidas, remos, trajes de neopreno (según temporada). Solo trae ropa cómoda y zapatos deportivos.",
        "source": "Manual de Equipamiento"
    }
}

# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/v1/rag/query",
    response_model=APIResponse,
    summary="Query the RAG knowledge base",
    tags=["🔍 RAG Query"],
)
async def rag_query(request: QueryRequest) -> APIResponse:
    """Consulta simulada al sistema RAG con conocimiento de demo."""
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Empty query")

    # Buscar en conocimiento demo
    query_lower = request.query.lower()
    
    best_match = None
    for key, data in DEMO_KNOWLEDGE.items():
        if key in query_lower:
            best_match = data
            break
    
    # Si no encuentra coincidencia exacta, usar una respuesta genérica
    if not best_match:
        if any(word in query_lower for word in ["actividad", "tour", "qué"]):
            best_match = {
                "answer": "Ofrecemos diversas actividades: rafting, trekking, city tours y más. Para información específica consulta nuestro catálogo completo o contacta a nuestros asesores.",
                "source": "Catálogo General"
            }
        else:
            best_match = {
                "answer": "No tengo información precisa sobre eso en mi base de conocimiento. ¿Te gustaría que te conecte con uno de nuestros asesores?",
                "source": "Respuesta automática"
            }

    # Crear respuesta simulada
    chunk_source = RAGChunkSource(
        doc_id="demo_doc_001",
        doc_name=best_match["source"],
        chunk_index=0,
        section="main_content",
        retrieval_score=0.85,
        rerank_score=0.92,
        text_excerpt=best_match["answer"][:200] + "..."
    )

    result = RAGQueryResult(
        query=request.query,
        answer=best_match["answer"],
        confidence_score=0.85,
        chunks_used=[chunk_source],
        groundedness_check=True,
        retrieval_model="demo-embed-model",
        generation_model="demo-llm",
        latency_retrieval_ms=45.0,
        latency_generation_ms=800.0,
        is_fallback=False
    )

    return APIResponse(data=result)


@app.post(
    "/v1/rag/ingest",
    response_model=IngestAPIResponse,
    status_code=201,
    summary="Ingest a document into the knowledge base",
    tags=["📚 Knowledge Management"],
)
async def ingest(
    tenant_id: str = Form(...),
    collection_name: str = Form(...),
    file: UploadFile = File(...),
) -> IngestAPIResponse:
    """Simulación de ingesta de documentos."""
    import uuid
    
    doc_id = str(uuid.uuid4())
    filename = file.filename or "document"
    content = await file.read()
    
    # Simular procesamiento
    estimated_chunks = len(content) // 1000  # Aprox. 1 chunk por cada 1KB
    
    return IngestAPIResponse(
        data=IngestResponse(
            doc_id=doc_id,
            filename=filename,
            chunks_created=max(1, estimated_chunks),
            tenant_id=tenant_id,
        )
    )


@app.post(
    "/v1/rag/ingest-json",
    response_model=IngestAPIResponse,
    status_code=201,
    summary="Ingest a JSON knowledge base (array of activity/knowledge objects)",
    tags=["📚 Knowledge Management"],
)
async def ingest_json(
    tenant_id: str = Form(...),
    collection_name: str = Form(...),
    file: UploadFile = File(...),
) -> IngestAPIResponse:
    """Simulación de ingesta de conocimiento JSON."""
    import uuid
    
    doc_id = str(uuid.uuid4())
    filename = file.filename or "knowledge.json"
    
    try:
        content = await file.read()
        data = json.loads(content)
        
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                data = [data]
        
        chunks_created = len(data) if isinstance(data, list) else 1
        
        return IngestAPIResponse(
            data=IngestResponse(
                doc_id=doc_id,
                filename=filename,
                chunks_created=chunks_created,
                tenant_id=tenant_id,
            )
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON file")


@app.delete(
    "/v1/rag/documents/{doc_id}",
    summary="Delete all chunks for a document",
    tags=["📚 Knowledge Management"],
)
async def delete_document(doc_id: str, tenant_id: str, collection_name: str):
    """Simulación de eliminación de documentos."""
    return {"deleted": True, "doc_id": doc_id, "tenant_id": tenant_id}


@app.get("/health", tags=["ops"])
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rag-demo", "qdrant": True}


@app.get("/", tags=["info"])
async def root():
    """Root endpoint con información del servicio."""
    return {
        "service": "NIA RAG Service (Demo)",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    print("🚀 Iniciando RAG Service (Demo) en puerto 8002...")
    print("📖 Documentación disponible en:")
    print("   🌐 http://localhost:8002/docs (Swagger UI)")
    print("   🌐 http://localhost:8002/redoc (ReDoc)")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)