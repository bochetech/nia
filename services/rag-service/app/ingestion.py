"""
Ingestion pipeline: document → chunks → embeddings → Qdrant.
Soporta PDF, DOCX, TXT, Markdown.
"""
from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from app.settings import RAGSettings
from shared.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    doc_name: str
    section: str
    chunk_index: int
    text: str
    tokens: int
    metadata: dict


# ─────────────────────────────────────────────────────────────────
# Text extraction
# ─────────────────────────────────────────────────────────────────

def extract_text_from_pdf(content: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def extract_text_from_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(content: bytes, filename: str) -> str:
    fname = filename.lower()
    if fname.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif fname.endswith(".docx"):
        return extract_text_from_docx(content)
    else:
        # TXT / MD — detectar encoding
        import chardet
        detected = chardet.detect(content)
        encoding = detected.get("encoding") or "utf-8"
        return content.decode(encoding, errors="replace")


# ─────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────

def count_tokens_approx(text: str) -> int:
    """Aproximación rápida: ~4 chars por token (sin cargar tiktoken)."""
    return max(1, len(text) // 4)


def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[tuple[str, int]]:
    """
    Divide texto en chunks por párrafos, respetando chunk_size en tokens.
    Retorna lista de (chunk_text, approx_tokens).
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current_chunk_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens_approx(para)

        if current_tokens + para_tokens > chunk_size and current_chunk_parts:
            chunk_text_str = "\n\n".join(current_chunk_parts)
            chunks.append((chunk_text_str, current_tokens))

            # Overlap: mantener últimas N palabras del chunk anterior
            overlap_text = " ".join(chunk_text_str.split()[-overlap:])
            current_chunk_parts = [overlap_text, para] if overlap_text else [para]
            current_tokens = count_tokens_approx(" ".join(current_chunk_parts))
        else:
            current_chunk_parts.append(para)
            current_tokens += para_tokens

    if current_chunk_parts:
        chunks.append(("\n\n".join(current_chunk_parts), current_tokens))

    return chunks


# ─────────────────────────────────────────────────────────────────
# Ingestion pipeline
# ─────────────────────────────────────────────────────────────────

async def ingest_document(
    *,
    content: bytes,
    filename: str,
    doc_id: str,
    tenant_id: str,
    collection_name: str,
    settings: RAGSettings,
    qdrant_client: AsyncQdrantClient,
) -> list[DocumentChunk]:
    """
    Pipeline completo de ingesta:
    1. Extraer texto
    2. Chunking semántico
    3. Embed via model-adapter
    4. Upsert en Qdrant
    """
    logger.info("ingestion_start", doc_id=doc_id, filename=filename, tenant_id=tenant_id)

    # 1. Extracción
    raw_text = extract_text(content, filename)
    if not raw_text.strip():
        raise ValueError(f"No text extracted from {filename}")

    # 2. Chunking
    raw_chunks = chunk_text(raw_text, settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    logger.info("chunking_done", doc_id=doc_id, num_chunks=len(raw_chunks))

    # Preparar chunks con metadata
    chunks: list[DocumentChunk] = []
    for i, (text, tokens) in enumerate(raw_chunks):
        chunk_id = hashlib.md5(f"{doc_id}:{i}:{text[:50]}".encode()).hexdigest()
        chunks.append(DocumentChunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            doc_name=filename,
            section=f"chunk_{i}",
            chunk_index=i,
            text=text,
            tokens=tokens,
            metadata={"tenant_id": tenant_id, "doc_id": doc_id, "filename": filename},
        ))

    # 3. Embeddings via model-adapter
    texts = [c.text for c in chunks]
    embeddings = await _get_embeddings(texts, tenant_id, settings)

    if len(embeddings) != len(chunks):
        raise ValueError(f"Embedding count mismatch: {len(embeddings)} vs {len(chunks)}")

    # 4. Upsert en Qdrant
    points = [
        PointStruct(
            id=c.chunk_id,
            vector=emb,
            payload={
                "doc_id": c.doc_id,
                "doc_name": c.doc_name,
                "section": c.section,
                "chunk_index": c.chunk_index,
                "text": c.text,
                "tokens": c.tokens,
                "tenant_id": tenant_id,
            },
        )
        for c, emb in zip(chunks, embeddings)
    ]

    await qdrant_client.upsert(collection_name=collection_name, points=points)
    logger.info("ingestion_done", doc_id=doc_id, points_upserted=len(points))

    return chunks


async def _get_embeddings(texts: list[str], tenant_id: str, settings: RAGSettings) -> list[list[float]]:
    """Llama al model-adapter para obtener embeddings."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.model_adapter_url}/v1/embed",
            json={"texts": texts, "tenant_id": tenant_id},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["embeddings"]
