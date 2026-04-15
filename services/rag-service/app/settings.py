"""RAG Service settings."""
from shared.config.base import BaseServiceSettings


class RAGSettings(BaseServiceSettings):
    service_name: str = "rag-service"
    port: int = 8002

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Chunking
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50
    embedding_dim: int = 768

    # Retrieval
    top_k_retrieval: int = 8
    top_k_after_rerank: int = 3

    # Grounding
    # Lower threshold for local embedding models (LM Studio / nomic) which
    # typically score 0.45–0.65 on cosine similarity. Vertex AI scores higher.
    min_confidence_threshold: float = 0.40
    groundedness_check_enabled: bool = True

    # Embed model names (for metadata/logging only)
    lm_studio_embed_model: str = "text-embedding-nomic-embed-text-v1.5"
    vertex_ai_embed_model: str = "textembedding-gecko@003"

    # Semantic cache
    semantic_cache_enabled: bool = True
    semantic_cache_similarity_threshold: float = 0.92
    semantic_cache_ttl_seconds: int = 3600


_settings: RAGSettings | None = None


def get_settings() -> RAGSettings:
    global _settings
    if _settings is None:
        _settings = RAGSettings()  # type: ignore[call-arg]
    return _settings
