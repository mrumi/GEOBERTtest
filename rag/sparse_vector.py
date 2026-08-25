# ============================================================
# rag/sparse_vector.py — Query-Time Sparse Vector Generation
# ============================================================
# This specific function
# is needed at QUERY time too (rag_node calls it per user query,
# not just during ingestion) — api/routes/query.py can't work
# without it.
# indexing/vector_uploader.py
# will import this same function for batch embedding during
# ingestion — no duplication.
# ============================================================

from qdrant_client.models import SparseVector


def generate_sparse_vector(text: str, sparse_embedder) -> SparseVector:
    """
    Generate a SPLADE sparse vector for a given text.

    Args:
        text           : Text to embed.
        sparse_embedder: FastEmbed SparseTextEmbedding instance
                         (core.clients.AppClients.sparse_embedder).

    Returns:
        SparseVector with indices and values.
    """
    sparse_embedding_result = list(sparse_embedder.embed([text]))[0]

    return SparseVector(
        indices = sparse_embedding_result.indices.tolist(),
        values  = sparse_embedding_result.values.tolist(),
    )